from harness.validate import report
from harness.validate.review_presentation import confidence_display


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
                "reviewDraft": "- Rejected model claim [2].",
                "reviewReferences": [{"index": 2, "resourceType": "obs"}],
            }
        )
    )

    assert "Needs review" in cell["answer_html"]
    assert "In-Depth was withheld because every claim failed checks." in cell["answer_html"]
    assert "Removed In-Depth claims" in cell["answer_html"]
    assert "Rejected model claim [2]." in cell["answer_html"]
    assert "not part of the final clinical response" in cell["answer_html"]
    assert "<details open class='reviewdraft'>" not in cell["answer_html"]
    assert "<details class='reviewdraft'>" in cell["answer_html"]
    assert "Draft sources for review (not final evidence)" in cell["answer_html"]
    assert all(
        source["citation_index"] != 2 for source in cell["sources"]["sources"]
    )


def test_report_low_confidence_content_is_visible_without_a_reveal():
    rendered = report._render_section(
        "Answer",
        "Flagged model answer [1].",
        confidence_display(
            {"level": "red", "note": "The date could not be verified."}
        ),
    )

    assert "Flagged model answer [1]." in rendered
    assert "The date could not be verified." in rendered
    assert "<details" not in rendered
    assert "show answer" not in rendered


def test_report_uses_response_confidence_when_trace_is_unavailable(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["response"]["confidence"] = {
        "answer": {"level": "red", "note": "The source check failed."}
    }

    cell = report._cell_blob(row)

    assert "Self-check low" in cell["answer_html"]
    assert "The source check failed." in cell["answer_html"]
    assert "Short answer [1]." in cell["answer_html"]
    assert "show answer" not in cell["answer_html"]


def test_report_shows_edited_original_without_treating_it_as_final_evidence(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["response"]["answerValidation"] = {
        "status": "edited",
        "originalAnswer": "Original flagged answer [99].",
    }
    row["response"]["references"] = [{"index": 1, "resourceType": "obs"}]

    cell = report._cell_blob(
        row,
        chart_fixture={
            "chart_snapshot": "[99] (2026-01-01) Original draft record",
            "mappings": [
                {"index": 99, "resourceType": "obs", "resourceUuid": "draft-99"}
            ],
            "valid_uuids": ["draft-99"],
        },
    )

    assert "Original model answer" in cell["answer_html"]
    assert "Original flagged answer [99]." in cell["answer_html"]
    assert "checked answer above is the current result" in cell["answer_html"]
    assert "Original-answer sources (not final evidence)" in cell["answer_html"]
    assert "Original draft record" in cell["answer_html"]
    assert [source["citation_index"] for source in cell["sources"]["sources"]] == [1]


def test_report_shows_changed_original_when_result_still_needs_review(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["response"]["answerValidation"] = {
        "status": "needs_review",
        "originalAnswer": "The model answer before checking [2].",
    }

    cell = report._cell_blob(row)

    assert "Original model answer" in cell["answer_html"]
    assert "The model answer before checking [2]." in cell["answer_html"]
    assert "current answer above remains flagged for review" in cell["answer_html"]


def test_report_shows_same_prose_when_supporting_citations_changed(monkeypatch):
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: {})
    row = _row(None)
    del row["response"]["inDepth"]
    row["response"]["answer"] = "Short answer [1]."
    row["response"]["answerValidation"] = {
        "status": "edited",
        "originalAnswer": "Short answer [1].",
        "originalReferences": [{"index": 1, "resourceType": "obs"}],
    }

    cell = report._cell_blob(row)

    assert "Original model answer" in cell["answer_html"]
    assert "answer or its supporting citations was changed" in cell["answer_html"]


def test_report_recovers_rejected_draft_from_historical_trace(monkeypatch):
    monkeypatch.setattr(
        report,
        "_trace_for_row",
        lambda _row, _traces: {
            "steps": [
                {"role": "indepth_synth", "claims": ["Initial rejected claim [1]."]},
                {
                    "role": "indepth_resynth",
                    "claims": ["Canonicalized claim [2]."],
                    "original_claims": ["Latest rejected model claim [2]."],
                },
            ]
        },
    )

    cell = report._cell_blob(
        _row(
            {
                "status": "needs_review",
                "answer": "",
                "error": "In-Depth was withheld.",
            }
        ),
        traces=[{}],
        chart_fixture={
            "chart_snapshot": (
                "Patient\n[1] (2026-01-01) Observation: initial source\n"
                "[2] (2026-01-02) Observation: historical source"
            ),
            "mappings": [
                {"index": 1, "resourceType": "obs", "resourceUuid": "obs-1"},
                {"index": 2, "resourceType": "obs", "resourceUuid": "obs-2"}
            ],
            "valid_uuids": ["obs-1", "obs-2"],
        },
    )

    assert "Initial rejected claim [1]." in cell["answer_html"]
    assert "Latest rejected model claim [2]." not in cell["answer_html"]
    assert "Observation: initial source" in cell["answer_html"]
    assert "Draft sources for review (not final evidence)" in cell["answer_html"]


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
