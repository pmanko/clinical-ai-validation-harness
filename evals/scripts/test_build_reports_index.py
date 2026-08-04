"""Tests for scripts/build-reports-index.py — the curated index renderer's pure logic.

Two behaviors with real bugs worth pinning:
  - human_arm's tier-token matching AFTER the `med-agent-team` prefix (the prefix itself
    contains "med", so a naive `"med" in arm` mislabels every team as Standard), plus the
    +checker/+in-depth flags and the single-12b-indepth special case;
  - _scout_table's In-Depth-Benchmark block (shown, NOT hidden, for any arm shipping a
    background score) + the best-cell highlight + harm flagging + the unscored fallback.

Loaded by path via importlib (hyphenated filename). human_arm reaches the live
arm_card resolver for the hover DETAIL, but the NAME assertions are deterministic on the
arm-id string. _scout_table is tested with human_arm stubbed so the table logic is isolated.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "build-reports-index.py"


def _load():
    assert _MOD_PATH.exists(), "scripts/build-reports-index.py missing"
    spec = importlib.util.spec_from_file_location("build_reports_index", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# human_arm — tier-token-after-prefix + flags
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("arm,expected_name", [
    ("med-agent-team-low", "AI team — Basic"),
    ("med-agent-team-med", "AI team — Standard"),
    ("med-agent-team-high", "AI team — Advanced"),
    ("med-agent-team-parity", "AI team — matched to baseline"),
    ("med-agent-team-12b", "AI team — 12B"),
])
def test_human_arm_team_tier_tokens(arm, expected_name):
    bri = _load()
    name, _detail = bri.human_arm(arm)
    assert name == expected_name


def test_human_arm_team_validated_and_indepth_flags():
    bri = _load()
    name, _ = bri.human_arm("med-agent-team-high-validated-indepth")
    # the tier is still Advanced (token after the prefix), with both flags appended
    assert name == "AI team — Advanced + checker + in-depth"


def test_human_arm_prefix_does_not_self_match_med():
    bri = _load()
    # 'med-agent-team' literally contains 'med'; a tier with no recognizable token after
    # the prefix must fall to the generic "team", NOT be mislabeled "Standard".
    name, _ = bri.human_arm("med-agent-team-zzz")
    assert name == "AI team — team"


def test_human_arm_single_12b_indepth_special_case():
    bri = _load()
    name, _ = bri.human_arm("single-12b-indepth")
    assert name == "Gemma 12B (single + in-depth)"


def test_human_arm_single_makeup_and_short_title(monkeypatch):
    bri = _load()
    # a SINGLE arm: detail is the model's id·params·quant; name is the card's short_title
    monkeypatch.setattr(bri, "arm_card", lambda arm: {
        "kind": "single", "short_title": "Gemma 4 12B · Q8",
        "models": [{"id": "gemma-4-12b", "params": "12B", "quant": "Q8_0"}]})
    name, detail = bri.human_arm("some-single")
    assert name == "Gemma 4 12B · Q8"
    assert detail == "gemma-4-12b · 12B · Q8_0"


def test_human_arm_team_makeup_detail(monkeypatch):
    bri = _load()
    monkeypatch.setattr(bri, "arm_card", lambda arm: {
        "kind": "team",
        "roles": {"orchestrator": {"id": "lfm2-2.6b"}, "synthesizer": {"id": "qwen2.5-32b"}}})
    name, detail = bri.human_arm("med-agent-team-low")
    assert name == "AI team — Basic"
    # the hover detail is the role=model lineup
    assert detail == "orchestrator=lfm2-2.6b · synthesizer=qwen2.5-32b"


def test_human_arm_short_title_falls_back_to_raw_label(monkeypatch):
    bri = _load()
    # a single card with NO short_title -> name falls back to the backends.json label (_RAW)
    monkeypatch.setattr(bri, "arm_card", lambda arm: {"kind": "single", "models": [{}]})
    monkeypatch.setattr(bri, "_RAW", {"weird-arm": "Weird Arm Label"})
    name, detail = bri.human_arm("weird-arm")
    assert name == "Weird Arm Label"
    assert detail == "Weird Arm Label"


# --------------------------------------------------------------------------- #
# _scout_table — rendering, In-Depth block, best/harm classes, unscored fallback
# --------------------------------------------------------------------------- #
def _stub_human_arm(monkeypatch, bri):
    # isolate _scout_table from the live arm_card resolver (plain names — the renderer
    # html-escapes, so avoid characters that would be entity-encoded in the assertions)
    monkeypatch.setattr(bri, "human_arm", lambda arm: (f"Name {arm}", f"detail {arm}"))


def test_scout_table_unscored_fallback():
    bri = _load()
    html = bri._scout_table([])
    assert "not yet scored" in html
    assert "<table" not in html


def test_scout_table_marks_best_and_harm(monkeypatch):
    bri = _load()
    _stub_human_arm(monkeypatch, bri)
    scout = [
        {"backend": "a", "n": 5, "benchmark_score": 80.0, "accuracy_mean": 8.0,
         "completeness_mean": 7.0, "relevance_mean": 9.0, "harm_count": 0,
         "confabulation_count": 0, "fabricated_citation_count": 0},
        {"backend": "b", "n": 5, "benchmark_score": 60.0, "accuracy_mean": 6.0,
         "completeness_mean": 6.0, "relevance_mean": 6.0, "harm_count": 2,
         "confabulation_count": 1, "fabricated_citation_count": 0},
    ]
    html = bri._scout_table(scout)
    # the higher benchmark (80) is flagged best
    assert 'class="bench best">80.0' in html
    # the arm with harm gets the harm class on its harm cell (count rendered)
    assert 'class="harm"' in html
    # both arms are rendered in the answer grid
    assert "Name a" in html and "Name b" in html


def test_scout_table_renders_indepth_block_for_arms_with_background(monkeypatch):
    bri = _load()
    _stub_human_arm(monkeypatch, bri)
    scout = [
        # an arm that shipped an In-Depth (a background block with n_background)
        {"backend": "team", "n": 4, "benchmark_score": 70.0, "accuracy_mean": 7.0,
         "completeness_mean": 7.0, "relevance_mean": 7.0, "harm_count": 0,
         "confabulation_count": 0, "fabricated_citation_count": 0,
         "background": {"n_background": 4, "benchmark_score": 88.5, "support_mean": 9.0,
                        "added_value_mean": 8.0, "new_harm_count": 0, "padded_count": 1}},
        # an arm with NO in-depth -> excluded from the In-Depth block
        {"backend": "single", "n": 4, "benchmark_score": 65.0, "accuracy_mean": 6.5,
         "completeness_mean": 6.5, "relevance_mean": 6.5, "harm_count": 0,
         "confabulation_count": 0, "fabricated_citation_count": 0, "background": {}},
    ]
    html = bri._scout_table(scout)
    # the separate In-Depth Benchmark section is rendered (shown, not hidden)...
    assert "In-Depth Benchmark" in html
    assert "scored separately on" in html
    assert "88.5" in html  # the In-Depth benchmark value
    # ...and the answer grid still carries BOTH arms above it
    assert "70.0" in html and "65.0" in html


def test_scout_table_no_indepth_block_when_no_background(monkeypatch):
    bri = _load()
    _stub_human_arm(monkeypatch, bri)
    scout = [{"backend": "x", "n": 3, "benchmark_score": 50.0, "accuracy_mean": 5.0,
              "completeness_mean": 5.0, "relevance_mean": 5.0, "harm_count": 0,
              "confabulation_count": 0, "fabricated_citation_count": 0}]
    html = bri._scout_table(scout)
    # no arm has a background -> the In-Depth block is absent
    assert "In-Depth Benchmark" not in html


# --------------------------------------------------------------------------- #
# main — index.html render + the staged-but-unlisted warning
# --------------------------------------------------------------------------- #
def test_main_writes_index_and_warns_on_staged_but_unlisted(tmp_path, monkeypatch, capsys):
    bri = _load()
    reports = tmp_path / "reports"
    (reports / "listed-run").mkdir(parents=True)
    (reports / "listed-run" / "meta.json").write_text("{}", encoding="utf-8")
    # a report STAGED under reports/ but absent from the curated manifest -> should warn
    (reports / "ghost-run").mkdir()
    (reports / "ghost-run" / "meta.json").write_text("{}", encoding="utf-8")

    manifest = tmp_path / "reports-index.json"
    manifest.write_text(json.dumps({
        "intro": "hello", "scoring_note": "note",
        "runs": [{"slug": "listed-run", "title": "Listed Run",
                  "summary": "s", "takeaway": "t"}]}), encoding="utf-8")

    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(bri, "MANIFEST", manifest)
    monkeypatch.setattr(bri, "VALIDATE", tmp_path / "validate")
    bri.main()

    out_html = (reports / "index.html").read_text(encoding="utf-8")
    assert "Listed Run" in out_html
    assert "hello" in out_html  # the intro copy
    # the staged-but-unlisted run is flagged on stderr
    assert "ghost-run is staged" in capsys.readouterr().err


def test_card_includes_gather_facts_and_dashboard_link(tmp_path, monkeypatch) -> None:
    bri = _load()
    reports = tmp_path / "reports"
    slug_dir = reports / "fact-run"
    slug_dir.mkdir(parents=True)
    (slug_dir / "dashboard.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(
        bri,
        "gather",
        lambda slug: {
            "patients": "12 patients",
            "cells": 24,
            "date": "2026-07-21",
            "scout": [],
        },
    )
    html = bri._card(
        {
            "slug": "fact-run",
            "title": "Fact Run",
            "summary": "summary",
            "takeaway": "take",
        }
    )
    assert "12 patients" in html
    assert "24 graded answers" in html
    assert "2026-07-21" in html
    assert 'href="fact-run/dashboard.html"' in html


def test_index_html_uses_shared_theme_toggle_assets(tmp_path, monkeypatch) -> None:
    from harness.report_shell import assets as shell_assets

    bri = _load()
    reports = tmp_path / "reports"
    reports.mkdir()
    manifest = tmp_path / "reports-index.json"
    manifest.write_text(
        json.dumps({"intro": "i", "scoring_note": "n", "runs": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(bri, "MANIFEST", manifest)
    monkeypatch.setattr(bri, "VALIDATE", tmp_path / "validate")
    bri.main()
    html = (reports / "index.html").read_text(encoding="utf-8")
    assert shell_assets.THEME_TOGGLE_BUTTON_HTML in html
    assert shell_assets.THEME_TOGGLE_CSS in html
    assert shell_assets.theme_bootstrap_js("oc-theme-index") in html
    assert shell_assets.theme_toggle_js("oc-theme-index") in html


def test_card_renders_meta_scoreline_instead_of_unscored_disclaimer(tmp_path, monkeypatch):
    """A run family without judge scores (e.g. the Catalyst notebook
    acceptance suite) declares a meta.json scoreline; the card renders it in
    place of the misleading 'not yet scored' disclaimer."""
    bri = _load()
    reports = tmp_path / "reports"
    slug_dir = reports / "catalyst-run"
    slug_dir.mkdir(parents=True)
    (slug_dir / "meta.json").write_text(json.dumps({
        "run_dir": "does-not-resolve",
        "scoreline": "12/12 scenario repetitions passed - 384 assertions",
    }), encoding="utf-8")
    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(bri, "VALIDATE", tmp_path / "validate")
    html = bri._card({"slug": "catalyst-run", "title": "T", "summary": "S"})
    assert "384 assertions" in html
    assert "not yet scored" not in html


def test_run_dir_for_rejects_a_traversal_path_outside_validate(tmp_path, monkeypatch):
    """A Catalyst run dir (a different family, referenced via a "../" run_dir —
    see the scoreline path above) now also streams results.jsonl. _run_dir_for
    must not resolve outside VALIDATE just because that sentinel file now
    exists there too, or gather() would misparse Catalyst rows as scored
    validate rows."""
    bri = _load()
    root = tmp_path
    reports = root / "artifacts" / "reports"
    validate = root / "artifacts" / "validate"
    other_family = root / "artifacts" / "catalyst-notebook-validation" / "some-run-id"
    other_family.mkdir(parents=True)
    (other_family / "results.jsonl").write_text(
        json.dumps({"scenario_id": "s", "backend_id": "b", "turn": 1}) + "\n",
        encoding="utf-8",
    )
    slug_dir = reports / "catalyst-run"
    slug_dir.mkdir(parents=True)
    (slug_dir / "meta.json").write_text(
        json.dumps({"run_dir": "../catalyst-notebook-validation/some-run-id"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(bri, "VALIDATE", validate)

    assert bri._run_dir_for("catalyst-run") is None


def test_catalyst_gather_uses_root_relative_run_and_never_calls_scout(
    tmp_path, monkeypatch
):
    bri = _load()
    root = tmp_path
    reports = root / "artifacts" / "reports"
    run_dir = root / "artifacts" / "catalyst-notebook-validation" / "run-1"
    slug_dir = reports / "catalyst-run"
    slug_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (slug_dir / "meta.json").write_text(
        json.dumps(
            {
                "report_family": "catalyst",
                "run_path": "artifacts/catalyst-notebook-validation/run-1",
                "suite_id": "suite-1",
                "suite_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "resultCount": 2,
                "passedCount": 1,
                "results": [
                    {
                        "assertions": [
                            {"name": "base_gold_execution_match", "passed": True},
                            {
                                "name": "successor_gold_execution_match",
                                "passed": False,
                            },
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "judge.jsonl").write_text(
        json.dumps({"composite": 80}) + "\n" + json.dumps({"composite": 100}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bri, "ROOT", root)
    monkeypatch.setattr(bri, "REPORTS", reports)
    monkeypatch.setattr(bri, "VALIDATE", root / "artifacts" / "validate")
    monkeypatch.setattr(
        bri, "_load_judge", lambda *_: (_ for _ in ()).throw(AssertionError("Scout"))
    )
    monkeypatch.setattr(
        bri, "scout_summary", lambda *_: (_ for _ in ()).throw(AssertionError("Scout"))
    )

    gathered = bri.gather("catalyst-run")

    assert gathered["family"] == "catalyst"
    assert gathered["cells"] == 2
    assert gathered["scout"] == []
    assert gathered["scoreline"] == (
        "Gold checks: 1/2 passed · Advisory judge median: 90/100"
    )
    html = bri._card(
        {"slug": "catalyst-run", "title": "Catalyst", "summary": "S"}
    )
    assert "Catalyst SQL" in html
    assert "2 scenario repetitions" in html


def test_root_relative_run_path_rejects_repository_traversal(tmp_path, monkeypatch):
    bri = _load()
    reports = tmp_path / "reports"
    slug_dir = reports / "bad"
    slug_dir.mkdir(parents=True)
    (slug_dir / "meta.json").write_text(
        json.dumps(
            {
                "report_family": "catalyst",
                "run_path": "../outside",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bri, "ROOT", tmp_path)
    monkeypatch.setattr(bri, "REPORTS", reports)
    assert bri._run_dir_for("bad") is None
