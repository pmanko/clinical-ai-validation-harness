from harness.validate.response_artifacts import (
    in_depth_artifact,
    response_for_displayed_evidence,
    split_answer_sections,
)


def test_split_answer_sections_accepts_spaced_and_compact_headings():
    assert split_answer_sections("A\n**In Depth** B") == ("A", "B")
    assert split_answer_sections("A\n**InDepth** B") == ("A", "B")


def test_current_product_envelope_is_authoritative_over_embedded_content():
    artifact = in_depth_artifact(
        {},
        {"inDepth": {"status": "needs_review", "answer": ""}},
        "old embedded content",
    )

    assert artifact["answer"] == ""
    assert artifact["status"] == "needs_review"
    assert artifact["source"] == "response.inDepth"


def test_historical_outer_error_becomes_failed_artifact():
    artifact = in_depth_artifact(
        {"indepth": {"response": None, "error": "request timed out"}},
        {},
    )

    assert artifact["status"] == "failed"
    assert artifact["error"] == "request timed out"
    assert artifact["source"] == "row.indepth"


def test_displayed_evidence_excludes_refs_used_only_by_withheld_embedded_text():
    response = {
        "answer": "Current [1]. **InDepth** Discarded [99].",
        "references": [{"index": 1}, {"index": 99}, {"index": 7}],
        "citations": [1, 99, 7],
        "blocks": [],
    }
    direct, embedded = split_answer_sections(response["answer"])
    artifact = in_depth_artifact(
        {}, {**response, "inDepth": {"status": "needs_review", "answer": ""}}, embedded
    )

    normalized = response_for_displayed_evidence(response, direct, artifact, embedded)

    assert normalized["answer"] == "Current [1]."
    assert [ref["index"] for ref in normalized["references"]] == [1, 7]
    assert normalized["citations"] == [1, 7]


def test_authoritative_artifact_metadata_preserves_shared_reference():
    response = {
        "answer": "Current. **InDepth** Discarded [99].",
        "references": [{"index": 99}],
        "blocks": [],
    }
    direct, embedded = split_answer_sections(response["answer"])
    artifact = in_depth_artifact(
        {},
        {
            **response,
            "inDepth": {
                "status": "complete",
                "answer": "Current background without an inline marker.",
                "references": [{"index": 99}],
            },
        },
        embedded,
    )

    normalized = response_for_displayed_evidence(response, direct, artifact, embedded)

    assert [ref["index"] for ref in normalized["references"]] == [99]


def test_historical_separate_call_replaces_embedded_evidence():
    response = {
        "answer": "Current [1]. **In Depth** Discarded [99].",
        "references": [{"index": 1}, {"index": 99}],
        "blocks": [],
    }
    direct, embedded = split_answer_sections(response["answer"])
    artifact = in_depth_artifact(
        {
            "indepth": {
                "response": {
                    "answer": "Separate background [2].",
                    "references": [{"index": 2}],
                }
            }
        },
        response,
        embedded,
    )

    normalized = response_for_displayed_evidence(response, direct, artifact, embedded)

    assert [ref["index"] for ref in normalized["references"]] == [1, 2]
    assert "Discarded" not in normalized["answer"]
