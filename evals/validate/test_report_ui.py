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


def test_judge_caveat_renders_actual_patient_and_judge_counts(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a"])
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    patient = next(iter(manifest["patients"].values()))
    patient_ids = [PATIENT_UUID, "patient-2", "patient-3"]
    manifest["patients"] = {
        patient_id: {**patient, "identifier": patient_id}
        for patient_id in patient_ids
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    results_path = run_dir / "results.jsonl"
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    for turn, patient_id in enumerate(patient_ids[1:], start=2):
        row = json.loads(json.dumps(rows[0]))
        row["turn"] = turn
        row["request"]["patient"] = patient_id
        rows.append(row)
    results_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    judge = {
        "scenario_id": "single-vitals-summary",
        "backend_id": "a",
        "accuracy": 8,
        "completeness": 8,
        "relevance": 8,
        "abstention_outcome": "n-a",
        "citation_groundedness": "supported",
        "harm": False,
        "note": "",
    }
    (run_dir / "judge.jsonl").write_text(json.dumps(judge) + "\n", encoding="utf-8")
    for actor in ("actor-a", "actor-b"):
        actor_dir = run_dir / "judges" / actor
        actor_dir.mkdir(parents=True)
        (actor_dir / "judge.jsonl").write_text(json.dumps(judge) + "\n", encoding="utf-8")

    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            caveat = page.text_content(".judge-section .legend-body") or ""
        finally:
            b.close()

    assert "small N, 3 patients, 2 judges" in caveat


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


def test_tile_renders_readonly_eval_footer_without_legacy_radios(tmp_path):
    """Each tile renders a read-only .tile-eval-footer with deterministic/judge/human pills
    and no legacy pass/fail radio inputs."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["a", "b"])
    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = _page(b, uri)
            footers = page.evaluate("document.querySelectorAll('.tile .tile-eval-footer').length")
            radios = page.evaluate("document.querySelectorAll('.tile input[type=radio]').length")
        finally:
            b.close()
    assert footers >= 2
    assert radios == 0


def test_progressive_disclosure_tabs_and_scenario_drawer(tmp_path):
    """Multi-scenario judged evaluations open into the Casual-First Overview tab (3 plain-English
    blocks), with progressive disclosure tabs for Browse All Questions (+ Slide-Over Answer Reader),
    Speed & Multi-User Scaling, and Methodology & Raw Data."""
    sync_api = pytest.importorskip("playwright.sync_api")
    run_dir = tmp_path / "run"
    _write_run(run_dir, ["single-12b", "team-12b"])
    # Add a second scenario so multi-scenario progressive disclosure activates.
    results_path = run_dir / "results.jsonl"
    existing = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    for row in list(existing):
        r2 = json.loads(json.dumps(row))
        r2["scenario_id"] = "convo-medications-adherence"
        r2["request"]["question"] = "What HIV medications is this patient currently taking?"
        existing.append(r2)
    results_path.write_text("".join(json.dumps(r) + "\n" for r in existing), encoding="utf-8")

    judge_rows = [
        {"scenario_id": "single-vitals-summary", "backend_id": "single-12b",
         "accuracy": 9.5, "completeness": 9.0, "relevance": 9.5,
         "abstention_outcome": "n-a", "citation_groundedness": "supported", "harm": False,
         "note": "Complete and accurate vitals summary."},
        {"scenario_id": "single-vitals-summary", "backend_id": "team-12b",
         "accuracy": 8.0, "completeness": 6.5, "relevance": 8.0,
         "abstention_outcome": "n-a", "citation_groundedness": "supported", "harm": False,
         "note": "Missed earliest weight measurement."},
        {"scenario_id": "convo-medications-adherence", "backend_id": "single-12b",
         "accuracy": 9.0, "completeness": 9.0, "relevance": 9.0,
         "abstention_outcome": "n-a", "citation_groundedness": "supported", "harm": False,
         "note": "Answered all follow-ups accurately."},
        {"scenario_id": "convo-medications-adherence", "backend_id": "team-12b",
         "accuracy": 7.5, "completeness": 6.0, "relevance": 5.5,
         "abstention_outcome": "over-abstained", "citation_groundedness": "supported", "harm": False,
         "note": "Over-abstained on follow-up turn."},
    ]
    (run_dir / "judge.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in judge_rows), encoding="utf-8"
    )

    uri = build_report(run_dir).resolve().as_uri()
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page(viewport={"width": 1400, "height": 900})
            page.goto(uri)
            page.wait_for_selector(".exec-summary")

            # Layer 1: Overview is active by default, showing 3 visual blocks; deep-dive sections are hidden
            active_tab = page.get_attribute("#report", "data-active-tab")
            assert active_tab == "overview"
            assert page.is_visible(".ov-banner-card")
            assert page.is_visible(".ov-table-card")
            assert page.is_visible(".ov-why-card")
            assert not page.is_visible("#sec-answers")
            assert not page.is_visible("#sec-engineering")

            # Layer 2: Click 'Browse All Questions' tab -> Question Explorer is visible
            page.click("button.rtab[data-tab='questions']")
            page.wait_for_selector(".question-explorer", state="visible")
            assert page.is_visible("#sec-answers")

            # Click a row in Question Explorer -> opens Slide-Over Answer Reader (#scenario-drawer-backdrop.open)
            page.click(".question-explorer tbody tr.qe-row >> nth=0")
            page.wait_for_selector("#scenario-drawer-backdrop.open", state="visible")
            drawer_text = page.text_content("#scenario-drawer-backdrop") or ""
            assert "1. Side-by-Side Answers" in drawer_text
            page.click("button[data-sd-tab='judge']")
            assert "Reviewer Note:" in (page.text_content("#scenario-drawer-backdrop") or "")
            page.click("#sd-close")

            # Layer 3: Click 'Speed & Multi-User Scaling' tab
            page.click("button.rtab[data-tab='speed']")
            page.wait_for_selector(".speed-visual", state="visible")
            assert page.is_visible("#sec-engineering")

            # Layer 4: Click 'Methodology & Raw Data' tab
            page.click("button.rtab[data-tab='methodology']")
            page.wait_for_selector("#sec-quality", state="visible")
            assert page.is_visible("#sec-arms")
        finally:
            b.close()
