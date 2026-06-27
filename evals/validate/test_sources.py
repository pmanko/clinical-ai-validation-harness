from harness.validate.sources import (
    audit_sources,
    build_sources,
    parse_snapshot_records,
    render_sources_for_judge,
)


def _chart():
    return {
        "valid_uuids": ["u1", "u2"],
        "chart_snapshot": (
            "Patient: Test\n"
            "[1] (2026-01-26) Finding — Weight (kg): 71.0 kg\n"
            "[2] (2026-01-07) Drug order: Efavirenz. Action: NEW\n"
        ),
        "mappings": [
            {"index": 1, "resourceType": "obs", "resourceUuid": "u1", "date": 1769385600000},
            {"index": 2, "resourceType": "order", "resourceUuid": "u2", "date": 1767744000000},
        ],
    }


def test_parse_snapshot_records_extracts_title_and_date():
    records = parse_snapshot_records(_chart()["chart_snapshot"])
    assert records[1]["date"] == "2026-01-26"
    assert records[1]["title"] == "Finding — Weight (kg): 71.0 kg"


def test_build_sources_from_top_level_references_only():
    response = {
        "answer": "The latest weight is 71 kg [1].",
        "references": [{"index": 1, "resourceType": "obs", "resourceUuid": "u1"}],
        "blocks": [],
    }
    sources = build_sources(response, _chart())
    assert sources["schema_version"] == "sources.v1"
    assert sources["sources"][0]["source_id"] == "S1"
    assert sources["sources"][0]["record_index"] == 1
    assert sources["sources"][0]["resolution_status"] == "resolved"
    assert sources["diagnostics"]["top_level_refs"] == [1]
    assert sources["diagnostics"]["answer_inline_refs"] == [1]


def test_build_sources_from_nested_table_refs_and_dedupes_repeated_cells():
    response = {
        "answer": "Orders are listed in the table.",
        "references": [],
        "blocks": [{
            "kind": "table",
            "title": "Orders",
            "columns": [{"key": "drug", "label": "Drug"}, {"key": "date", "label": "Date"}],
            "rows": [{"cells": {
                "drug": {"text": "Efavirenz", "refs": [2]},
                "date": {"text": "2026-01-07", "refs": [2]},
            }}],
        }],
    }
    sources = build_sources(response, _chart())
    assert [s["record_index"] for s in sources["sources"]] == [2]
    assert sources["sources"][0]["facts_used"] == ["Drug: Efavirenz", "Date: 2026-01-07"]
    assert sources["diagnostics"]["nested_refs"] == [2, 2]
    assert sources["diagnostics"]["unique_nested_refs"] == [2]
    assert sources["diagnostics"]["duplicated_nested_refs"] == [2]
    assert sources["diagnostics"]["nested_only_refs"] == [2]


def test_build_sources_records_mismatches_malformed_tokens_and_rows_without_refs():
    response = {
        "answer": "Weight was 71 kg [1] and malformed [٣٦] plus broken [2>.",
        "references": [{"index": 1, "resourceUuid": "u1"}, {"index": 2, "resourceUuid": "u2"}],
        "blocks": [{
            "kind": "table",
            "title": "Uncited rows",
            "columns": [{"key": "value", "label": "Value"}],
            "rows": [{"cells": {"value": {"text": "No source here", "refs": []}}}],
        }],
    }
    sources = build_sources(response, _chart())
    assert sources["diagnostics"]["unused_top_refs"] == [2]
    assert "[٣٦]" in sources["diagnostics"]["malformed_tokens"]
    assert "[2>" in sources["diagnostics"]["malformed_tokens"]
    assert sources["diagnostics"]["rows_without_refs"][0]["block"] == "Uncited rows"


def test_build_sources_handles_missing_chart_fixture_without_crashing():
    response = {"answer": "Known [9].", "citations": [9], "blocks": []}
    sources = build_sources(response, None)
    assert sources["sources"][0]["record_index"] == 9
    assert sources["sources"][0]["resolution_status"] == "unknown"


def test_render_sources_for_judge_uses_canonical_sources_and_diagnostics():
    response = {"answer": "Orders are listed.", "citations": [2], "blocks": []}
    text = render_sources_for_judge(build_sources(response, _chart()))
    assert "[Evidence Used]" in text
    assert "S1 = [2]" in text
    assert "Drug order: Efavirenz" in text


def test_audit_sources_returns_diagnostics_for_new_and_legacy_sources():
    response = {
        "answer": "Orders are listed.",
        "references": [{"index": 1, "resourceUuid": "u1"}],
        "blocks": [{
            "kind": "table",
            "title": "Orders",
            "columns": [{"key": "drug", "label": "Drug"}],
            "rows": [{"cells": {"drug": {"text": "Efavirenz", "refs": [2, 2]}}}],
        }],
    }
    sources = build_sources(response, _chart())
    assert audit_sources(response, sources)["duplicated_nested_refs"] == [2]

    legacy_sources = {"schema_version": "sources.v1", "sources": sources["sources"]}
    diagnostics = audit_sources(response, legacy_sources)
    assert diagnostics["top_level_refs"] == [1]
    assert diagnostics["nested_only_refs"] == [2]
    assert diagnostics["duplicated_nested_refs"] == [2]
