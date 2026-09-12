"""Exercise seed's actual REST calls without a database or server."""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_seed_uses_configured_openmrs_credentials_for_every_rest_request(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(ROOT / "scripts/seed-local.sh", scripts)
    # The dump verifier has its own real fixture tests; this test isolates auth
    # forwarding in the seed shell, not database or corpus correctness.
    (scripts / "verify-portable-dump.py").write_text("raise SystemExit(0)\n")
    dump = tmp_path / "baseline.sql.gz"
    with gzip.open(dump, "wb") as out:
        out.write(b"SELECT 1;\n")
    Path(str(dump) + ".provenance.json").write_text(
        json.dumps(
            {
                "output_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
                "output_bytes": dump.stat().st_size,
            }
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "curl.jsonl"
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\nimport sys\nif '-i' in sys.argv: sys.stdin.read()\n"
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\nimport os, sys, json\n"
        "with open(os.environ['CURL_TEST_LOG'], 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        "if '-w' in sys.argv: print('200')\n"
        "elif any('/module?' in a for a in sys.argv): print('{\"results\":[]}')\n"
    )
    for path in (docker, curl):
        path.chmod(0o755)
    result = subprocess.run(
        ["bash", str(scripts / "seed-local.sh"), "--dump", str(dump)],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "CURL_TEST_LOG": str(log),
            "CHARTSEARCH_ADMIN_USER": "local-admin",
            "CHARTSEARCH_ADMIN_PASSWORD": "test-only-password",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == 3
    assert all(
        call[call.index("-u") + 1] == "local-admin:test-only-password" for call in calls
    )
    assert "test-only-password" not in result.stdout + result.stderr


def test_seed_rejects_unsafe_database_identifier_before_any_container_call(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/seed-local.sh"), "--target", "openmrs;DROP"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "simple SQL identifiers" in result.stderr
