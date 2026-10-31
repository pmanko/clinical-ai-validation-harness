"""The judge card travels from the runner through finalize to every page that shows a score."""
import json
import subprocess
import sys
from pathlib import Path

from harness.validate import report


ROOT = Path(__file__).resolve().parents[1]
FINALIZE = ROOT / "scripts" / "judge-finalize.py"


def _run_dir(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "judge-cells.jsonl").write_text(json.dumps({
        "scenario_id": "s1", "backend_id": "b1", "score_background": False,
        "citation_resolution": {"n_refs": 1, "n_resolved": 1, "n_unresolved": 0,
                                "unresolved": [], "rate": 1.0},
    }) + "\n")
    (run / "run_manifest.json").write_text(json.dumps({"run_id": "run", "otel": {}}))
    (run / "results.jsonl").write_text("")
    (run / "events.jsonl").write_text("")
    return run


def _rows(tmp_path: Path) -> Path:
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([{
        "scenario_id": "s1", "backend_id": "b1", "accuracy": 9, "completeness": 8,
        "relevance": 9, "abstention_outcome": "n-a", "citation_groundedness": "supported",
        "harm": False, "note": "fine",
    }]))
    return rows


def _finalize(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(FINALIZE), *args], capture_output=True, text=True,
                          cwd=ROOT, check=True)


def test_finalize_writes_the_card_the_runner_supplied_and_derives_the_actor(tmp_path):
    run = _run_dir(tmp_path)
    card = tmp_path / "card.json"
    card.write_text(json.dumps({
        "agent": "codex", "agent_version": "0.160.1", "model": "gpt-6-astra",
        "reasoning_effort": "high", "sampling": "provider default", "pass_index": 1, "passes": 1,
        "brief_sha256": "8b3b7a18" + "0" * 56, "started_at": "2026-10-27T00:03:20Z",
        "finished_at": "2026-10-27T00:09:01Z", "ignored": "not a card field",
    }))

    _finalize(str(run), str(_rows(tmp_path)), "--card", str(card), "--promote")

    actor = run / "judges" / "codex-gpt-6-astra-high-p1"
    manifest = json.loads((actor / "manifest.json").read_text())
    assert manifest["schema_version"] == "judge_actor.v2"
    assert manifest["model"] == "gpt-6-astra"
    assert manifest["reasoning_effort"] == "high"
    assert manifest["agent_version"] == "0.160.1"
    assert manifest["brief_sha256"].startswith("8b3b7a18")
    assert manifest["promoted_to_canonical"] is True
    assert "ignored" not in manifest
    assert len(manifest["source_cells_sha256"]) == 64
    assert (actor / "judge.jsonl").read_text() == (run / "judge.jsonl").read_text()
    canonical = json.loads((run / "judges" / "canonical.json").read_text())
    assert canonical["built_from"] == ["codex-gpt-6-astra-high-p1"]
    assert canonical["aggregation"] == "single-pass"


def test_finalize_without_a_card_records_that_no_judge_was_recorded(tmp_path):
    run = _run_dir(tmp_path)

    _finalize(str(run), str(_rows(tmp_path)))

    assert (run / "judge.jsonl").exists()
    canonical = json.loads((run / "judges" / "canonical.json").read_text())
    assert canonical == {**canonical, "built_from": [], "aggregation": "not-recorded"}
    assert not list((run / "judges").glob("*/manifest.json"))


def test_the_report_names_the_judge_from_the_cards(tmp_path):
    run = _run_dir(tmp_path)
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"agent": "claude", "model": "claude-opus-5-5",
                                "reasoning_effort": "high", "pass_index": 1, "passes": 1}))
    _finalize(str(run), str(_rows(tmp_path)), "--card", str(card), "--promote")

    blob = report._run_blob(run)
    html = report.build_report(run).read_text(encoding="utf-8")

    assert blob["judging"]["recorded"] is True
    assert blob["judging"]["sentence"] == \
        "Judged by claude-opus-5-5, reasoning high, Claude Code CLI, pass 1 of 1."
    assert "Judged by claude-opus-5-5, reasoning high, Claude Code CLI, pass 1 of 1." in html
    assert list(blob["judge_passes"]) == ["claude-claude-opus-5-5-high-p1"]
    assert blob["judge_passes"]["claude-claude-opus-5-5-high-p1"][0]["note"] == "fine"


def test_the_report_says_when_no_judge_was_recorded(tmp_path):
    run = _run_dir(tmp_path)
    _finalize(str(run), str(_rows(tmp_path)))

    blob = report._run_blob(run)

    assert blob["judging"] == {"recorded": False, "cards": [], "canonical": [], "aggregation": "not-recorded",
                               "sentence": "Judge not recorded for this run.", "consensus": {}}


def test_the_dashboard_cell_detail_carries_every_passes_row(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("vd", ROOT / "scripts" / "validate-dashboard.py")
    assert spec and spec.loader
    vd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd)
    run = _run_dir(tmp_path)
    for i in (1, 2):
        d = run / "judges" / f"p{i}"
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps({"scenario_id": "s1", "backend_id": "b1",
                                                   "accuracy": 7 + i, "note": f"pass {i}"}) + "\n")
    monkeypatch.setattr(vd, "newest_run", lambda: str(run))

    detail = vd.detail("s1", "b1")

    assert detail["judge"]["p1"]["note"] == "pass 1"
    assert detail["judge"]["p2"]["accuracy"] == 9
    assert vd.detail("s1", "other")["judge"] == {}
