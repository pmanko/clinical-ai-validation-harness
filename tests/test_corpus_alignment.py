import importlib.util
import json
from pathlib import Path

import pytest

from harness.validate.corpus_alignment import alignment_issues, expected_record_dates

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_chart_fixture", ROOT / "scripts" / "capture-chart-fixture.py"
)
CAPTURE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CAPTURE)


def test_expected_record_dates_are_derived_from_fixture_mappings(tmp_path):
    root = tmp_path
    (root / "comparison_sets").mkdir()
    (root / "scenarios").mkdir()
    (root / "charts").mkdir()
    (root / "comparison_sets" / "set.json").write_text(
        json.dumps({"scenario_ids": ["s"], "backend_ids": ["b"]})
    )
    (root / "scenarios" / "s.json").write_text(json.dumps({"patient_ref": "p"}))
    (root / "charts" / "p.json").write_text(
        json.dumps(
            {
                "patient": {"uuid": "p"},
                "mappings": [
                    {"resourceUuid": "a", "date": "2025-01-01"},
                    {"resourceUuid": "b", "date": 1767312000000},
                ],
            }
        )
    )

    assert expected_record_dates(root, "set") == {
        "p": {"a": "2025-01-01", "b": "2026-01-02"}
    }
    assert alignment_issues(
        {"p": {"a": "2025-01-01", "b": "2026-01-02"}},
        {"p": {"a": "2006-06-06", "c": "2026-01-02"}},
    ) == [
        "p: 1 fixture record(s) missing live; sample ['b']",
        "p: 1 unexpected live record(s); sample ['c']",
        "p: 1 record date mismatch(es); sample ['a fixture=2025-01-01 live=2006-06-06']",
    ]


def test_expected_latest_dates_fails_without_patient_fixture(tmp_path):
    root = tmp_path
    (root / "comparison_sets").mkdir()
    (root / "scenarios").mkdir()
    (root / "charts").mkdir()
    (root / "comparison_sets" / "set.json").write_text(
        json.dumps({"scenario_ids": ["s"], "backend_ids": ["b"]})
    )
    (root / "scenarios" / "s.json").write_text(json.dumps({"patient_ref": "p"}))

    with pytest.raises(ValueError, match="no dated chart fixture"):
        expected_record_dates(root, "set")


def test_fixture_refresh_uses_hub_serializer_and_preserves_curated_identity():
    original = {
        "slug": "patient-a",
        "patient": {"uuid": "patient-1", "birthdate": "1990-01-01"},
        "chart_snapshot": "stale",
        "mappings": [],
    }
    records = [
        {
            "resourceType": "visit",
            "resourceUuid": "visit-1",
            "date": "2026-01-02",
            "text": "Visit -- Adult outpatient",
            "metadata": {},
        },
        {
            "resourceType": "obs",
            "resourceUuid": "obs-1",
            "date": "2026-01-02",
            "text": "Finding -- Weight: 71.0 kg",
            "metadata": {},
        },
    ]

    refreshed = CAPTURE.updated_fixture(
        original,
        records,
        captured_at="2026-07-12T00:00:00+00:00",
        hub_commit="a" * 40,
    )

    assert refreshed["slug"] == "patient-a"
    assert refreshed["patient"] == original["patient"]
    assert refreshed["chart_snapshot"] == (
        "[1] (2026-01-02) Visit -- Adult outpatient\n"
        "[2] (2026-01-02) Finding -- Weight: 71 kg\n"
    )
    assert refreshed["valid_uuids"] == ["obs-1", "visit-1"]
    assert refreshed["provenance"]["resource_types"] == {"obs": 1, "visit": 1}
    assert "chartsearchai_chat_session" not in refreshed["provenance"]["source"]


def test_all_fixture_capture_fetches_every_patient_before_writing(tmp_path, monkeypatch):
    fixtures = []
    for patient in ("p1", "p2"):
        path = tmp_path / f"{patient}.json"
        path.write_text(
            json.dumps(
                {
                    "slug": patient,
                    "patient": {"uuid": patient},
                    "chart_snapshot": "original",
                    "mappings": [],
                }
            ),
            encoding="utf-8",
        )
        fixtures.append(path)
    before = [path.read_text(encoding="utf-8") for path in fixtures]
    monkeypatch.setattr(CAPTURE, "_fixture_paths", lambda *_args: fixtures)
    monkeypatch.setattr(CAPTURE, "_hub_commit", lambda: "a" * 40)
    calls = 0

    def fetch(_endpoint, _patient, _username, _password):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second patient unavailable")
        return [
            {
                "resourceType": "obs",
                "resourceUuid": "obs-1",
                "date": "2026-01-01",
                "text": "Finding -- Weight: 71 kg",
            }
        ]

    monkeypatch.setattr(CAPTURE, "live_records", fetch)

    assert CAPTURE.main(["--all", "--username", "reader", "--password", "secret"]) == 1
    assert [path.read_text(encoding="utf-8") for path in fixtures] == before
