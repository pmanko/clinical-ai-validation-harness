"""Behavior of the shared review label policy, run on result rows captured from a
real comparison run (trimmed; see tests/fixtures/review_presentation_rows.json)."""

import json
from pathlib import Path

from harness.validate.response_artifacts import in_depth_artifact, split_answer_sections
from harness.validate.review_presentation import (
    SECTION_STATUS,
    annotate_sources,
    answer_section_view,
    cell_review_summary,
    confidence_display,
    draft_view,
    format_latency,
    indepth_claim_rows,
    indepth_section_view,
    markdown_html,
    section_confidence_displays,
    status_display,
)
from harness.validate.sources import build_sources

ROWS = json.loads(
    (Path(__file__).parent / "fixtures" / "review_presentation_rows.json").read_text(
        encoding="utf-8"
    )
)


def _views(name):
    row = ROWS[name]
    resp = row["response"]
    answer, embedded = split_answer_sections(resp.get("answer"))
    indepth = in_depth_artifact(row, resp, embedded)
    answer_conf, indepth_conf = section_confidence_displays({}, resp.get("confidence"))
    sources = annotate_sources(
        build_sources({**resp, "answer": answer + "\n\n" + (indepth.get("answer") or "")}),
        answer,
        resp.get("blocks"),
        indepth,
    )
    return (
        answer_section_view(
            resp.get("answerValidation"), answer_conf, answer, resp.get("blocks"), resp.get("references")
        ),
        indepth_section_view(indepth, indepth_conf, sources),
        sources,
    )


def _all_text(view):
    return json.dumps(view).lower()


def test_no_section_is_ever_labelled_a_self_check():
    """Reviewers differ by arm (same model, another model, or none)."""
    for name in ROWS:
        answer, indepth, _ = _views(name)
        assert "self-check" not in _all_text(answer)
        assert "self-check" not in _all_text(indepth)
    for level in ("green", "yellow", "red"):
        assert "self-check" not in confidence_display({"level": level})["label"].lower()


def test_cross_check_in_depth_names_the_checks_that_marked_it():
    _, indepth, _ = _views("xcheck")

    assert indepth["status"] == "needs_review"
    assert indepth["tone"] == "danger"
    assert indepth["marked"] == [2, 3]
    assert set(indepth["checks"]) == {"Model review", "Citation support"}
    assert indepth["note"]


def test_each_claim_row_carries_every_checks_verdict_and_reason():
    _, indepth, _ = _views("checked")
    rows = {row["index"]: row for row in indepth["claims"]}

    assert len(rows) == 3
    marked = rows[3]
    assert marked["marked"] is True
    assert marked["cited"] == [2, 33]
    assert marked["checks"]["date"]["tone"] == "danger" and marked["checks"]["date"]["reason"]
    assert marked["checks"]["review"]["tone"] == "warning" and marked["checks"]["review"]["reason"]
    assert marked["checks"]["citation"]["tone"] == "danger" and marked["checks"]["citation"]["reason"]
    # An uncited general-guidance point is labelled neutrally, never as a failure.
    guidance = rows[2]
    assert guidance["general_guidance"] is True
    assert guidance["checks"]["citation"]["tone"] == "neutral"
    # A cited point with no failing entry reads its records' grounding.
    assert rows[1]["checks"]["citation"]["tone"] == "success"


def test_no_claims_and_absent_in_depth_map_to_plain_neutral_labels():
    _, no_claims, _ = _views("no_claims")
    _, answer_only, _ = _views("answer_only")
    _, bundled, _ = _views("bundled")

    for view in (no_claims, answer_only, bundled):
        assert "_" not in view["label"]
        assert view["tone"] == "neutral"
        assert not view["note"]
    assert no_claims["status"] == "no_claims"
    assert answer_only["status"] == bundled["status"] == "not_in_profile"
    assert answer_only["confidence"] is None
    assert status_display("some_new_state")["label"] == "Some new state"


def test_every_known_status_has_a_plain_label():
    for status in SECTION_STATUS:
        assert "_" not in status_display(status)["label"]


def test_a_citation_format_only_draft_difference_shows_no_draft():
    _, indepth, _ = _views("citation_format_draft")
    assert ROWS["citation_format_draft"]["response"]["inDepth"]["reviewDraft"]

    assert indepth["draft"] is None


def test_a_draft_is_named_for_what_happened_to_it():
    changed = draft_view({"answer": "- Weight is 41 kg [2].", "reviewDraft": "- Weight is 44 kg [2]."})
    withheld = draft_view({"answer": "", "reviewDraft": "- Weight is 44 kg [2]."})

    assert changed["kind"] == "changed"
    assert withheld["kind"] == "withheld"
    assert changed["title"] != withheld["title"]


def test_an_answer_unchanged_by_its_check_hides_the_original():
    answer, _, _ = _views("checked")

    assert answer["status"] == "edited"
    assert answer["show_original"] is False
    assert answer["checks"] == ["Date check"]


def test_a_changed_answer_shows_the_original():
    view = answer_section_view(
        {"status": "edited", "originalAnswer": "Weight was 44 kg [21]."},
        None,
        "Weight was 41 kg [21].",
    )
    assert view["show_original"] is True
    reordered = answer_section_view(
        {"status": "edited", "originalAnswer": "Fell from 52 kg [287] to 41 kg [21]."},
        None,
        "Fell from 52 kg [287] to 41 kg  [21].",
    )
    assert reordered["show_original"] is False


def test_an_answer_review_finding_is_attributed_to_the_model_review():
    answer, _, _ = _views("answer_review")

    assert "Model review" in answer["checks"]
    assert answer["note"]


def test_an_arm_reporting_no_answer_checks_has_no_answer_status():
    answer, _, _ = _views("bundled")
    assert answer is None


def test_markdown_bullets_render_as_a_list_with_marks_visible_and_text_escaped():
    out = markdown_html(
        "- First point [1].\n- Second point. *(General guidance, not from the chart.)*\n"
        "- Third <b>point</b> [2]. *(Check: its cited record does not support it.)*"
    )

    assert out.count("<li>") == 3
    assert "\n" not in out
    assert "claim-guidance" in out and "claim-mark" in out
    assert "<b>" not in out


def test_sources_say_which_section_cites_them_and_name_knowledge_references():
    annotated = annotate_sources(
        {
            "diagnostics": {"unresolved_refs": [7]},
            "sources": [
                {"citation_index": 1, "resource_type": "obs", "resolution_status": "resolved", "support_status": "verified"},
                {"citation_index": 7, "resource_type": "KnowledgeReference", "resolution_status": "unresolved", "support_status": "unsupported"},
                {"citation_index": 9, "resource_type": "obs", "resolution_status": "resolved", "support_status": "unchecked"},
            ]
        },
        "Answer text [1] [7].",
        [],
        {"answer": "- Point [7].\n- Point [9]."},
    )
    sources = annotated["sources"]
    assert annotated["diagnostics"]["unresolved_refs"] == []

    assert sources[0]["sections"] == ["Answer"]
    assert sources[1]["sections"] == ["Answer", "In-Depth"]
    assert sources[2]["sections"] == ["In-Depth"]
    assert sources[1]["record_tone"] == "neutral"
    assert sources[1]["record_label"] != sources[0]["record_label"]
    assert [s["support_tone"] for s in sources] == ["success", "danger", "neutral"]


def test_a_grid_cell_carries_the_worst_status_and_marked_points_across_turns():
    summary = cell_review_summary([ROWS["checked"], ROWS["citation_format_draft"], ROWS["no_claims"]])

    assert summary["answer"]["status"] == "edited"
    assert summary["indepth"]["status"] == "needs_review"
    assert summary["marked"] == 2
    bundled = cell_review_summary([ROWS["bundled"]])
    assert bundled["indepth"]["status"] == "not_in_profile"


def test_claim_rows_are_empty_without_a_claim_record():
    assert indepth_claim_rows({"answer": "- Legacy point."}) == []


def test_latency_reads_in_seconds():
    assert format_latency(56601) == "56.6 s"
    assert format_latency(None) == "n/a"


# ------------------------------------------------- the three-way label contract


def _contract_row():
    """An envelope under the confidence-labels contract: withdrawn levels, findings,
    three-way citation support, info issues, clean review and pass entries."""
    return {
        "answer": "Weight fell from 52 kg [287] to 41 kg [21]; CD4 was 72 on 2025-10-22 [311].",
        "blocks": [],
        "references": [
            {"index": 21, "resolutionStatus": "resolved", "groundingStatus": "mixed",
             "support": "not_addressed", "usage": [{"location": "answer"}],
             "groundingChecks": [{"support": "not_addressed", "facts": [
                 {"fact": "52 kg", "found": False}, {"fact": "41 kg", "found": True, "source_index": 21}]}]},
            {"index": 287, "resolutionStatus": "resolved", "groundingStatus": "verified",
             "support": "supported", "usage": [{"location": "answer"}]},
            {"index": 311, "resolutionStatus": "resolved", "groundingStatus": "unsupported",
             "support": "contradicted", "usage": [{"location": "answer"}],
             "groundingChecks": [{"support": "contradicted", "chart_value": "CD4 341 on 2025-11-24",
                                  "facts": [{"fact": "CD4 72", "found": False}]}]},
        ],
        "answerValidation": {
            "status": "needs_review",
            "label": "Needs review",
            "issues": [
                {"id": "citation_grounding", "status": "fail", "severity": "block",
                 "reason": "[311] states CD4 341 on 2025-11-24, not 72.", "source_indices": [311]},
                {"id": "citation_grounding", "status": "info",
                 "reason": "[21] does not hold 52 kg.", "source_indices": [21]},
            ],
        },
        "confidence": {
            "answer": {"level": None, "note": "", "findings": [
                {"check": "citation", "where": "answer", "says": "[311] states CD4 341, not 72"},
                {"check": "record", "where": "answer", "says": "no cited record is outside the chart"},
            ]},
            "in_depth": {"level": None, "note": "", "findings": [
                {"check": "date", "where": "point 2", "says": "2026-01_26 is not a date in the chart"},
            ]},
        },
        "inDepth": {
            "status": "complete",
            "answer": "- Adherence was half in the week before the visit [14].\n- Weight fell to 41 kg on 2026-01_26 [21].\n- Fever may signal infection.",
            "validation": {
                "status": "needs_review",
                "claims": [
                    "Adherence was half in the week before the visit [14].",
                    "Weight fell to 41 kg on 2026-01_26 [21].",
                    "Fever may signal infection.",
                ],
                "checks": [
                    {"claim_index": 1, "gate": {"status": "not_applicable", "checks": []}},
                    {"claim_index": 2, "gate": {"status": "fail", "checks": [
                        {"id": "date_format", "status": "fail", "reason": "2026-01_26 is not a chart date."}]}},
                    {"claim_index": 3, "gate": {"status": "not_applicable", "checks": []}},
                ],
                "citation_checks": [
                    {"claim_index": 1, "status": "pass", "reason": "[14] states half adherence.", "source_indices": [14]},
                    {"claim_index": 2, "status": "not_addressed", "reason": "[21] holds 41 kg, not the date.", "source_indices": [21]},
                    {"claim_index": 3, "status": "info", "reason": "In-Depth claim cites no record; it is general guidance.", "source_indices": []},
                ],
                "review_status": "clean",
                "marked": [2],
            },
        },
    }


def _contract_views(resp):
    answer, embedded = split_answer_sections(resp.get("answer"))
    indepth = in_depth_artifact({"response": resp}, resp, embedded)
    answer_conf, indepth_conf = section_confidence_displays({}, resp.get("confidence"))
    sources = annotate_sources(build_sources(resp), answer, resp.get("blocks"), indepth)
    return (
        answer_section_view(resp.get("answerValidation"), answer_conf, answer, resp.get("blocks"), resp.get("references")),
        indepth_section_view(indepth, indepth_conf, sources),
        sources,
    )


def test_a_withdrawn_confidence_level_shows_no_chip_and_lists_the_findings():
    answer, indepth, _ = _contract_views(_contract_row())

    assert answer["confidence"] is None and answer["confidence_level"] is None
    assert answer["status"] == "needs_review"
    assert [f["name"] for f in answer["findings"]][:2] == ["Citation support", "Record check"]
    assert answer["findings"][0]["where"] == "answer" and "341" in answer["findings"][0]["says"]
    # The check's info note joins the list as a neutral finding, never the questioned checks.
    assert answer["findings"][-1]["says"] == "[21] does not hold 52 kg"
    assert answer["findings"][-1]["tone"] == "neutral"
    assert answer["checks"] == ["Citation support"]
    assert "does not hold" not in answer["note"]
    assert indepth["confidence"] is None
    assert indepth["findings"] == [{"check": "date", "name": "Date check", "where": "point 2",
                                    "says": "2026-01_26 is not a date in the chart", "tone": "neutral"}]
    # A level string keeps today's behaviour.
    assert confidence_display({"level": "red", "note": "x"})["label"] == "Low confidence"
    assert confidence_display({"level": None})["label"] is None
    assert confidence_display({}) is None


def test_not_addressed_is_neutral_and_contradicted_names_the_chart_value():
    _, indepth, sources = _contract_views(_contract_row())
    by_index = {s["citation_index"]: s for s in sources["sources"]}

    assert by_index[21]["support_label"] == "does not hold this fact"
    assert by_index[21]["support_tone"] == "neutral"
    assert by_index[287]["support_label"] == "supports its claim"
    assert by_index[287]["support_tone"] == "success"
    assert by_index[311]["support_label"] == "contradicts: CD4 341 on 2025-11-24"
    assert by_index[311]["support_tone"] == "danger"
    rows = {row["index"]: row for row in indepth["claims"]}
    assert rows[2]["checks"]["citation"]["verdict"] == "not addressed"
    assert rows[2]["checks"]["citation"]["tone"] == "neutral"
    assert "Citation support" not in indepth["checks"]
    assert indepth["checks"] == ["Date check"]


def test_pass_entries_and_a_clean_review_read_as_passed():
    _, indepth, _ = _contract_views(_contract_row())
    rows = {row["index"]: row for row in indepth["claims"]}

    assert rows[1]["checks"]["citation"]["verdict"] == "passed"
    assert rows[1]["checks"]["citation"]["tone"] == "success"
    for index in (1, 2, 3):
        assert rows[index]["checks"]["review"] == {"verdict": "passed", "tone": "success", "reason": ""}
    assert rows[3]["checks"]["citation"]["verdict"] == "general guidance"


def test_a_contradicted_citation_without_a_chart_value_names_the_missing_facts():
    source = {"index": 5, "support": "contradicted", "groundingStatus": "unsupported",
              "groundingChecks": [{"support": "contradicted", "facts": [
                  {"fact": "52 kg", "found": False}, {"fact": "2025-10-22", "found": True}]}]}
    sources = annotate_sources(build_sources({"answer": "Weight 52 kg [5].", "references": [source]}))
    assert sources["sources"][0]["support_label"] == "contradicts: not found: 52 kg"
