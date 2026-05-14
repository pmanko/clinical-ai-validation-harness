"""MariaDB query helper for harness.profile modules.

Uses `docker exec ... mariadb -B -N` rather than a native client so we don't
yet need to drag in the T001 PyMySQL/mariadb-connector dependency. Output is
tab-separated; we parse it back into list[tuple[str, ...]]. NULLs come back
as the literal string 'NULL' under -N (the no-tabs / batch mode); we
normalize to Python None.

If T001 lands later, swap _exec for a real client without changing callers.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


class DBError(RuntimeError):
    pass


@dataclass(frozen=True)
class DBConfig:
    container: str = "harness-openmrs-db"
    user: str = "openmrs"
    password: str = "openmrs"
    database: str = "legacy_27_raw"

    @classmethod
    def from_env(cls, *, database: str | None = None) -> "DBConfig":
        return cls(
            container=os.environ.get("DB_CONTAINER", "harness-openmrs-db"),
            user=os.environ.get("OMRS_DB_USER", "openmrs"),
            password=os.environ.get("OMRS_DB_PASSWORD", "openmrs"),
            database=database or os.environ.get("LEGACY_DB", "legacy_27_raw"),
        )


def _exec(cfg: DBConfig, sql: str, *, timeout: int = 120) -> str:
    """Run SQL inside the DB container; return raw stdout (tab-separated, no header)."""
    cmd = [
        "docker", "exec", "-i", cfg.container,
        "mariadb",
        f"--user={cfg.user}", f"--password={cfg.password}",
        "--default-character-set=utf8mb4",
        "-B", "-N",  # batch mode, no column names
        cfg.database,
        "-e", sql,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise DBError(f"mariadb query failed (rc={r.returncode}): {r.stderr.strip()[:500]}")
    return r.stdout


def query(cfg: DBConfig, sql: str, *, timeout: int = 120) -> list[tuple[str | None, ...]]:
    """Run SQL, parse tab-separated output to list of tuples; 'NULL' → None."""
    raw = _exec(cfg, sql, timeout=timeout)
    rows: list[tuple[str | None, ...]] = []
    for line in raw.splitlines():
        if not line:
            continue
        cells = line.split("\t")
        rows.append(tuple(None if c == "NULL" else c for c in cells))
    return rows


def query_scalar(cfg: DBConfig, sql: str, *, timeout: int = 30) -> str | None:
    """Run SQL that returns a single value; raise if it doesn't."""
    rows = query(cfg, sql, timeout=timeout)
    if not rows or not rows[0]:
        return None
    return rows[0][0]
