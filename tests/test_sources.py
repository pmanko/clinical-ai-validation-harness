from harness.validate.sources import build_sources, render_sources_for_judge, source_ref_labels


def test_source_tile_uses_uuid_resolved_chart_row_when_citation_index_differs():
    chart = {
        "chart_snapshot": "\n".join(
            [
                "Patient records (most recent first):",
                "[2] (2026-01-07) Assessment -- Discordant couple: No",
                "[28] (2026-01-07) Drug order: Trimethoprim and sulfamethoxazole. Action: NEW.",
            ]
        ),
        "mappings": [
            {
                "index": 2,
                "resourceType": "obs",
                "resourceUuid": "obs-2",
                "date": 1767744000000,
            },
            {
                "index": 28,
                "resourceType": "order",
                "resourceUuid": "drug-28",
                "date": 1767744000000,
            },
        ],
        "valid_uuids": ["obs-2", "drug-28"],
    }
    response = {
        "answer": "Trimethoprim was ordered [2].",
        "references": [
            {
                "index": 2,
                "resourceType": "drug_order",
                "resourceUuid": "drug-28",
                "date": "2026-01-07",
            }
        ],
        "blocks": [
            {
                "kind": "table",
                "title": "Orders",
                "columns": [{"key": "item", "label": "Ordered Item"}],
                "rows": [{"cells": {"item": {"text": "Trimethoprim", "refs": [2]}}}],
            }
        ],
    }

    sources = build_sources(response, chart)

    source = sources["sources"][0]
    assert source["record_index"] == 2
    assert source["citation_index"] == 2
    assert source["chart_record_index"] == 28
    assert source["resource_type"] == "drug_order"
    assert source["resolution_status"] == "resolved"
    assert source["title"].startswith("Drug order: Trimethoprim")
    assert source["source_text"].startswith("(2026-01-07) Drug order: Trimethoprim")
    assert source_ref_labels(sources) == {2: "S1"}

    judge_text = render_sources_for_judge(sources)
    assert "cite [2] chart [28]" in judge_text
    assert "hub grounding: unchecked" in judge_text


def test_source_tile_falls_back_to_chart_index_when_no_uuid_mapping_exists():
    chart = {
        "chart_snapshot": "[7] (2026-01-07) Finding -- Weight: 41 kg",
        "mappings": [
            {
                "index": 7,
                "resourceType": "obs",
                "resourceUuid": "obs-7",
                "date": 1767744000000,
            }
        ],
        "valid_uuids": ["obs-7"],
    }
    response = {
        "answer": "Weight was 41 kg [7].",
        "references": [
            {
                "index": 7,
                "resourceType": "obs",
                "resourceUuid": "obs-7",
                "date": "2026-01-07",
            }
        ],
    }

    source = build_sources(response, chart)["sources"][0]

    assert source["citation_index"] == 7
    assert source["chart_record_index"] == 7
    assert source["title"] == "Finding -- Weight: 41 kg"


def test_source_tiles_preserve_final_grounding_verdicts_and_legacy_default():
    response = {
        "answer": "Grounding examples [7][8][9][10][11][12][13][14].",
        "references": [
            {"index": 7, "groundingStatus": "verified", "grounded": False},
            {"index": 8, "groundingStatus": "unsupported", "grounded": True},
            {"index": 9, "groundingStatus": "checking", "grounded": True},
            {"index": 10, "groundingStatus": "mixed", "grounded": False},
            {"index": 11, "grounded": True},
            {"index": 12, "grounded": False},
            {"index": 13, "groundingStatus": "unchecked", "grounded": True},
            {"index": 14},
        ],
    }

    sources = build_sources(response, None)["sources"]

    assert {source["record_index"]: source["support_status"] for source in sources} == {
        7: "verified",
        8: "unsupported",
        9: "checking",
        10: "mixed",
        11: "verified",
        12: "unsupported",
        13: "unchecked",
        14: "unchecked",
    }
