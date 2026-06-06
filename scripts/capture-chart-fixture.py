#!/usr/bin/env python3
"""Refresh a committed chart ground-truth fixture from the live OpenMRS DB.

The judge (clinical-answer-scoring) scores answers against the committed
``datasets/validation/charts/<slug>.json`` fixture's ``chart_snapshot`` +
``mappings`` + ``valid_uuids`` as the closed-context ground truth. Those are a
point-in-time capture of chartsearchai's serialized PatientChart (stored in
``chartsearchai_chat_session.chart_snapshot`` / ``chart_mappings_json``). When
the underlying data changes (e.g. the date-transplant shifting 2006 -> 2025/26),
the fixture goes stale and the judge mis-scores correct answers as fabricated.

This refreshes a fixture IN PLACE from the patient's LATEST chat session:
swaps chart_snapshot / mappings / valid_uuids / counts / birthdate + stamps
provenance, while preserving curated fields (slug, canvas_role, name, etc.).

Usage:
  .venv/bin/python scripts/capture-chart-fixture.py --fixture datasets/validation/charts/aloice-mukangu.json --patient-id 39
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pymysql


def _latest_session(cur, patient_id: int):
    cur.execute(
        "SELECT chart_snapshot, chart_mappings_json, chart_built_at "
        "FROM chartsearchai_chat_session WHERE patient_id=%s AND chart_snapshot IS NOT NULL "
        "ORDER BY chart_built_at DESC LIMIT 1",
        (patient_id,),
    )
    return cur.fetchone()


def _birthdate(cur, patient_id: int):
    cur.execute("SELECT birthdate FROM person WHERE person_id=%s", (patient_id,))
    row = cur.fetchone()
    return str(row[0]) if row and row[0] is not None else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", required=True, help="path to the fixture JSON to refresh in place")
    p.add_argument("--patient-id", required=True, type=int)
    p.add_argument("--host", default=os.environ.get("MARIADB_HOST", "127.0.0.1"))
    p.add_argument("--port", default=int(os.environ.get("MARIADB_PORT", "3307")), type=int)
    p.add_argument("--user", default=os.environ.get("MARIADB_USER", "openmrs"))
    p.add_argument("--password", default=os.environ.get("MARIADB_PASSWORD", "openmrs"))
    p.add_argument("--database", default=os.environ.get("MARIADB_DB", "openmrs"))
    args = p.parse_args(argv)

    fixture_path = Path(args.fixture)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    conn = pymysql.connect(host=args.host, port=args.port, user=args.user,
                           password=args.password, database=args.database)
    try:
        with conn.cursor() as cur:
            sess = _latest_session(cur, args.patient_id)
            if not sess:
                print(f"ERROR: no chat session with a chart_snapshot for patient_id={args.patient_id}", file=sys.stderr)
                return 1
            snapshot, mappings_json, built_at = sess
            birthdate = _birthdate(cur, args.patient_id)
    finally:
        conn.close()

    mappings = json.loads(mappings_json) if mappings_json else []
    valid_uuids = sorted({m["resourceUuid"] for m in mappings if m.get("resourceUuid")})

    fixture["chart_snapshot"] = snapshot
    fixture["mappings"] = mappings
    fixture["valid_uuids"] = valid_uuids
    fixture["n_records"] = len(mappings)
    fixture["n_valid_uuids"] = len(valid_uuids)
    if birthdate and isinstance(fixture.get("patient"), dict):
        fixture["patient"]["birthdate"] = birthdate
    fixture["provenance"] = {
        "source": "chartsearchai_chat_session.chart_snapshot / chart_mappings_json (latest session)",
        "patient_id": args.patient_id,
        "chart_built_at": str(built_at),
        "note": "Refreshed post date-transplant; records are date-shifted to the recent window (real clock). "
                "Record VALUES are the scoring ground truth; dates reflect the transplanted era.",
    }

    fixture_path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    print(f"refreshed {fixture_path}: {len(mappings)} records, {len(valid_uuids)} uuids, built_at={built_at}, birthdate={birthdate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
