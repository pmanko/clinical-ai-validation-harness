from harness.validate.response_artifacts import (
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)


def test_review_recovery_keeps_earliest_rejected_retry_draft():
    prepared = prepare_indepth_review(
        {"status": "complete", "answer": "- Accepted retry [2]."},
        {
            "steps": [
                {"role": "indepth_synth", "claims": ["Rejected first draft [1]."]},
                {"role": "indepth_resynth", "claims": ["Accepted retry [2]."]},
            ]
        },
        None,
    )

    assert prepared["reviewDraft"] == "- Rejected first draft [1]."


def test_answer_review_sources_are_separate_from_final_sources():
    prepared = prepare_answer_review(
        {
            "status": "edited",
            "originalAnswer": "Original draft [1].",
            "originalReferences": [{"index": 1, "resourceUuid": "draft-1"}],
        },
        "Final answer [2].",
        {},
        {
            "chart_snapshot": "[1] (2026-01-01) Draft record\n[2] (2026-02-02) Final record",
            "mappings": [
                {"index": 1, "resourceType": "obs", "resourceUuid": "draft-1"},
                {"index": 2, "resourceType": "obs", "resourceUuid": "final-2"},
            ],
            "valid_uuids": ["draft-1", "final-2"],
        },
    )

    assert [
        source["citation_index"]
        for source in prepared["originalSources"]["sources"]
    ] == [1]


def test_same_prose_with_changed_references_keeps_original_sources_for_review():
    prepared = prepare_answer_review(
        {
            "status": "edited",
            "originalAnswer": "Same clinical statement [1].",
            "originalReferences": [{"index": 1, "resourceUuid": "old-1"}],
        },
        "Same clinical statement [1].",
        {},
        {
            "chart_snapshot": "[1] (2026-01-01) Original source record",
            "mappings": [
                {"index": 1, "resourceType": "obs", "resourceUuid": "old-1"}
            ],
            "valid_uuids": ["old-1"],
        },
    )

    assert prepared["originalAnswer"] == "Same clinical statement [1]."
    assert prepared["originalSources"]["sources"][0]["citation_index"] == 1


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


def test_review_draft_and_its_references_do_not_enter_shipped_evidence():
    response = {
        "answer": "Checked answer [1].",
        "references": [{"index": 1}],
        "inDepth": {
            "status": "needs_review",
            "answer": "",
            "reviewDraft": "Rejected claim [99].",
            "reviewReferences": [{"index": 99}],
        },
    }
    artifact = in_depth_artifact({}, response)

    normalized = response_for_displayed_evidence(
        response, response["answer"], artifact
    )

    assert normalized["answer"] == "Checked answer [1]."
    assert [ref["index"] for ref in normalized["references"]] == [1]
    assert "Rejected claim" not in normalized["answer"]


def test_unchanged_prose_with_rejected_blocks_keeps_block_sources_for_review():
    prepared = prepare_answer_review(
        {
            "status": "needs_review",
            "originalAnswer": "The recorded weight is below [1].",
            "originalReferences": [
                {"index": 1, "resourceType": "Observation", "resourceUuid": "obs-1"}
            ],
            "originalBlocks": [
                {
                    "kind": "table",
                    "title": "Rejected table",
                    "columns": [{"key": "weight", "label": "Weight"}],
                    "rows": [
                        {"cells": {"weight": {"text": "6.2 kg", "refs": [1]}}}
                    ],
                }
            ],
        },
        "The recorded weight is below [1].",
        None,
        {
            "chart_snapshot": "[1] (2026-01-01) Observation: Weight 6.2 kg",
            "mappings": [
                {"index": 1, "resourceType": "Observation", "resourceUuid": "obs-1"}
            ],
            "valid_uuids": ["obs-1"],
        },
    )

    source = prepared["originalSources"]["sources"][0]
    assert source["citation_index"] == 1
    assert any(usage["kind"] == "table_row" for usage in source["used_by"])


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
