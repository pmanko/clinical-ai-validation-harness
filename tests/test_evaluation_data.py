"""No data mutation without a verified baseline and a verified full backup."""

import gzip
import json
from pathlib import Path

import pytest

from harness.evaluation_setup import SetupError, prepare_data
from harness.validate.dump_provenance import sha256_file


def dump(path: Path, *, full=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as stream:
        stream.write(b"CREATE TABLE `patient` (`id` integer);\n")
        if full:
            stream.write(b"CREATE TABLE `chartsearchai_chat_session` (`id` integer);\n")
    Path(str(path) + ".provenance.json").write_text(
        json.dumps(
            {
                "output_sha256": sha256_file(path),
                "output_bytes": path.stat().st_size,
                "module_state_included": full,
                "excluded_module_prefixes": []
                if full
                else ["chartsearchai", "querystore"],
            }
        )
    )


def test_preserve_is_a_noop_even_without_baseline(tmp_path):
    calls = []
    result = prepare_data(tmp_path, run=lambda args: calls.append(args))
    assert result == {"action": "preserve"}
    assert calls == []


def test_missing_or_corrupt_baseline_prevents_any_stop_or_reset(tmp_path):
    calls = []
    baseline = tmp_path / "baseline.sql.gz"
    for exists in (False, True):
        if exists:
            dump(baseline)
            baseline.write_bytes(b"corrupt")
        with pytest.raises(SetupError, match="baseline"):
            prepare_data(tmp_path, reset=True, baseline=baseline, run=calls.append)
        assert not calls


def test_reset_backs_up_all_module_state_before_seed(tmp_path):
    baseline = tmp_path / "baseline.sql.gz"
    dump(baseline)
    calls = []

    def run(args):
        calls.append(args)
        if "scripts/dump-loaded.sh" in args:
            assert "--include-module-state" in args
            dump(Path(args[args.index("--out") + 1]), full=True)

    result = prepare_data(tmp_path, reset=True, baseline=baseline, run=run)

    assert calls[0] == ["docker", "stop", "harness-openmrs-backend"]
    assert "scripts/dump-loaded.sh" in calls[1]
    assert "scripts/seed-local.sh" in calls[2]
    assert "--dump" in calls[2]
    assert calls[3] == [
        "make",
        "querystore-recreate-index",
        "ALLOW_QUERYSTORE_INDEX_RESET=1",
    ]
    assert result["backup_sha256"] == sha256_file(Path(result["backup"]))
    assert result["baseline_sha256"] == sha256_file(baseline)


@pytest.mark.parametrize("failure", ["command", "portable_backup", "missing_backup"])
def test_failed_backup_restarts_unchanged_backend_without_seeding(tmp_path, failure):
    baseline = tmp_path / "baseline.sql.gz"
    dump(baseline)
    calls = []

    def run(args):
        calls.append(args)
        if "scripts/dump-loaded.sh" in args:
            if failure == "command":
                raise SetupError("backup command failed")
            if failure == "portable_backup":
                dump(Path(args[args.index("--out") + 1]), full=False)

    with pytest.raises(SetupError):
        prepare_data(tmp_path, reset=True, baseline=baseline, run=run)
    assert calls[-1] == ["docker", "start", "harness-openmrs-backend"]
    assert not any("scripts/seed-local.sh" in args for args in calls)


def test_seed_failure_is_not_retried_and_backup_is_retained(tmp_path):
    baseline = tmp_path / "baseline.sql.gz"
    dump(baseline)
    calls = []

    def run(args):
        calls.append(args)
        if "scripts/dump-loaded.sh" in args:
            dump(Path(args[args.index("--out") + 1]), full=True)
        if "scripts/seed-local.sh" in args:
            raise SetupError("restore failed")

    with pytest.raises(SetupError, match="restore failed"):
        prepare_data(tmp_path, reset=True, baseline=baseline, run=run)
    assert len([args for args in calls if "scripts/seed-local.sh" in args]) == 1
    assert (
        len(list((tmp_path / "artifacts/evaluation-setup/backups").glob("*.sql.gz")))
        == 1
    )
