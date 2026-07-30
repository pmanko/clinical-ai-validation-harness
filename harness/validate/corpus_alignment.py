"""Compare committed judge fixtures with the complete live hub evidence ledger."""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def canonical_ledger(
    chart_snapshot: str, mappings: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "chart_snapshot": chart_snapshot,
        "mappings": mappings,
    }


def ledger_sha256(ledger: dict[str, Any]) -> str:
    payload = json.dumps(
        ledger, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def expected_ledgers(
    data_root: Path, comparison_set: str
) -> dict[str, dict[str, Any]]:
    comparison = json.loads(
        (data_root / "comparison_sets" / f"{comparison_set}.json").read_text()
    )
    patient_ids = {
        json.loads((data_root / "scenarios" / f"{scenario}.json").read_text())[
            "patient_ref"
        ]
        for scenario in comparison["scenario_ids"]
    }
    fixtures: dict[str, dict[str, Any]] = {}
    for path in (data_root / "charts").glob("*.json"):
        fixture = json.loads(path.read_text())
        patient_id = (fixture.get("patient") or {}).get("uuid")
        snapshot = fixture.get("chart_snapshot")
        mappings = fixture.get("mappings")
        if patient_id in patient_ids and isinstance(snapshot, str) and isinstance(mappings, list):
            fixtures[patient_id] = canonical_ledger(snapshot, mappings)
    missing = sorted(patient_ids - fixtures.keys())
    if missing:
        raise ValueError(f"no complete chart fixture for patient(s): {', '.join(missing)}")
    return fixtures


def live_records(
    endpoint: str,
    patient: str,
    username: str,
    password: str,
    *,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start = 0
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    while True:
        query = urllib.parse.urlencode(
            {"patient": patient, "limit": page_size, "startIndex": start}
        )
        request = urllib.request.Request(
            f"{endpoint}?{query}", headers={"Authorization": f"Basic {token}"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload: dict[str, Any] = json.load(response)
        page = payload.get("results") or []
        records.extend(page)
        start += len(page)
        total = payload.get("totalCount")
        if not page or len(page) < page_size or (
            total is not None and start >= int(total)
        ):
            break
    return records


def alignment_issues(
    expected: dict[str, dict[str, Any]],
    live: dict[str, dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    for patient, fixture_ledger in sorted(expected.items()):
        live_ledger = live.get(patient)
        if live_ledger is None:
            issues.append(f"{patient}: live ledger missing")
            continue
        if ledger_sha256(fixture_ledger) == ledger_sha256(live_ledger):
            continue
        fixture_mappings = fixture_ledger.get("mappings") or []
        live_mappings = live_ledger.get("mappings") or []
        fixture_ids = {
            row.get("resourceUuid") for row in fixture_mappings if row.get("resourceUuid")
        }
        live_ids = {
            row.get("resourceUuid") for row in live_mappings if row.get("resourceUuid")
        }
        missing = sorted(fixture_ids - live_ids)
        unexpected = sorted(live_ids - fixture_ids)
        if missing:
            issues.append(
                f"{patient}: {len(missing)} fixture record(s) missing live; sample {missing[:3]}"
            )
        if unexpected:
            issues.append(
                f"{patient}: {len(unexpected)} unexpected live record(s); sample {unexpected[:3]}"
            )
        first_difference = next(
            (
                index
                for index, (fixture_row, live_row) in enumerate(
                    zip(fixture_mappings, live_mappings), start=1
                )
                if fixture_row != live_row
            ),
            None,
        )
        if len(fixture_mappings) != len(live_mappings):
            issues.append(
                f"{patient}: mapping count fixture={len(fixture_mappings)} live={len(live_mappings)}"
            )
        elif first_difference is not None:
            issues.append(f"{patient}: mapping content/order differs at index {first_difference}")
        if fixture_ledger.get("chart_snapshot") != live_ledger.get("chart_snapshot"):
            issues.append(f"{patient}: rendered chart text differs")
        issues.append(
            f"{patient}: ledger sha fixture={ledger_sha256(fixture_ledger)} "
            f"live={ledger_sha256(live_ledger)}"
        )
    return issues
