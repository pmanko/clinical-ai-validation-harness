from __future__ import annotations

import gzip
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _docker(
    *args: str, check: bool = True, input: bytes | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        input=input,
        capture_output=True,
        check=check,
    )


@pytest.mark.slow
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="set RUN_DOCKER_TESTS=1 to run the real MariaDB dump/restore contract",
)
def test_portable_dump_round_trip_excludes_consumer_module_state(tmp_path: Path) -> None:
    container = f"harness-dump-test-{uuid4().hex[:10]}"
    portable = tmp_path / "portable.sql.gz"
    full = tmp_path / "full.sql.gz"
    try:
        _docker(
            "run",
            "-d",
            "--rm",
            "--name",
            container,
            "-e",
            "MARIADB_ROOT_PASSWORD=openmrs",
            "mariadb:10.11",
        )
        for _ in range(60):
            ready = _docker(
                "exec",
                container,
                "mariadb",
                "--user=root",
                "--password=openmrs",
                "-e",
                "SELECT 1",
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            pytest.fail("MariaDB test container did not become ready")

        setup_sql = """
CREATE DATABASE source_db;
USE source_db;
CREATE TABLE patient (patient_id INT PRIMARY KEY);
INSERT INTO patient VALUES (1);
CREATE TABLE chartsearchai_session (id INT PRIMARY KEY);
INSERT INTO chartsearchai_session VALUES (10);
CREATE TABLE querystore_document (id INT PRIMARY KEY);
INSERT INTO querystore_document VALUES (20);
CREATE TABLE liquibasechangelog (id VARCHAR(255), filename VARCHAR(255));
INSERT INTO liquibasechangelog VALUES
  ('core-001', 'liquibase/core.xml'),
  ('chartsearchai-001', 'liquibase/chartsearchai.xml'),
  ('querystore-001', 'liquibase/querystore.xml');
"""
        _docker(
            "exec",
            "-i",
            container,
            "mariadb",
            "--user=root",
            "--password=openmrs",
            input=setup_sql.encode(),
        )
        env = {
            **os.environ,
            "DB_CONTAINER": container,
            "MYSQL_ROOT_PASSWORD": "openmrs",
        }
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [
                "bash",
                "scripts/dump-loaded.sh",
                "--source",
                "source_db",
                "--out",
                str(portable),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "bash",
                "scripts/dump-loaded.sh",
                "--source",
                "source_db",
                "--out",
                str(full),
                "--include-module-state",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        portable_sql = gzip.decompress(portable.read_bytes()).decode()
        full_sql = gzip.decompress(full.read_bytes()).decode()
        assert "CREATE TABLE `patient`" in portable_sql
        assert "chartsearchai_session" not in portable_sql
        assert "querystore_document" not in portable_sql
        assert "chartsearchai-001" not in portable_sql
        assert "querystore-001" not in portable_sql
        assert "chartsearchai_session" in full_sql
        assert "querystore_document" in full_sql

        rejected = subprocess.run(
            [
                "python3",
                "scripts/verify-portable-dump.py",
                "--dump",
                str(full),
                "--require-portable",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert rejected.returncode == 1
        assert "seed input must be a portable corpus" in rejected.stdout

        _docker(
            "exec",
            container,
            "mariadb",
            "--user=root",
            "--password=openmrs",
            "-e",
            "CREATE DATABASE restored;",
        )
        _docker(
            "exec",
            "-i",
            container,
            "mariadb",
            "--user=root",
            "--password=openmrs",
            "restored",
            input=gzip.decompress(portable.read_bytes()),
        )
        query = (
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='restored' "
            "AND (table_name LIKE 'chartsearchai_%' OR table_name LIKE 'querystore_%');"
            "SELECT COUNT(*) FROM restored.liquibasechangelog "
            "WHERE id LIKE 'chartsearchai%' OR id LIKE 'querystore%';"
        )
        result = _docker(
            "exec",
            container,
            "mariadb",
            "--user=root",
            "--password=openmrs",
            "-N",
            "-B",
            "-e",
            query,
        )
        assert result.stdout.decode().splitlines() == ["0", "0"]
    finally:
        _docker("rm", "-f", container, check=False)
