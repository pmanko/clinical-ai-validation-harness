"""Tests for the Phase 1 read-only report revamp and clean separation from human adjudication."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from evals.validate._test_shell import (
    render_report_for_test,
    report_shell_css,
    report_shell_js,
)
from harness.validate import report
from harness.validate.adjudicate import adjudication_record


def _write_stage1_fixture(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": "run-revamp-01",
        "component": "chartsearchai",
        "git_sha": "abc1234",
        "dataset_id": "hiv-cohort-v1",
        "provider": "llama.cpp",
        "reference_date": "2026-06-01",
        "backends": ["team-alpha", "single-beta"],
        "patients": {
            "pt-1": {
                "uuid": "pt-1",
                "identifier": "10001X",
                "display": "Test Patient",
                "gender": "F",
                "age": 34,
                "chart_snapshot": (
                    "Patient: Test Patient\n"
                    "[1] (2026-05-01) Viral Load: 40 copies/mL\n"
                    "[2] (2026-05-15) CD4 Count: 520 cells/uL\n"
                ),
                "mappings": [
                    {"index": 1, "resourceType": "obs", "resourceUuid": "uuid-vl-1"},
                    {"index": 2, "resourceType": "obs", "resourceUuid": "uuid-cd4-2"},
                ],
                "valid_uuids": ["uuid-vl-1", "uuid-cd4-2"],
            }
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    results = [
        {
            "run_id": "run-revamp-01",
            "scenario_id": "S1_viral_load",
            "turn": 1,
            "backend_id": "team-alpha",
            "request": {"patient": "pt-1", "question": "What is the latest viral load and CD4 count?"},
            "response": {
                "answer": "Latest viral load is 40 copies/mL [1] and CD4 is 520 cells/uL [2].",
                "references": [
                    {"index": 1, "resourceType": "obs", "resourceUuid": "uuid-vl-1"},
                    {"index": 2, "resourceType": "obs", "resourceUuid": "uuid-cd4-2"},
                ],
                "blocks": [],
                "temporalGate": {"status": "pass", "applied": False},
            },
            "metrics": {"latency_ms": 420, "http_status": 200, "chart_ref_count": 2, "degraded": False},
            "error": None,
        },
        {
            "run_id": "run-revamp-01",
            "scenario_id": "S1_viral_load",
            "turn": 1,
            "backend_id": "single-beta",
            "request": {"patient": "pt-1", "question": "What is the latest viral load and CD4 count?"},
            "response": {
                "answer": "Viral load is undetectable [99].",
                "references": [
                    {"index": 99, "resourceType": "obs", "resourceUuid": "uuid-missing-99"},
                ],
                "blocks": [],
                "temporalGate": {"status": "fail", "applied": True, "action": "patched"},
                "answerValidation": {"status": "needs_review", "originalAnswer": "Old draft [99]."},
            },
            "metrics": {"latency_ms": 810, "http_status": 200, "chart_ref_count": 1, "degraded": True},
            "error": None,
        },
    ]
    (run_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in results) + "\n", encoding="utf-8"
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "comparison_set": "revamp-test"}) + "\n",
        encoding="utf-8",
    )


def _write_stage2_judge_fixture(run_dir: Path) -> None:
    judge_rows = [
        {
            "run_id": "run-revamp-01",
            "scenario_id": "S1_viral_load",
            "turn": 1,
            "backend_id": "team-alpha",
            "judge_model": "gemini-2.5-pro",
            "accuracy": 9,
            "completeness": 9,
            "relevance": 10,
            "abstention_outcome": "n-a",
            "citation_groundedness": "supported",
            "harm": False,
            "temporal_accuracy": {
                "date_value_mismatch": False,
                "date_fabricated": False,
                "window_overclaimed": False,
                "trend_fabricated": False,
            },
            "citation_resolution": {"n_cited": 2, "n_resolved": 2, "n_unresolved": 0},
            "note": "Accurate and complete summary of both labs.",
        },
        {
            "run_id": "run-revamp-01",
            "scenario_id": "S1_viral_load",
            "turn": 1,
            "backend_id": "single-beta",
            "judge_model": "gemini-2.5-pro",
            "accuracy": 3,
            "completeness": 2,
            "relevance": 6,
            "abstention_outcome": "n-a",
            "citation_groundedness": "unsupported",
            "harm": True,
            "critical_omission": True,
            "temporal_accuracy": {
                "date_value_mismatch": True,
                "date_fabricated": False,
                "window_overclaimed": False,
                "trend_fabricated": False,
            },
            "citation_resolution": {"n_cited": 1, "n_resolved": 0, "n_unresolved": 1},
            "note": "Omitted CD4 count and cited non-existent record [99].",
        },
    ]
    (run_dir / "judge.jsonl").write_text(
        "\n".join(json.dumps(r) for r in judge_rows) + "\n", encoding="utf-8"
    )

    # Multi-actor judge directories
    actor1 = run_dir / "judges" / "gemini-2.5-pro"
    actor2 = run_dir / "judges" / "claude-sonnet-4"
    actor1.mkdir(parents=True, exist_ok=True)
    actor2.mkdir(parents=True, exist_ok=True)
    (actor1 / "judge.jsonl").write_text(
        "\n".join(json.dumps(r) for r in judge_rows) + "\n", encoding="utf-8"
    )
    actor2_rows = [
        {**judge_rows[0], "judge_model": "claude-sonnet-4", "accuracy": 10, "completeness": 9, "note": "Spot on."},
        {**judge_rows[1], "judge_model": "claude-sonnet-4", "accuracy": 2, "completeness": 2, "note": "Hallucinated ref."},
    ]
    (actor2 / "judge.jsonl").write_text(
        "\n".join(json.dumps(r) for r in actor2_rows) + "\n", encoding="utf-8"
    )


def _write_stage3_adjudication_fixture(run_dir: Path) -> None:
    rows = [
        adjudication_record(
            scenario_id="S1_viral_load",
            backend_id="team-alpha",
            reviewer_id="dr.okafor@clinic.org",
            reviewer_tier="clinical",
            accuracy=10,
            completeness=10,
            relevance=10,
            harm=False,
            abstention_outcome="n-a",
            citation_groundedness="supported",
            note="Clinically accurate and well-grounded.",
        ),
        adjudication_record(
            scenario_id="S1_viral_load",
            backend_id="single-beta",
            reviewer_id="dr.okafor@clinic.org",
            reviewer_tier="clinical",
            accuracy=2,
            completeness=2,
            relevance=5,
            harm=True,
            critical_omission=True,
            abstention_outcome="n-a",
            citation_groundedness="unsupported",
            note="Unsafe omission of CD4 + fabricated citation.",
        ),
    ]
    (run_dir / "adjudication.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def test_report_removes_embedded_adjudication_forms_and_drag_ranking(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_stage1_fixture(run_dir)
    _write_stage2_judge_fixture(run_dir)
    _write_stage3_adjudication_fixture(run_dir)

    out = report.build_report(run_dir)
    html = render_report_for_test(out).read_text(encoding="utf-8")

    # Verify all legacy interactive adjudication & drag-to-rank widgets are gone
    for forbidden in (
        "rubric-template",
        "cell-form",
        "collectFeedback",
        "exportRankings",
        "feedback.jsonl",
        "rankings.json",
        "export-menu",
        "user-select: none",
        "cursor: grab",
        "rank-badge",
    ):
        assert forbidden not in html, f"Expected {forbidden!r} to be removed from report.html"

    # Verify the new 3-layer verification sections and read-only tile evaluation footers exist
    for expected in (
        "vtiers-banner",
        "sec-deterministic",
        "sec-quality",
        "sec-adjudication",
        "tile-eval-footer",
        "tile-eval-pills",
        "tile-eval-drawer",
        "verdict-filter",
    ):
        assert expected in html, f"Expected {expected!r} in report.html"


def test_run_blob_enriches_deterministic_judge_and_human_layers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_stage1_fixture(run_dir)
    _write_stage2_judge_fixture(run_dir)
    _write_stage3_adjudication_fixture(run_dir)

    blob = report._run_blob(run_dir)

    # Layer 1: Deterministic summary counts
    by_backend = {row["backend_id"]: row for row in blob["summary"]}
    assert by_backend["team-alpha"]["valid_turns"] == 1
    assert by_backend["team-alpha"]["resolved_chart_refs"] == 2
    assert by_backend["team-alpha"]["unresolved_chart_refs"] == 0
    assert by_backend["team-alpha"]["temporal_gate_pass"] == 1

    assert by_backend["single-beta"]["valid_turns"] == 1
    assert by_backend["single-beta"]["resolved_chart_refs"] == 0
    assert by_backend["single-beta"]["unresolved_chart_refs"] == 1
    assert by_backend["single-beta"]["temporal_gate_fail"] == 1
    assert by_backend["single-beta"]["temporal_gate_applied"] == 1
    assert by_backend["single-beta"]["answer_check_flagged"] == 1

    # Layer 2: Enriched judge rows + multi-actor cells
    j_by_arm = {row["backend_id"]: row for row in blob["judge_rows"]}
    assert j_by_arm["team-alpha"]["benchmark_score"] == 92.0
    assert j_by_arm["team-alpha"]["safety_adjusted_benchmark_score"] == 91.8
    assert j_by_arm["team-alpha"]["critical_omission"] is False
    assert j_by_arm["team-alpha"]["severe_harm"] is False

    assert j_by_arm["single-beta"]["critical_omission"] is True
    assert j_by_arm["single-beta"]["severe_harm"] is True
    assert j_by_arm["single-beta"]["safety_adjusted_benchmark_score"] == 0.0

    actor_cells = blob["judge_actor_cells"]["S1_viral_load|team-alpha"]
    assert len(actor_cells) == 2
    assert {c["actor"] for c in actor_cells} == {"gemini-2.5-pro", "claude-sonnet-4"}

    # Layer 3: Enriched human adjudication rows + PPI calibrated summary
    a_by_arm = {row["backend_id"]: row for row in blob["adjudication_rows"]}
    assert a_by_arm["team-alpha"]["human_benchmark_score"] == 100.0
    assert a_by_arm["team-alpha"]["reviewer_tier"] == "clinical"
    assert a_by_arm["single-beta"]["human_benchmark_score"] < 40.0
    assert a_by_arm["single-beta"]["critical_omission"] is True

    cal_by_arm = {row["backend"]: row["calibrated"] for row in blob["calibrated"]}
    assert cal_by_arm["__run__"]["adjudicated"] is True
    assert cal_by_arm["__run__"]["tier"] == "clinical"
    assert cal_by_arm["__run__"]["n_labeled"] == 2


def test_report_script_passes_node_syntax_check(tmp_path: Path) -> None:
    if not shutil.which("node"):
        return
    js_file = tmp_path / "report_script.js"
    js_file.write_text(report_shell_js(), encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(js_file)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def test_build_report_emits_standalone_report_data_json_and_external_shell(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_stage1_fixture(run_dir)
    _write_stage2_judge_fixture(run_dir)
    _write_stage3_adjudication_fixture(run_dir)

    out = report.build_report(
        run_dir,
        deduplicate=True,
        write_data_json=True,
    )
    data_path = run_dir / "report-data.json"
    assert out == data_path
    assert data_path.is_file()
    assert (run_dir / "run-summary.json").is_file()
    assert (run_dir / "dashboard-data.json").is_file()
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "openclinai.report.v2"
    assert payload["schema_version"] == 2
    run0 = payload["runs"][0]
    assert "source_card_pool" in run0


def test_enrich_and_deduplicate_run_edge_cases() -> None:
    from harness.validate.report_data import enrich_and_deduplicate_run

    src_item = {
        "source_id": "S1",
        "citation_index": 1,
        "chart_record_index": 10,
        "title": "Labs",
        "resource_type": "obs",
        "date": "2026-05-01",
        "sections": ["answer"],
        "record_label": "resolved",
        "record_tone": "success",
        "support_label": "supported",
        "support_tone": "success",
        "facts_used": ["Labs"],
        "source_text": "Labs",
    }
    run_obj = {
        "backends": ["b1"],
        "scenarios": [
            {
                "id": "sc1",
                "turns": [
                    {
                        "cells": {
                            "b1": {
                                "http_status": 200,
                                "sources": {
                                    "sources": [src_item],
                                    "diagnostics": {"top_level_refs": [1], "unresolved_refs": []},
                                },
                                "indepth_view": {"status": "not_in_profile", "extra": 1},
                            },
                            "skip": "not-a-dict",
                        }
                    },
                    {"cells": {"b1": {"http_status": 200}}},
                ],
            }
        ],
        "summary": [{"backend_id": "b1", "turns": 2, "errors": 0}],
        "judge": [{"backend": "b1"}],
        "judge_rows": [{"scenario_id": "sc1", "backend_id": "b1", "accuracy": 8, "completeness": 8, "relevance": 8}],
        "judge_passes": {"only_one": [{"scenario_id": "sc1", "backend_id": "b1"}]},
    }
    total_cells, pool_len = enrich_and_deduplicate_run(run_obj, pool_threshold=10, force_pool=False)
    assert total_cells == 3
    assert pool_len == 0

    total_cells, pool_len = enrich_and_deduplicate_run(run_obj, force_pool=True)
    assert pool_len == 1
    assert run_obj["judge_passes"] == {}
    assert run_obj["summary"][0]["valid_turns"] == 2
    assert run_obj["judge"][0]["benchmark_score"] is not None
    assert run_obj["calibrated"]


def test_report_shell_includes_viewport_catalog_meta_and_overflow_guards(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_stage1_fixture(run_dir)
    _write_stage2_judge_fixture(run_dir)
    out = report.build_report(run_dir)
    html = render_report_for_test(out).read_text(encoding="utf-8")
    assert "<meta name='viewport' content='width=device-width, initial-scale=1'>" in html

    css = report_shell_css()
    js = report_shell_js()
    assert ".ov-diff-sc > .ov-score-num" in css
    assert "overflow-x: clip" in css
    assert "@media (max-width: 720px)" in css
    assert "ov-study-brief" in css
    assert "compactArmLabel" in js
    assert "What We Tested" in js
    assert "Key Takeaway" in js


def test_build_report_loads_domain_guardrails_and_family_from_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_guardrails"
    _write_stage1_fixture(run_dir)
    _write_stage2_judge_fixture(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["family"] = "wahs"
    manifest["evaluation_modality"] = "live_model_and_team_eval"
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "domain_guardrails.json").write_text(
        json.dumps(
            [
                {
                    "id": "privacy_external_share_engine",
                    "label": "42 CFR Part 2 & WA MHMDA External-Share Privacy Gate",
                    "scope": "WAHS Engine / Hub setups",
                    "passed": 36,
                    "total": 36,
                    "pass_rate": 1.0,
                    "ci95_low": 0.9036,
                    "ci95_high": 1.0,
                    "status": "pass",
                    "detail": "0/36 external_share responses leaked protected records",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = report.build_report(run_dir)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["family"] == "wahs"
    assert payload["runs"][0]["family"] == "wahs"
    assert payload["runs"][0]["evaluation_modality"] == "live_model_and_team_eval"
    assert payload["runs"][0]["domain_guardrails"][0]["id"] == "privacy_external_share_engine"
    summary_payload = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
    assert summary_payload["family"] == "wahs"
    assert summary_payload["domain_guardrails"][0]["passed"] == 36
    assert len(summary_payload["scout"]) == 2



