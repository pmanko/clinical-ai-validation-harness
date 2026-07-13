from harness.validate import report


def _row(in_depth):
    return {
        "response": {
            "answer": "Short answer [1].",
            "references": [],
            "blocks": [],
            "inDepth": in_depth,
        },
        "metrics": {"latency_ms": 100, "http_status": 200},
    }


def test_report_renders_hub_native_indepth_content(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})

    cell = report._cell_blob(
        _row(
            {
                "status": "complete",
                "answer": "A checked background claim [2].",
                "validation": {"mode": "enforce", "status": "edited"},
            }
        )
    )

    assert "A checked background claim [2]." in cell["answer_html"]
    assert "Updated after check" in cell["answer_html"]


def test_report_renders_withheld_hub_native_indepth_status(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})

    cell = report._cell_blob(
        _row(
            {
                "status": "needs_review",
                "answer": "",
                "error": "In-Depth was withheld because every claim failed checks.",
                "validation": {"mode": "enforce", "status": "needs_review"},
            }
        )
    )

    assert "Needs review" in cell["answer_html"]
    assert "In-Depth was withheld because every claim failed checks." in cell["answer_html"]


def test_report_retains_legacy_separate_indepth(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["indepth"] = {"response": {"answer": "Legacy In-Depth [3]."}}

    cell = report._cell_blob(row)

    assert "Legacy In-Depth [3]." in cell["answer_html"]


def test_report_does_not_show_embedded_text_withheld_by_product_envelope(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(
        {
            "status": "needs_review",
            "answer": "",
            "error": "Current In-Depth was withheld.",
        }
    )
    row["response"]["answer"] = "Short answer.\n\n**InDepth** Old unsafe background."

    cell = report._cell_blob(row)

    assert "Short answer." in cell["answer_html"]
    assert "Current In-Depth was withheld." in cell["answer_html"]
    assert "Old unsafe background." not in cell["answer_html"]


def test_report_drops_evidence_used_only_by_discarded_embedded_text(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row({"status": "needs_review", "answer": ""})
    row["response"]["answer"] = "Current [1]. **InDepth** Discarded [99]."
    row["response"]["references"] = [
        {"index": 1, "resourceType": "obs"},
        {"index": 99, "resourceType": "obs"},
    ]

    cell = report._cell_blob(row)

    assert cell["sources"]["diagnostics"]["top_level_refs"] == [1]
    assert [source["citation_index"] for source in cell["sources"]["sources"]] == [1]


def test_report_shows_historical_indepth_call_failure(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["indepth"] = {
        "response": None,
        "error": "in-depth request failed: timeout",
    }

    cell = report._cell_blob(row)

    assert "Failed" in cell["answer_html"]
    assert "in-depth request failed: timeout" in cell["answer_html"]
