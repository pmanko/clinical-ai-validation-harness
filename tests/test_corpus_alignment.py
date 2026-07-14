import importlib.util
import json
from pathlib import Path

import pytest

from harness.validate.corpus_alignment import (
    alignment_issues,
    expected_ledgers,
    live_records,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_chart_fixture", ROOT / "scripts" / "capture-chart-fixture.py"
)
CAPTURE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CAPTURE)
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_validation_corpus", ROOT / "scripts" / "verify-validation-corpus.py"
)
VERIFY_CORPUS = importlib.util.module_from_spec(VERIFY_SPEC)
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY_SPEC.loader.exec_module(VERIFY_CORPUS)


def test_expected_ledger_and_alignment_compare_complete_rendered_content(tmp_path):
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
                "chart_snapshot": "[1] (2025-01-01) Finding -- Weight: 71 kg\n",
                "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "a", "date": "2025-01-01", "text": "(2025-01-01) Finding -- Weight: 71 kg"}],
            }
        )
    )

    expected = expected_ledgers(root, "set")
    assert alignment_issues(expected, expected) == []

    changed = json.loads(json.dumps(expected))
    changed["p"]["mappings"][0]["text"] = "(2025-01-01) Finding -- Weight: 17 kg"
    changed["p"]["chart_snapshot"] = "[1] (2025-01-01) Finding -- Weight: 17 kg\n"
    issues = alignment_issues(expected, changed)
    assert "p: mapping content/order differs at index 1" in issues
    assert "p: rendered chart text differs" in issues
    assert any("ledger sha fixture=" in issue for issue in issues)


def test_expected_ledgers_fails_without_patient_fixture(tmp_path):
    root = tmp_path
    (root / "comparison_sets").mkdir()
    (root / "scenarios").mkdir()
    (root / "charts").mkdir()
    (root / "comparison_sets" / "set.json").write_text(
        json.dumps({"scenario_ids": ["s"], "backend_ids": ["b"]})
    )
    (root / "scenarios" / "s.json").write_text(json.dumps({"patient_ref": "p"}))

    with pytest.raises(ValueError, match="no complete chart fixture"):
        expected_ledgers(root, "set")


def test_live_records_pages_until_total_count(monkeypatch):
    pages = [
        {"results": [{"resourceUuid": "a"}], "totalCount": 2},
        {"results": [{"resourceUuid": "b"}], "totalCount": 2},
    ]
    urls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def urlopen(request, timeout):
        urls.append(request.full_url)
        return Response(pages.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    assert live_records("http://example/records", "p", "u", "pw", page_size=1) == [
        {"resourceUuid": "a"},
        {"resourceUuid": "b"},
    ]
    assert "startIndex=0" in urls[0]
    assert "startIndex=1" in urls[1]


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


def test_successful_fixture_capture_replaces_staged_file_atomically(tmp_path, monkeypatch):
    fixture = tmp_path / "p1.json"
    fixture.write_text(
        json.dumps({"patient": {"uuid": "p1"}, "chart_snapshot": "old", "mappings": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(CAPTURE, "ROOT", tmp_path)
    monkeypatch.setattr(CAPTURE, "_fixture_paths", lambda *_args: [fixture])
    monkeypatch.setattr(CAPTURE, "_hub_commit", lambda: "a" * 40)
    monkeypatch.setattr(
        CAPTURE,
        "live_records",
        lambda *_args: [{"resourceType": "obs", "resourceUuid": "o1", "date": "2026-01-01", "text": "Finding -- Weight: 71 kg"}],
    )
    replacements = []
    real_replace = CAPTURE.os.replace

    def replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(CAPTURE.os, "replace", replace)

    assert CAPTURE.main(["--all", "--username", "reader", "--password", "secret"]) == 0
    assert replacements == [(tmp_path / ".p1.json.tmp", fixture)]
    assert json.loads(fixture.read_text())["valid_uuids"] == ["o1"]


def test_verify_corpus_cli_reports_matching_live_ledger(monkeypatch, capsys):
    expected = {
        "p1": {
            "chart_snapshot": "[1] (2026-01-01) Finding -- Weight: 71 kg\n",
            "mappings": [{"index": 1, "resourceUuid": "o1"}],
        }
    }
    monkeypatch.setattr(VERIFY_CORPUS, "expected_ledgers", lambda *_args: expected)
    monkeypatch.setattr(VERIFY_CORPUS, "live_records", lambda *_args: [{"uuid": "o1"}])
    monkeypatch.setattr(
        VERIFY_CORPUS,
        "render_chart",
        lambda _records: (expected["p1"]["chart_snapshot"], expected["p1"]["mappings"]),
    )
    monkeypatch.setattr(VERIFY_CORPUS, "alignment_issues", lambda *_args: [])
    monkeypatch.setattr(
        VERIFY_CORPUS.sys,
        "argv",
        [
            "verify-validation-corpus.py",
            "--set",
            "set",
            "--endpoint",
            "http://querystore",
            "--username",
            "reader",
            "--password",
            "secret",
        ],
    )

    assert VERIFY_CORPUS.main() == 0
    assert "p1: 1 exact fixture/live records" in capsys.readouterr().out


def test_verify_corpus_cli_reports_alignment_issues(monkeypatch, capsys):
    expected = {"p1": {"chart_snapshot": "fixture", "mappings": []}}
    monkeypatch.setattr(VERIFY_CORPUS, "expected_ledgers", lambda *_args: expected)
    monkeypatch.setattr(VERIFY_CORPUS, "live_records", lambda *_args: [])
    monkeypatch.setattr(VERIFY_CORPUS, "render_chart", lambda _records: ("live", []))
    monkeypatch.setattr(
        VERIFY_CORPUS,
        "alignment_issues",
        lambda *_args: ["p1: rendered chart text differs"],
    )
    monkeypatch.setattr(
        VERIFY_CORPUS.sys,
        "argv",
        [
            "verify-validation-corpus.py",
            "--set",
            "set",
            "--endpoint",
            "http://querystore",
            "--username",
            "reader",
            "--password",
            "secret",
        ],
    )

    assert VERIFY_CORPUS.main() == 1
    output = capsys.readouterr().out
    assert "p1: rendered chart text differs" in output
    assert "Restore/reindex" in output
