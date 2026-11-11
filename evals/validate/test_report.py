import json
import re
from pathlib import Path

from evals.validate._test_shell import render_cell_via_js, render_report_for_test
from harness.validate.report import build_multi_report, build_report

_DEGRADED_ANSWER = "I could not produce a complete answer for this turn. Please try again."


def _write_run(run_dir: Path, results):
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "r1", "component": "validate", "git_sha": "abc123",
            "dataset_id": "demo", "otel": {"gen_ai.provider.name": "lmstudio"},
            "generated_at": "2026-05-30",
        }),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team",
                    "modelName": "med-agent-team"}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "gemma-local",
                      "modelName": "gemma-4-e2b-it"}) + "\n",
        encoding="utf-8",
    )
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


def _result(backend, answer, refs, **metrics):
    base = {"latency_ms": 10, "http_status": 200, "json_valid": True,
            "citation_count": len(refs), "references_empty": not refs, "first_turn": True}
    base.update(metrics)
    return {"run_id": "r1", "scenario_id": "s", "backend_id": backend, "turn": 1,
            "request": {"question": "q"}, "response": {"answer": answer, "references": refs},
            "metrics": base}


def test_report_flags_the_degraded_fallback_envelope(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", _DEGRADED_ANSWER, []),
        _result("gemma-local", "Lisinopril 10 mg [1]",
                [{"index": 1, "resourceType": "MedicationRequest"}]),
    ])

    data_path = build_report(run_dir)
    run = json.loads(data_path.read_text(encoding="utf-8"))["runs"][0]
    cells = run["scenarios"][0]["turns"][0]["cells"]

    # The fallback envelope is flagged degraded via the precomputed boolean (the JS
    # keys the ⚠ chip on it); the real gemma answer is not. The chip HTML is emitted
    # exactly once across the run.
    assert cells["med-agent-team"]["degraded"] is True
    assert cells["gemma-local"]["degraded"] is False
    team_chips = render_cell_via_js(cells["med-agent-team"], run)["chips_html"]
    gemma_chips = render_cell_via_js(cells["gemma-local"], run)["chips_html"]
    assert "⚠ degraded" in team_chips
    assert "⚠ degraded" not in gemma_chips


def test_report_has_pdf_button_print_styles_and_feedback_seam(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [_result("gemma-local", "Lisinopril 10 mg [1]",
                                  [{"index": 1, "resourceType": "MedicationRequest"}])])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")
    assert "id='print-pdf'" in html            # the PDF button
    assert "window.print()" in html            # wired to browser print/save-as-PDF
    assert "@media print" in html              # print stylesheet
    assert "id='theme-toggle'" in html         # theme toggle remains accessible


def test_report_renders_markdown_answer_headings_as_html(tmp_path):
    bold_answer = "**Answer**\nHer regimen is no longer first-line [4].\n\n**In Depth**\nThe chart lists a stavudine-based regimen [4]."
    atx_answer = "## In Depth\nGuidance per WHO HIV.\n\nMore detail here."
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", bold_answer,
                [{"index": 4, "resourceType": "MedicationRequest"}]),
        _result("gemma-local", atx_answer, []),
    ])

    run = json.loads(build_report(run_dir).read_text(encoding="utf-8"))["runs"][0]
    cells = run["scenarios"][0]["turns"][0]["cells"]
    team = render_cell_via_js(cells["med-agent-team"], run)["answer_html"]
    gemma = render_cell_via_js(cells["gemma-local"], run)["answer_html"]

    assert "**In Depth**" not in team
    assert "The chart lists a stavudine-based regimen [4]." in team
    assert "<strong>Answer</strong>" in team
    assert "**In Depth**" not in team
    assert "**Answer**" not in team
    assert "<h3>In Depth</h3>" in gemma
    assert "## In Depth" not in gemma


def test_report_normalizes_literal_backslash_n_in_answer(tmp_path):
    answer = "**Answer**\\nbottom line [4].\\n\\n**In Depth**\\nstavudine regimen [4]."
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", answer,
                [{"index": 4, "resourceType": "MedicationRequest"}]),
    ])

    run = json.loads(build_report(run_dir).read_text(encoding="utf-8"))["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    ans = render_cell_via_js(cell, run)["answer_html"]
    assert "**In Depth**" not in ans
    assert "stavudine regimen [4]." in ans
    assert "\\n" not in ans


# The real medications-table block the bridge returns (copied from an actual run:
# artifacts/validate/21b42fd5-.../results.jsonl). A fixture simpler than reality
# would pass green while real nested cells/refs break, so keep the full shape.
_MED_BLOCK = {
    "kind": "table",
    "title": "Medications Ordered",
    "columns": [
        {"key": "medication", "label": "Medication"},
        {"key": "action", "label": "Action"},
        {"key": "urgency", "label": "Urgency"},
    ],
    "rows": [
        {"cells": {
            "medication": {"text": "Lamivudine", "refs": [29, 62, 117]},
            "action": {"text": "NEW", "refs": [29, 62]},
            "urgency": {"text": "ROUTINE", "refs": [29]},
        }},
        {"cells": {
            "medication": {"text": "Nevirapine", "refs": [30, 63]},
            "action": {"text": "NEW", "refs": [30]},
            "urgency": {"text": "ROUTINE", "refs": [30]},
        }},
    ],
}


def test_report_renders_blocks_table_with_cells_and_row_sources(tmp_path):
    run_dir = tmp_path / "run"
    r = _result("med-agent-team", "See medications table.",
                [{"index": 29, "resourceType": "MedicationRequest"}])
    r["response"]["blocks"] = [_MED_BLOCK]
    _write_run(run_dir, [r])

    run = json.loads(build_report(run_dir).read_text(encoding="utf-8"))["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    blocks = render_cell_via_js(cell, run)["blocks_html"]

    assert "Medications Ordered" in blocks
    assert ">Medication</th>" in blocks
    assert ">Action</th>" in blocks
    assert "Lamivudine" in blocks
    assert "Nevirapine" in blocks
    assert "<span class='ref'>[29]</span>" not in blocks
    assert "row-sources" in blocks
    assert "sources" in blocks


def test_report_renders_evidence_tiles_and_keeps_raw_refs_debug_only(tmp_path):
    run_dir = tmp_path / "run"
    r = _result("med-agent-team", "See medications table.",
                [{"index": 29, "resourceType": "MedicationRequest"}])
    r["response"]["blocks"] = [_MED_BLOCK]
    _write_run(run_dir, [r])

    run = json.loads(build_report(run_dir).read_text(encoding="utf-8"))["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    rendered = render_cell_via_js(cell, run)

    assert cell["source_card_refs"]
    assert "Evidence Used" in rendered["sources_html"]
    assert "source-card" in rendered["sources_html"]
    assert "raw resolved refs" in rendered["refs_html"]


def test_report_uses_final_grounding_verdict_and_data_derived_review_scope(tmp_path):
    run_dir = tmp_path / "run"
    r = _result(
        "med-agent-team",
        "The latest weight is 71 kg [29]; another claim is unsupported [30].",
        [
            {"index": 29, "resourceType": "obs", "groundingStatus": "verified", "grounded": True},
            {"index": 30, "resourceType": "obs", "groundingStatus": "unsupported", "grounded": False},
        ],
    )
    _write_run(run_dir, [r])

    data_path = build_report(run_dir)
    run = json.loads(data_path.read_text(encoding="utf-8"))["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    rendered = render_cell_via_js(cell, run)
    html = render_report_for_test(data_path).read_text(encoding="utf-8")

    pool = run.get("source_card_pool") or []
    supports = {
        ref[2]: pool[ref[0]]["support_tone"]
        for ref in cell["source_card_refs"]
    }
    assert supports == {29: "success", 30: "danger"}
    assert "source-status ok" in rendered["sources_html"]
    assert "source-status bad" in rendered["sources_html"]
    assert "not a whole-answer quality verdict" in rendered["sources_html"]
    assert "var patientScope=nPatients===1?'one patient':nPatients+' patients';" in html
    assert "small N, one patient, single judge" not in html


def test_report_escapes_untrusted_text_in_answer_and_blocks(tmp_path):
    block = {
        "kind": "table", "title": "Labs & Vitals",
        "columns": [{"key": "name", "label": "Test"}],
        "rows": [{"cells": {"name": {"text": "CD4 <script>x</script> & co", "refs": [7]}}}],
    }
    run_dir = tmp_path / "run"
    r = _result("med-agent-team", "Result is 5 < 10 & rising <b>now</b>.", [])
    r["response"]["blocks"] = [block]
    _write_run(run_dir, [r])

    run = json.loads(build_report(run_dir).read_text(encoding="utf-8"))["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    rendered = render_cell_via_js(cell, run)
    answer, blocks = rendered["answer_html"], rendered["blocks_html"]

    assert "<script>x</script>" not in answer and "<script>x</script>" not in blocks
    assert "<b>now</b>" not in answer
    assert "&lt;script&gt;x&lt;/script&gt;" in blocks
    assert "&lt;b&gt;now&lt;/b&gt;" in answer
    assert "&amp;" in answer
    assert "Labs &amp; Vitals" in blocks


def test_report_omits_citation_zero_abstention_proxy(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "Stavudine is no longer first-line per WHO guidance.", []),
    ])

    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "no refs" not in html        # the '∅ no refs' chip is gone
    assert "∅" not in html
    assert "no-refs turns" not in html  # the summary column is gone


def test_report_labels_citation_count_as_chart_refs_not_grounding(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("gemma-local", "Lisinopril [1]", [{"index": 1, "resourceType": "MedicationRequest"}]),
    ])

    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "chart refs" in html           # relabeled chip + summary header
    assert "cites " not in html           # old misleading chip label gone
    assert "total citations" not in html  # old summary header gone


def test_report_surfaces_backend_config_label(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team-c", "ans c", []),
        _result("med-agent-team-d", "ans d", []),
    ])
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team-c",
                    "modelName": "med-agent-team",
                    "label": "v2 prompt | orch=gemma-4-31b | expert=medgemma-1.5-4b"}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team-d",
                      "modelName": "med-agent-team",
                      "label": "v2 prompt | orch=gemma-4-31b | expert=medgemma-27b"}) + "\n",
        encoding="utf-8",
    )

    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "orch=gemma-4-31b | expert=medgemma-1.5-4b" in html
    assert "orch=gemma-4-31b | expert=medgemma-27b" in html


def test_report_embeds_multiple_runs_with_run_selector(tmp_path):
    a = tmp_path / "runA"
    b = tmp_path / "runB"
    _write_run(a, [_result("gemma-local", "answer a", [])])
    _write_run(b, [_result("gemma-local", "answer b", [])])
    manifest_b = json.loads((b / "run_manifest.json").read_text(encoding="utf-8"))
    manifest_b["run_id"] = "r2"
    (b / "run_manifest.json").write_text(json.dumps(manifest_b), encoding="utf-8")

    data_path = build_multi_report([a, b], tmp_path / "multi-report-data.json")
    html = render_report_for_test(data_path).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    blob = json.loads(body)

    assert len(blob["runs"]) == 2
    assert blob["runs"][0]["run_id"] == "r1"
    assert blob["runs"][1]["run_id"] == "r2"
    assert "<select id='run-select'>" in html


def test_report_topbar_has_data_derived_identity_not_generic_h1(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "ans a", []),
        _result("gemma-local", "ans b", []),
    ])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "<h1>Validation report</h1>" not in html
    assert "id='report-title'" in html
    assert "function buildTitle(" in html
    assert "dataset_id" in html  # already present for run-meta; title reuses it
    assert "id='print-pdf'" in html
    assert "id='theme-toggle'" in html


def test_report_export_actions_live_in_overflow_menu_and_stay_wired(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [_result("gemma-local", "ans", [])])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "id='export-menu'" not in html
    assert "id='print-pdf'" in html
    assert "id='theme-toggle'" in html


def test_report_dense_legends_are_structured_definition_lists(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [_result("gemma-local", "Lisinopril [1]",
                                 [{"index": 1, "resourceType": "MedicationRequest"}])])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "class='legend-key'" in html or 'class="legend-key"' in html
    assert "<dl" in html and "<dt" in html and "<dd" in html
    assert "class='legend-detail'" in html or 'class="legend-detail"' in html
    assert "<summary" in html
    for term in ("accuracy", "completeness", "relevance", "grounding", "harm", "temporal"):
        assert term in html, f"rubric term '{term}' must survive the restructure"
    for term in ("median", "mean", "whisker"):
        assert term in html, f"box-plot term '{term}' must survive the restructure"


def test_report_blob_is_embedding_safe_against_script_breakout(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "before </script><script>alert(1)</script> after", []),
    ])

    data_path = build_report(run_dir)
    html = render_report_for_test(data_path).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    assert "</script>" not in body
    blob = json.loads(body)
    run = blob["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    ans = render_cell_via_js(cell, run)["answer_html"]
    assert "&lt;/script&gt;" in ans


def test_report_run_dropdown_is_a_published_run_switcher_that_degrades(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [_result("gemma-local", "ans", [])])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "../reports-index.json" in html
    assert "function loadRunSwitcher(" in html
    assert "run-switcher" in html
    assert "../' + " in html or "'../'" in html


def test_report_scenario_and_question_filters_are_section_local(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "ans a", []),
        _result("gemma-local", "ans b", []),
    ])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "scenario-filter" in html
    assert "q-search" in html
    assert "function buildAnswersFilters(" in html
    controls = re.search(r"class='controls'>(.*?)</div>\s*<nav", html, re.DOTALL)
    assert controls is not None
    assert "scenario-filter" not in controls.group(1)
    assert "q-search" not in controls.group(1)
    assert "answers-filters" in html


def test_report_splits_heatmap_and_answers_into_two_nav_sections(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "ans a", []),
        _result("gemma-local", "ans b", []),
    ])
    (run_dir / "judge.jsonl").write_text(
        json.dumps({"scenario_id": "s", "backend_id": "gemma-local", "accuracy": 8,
                    "completeness": 7, "relevance": 9, "abstention_outcome": "n-a",
                    "citation_groundedness": "supported", "harm": False, "note": ""}) + "\n",
        encoding="utf-8",
    )
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "'sec-heatmap'" in html
    assert "'sec-answers'" in html
    assert "'Heatmap'" in html
    assert "'Answers'" in html


def test_report_setup_filter_is_a_multiselect_dropdown_not_a_checkbox_list(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "ans a", []),
        _result("gemma-local", "ans b", []),
    ])
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "setup-filter" in html
    assert "Filter setups" in html
    assert "select-all" in html.replace("Select all", "select-all").replace("selectAll", "select-all")
    assert "clear-all" in html.replace("Clear all", "clear-all").replace("clearAll", "clear-all")
    assert "setup-count" in html or "count-badge" in html
    assert "applyBackendToggle" in html


def test_report_renders_executive_summary_results_first_and_tile_judge_pills(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "ans a", []),
        _result("gemma-local", "ans b", []),
    ])
    (run_dir / "judge.jsonl").write_text(
        json.dumps({"scenario_id": "s", "backend_id": "gemma-local", "accuracy": 9,
                    "completeness": 8, "relevance": 9, "abstention_outcome": "n-a",
                    "citation_groundedness": "supported", "harm": False, "note": "Clean chart grounding."}) + "\n",
        encoding="utf-8",
    )
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")

    assert "function renderExecutiveSummary(" in html
    assert "At-a-Glance Setup Leaderboard" in html
    assert "toggle-tile-details" in html
    assert "tile-jscore" in html
    assert "../index.html" in html
    assert html.index("'sec-quality'") < html.index("'sec-arms'")
    assert html.index("'sec-answers'") < html.index("'sec-arms'")


def test_report_embeds_hardware_streaming_latency_and_concurrency_runs(tmp_path):
    run_dir = tmp_path / "run"
    row = _result("gemma-local", "ans b", [])
    row["metrics"]["ttft_ms"] = 1650
    row["metrics"]["answer_done_ms"] = 5500
    row["metrics"]["turn_done_ms"] = 5520
    row["metrics"]["tpot_ms"] = 11.3
    _write_run(run_dir, [row])
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "hardware": {
                    "tier": "gpu_server",
                    "gpu": "Shared 24 GB Cloud GPU Server (24 GB VRAM)",
                    "vram_gb": 24,
                    "serving_engine": "Ollama (gemma4:12b Q4_K_M, 16k–24k context)",
                    "parallel_slots": 4,
                    "concurrency_runs": [
                        {
                            "backend_id": "gemma-local",
                            "n_users": 4,
                            "throughput_turns_per_min": 12.96,
                            "goodput_rate": 0.5,
                            "goodput_turns_per_min": 6.48,
                            "ttft_p50_ms": 4259.0,
                            "turn_1_ttft_p50_ms": 5268.0,
                            "turn_2plus_ttft_p50_ms": 3170.5,
                            "answer_done_p50_ms": 10600.0,
                            "tpot_p50_ms": 7.5,
                            "error_rate": 0.0,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    html = render_report_for_test(build_report(run_dir)).read_text(encoding="utf-8")
    assert "Hardware & serving configuration" in html
    assert "Streaming latency breakdown (TTFT · Answer-Done · Turn-Done · TPOT)" in html
    assert "Multi-clinician session concurrency (N=1, 2, 4) & SLO goodput" in html
    assert "Shared 24 GB Cloud GPU Server (24 GB VRAM)" in html
    assert "12.96" in html


