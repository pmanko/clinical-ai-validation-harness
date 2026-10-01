import json
from pathlib import Path

import pytest

from harness.validate.corpus_alignment import (
    alignment_issues,
    expected_ledgers,
    live_records,
)

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
