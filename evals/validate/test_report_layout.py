"""Browser layout regression test for the validation report (real Chromium via Playwright).

CSS layout (page width + per-question tile-strip scroll) has no jsdom-testable contract, so
this loads the rendered report.html in a real browser, measures it, and captures a screenshot.

Regression guarded: the report is a WIDE comparison grid (one tile per backend). It must use
the available viewport width so every backend tile shows on a wide screen — a fixed narrow
``max-width`` cap leaves the right-most backends (e.g. the GGUF arm) pushed into horizontal
scroll/off-screen instead of shown — while the per-question strip still scrolls when the
viewport is genuinely narrow.
"""
import json
from pathlib import Path

import pytest

from harness.validate.report import build_report


def _write_many_backend_run(run_dir: Path, backends, turns: int = 1) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(json.dumps({
        "run_id": "r1", "component": "validate", "git_sha": "abc123",
        "dataset_id": "demo", "otel": {"gen_ai.provider.name": "lmstudio"},
        "generated_at": "2026-06-03",
    }), encoding="utf-8")
    (run_dir / "events.jsonl").write_text("".join(
        json.dumps({"event_type": "backend_selected", "backend_id": b,
                    "modelName": b, "label": f"{b} (a fairly descriptive backend label)"}) + "\n"
        for b in backends), encoding="utf-8")
    answer = ("The patient's vital signs including blood pressure, pulse, temperature, weight "
              "and oxygen saturation were recorded across multiple visits [1].")
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for b in backends:
            for t in range(1, turns + 1):
                f.write(json.dumps({
                    "run_id": "r1", "scenario_id": "single-vitals-summary", "backend_id": b,
                    "turn": t, "request": {"question": "Summarize this patient's vital signs."},
                    "response": {"answer": answer,
                                 "references": [{"index": 1, "resourceType": "Observation"}]},
                    "metrics": {"latency_ms": 10, "http_status": 200, "json_valid": True,
                                "citation_count": 1, "first_turn": t == 1},
                }) + "\n")


def test_report_extends_to_full_width_with_scrollable_bands(tmp_path):
    """RED before the fix: ``main`` is capped at ``max-width: 1500px``, so on a 2400px
    viewport the content is still ~1500px and the right-most backend tiles (incl. the GGUF
    arm) are pushed into scroll instead of shown. GREEN: ``main`` uses the full width, while
    the per-question strip still scrolls on a narrow (1000px) viewport."""
    sync_api = pytest.importorskip("playwright.sync_api")
    backends = [f"backend-{i:02d}" for i in range(6)]
    run_dir = tmp_path / "run"
    _write_many_backend_run(run_dir, backends)
    uri = build_report(run_dir).resolve().as_uri()

    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            wide = browser.new_page(viewport={"width": 2400, "height": 1000})
            wide.goto(uri)
            wide.wait_for_selector("main")
            main_width = wide.evaluate("document.querySelector('main').clientWidth")
            wide.screenshot(path=str(tmp_path / "wide.png"), full_page=True)

            narrow = browser.new_page(viewport={"width": 1000, "height": 900})
            narrow.goto(uri)
            narrow.wait_for_selector(".tiles")
            band_scrolls = narrow.evaluate(
                "[...document.querySelectorAll('.tiles')].some(t => t.scrollWidth > t.clientWidth + 2)")
        finally:
            browser.close()

    print(f"\n[layout] main_width@2400px={main_width}  band_scrolls@1000px={band_scrolls}")
    assert main_width > 1800, (
        f"report content is only {main_width}px wide on a 2400px viewport — it's capped, so the "
        "right-most backends (incl. the GGUF arm) get pushed into scroll instead of shown")
    assert band_scrolls, (
        "the per-question tile strip should still scroll horizontally on a narrow viewport")
