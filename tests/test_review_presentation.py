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
