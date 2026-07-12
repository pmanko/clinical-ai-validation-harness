from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from harness.validate import report


def _write_timed_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "timed",
                "component": "validate",
                "git_sha": "abc",
                "dataset_id": "test",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "otel": {"gen_ai.provider.name": "med-agent-hub"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "backend_selected",
                "backend_id": "team",
                "label": "Checked medical team",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "results.jsonl").write_text(
        json.dumps(
            {
                "run_id": "timed",
                "scenario_id": "am-weight-trend",
                "backend_id": "team",
                "turn": 1,
                "request": {"patient": "p", "question": "What changed?"},
                "response": {"answer": "Weight changed [1].", "references": [], "blocks": []},
                "metrics": {
                    "latency_ms": 170,
                    "http_status": 200,
                    "json_valid": True,
                    "citation_count": 1,
                    "answer_chars": 19,
                    "first_turn": True,
                },
                "started_at": "2026-07-12T00:00:00+00:00",
                "ended_at": "2026-07-12T00:00:01+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _timing_trace() -> dict:
    return {
        "level_id": "team",
        "ts": "2026-07-12T00:00:00.500000+00:00",
        "answer_text": "Weight changed [1].",
        "steps": [
            {
                "role": "stage_timing",
                "stage": "context",
                "occurrence": 1,
                "duration_ms": 10,
                "status": "completed",
            },
            {
                "role": "stage_timing",
                "stage": "answer",
                "occurrence": 1,
                "duration_ms": 100,
                "status": "completed",
            },
            {
                "role": "stage_timing",
                "stage": "gate",
                "occurrence": 1,
                "duration_ms": 20,
                "status": "failed",
            },
            {
                "role": "stage_timing",
                "stage": "indepth",
                "occurrence": 1,
                "duration_ms": 40,
                "status": "cancelled",
            },
        ],
    }


def test_static_report_renders_stage_status_and_missing_coverage(tmp_path, monkeypatch):
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_timed_run(run_dir)
    trace = _timing_trace()
    monkeypatch.setattr(report, "load_traces", lambda _path: [trace])
    monkeypatch.setattr(report, "arm_model_name", lambda _backend: "team")
    monkeypatch.setattr(
        report,
        "arm_card",
        lambda _backend: {
            "backend_id": "team",
            "title": "Gemma coord · MedGemma expert · Qwen writer",
            "short_title": "Medical team",
            "label": "Checked medical team",
            "kind": "team",
            "stages": ["context", "answer", "gate", "review", "indepth"],
            "models": [],
            "roles": {},
            "config": {},
        },
    )
    uri = report.build_report(run_dir).resolve().as_uri()

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(uri)
            page.wait_for_selector(".summary-section")
            text = page.text_content(".summary-section") or ""
            detail = page.text_content(".stage-timings") or ""
        finally:
            browser.close()

    assert "Average latency by stage" in text
    assert "Gemma coord · MedGemma expert · Qwen writer" in text
    assert "1 failed @ 20 ms" in text
    assert "1 cancelled @ 40 ms" in text
    assert "review" in text and "0/1" in text
    assert "context" in detail and "completed" in detail
    assert "gate" in detail and "failed" in detail
    assert "indepth" in detail and "cancelled" in detail


def test_frozen_dashboard_renders_stage_timing_detail(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    script = Path(__file__).resolve().parents[2] / "scripts/validate-dashboard.py"
    spec = importlib.util.spec_from_file_location("validate_dashboard_test", script)
    assert spec and spec.loader
    dashboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard)
    dashboard.status = lambda: {
        "run": "timed",
        "set": "test",
        "done": 1,
        "total": 1,
        "scenarios": ["s1"],
        "backends": ["team"],
        "arms": {"team": {}},
        "arm_cards": {
            "team": {
                "title": "Gemma coord · MedGemma expert · Qwen writer",
                "kind": "team",
                "roles": {},
                "config": {},
            }
        },
        "judge_actors": [],
        "judge_combined": [],
        "grid": [{"scenario": "s1", "backend": "team", "state": "done"}],
        "feed": [],
        "models": [],
    }
    dashboard.detail = lambda _scenario, _backend: {
        "expectations": {},
        "turns": [
            {
                "turn": 1,
                "question": "What changed?",
                "status": 200,
                "latency_ms": 170,
                "chars": 19,
                "citations": 1,
                "answer": "Weight changed.",
                "blocks": [],
                "sources": {},
                "refs": [],
                "error": None,
                "trace": {
                    "answer_text": "Weight changed.",
                    "answer_confidence": {"level": "green", "note": ""},
                    "indepth_confidence": {"level": "green", "note": ""},
                    "steps": [],
                    "stage_timings": _timing_trace()["steps"],
                    "models": {},
                },
            }
        ],
    }
    frozen = tmp_path / "dashboard.html"
    dashboard.freeze(frozen)

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(frozen.resolve().as_uri())
            page.wait_for_selector(".grid td.c200")
            page.click(".grid td.c200")
            page.wait_for_selector(".stage-timings")
            text = page.text_content(".stage-timings") or ""
        finally:
            browser.close()

    assert "stage timing breakdown" in text
    assert "context" in text and "completed" in text
    assert "gate" in text and "failed" in text
    assert "indepth" in text and "cancelled" in text
