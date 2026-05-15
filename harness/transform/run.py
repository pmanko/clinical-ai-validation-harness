"""Wrap the SQLMesh CLI to plan, run, and audit the project, then dump
the materialized ``refapp_28_demo`` schema to a deterministic SQL artifact.

The transform is materialized by SQLMesh against the live MariaDB; this
module is the thin Python orchestrator only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from harness.conceptmap.load import load_conceptmap
from harness.config import get_feature_002_paths


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_tree(root: Path, exclude_dirs: tuple[str, ...] = ("seeds",)) -> str:
    """Stable hash of a directory tree (sorted file order)."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] in exclude_dirs:
            continue
        h.update(str(rel).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _ensure_target_schema(host: str, port: str, user: str, password: str, schema: str) -> None:
    """Create the target schema if it doesn't exist."""
    import pymysql
    conn = pymysql.connect(host=host, port=int(port), user=user, password=password)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{schema}` "
                        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
        conn.commit()
    finally:
        conn.close()


_CLINICAL_MARTS: tuple[str, ...] = (
    "clin__obs", "clin__drug_order", "clin__conditions",
    "clin__allergy", "clin__test_order",
)


def _materialized_outputs(
    host: str, port: str, user: str, password: str, schema: str
) -> list[dict[str, Any]]:
    """Per-clinical-mart row counts + content hash for determinism check.

    ``row_count`` is the load-bearing signal — it caught the C2-class
    "silent 0" failure mode (mart materialized as empty view).

    ``content_checksum`` is a SHA-256 of a canonical column-ordered,
    PK-ordered row representation. The clinical marts are SQLMesh
    views (CHECKSUM TABLE returns NULL on views), so we compute the
    hash in Python over a streaming row scan. Skippable per-table if
    a table's row count is below a small threshold.
    """
    import hashlib
    import pymysql
    conn = pymysql.connect(host=host, port=int(port), user=user, password=password,
                           database=schema)
    out: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            for table in _CLINICAL_MARTS:
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                row_count = int(cur.fetchone()[0])

                cur.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s
                    ORDER BY ordinal_position
                """, (schema, table))
                cols = [r[0] for r in cur.fetchall()]
                col_list = ", ".join(f"`{c}`" for c in cols)

                pk = "uuid" if "uuid" in cols else cols[0]
                h = hashlib.sha256()
                cur.execute(f"SELECT {col_list} FROM `{table}` ORDER BY `{pk}`")
                for row in cur:
                    h.update("\x1f".join("" if v is None else str(v) for v in row).encode("utf-8"))
                    h.update(b"\x1e")

                out.append({
                    "table_name": f"{schema}.{table}",
                    "row_count": row_count,
                    "content_checksum": h.hexdigest(),
                    "checksum_method": "sha256_of_canonical_dump",
                })
    finally:
        conn.close()
    return out


def _sqlmesh_bin() -> str:
    """Locate the sqlmesh CLI binary alongside the active Python interpreter."""
    candidate = Path(sys.executable).parent / "sqlmesh"
    return str(candidate) if candidate.is_file() else "sqlmesh"


def _invoke_sqlmesh(project_dir: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_sqlmesh_bin(), "-p", str(project_dir), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _dump_target_schema(out_sql: Path, host: str, port: str, user: str,
                       password: str, schema: str, db_container: str | None) -> Path:
    """mariadb-dump the materialized target schema with deterministic flags."""
    out_sql.parent.mkdir(parents=True, exist_ok=True)
    if db_container and shutil.which("docker"):
        cmd = [
            "docker", "exec", db_container, "mariadb-dump",
            f"--user={user}", f"--password={password}",
            "--no-create-info" if False else "--complete-insert",
            "--insert-ignore",
            "--extended-insert",
            "--hex-blob",
            "--skip-comments",
            "--skip-dump-date",
            "--skip-add-locks",
            "--skip-disable-keys",
            "--skip-tz-utc",
            "--single-transaction",
            "--quick",
            "--default-character-set=utf8mb4",
            schema,
        ]
        with out_sql.open("w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    else:
        cmd = [
            "mariadb-dump", f"--host={host}", f"--port={port}",
            f"--user={user}", f"--password={password}",
            "--complete-insert", "--insert-ignore", "--extended-insert",
            "--hex-blob", "--skip-comments", "--skip-dump-date",
            "--skip-add-locks", "--skip-disable-keys", "--skip-tz-utc",
            "--single-transaction", "--quick",
            "--default-character-set=utf8mb4",
            schema,
        ]
        with out_sql.open("w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    return out_sql


def run_transform(
    *,
    project_dir: Path,
    conceptmap_path: Path,
    output_dir: Path,
    target_schema: str = "refapp_28_demo",
    dry_run: bool = False,
    db_container: str | None = "harness-openmrs-db",
) -> dict[str, Any]:
    """End-to-end: validate the ConceptMap, ensure target schema, sqlmesh
    plan + run + audit, dump the target, stamp the run report."""
    cm = load_conceptmap(conceptmap_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    host = os.environ.get("MARIADB_HOST", "127.0.0.1")
    port = os.environ.get("MARIADB_PORT", "3307")
    user = os.environ.get("MARIADB_USER", "openmrs")
    password = os.environ.get("MARIADB_PASSWORD", "openmrs")

    _ensure_target_schema(host, port, user, password, target_schema)

    env = {**os.environ, "MARIADB_HOST": host, "MARIADB_PORT": port,
           "MARIADB_USER": user, "MARIADB_PASSWORD": password}

    plan_args = ["plan", "--no-prompts", "--auto-apply"]
    if dry_run:
        plan_args.append("--skip-backfill")
    plan = _invoke_sqlmesh(project_dir, plan_args, env)
    (output_dir / "sqlmesh-plan.txt").write_text(plan.stdout + "\n--- stderr ---\n" + plan.stderr)
    if plan.returncode != 0:
        return {
            "status": "failed",
            "stage": "plan",
            "exit_code": plan.returncode,
            "log_path": str(output_dir / "sqlmesh-plan.txt"),
        }

    if dry_run:
        return {"status": "dry_run_ok", "log_path": str(output_dir / "sqlmesh-plan.txt")}

    run = _invoke_sqlmesh(project_dir, ["run"], env)
    (output_dir / "sqlmesh-run.txt").write_text(run.stdout + "\n--- stderr ---\n" + run.stderr)
    if run.returncode != 0:
        return {
            "status": "failed", "stage": "run",
            "exit_code": run.returncode,
            "log_path": str(output_dir / "sqlmesh-run.txt"),
        }

    audit = _invoke_sqlmesh(project_dir, ["audit"], env)
    (output_dir / "sqlmesh-audit.txt").write_text(audit.stdout + "\n--- stderr ---\n" + audit.stderr)

    dump_path = output_dir / "refapp_28_demo.sql"
    try:
        _dump_target_schema(dump_path, host, port, user, password, target_schema, db_container)
    except subprocess.CalledProcessError as e:
        return {
            "status": "failed", "stage": "dump",
            "exit_code": e.returncode,
            "log_path": str(output_dir / "sqlmesh-audit.txt"),
        }

    project_sha = _sha256_of_tree(project_dir)
    seed_translation_sha = _sha256_of_file(project_dir / "seeds" / "concept_translation.csv")
    seed_policy_sha = _sha256_of_file(project_dir / "seeds" / "module_table_policy.csv")

    materialized_outputs = _materialized_outputs(host, port, user, password, target_schema)

    report = {
        "status": "ok" if audit.returncode == 0 else "audit_failed",
        "audit_exit_code": audit.returncode,
        "conceptmap_path": str(conceptmap_path),
        "conceptmap_checksum": cm.raw_checksum,
        "sqlmesh_project_path": str(project_dir),
        "sqlmesh_project_checksum": project_sha,
        "concept_translation_seed_checksum": seed_translation_sha,
        "module_table_policy_seed_checksum": seed_policy_sha,
        "refapp_28_demo_sql_path": str(dump_path),
        "refapp_28_demo_sql_checksum": _sha256_of_file(dump_path),
        "refapp_28_demo_sql_bytes": dump_path.stat().st_size,
        "materialized_outputs": materialized_outputs,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output_dir / "transform.report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.transform.run")
    p.add_argument("--project-dir", default="datasets/transforms/sqlmesh")
    p.add_argument("--conceptmap",
                   default="datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Plan only; do not materialize models.")
    p.add_argument("--db-container", default="harness-openmrs-db",
                   help="Docker container running MariaDB (for mariadb-dump). Set to '' to use host binary.")
    args = p.parse_args(argv)

    paths = get_feature_002_paths()
    run_id = args.run_id or f"dev-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
    output_dir = paths.transform_artifact_dir(run_id)

    report = run_transform(
        project_dir=Path(args.project_dir),
        conceptmap_path=Path(args.conceptmap),
        output_dir=output_dir,
        dry_run=args.dry_run,
        db_container=args.db_container or None,
    )
    print(json.dumps(report, indent=2))
    if report.get("status") not in {"ok", "dry_run_ok"}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
