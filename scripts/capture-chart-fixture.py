#!/usr/bin/env python3
"""Refresh judge fixtures from the same live evidence path med-agent-hub uses."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HUB_ROOT = ROOT / "targets" / "med-agent-hub"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HUB_ROOT))

from harness.validate.corpus_alignment import live_records  # noqa: E402
from server.chart_serializer import render_chart  # noqa: E402


def _hub_commit() -> str:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=HUB_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError("med-agent-hub must be clean before capturing judge fixtures")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=HUB_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def updated_fixture(
    fixture: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    captured_at: str,
    hub_commit: str,
) -> dict[str, Any]:
    """Return a refreshed fixture while preserving its curated identity fields."""
    updated = deepcopy(fixture)
    chart_snapshot, mappings = render_chart(records)
    valid_uuids = sorted(
        {mapping["resourceUuid"] for mapping in mappings if mapping.get("resourceUuid")}
    )
    updated["chart_snapshot"] = chart_snapshot
    updated["mappings"] = mappings
    updated["valid_uuids"] = valid_uuids
    updated["n_records"] = len(mappings)
    updated["n_valid_uuids"] = len(valid_uuids)
    updated["provenance"] = {
        "source": "Querystore patientrecord rendered by med-agent-hub chart_serializer",
        "captured_at": captured_at,
        "med_agent_hub_commit": hub_commit,
        "resource_types": dict(
            sorted(Counter(mapping["resourceType"] for mapping in mappings).items())
        ),
        "note": (
            "Closed-context scoring fixture captured from the same complete evidence ledger "
            "and serializer used by med-agent-hub."
        ),
    }
    return updated


def _fixture_paths(path: str | None, all_fixtures: bool) -> list[Path]:
    if all_fixtures:
        return sorted((ROOT / "datasets" / "validation" / "charts").glob("*.json"))
    assert path is not None
    candidate = Path(path)
    return [candidate if candidate.is_absolute() else ROOT / candidate]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--fixture", help="fixture JSON to refresh in place")
    selected.add_argument("--all", action="store_true", help="refresh every committed chart fixture")
    port = os.environ.get("HARNESS_PROXY_HTTP_PORT", "8088")
    parser.add_argument(
        "--endpoint",
        default=f"http://localhost:{port}/openmrs/ws/rest/v1/querystore/patientrecord",
    )
    parser.add_argument("--username", default=os.environ.get("QUERYSTORE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("QUERYSTORE_PASSWORD", ""))
    args = parser.parse_args(argv)

    if not args.username or not args.password:
        print(
            "ERROR: set QUERYSTORE_USERNAME and QUERYSTORE_PASSWORD for the read-only fixture capture",
            file=sys.stderr,
        )
        return 1

    captured_at = datetime.now(timezone.utc).isoformat()
    try:
        hub_commit = _hub_commit()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    prepared: list[tuple[Path, dict[str, Any]]] = []
    try:
        for fixture_path in _fixture_paths(args.fixture, args.all):
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            patient_uuid = str((fixture.get("patient") or {}).get("uuid") or "").strip()
            if not patient_uuid:
                raise ValueError(f"{fixture_path} has no patient.uuid")
            records = live_records(
                args.endpoint,
                patient_uuid,
                args.username,
                args.password,
            )
            if not records:
                raise ValueError(f"no live records for {patient_uuid}")
            prepared.append(
                (
                    fixture_path,
                    updated_fixture(
                        fixture,
                        records,
                        captured_at=captured_at,
                        hub_commit=hub_commit,
                    ),
                )
            )
    except Exception as exc:
        print(f"ERROR: fixture capture aborted before writing: {exc}", file=sys.stderr)
        return 1

    staged: list[tuple[Path, Path, dict[str, Any]]] = []
    try:
        for fixture_path, refreshed in prepared:
            temp_path = fixture_path.with_name(f".{fixture_path.name}.tmp")
            temp_path.write_text(
                json.dumps(refreshed, indent=2) + "\n", encoding="utf-8"
            )
            staged.append((fixture_path, temp_path, refreshed))
        for fixture_path, temp_path, refreshed in staged:
            os.replace(temp_path, fixture_path)
            print(
                f"refreshed {fixture_path.relative_to(ROOT)}: "
                f"{refreshed['n_records']} records"
            )
    finally:
        for _, temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
