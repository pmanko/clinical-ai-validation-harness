from harness.validate.review_presentation import (
    confidence_display,
    indepth_validation_display,
    section_confidence_displays,
    validation_display,
)


def test_low_confidence_is_prominent_without_hiding_output():
    display = confidence_display({"level": "red", "note": "Check the date."})

    assert display == {
        "level": "red",
        "label": "Self-check low",
        "note": "Check the date.",
        "note_treatment": "prominent",
        "show_output": True,
        "tone": "danger",
    }


def test_response_confidence_precedes_stale_trace_fallback():
    answer, indepth = section_confidence_displays(
        {"answer_confidence": {"level": "yellow", "note": "Trace note"}},
        {
            "answer": {"level": "green", "note": "Response note"},
            "in_depth": {"level": "red", "note": "In-Depth note"},
        },
    )

    assert answer["level"] == "green"
    assert answer["note"] == "Response note"
    assert indepth["level"] == "red"


def test_trace_confidence_fills_missing_response_sections():
    answer, indepth = section_confidence_displays(
        {
            "answer_confidence": {"level": "yellow", "note": "Trace answer"},
            "indepth_confidence": {"level": "red", "note": "Trace In-Depth"},
        },
        {"answer": {"level": "green", "note": "Response answer"}},
    )

    assert answer["level"] == "green"
    assert answer["note"] == "Response answer"
    assert indepth["level"] == "red"
    assert indepth["note"] == "Trace In-Depth"


def test_validation_labels_are_shared_for_answer_and_indepth():
    answer = validation_display({"status": "needs_review"})
    indepth = indepth_validation_display({"status": "needs_review", "answer": ""})

    assert answer == indepth == {
        "status": "needs_review",
        "label": "Needs review",
        "tone": "danger",
    }


def test_indepth_validation_display_is_none_for_a_non_dict_indepth():
    """A turn with no In-Depth section at all (None, or a bare string status) must
    resolve to no validation display rather than raising on dict-style access."""
    assert indepth_validation_display(None) is None
    assert indepth_validation_display("pending") is None
