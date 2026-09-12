"""Exercise the real restore shell and verifier with fake container commands.

These checks prove command ordering and input preservation, not live recovery.
"""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def recovery(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("seed-local.sh", "verify-portable-dump.py"):
        shutil.copy(ROOT / "scripts" / name, scripts)
    (tmp_path / "harness").symlink_to(ROOT / "harness", target_is_directory=True)
    sql = (
        b"CREATE TABLE `patient` (`id` integer);\n"
        b"CREATE TABLE `chartsearchai_chat_session` (`id` integer);\n"
        b"INSERT INTO `chartsearchai_chat_session` VALUES (17);\n"
        b"INSERT INTO `global_property` VALUES ('chartsearchai.llm.systemPrompt','custom instructions');\n"
    )
    backup = tmp_path / "full-backup.sql.gz"
    with gzip.open(backup, "wb") as stream:
        stream.write(sql)
    provenance = Path(f"{backup}.provenance.json")
    provenance.write_text(
        json.dumps(
            {
                "source_schema": "openmrs",
                "output_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                "output_bytes": backup.stat().st_size,
                "module_state_included": True,
                "excluded_module_prefixes": ["chartsearchai", "querystore"],
                "excluded_tables": [],
            }
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\nimport json, os, pathlib, sys\n"
        "root = pathlib.Path(os.environ['TEST_WORKSPACE'])\n"
        "with (root/'commands.jsonl').open('a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        "if sys.argv[1] == 'stop' and os.environ.get('FAIL_STOP'): sys.exit(1)\n"
        "if '-i' in sys.argv: (root/'restored.sql').write_bytes(sys.stdin.buffer.read())\n"
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if '-w' in sys.argv: print('200')\n"
        "elif any('/module?' in a for a in sys.argv): print('{\"results\":[]}')\n"
    )
    docker.chmod(0o755)
    curl.chmod(0o755)

    def run(*args, fail_stop=False):
        return subprocess.run(
            ["bash", str(scripts / "seed-local.sh"), *args],
            env={
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "TEST_WORKSPACE": str(tmp_path),
                "FAIL_STOP": "1" if fail_stop else "",
            },
            text=True,
            capture_output=True,
            timeout=15,
        )

    return backup, provenance, sql, run


def test_full_recovery_passes_unmodified_sql_and_records_backup_kind(
    tmp_path, recovery
):
    backup, _, sql, run = recovery
    result = run("--restore-backup", str(backup))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "restored.sql").read_bytes() == sql
    commands = [
        json.loads(line)
        for line in (tmp_path / "commands.jsonl").read_text().splitlines()
    ]
    stop = next(i for i, cmd in enumerate(commands) if cmd[0] == "stop")
    drop = next(
        i for i, cmd in enumerate(commands) if any("DROP DATABASE" in a for a in cmd)
    )
    assert stop < drop
    receipt = json.loads(
        (tmp_path / "artifacts/chartsearchai-local/corpus-provenance.json").read_text()
    )
    assert receipt["restore_kind"] == "full_backup"
    assert receipt["dump_sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()


def test_portable_seed_still_rejects_a_full_backup(tmp_path, recovery):
    backup, _, _, run = recovery
    result = run("--dump", str(backup))
    assert result.returncode != 0
    assert "portable corpus" in result.stdout + result.stderr
    assert not (tmp_path / "commands.jsonl").exists()


@pytest.mark.parametrize("change", ["hash", "truncated", "excluded_tables", "portable"])
def test_invalid_backup_fails_before_any_container_operation(
    tmp_path, recovery, change
):
    backup, provenance, _, run = recovery
    metadata = json.loads(provenance.read_text())
    if change == "hash":
        backup.write_bytes(b"bad archive")
    elif change == "truncated":
        backup.write_bytes(backup.read_bytes()[:-8])
        metadata.update(
            output_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
            output_bytes=backup.stat().st_size,
        )
    elif change == "excluded_tables":
        metadata["excluded_tables"] = ["users"]
    else:
        metadata["module_state_included"] = False
    provenance.write_text(json.dumps(metadata))
    result = run("--restore-backup", str(backup))
    assert result.returncode != 0
    assert "verifying full backup" in result.stdout
    assert not (tmp_path / "commands.jsonl").exists()
    assert not (tmp_path / "restored.sql").exists()


def test_backend_stop_failure_prevents_schema_replacement(tmp_path, recovery):
    backup, _, _, run = recovery
    result = run("--restore-backup", str(backup), fail_stop=True)
    assert result.returncode != 0
    commands = (tmp_path / "commands.jsonl").read_text()
    assert "DROP DATABASE" not in commands
    assert not (tmp_path / "restored.sql").exists()


def test_backup_and_corpus_inputs_cannot_be_combined(tmp_path, recovery):
    backup, _, _, run = recovery
    result = run("--restore-backup", str(backup), "--dump", str(backup))
    assert result.returncode != 0
    assert "one" in result.stderr.lower()
    assert not (tmp_path / "commands.jsonl").exists()


def test_empty_backup_path_cannot_fall_back_to_baseline(tmp_path, recovery):
    *_, run = recovery
    result = run("--restore-backup", "")
    assert result.returncode == 2
    assert "requires a file path" in result.stderr
    assert not (tmp_path / "commands.jsonl").exists()
