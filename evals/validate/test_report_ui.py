"""Browser UI-behavior tests for the validation report (real Chromium via Playwright).

These guard the report-UI polish that has no jsdom-testable contract — it's real layout +
interaction in a browser: a genuinely-clickable expand BUTTON (not a text link), larger tile
min-width, click-to-fullscreen, greyed scroll-affordance arrows when tiles overflow, and a
patient-grounding banner that links to the live OpenMRS chart. Each assertion is red against
the pre-polish report and green after.
"""
import json
from pathlib import Path

import pytest

from harness.validate.report import build_report

PATIENT_UUID = "dd75c020-1691-11df-97a5-7038c432aabf"


def _write_run(run_dir: Path, backends, *, with_patient=True, labels=None) -> None:
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": "r1", "component": "validate", "git_sha": "abc123",
        "dataset_id": "core-round", "otel": {"gen_ai.provider.name": "llamacpp"},
        "generated_at": "2026-06-04",
    }
    if with_patient:
        manifest["patients"] = {
            PATIENT_UUID: {
                "display": "Zabella Talai Halambe", "identifier": "2428TU-4",
                "gender": "F", "age": 47, "birthdate": "1978-10-08",
                "medications": ["Lamivudine", "Nevirapine", "Stavudine"],
                "encounter_count": 11, "observation_count": 303,
                "vitals": {"Systolic BP": "110 mmHg", "Pulse": "69 beats/min", "SpO2": "93%"},
            },
        }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "events.jsonl").write_text("".join(
        json.dumps({"event_type": "backend_selected", "backend_id": b,
                    "modelName": b, "label": (labels or {}).get(b, f"{b} label")}) + "\n"
        for b in backends), encoding="utf-8")
    answer = ("The patient's vital signs including blood pressure, pulse, temperature and oxygen "
              "saturation were recorded across multiple visits [1]. " * 6)
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for b in backends:
            f.write(json.dumps({
                "run_id": "r1", "scenario_id": "single-vitals-summary", "backend_id": b,
                "turn": 1, "request": {"patient": PATIENT_UUID,
                                       "question": "Summarize this patient's vital signs."},
                "response": {"answer": answer,
                             "references": [{"index": 1, "resourceType": "Observation"}]},
                "metrics": {"latency_ms": 10, "http_status": 200, "json_valid": True,
                            "citation_count": 1, "answer_chars": len(answer), "first_turn": True},
            }) + "\n")


def _page(browser, uri, width=1400, height=900):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(uri)
    page.wait_for_selector(".tiles")
    return page


def test_expand_is_a_real_button(tmp_path):
    """RED: the expand control is a borderless text-link (.expand { border: none }). GREEN: a
    real button with a visible border."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a", "b"])
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            info = page.evaluate(
                "(() => { const e = document.querySelector('.expand'); if(!e) return null;"
                " const s = getComputedStyle(e);"
                " return {tag: e.tagName, border: parseFloat(s.borderTopWidth)}; })()")
        finally:
            b.close()
    assert info is not None, "no .expand control found"
    assert info["tag"] == "BUTTON", f"expand should be a <button>, got {info['tag']}"
    assert info["border"] > 0, f"expand button should have a visible border, got {info['border']}px"


def test_tiles_have_larger_min_width(tmp_path):
    """RED: tiles min-width is 280px. GREEN: >=340px (each tile shows more answer before scroll)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, [f"backend-{i}" for i in range(6)])  # 6 tiles overflow a 1400px viewport
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri, width=1400)
            tile_w = page.evaluate("document.querySelector('.tile').clientWidth")
        finally:
            b.close()
    print(f"\n[ui] tile_width={tile_w}")
    assert tile_w >= 330, f"tile min-width should be ~340px, got {tile_w}px"


def test_click_tile_opens_fullscreen(tmp_path):
    """RED: no fullscreen affordance. GREEN: a per-tile control opens an overlay that covers the
    viewport (so a reviewer can read one answer full-screen)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a", "b"])
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri, width=1400, height=900)
            btn = page.query_selector(".tile .fs-btn")
            assert btn is not None, "no per-tile fullscreen button (.fs-btn)"
            btn.click()
            page.wait_for_selector(".fs-overlay", state="visible", timeout=2000)
            covers = page.evaluate(
                "(() => { const o = document.querySelector('.fs-overlay');"
                " return o && o.clientWidth >= window.innerWidth * 0.8"
                " && o.clientHeight >= window.innerHeight * 0.8; })()")
        finally:
            b.close()
    assert covers, "fullscreen overlay should cover most of the viewport"


def test_scroll_arrows_grey_at_edges(tmp_path):
    """RED: no scroll affordance. GREEN: ◀▶ arrows; at scrollLeft=0 the left arrow is disabled and
    the right arrow is enabled (tiles overflow to the right)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, [f"backend-{i}" for i in range(8)])  # force overflow
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri, width=1100)
            page.wait_for_timeout(400)
            state = page.evaluate(
                "(() => { const l = document.querySelector('.scroll-arrow.left');"
                " const r = document.querySelector('.scroll-arrow.right'); if(!l||!r) return null;"
                " return {left_disabled: l.classList.contains('disabled'),"
                "         right_disabled: r.classList.contains('disabled')}; })()")
        finally:
            b.close()
    assert state is not None, "no .scroll-arrow.left/.right affordances"
    assert state["left_disabled"], "left arrow should be greyed/disabled at the left edge"
    assert not state["right_disabled"], "right arrow should be enabled (more tiles to the right)"


def test_patient_banner_links_to_openmrs_chart(tmp_path):
    """RED: no patient grounding. GREEN: a banner shows the patient identifier and links to the
    live OpenMRS chart for the actual patient UUID."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a", "b"], with_patient=True)
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            banner_text = page.text_content(".patient-banner") or ""
            href = page.get_attribute(".patient-banner a", "href") or ""
        finally:
            b.close()
    assert "2428TU-4" in banner_text, f"patient identifier missing from banner: {banner_text!r}"
    assert "openmrs.openclinai.org" in href and PATIENT_UUID in href, (
        f"banner should link to the live OpenMRS chart for {PATIENT_UUID}, got {href!r}")
    # richer grounding: active regimen, chart counts, recent vitals
    assert "Lamivudine" in banner_text, f"active regimen missing from banner: {banner_text!r}"
    assert "11" in banner_text, f"encounter count missing from banner: {banner_text!r}"
    assert ("SpO2" in banner_text) or ("93%" in banner_text), (
        f"recent vitals missing from banner: {banner_text!r}")


def test_summary_label_is_escaped_not_injected(tmp_path):
    """A backend label is attacker-influenced config text; the summary must escape it into
    text, not inject it as live markup (the renderSummary innerHTML surface)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a"], labels={"a": "<img src=x onerror=window.__xss=1>"})
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            injected = page.evaluate("window.__xss === 1")
            imgs = page.evaluate("document.querySelector('.summary').querySelectorAll('img').length")
        finally:
            b.close()
    assert injected is not True, "summary label was executed as live markup (XSS)"
    assert imgs == 0, "summary label injected a live <img> element instead of escaped text"


def test_adjudication_radios_are_unique_per_tile(tmp_path):
    """Each tile's pass/fail radios must be their own group — a single global name='decision'
    makes picking pass in one tile deselect another."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a", "b"])
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            names = page.evaluate(
                "[...document.querySelectorAll('.tile')]"
                ".map(t => { const r = t.querySelector('input[type=radio]'); return r ? r.name : null; })"
                ".filter(Boolean)")
        finally:
            b.close()
    assert len(names) >= 2 and len(set(names)) == len(names), (
        f"decision radios share a name across tiles (one global group): {names}")
