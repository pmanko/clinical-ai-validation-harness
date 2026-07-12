"""Verify that live patient ledgers and committed judge fixtures share a date era."""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _normalise_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) or (
        isinstance(value, str) and value.strip().isdigit()
    ):
        number = float(value)
        if number > 10_000_000_000:
            return datetime.fromtimestamp(number / 1000, timezone.utc).date().isoformat()
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else None


def expected_record_dates(
    data_root: Path, comparison_set: str
) -> dict[str, dict[str, str | None]]:
    comparison = json.loads(
        (data_root / "comparison_sets" / f"{comparison_set}.json").read_text()
    )
    patient_ids = {
        json.loads((data_root / "scenarios" / f"{scenario}.json").read_text())[
            "patient_ref"
        ]
        for scenario in comparison["scenario_ids"]
    }
    fixtures: dict[str, dict[str, str | None]] = {}
    for path in (data_root / "charts").glob("*.json"):
        fixture = json.loads(path.read_text())
        patient = fixture.get("patient") or {}
        patient_id = patient.get("uuid")
        records = {
            str(mapping["resourceUuid"]): _normalise_date(mapping.get("date"))
            for mapping in fixture.get("mappings") or []
            if mapping.get("resourceUuid")
        }
        if patient_id in patient_ids and records:
            fixtures[patient_id] = records
    missing = sorted(patient_ids - fixtures.keys())
    if missing:
        raise ValueError(f"no dated chart fixture for patient(s): {', '.join(missing)}")
    return fixtures


def live_record_dates(
    endpoint: str,
    patient: str,
    username: str,
    password: str,
    *,
    page_size: int = 500,
) -> dict[str, str | None]:
    return {
        str(record["resourceUuid"]): _normalise_date(record.get("date"))
        for record in live_records(
            endpoint,
            patient,
            username,
            password,
            page_size=page_size,
        )
        if record.get("resourceUuid")
    }


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
    expected: dict[str, dict[str, str | None]],
    live: dict[str, dict[str, str | None]],
) -> list[str]:
    issues: list[str] = []
    for patient, fixture_records in sorted(expected.items()):
        live_records = live.get(patient) or {}
        missing = sorted(fixture_records.keys() - live_records.keys())
        unexpected = sorted(live_records.keys() - fixture_records.keys())
        changed = sorted(
            uuid
            for uuid in fixture_records.keys() & live_records.keys()
            if fixture_records[uuid] != live_records[uuid]
        )
        if missing:
            issues.append(
                f"{patient}: {len(missing)} fixture record(s) missing live; sample {missing[:3]}"
            )
        if unexpected:
            issues.append(
                f"{patient}: {len(unexpected)} unexpected live record(s); sample {unexpected[:3]}"
            )
        if changed:
            sample = [
                f"{uuid} fixture={fixture_records[uuid]} live={live_records[uuid]}"
                for uuid in changed[:3]
            ]
            issues.append(
                f"{patient}: {len(changed)} record date mismatch(es); sample {sample}"
            )
    return issues
