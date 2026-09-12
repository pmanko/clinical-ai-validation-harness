"""Explicit asset acquisition must not alter services, data, or existing files."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from harness import environment_assets as assets
from harness.evaluation_setup import SetupError


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "datasets/sources").mkdir(parents=True)
    model = b"test model bytes"
    sha = hashlib.sha256(model).hexdigest()
    (root / "scripts/catalyst-model-router.models.tsv").write_text(
        f"gemma-e4b\tmodel.gguf\t{sha}\thttps://example.test/model.gguf\n"
    )
    monkeypatch.setenv("LLAMA_MODEL_DIR", str(tmp_path / "models"))
    source = tmp_path / "shared/baseline.sql.gz"
    source.parent.mkdir()
    with gzip.open(source, "wb") as stream:
        stream.write(b"CREATE TABLE `patient` (`id` integer);\n")
    identity = {
        "filename": "refapp_28_demo.sql.gz",
        "sha256": assets.sha256_file(source),
        "bytes": source.stat().st_size,
    }
    (root / "datasets/sources/evaluation-baseline.json").write_text(
        json.dumps(identity)
    )
    Path(f"{source}.provenance.json").write_text(
        json.dumps(
            {
                "output_sha256": identity["sha256"],
                "output_bytes": identity["bytes"],
                "module_state_included": False,
                "excluded_module_prefixes": ["chartsearchai", "querystore"],
            }
        )
    )
    return root, source, model


def test_check_is_read_only_and_does_not_download(workspace, monkeypatch):
    root, _, _ = workspace
    monkeypatch.setattr(assets, "_copy_source", lambda *args: pytest.fail("download"))
    with pytest.raises(SetupError, match="missing"):
        assets.prepare_assets(root, model="gemma-e4b")
    assert not (root.parent / "models").exists()
    assert not (root / "artifacts").exists()


def test_model_installs_router_alias_only_after_verification(workspace, monkeypatch):
    root, _, content = workspace
    calls = []

    def download(source, destination):
        calls.append(source)
        destination.write_bytes(content)

    monkeypatch.setattr(assets, "_copy_source", download)
    report = assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    target = root.parent / "models/gemma-e4b.gguf"
    assert target.read_bytes() == content
    assert report["model"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert report["model"]["path"] == str(target)
    assert report["readiness"] == "not_checked"
    assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    assert calls == ["https://example.test/model.gguf"]


def test_bad_model_never_becomes_installed(workspace, monkeypatch):
    root, _, _ = workspace
    monkeypatch.setattr(
        assets, "_copy_source", lambda _, path: path.write_bytes(b"wrong")
    )
    with pytest.raises(SetupError, match="checksum"):
        assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    assert list((root.parent / "models").iterdir()) == []


@pytest.mark.parametrize("kind", ["file", "symlink", "broken_symlink"])
def test_existing_different_model_is_never_replaced(workspace, monkeypatch, kind):
    root, _, _ = workspace
    directory = root.parent / "models"
    directory.mkdir()
    target = directory / "gemma-e4b.gguf"
    other = root.parent / "other.gguf"
    if kind != "broken_symlink":
        other.write_bytes(b"operator's different model")
    if kind == "file":
        target.write_bytes(other.read_bytes())
    else:
        target.symlink_to(other)
    monkeypatch.setattr(assets, "_copy_source", lambda *args: pytest.fail("download"))
    with pytest.raises(SetupError):
        assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    assert (
        target.is_symlink()
        if kind != "file"
        else target.read_bytes() == other.read_bytes()
    )


def test_local_baseline_pair_copied_and_verified_without_restoring(workspace):
    root, source, _ = workspace
    report = assets.prepare_assets(root, baseline_source=str(source), fetch=True)
    target = Path(report["baseline"]["path"])
    assert target == root / "artifacts/demo-data/refapp_28_demo.sql.gz"
    assert target.read_bytes() == source.read_bytes()
    assert (
        Path(f"{target}.provenance.json").read_bytes()
        == Path(f"{source}.provenance.json").read_bytes()
    )
    assert report["baseline"]["sha256"] == assets.sha256_file(source)
    assert report["readiness"] == "not_checked"
    assert (
        assets.prepare_assets(root, baseline=target)["baseline"]["status"] == "verified"
    )


def test_baseline_fetch_requires_an_explicit_source(workspace):
    root, _, _ = workspace
    with pytest.raises(SetupError, match="source"):
        assets.prepare_assets(root, baseline=root / "baseline.sql.gz", fetch=True)
    assert not (root / "baseline.sql.gz").exists()


@pytest.mark.parametrize("failure", ["hash", "provenance", "full_backup"])
def test_invalid_baseline_does_not_install_either_file(workspace, failure):
    root, source, _ = workspace
    if failure == "hash":
        source.write_bytes(b"not the approved corpus")
    elif failure == "provenance":
        Path(f"{source}.provenance.json").write_text("{}")
    else:
        path = Path(f"{source}.provenance.json")
        value = json.loads(path.read_text())
        value["module_state_included"] = True
        path.write_text(json.dumps(value))
    with pytest.raises(SetupError):
        assets.prepare_assets(root, baseline_source=str(source), fetch=True)
    assert list((root / "artifacts/demo-data").iterdir()) == []


def test_incomplete_existing_pair_is_not_overwritten(workspace):
    root, source, _ = workspace
    target = root / "existing.sql.gz"
    target.write_bytes(source.read_bytes())
    with pytest.raises(SetupError, match="provenance"):
        assets.prepare_assets(
            root, baseline=target, baseline_source=str(source), fetch=True
        )
    assert target.read_bytes() == source.read_bytes()
    assert not Path(f"{target}.provenance.json").exists()


def test_interrupted_download_leaves_no_installed_or_partial_file(
    workspace, monkeypatch
):
    root, _, _ = workspace

    def interrupted(source, destination):
        destination.write_bytes(b"partial")
        raise OSError("connection ended")

    monkeypatch.setattr(assets, "_copy_source", interrupted)
    with pytest.raises(OSError):
        assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    assert list((root.parent / "models").iterdir()) == []


def test_concurrent_install_does_not_overwrite_the_other_file(workspace, monkeypatch):
    root, _, model = workspace

    def race(source, destination):
        destination.write_bytes(model)
        (root.parent / "models/gemma-e4b.gguf").write_bytes(b"other installer")

    monkeypatch.setattr(assets, "_copy_source", race)
    with pytest.raises(SetupError, match="changed"):
        assets.prepare_assets(root, model="gemma-e4b", fetch=True)
    assert (root.parent / "models/gemma-e4b.gguf").read_bytes() == b"other installer"


@pytest.mark.parametrize("model", ["unknown", "../outside", "gemma-e4b-q8"])
def test_no_silent_model_substitution(workspace, model):
    with pytest.raises(SetupError, match="model"):
        assets.prepare_assets(workspace[0], model=model, fetch=True)


@pytest.mark.parametrize(
    "source", ["http://example.test/data", "ftp://example.test/data"]
)
def test_remote_sources_require_https(tmp_path, source):
    with pytest.raises(SetupError, match="HTTPS"):
        assets._copy_source(source, tmp_path / "download")
    assert not (tmp_path / "download").exists()


def test_https_download_prevents_protocol_downgrade_and_redacts_failures(
    tmp_path, monkeypatch
):
    calls = []

    def curl(args, **kwargs):
        calls.append(args)
        assert kwargs["capture_output"] is True
        from subprocess import CompletedProcess

        return CompletedProcess(args, 22, "", "secret-in-response")

    monkeypatch.setattr(assets.subprocess, "run", curl)
    with pytest.raises(SetupError) as error:
        assets._copy_source(
            "https://example.test/data?token=private", tmp_path / "data"
        )
    assert "private" not in str(error.value)
    assert "secret-in-response" not in str(error.value)
    assert calls[0][calls[0].index("--proto") + 1] == "=https"
    assert calls[0][calls[0].index("--proto-redir") + 1] == "=https"


def test_checked_in_identity_matches_reviewed_baseline():
    value = json.loads((ROOT / "datasets/sources/evaluation-baseline.json").read_text())
    assert (
        value["sha256"]
        == "f76619b40b45f0261467ceaeb2708b97795d115d99a7b2c2a7c73b38d9a8512a"
    )
    assert value["bytes"] == 44057876
    assert value["source"] is None


def test_pinned_models_install_under_matching_main_router_names():
    import configparser
    import csv

    presets = configparser.ConfigParser(interpolation=None, strict=False)
    presets.read(ROOT / "scripts/llama-router.ini")
    with (ROOT / "scripts/catalyst-model-router.models.tsv").open() as stream:
        aliases = [
            r[0]
            for r in csv.reader(stream, delimiter="\t")
            if r and not r[0].startswith("#")
        ]
    for alias in aliases:
        assert Path(presets[alias]["model"]).name == f"{alias}.gguf"


def test_successful_https_fetch_keeps_credential_out_of_receipt(workspace, monkeypatch):
    root, source, _ = workspace
    url = "https://example.test/baseline.sql.gz?token=fixture-secret-token"
    calls = []

    def download(actual, destination):
        calls.append(actual)
        local = source if len(calls) == 1 else Path(f"{source}.provenance.json")
        destination.write_bytes(local.read_bytes())

    monkeypatch.setattr(assets, "_copy_source", download)
    result = assets.prepare_assets(root, baseline_source=url, fetch=True)
    assert calls == [
        url,
        "https://example.test/baseline.sql.gz.provenance.json?token=fixture-secret-token",
    ]
    assert "fixture-secret-token" not in json.dumps(result)


def test_sidecar_install_failure_rolls_back_only_own_new_file(workspace, monkeypatch):
    root, source, _ = workspace
    original_link = assets.os.link

    def link(staged, target):
        if str(target).endswith(".provenance.json"):
            target.write_bytes(b"other process")
        original_link(staged, target)

    monkeypatch.setattr(assets.os, "link", link)
    with pytest.raises(SetupError, match="changed"):
        assets.prepare_assets(root, baseline_source=str(source), fetch=True)
    target = root / "artifacts/demo-data/refapp_28_demo.sql.gz"
    assert not target.exists()
    assert Path(f"{target}.provenance.json").read_bytes() == b"other process"


def test_missing_selection_never_creates_directories(workspace):
    with pytest.raises(SetupError, match="Select"):
        assets.prepare_assets(workspace[0], fetch=True)
    assert not (workspace[0] / "artifacts").exists()
