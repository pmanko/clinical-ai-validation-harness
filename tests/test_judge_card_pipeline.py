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
    assert len(manifest["rubric_sha256"]) == 64
    assert manifest["source_rows"] == "rows.json"
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
    assert "source_rows" not in html
    assert str(tmp_path) not in html
    assert list(blob["judge_passes"]) == ["claude-claude-opus-5-5-high-p1"]
    assert blob["judge_passes"]["claude-claude-opus-5-5-high-p1"][0]["note"] == "fine"


def test_report_heatmap_click_renders_per_pass_drilldown_and_aggregate_caption(tmp_path):
    run = _run_dir(tmp_path)
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "scenario_ids": ["s1"], "backend_ids": ["b1"]}) + "\n"
    )
    (run / "results.jsonl").write_text(
        json.dumps({
            "scenario_id": "s1", "backend_id": "b1", "turn": 1,
            "request": {"question": "What is the weight?"},
            "response": {"answer": "70 kg."},
            "metrics": {"http_status": 200, "latency_ms": 100, "answer_chars": 6},
        }) + "\n"
    )
    for idx, (acc, note) in enumerate(((10, "pass one note"), (6, "pass two note")), 1):
        card = tmp_path / f"card-{idx}.json"
        card.write_text(json.dumps({
            "agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high",
            "pass_index": idx, "passes": 2,
        }))
        rows = tmp_path / f"rows-{idx}.json"
        rows.write_text(json.dumps([{
            "scenario_id": "s1", "backend_id": "b1", "accuracy": acc, "completeness": 8,
            "relevance": 9, "abstention_outcome": "n-a", "citation_groundedness": "supported",
            "harm": False, "note": note,
        }]))
        _finalize(str(run), str(rows), "--card", str(card))

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
         "--actor", "codex-gpt-6-astra-high-p1", "--actor", "codex-gpt-6-astra-high-p2"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    html = report.build_report(run).read_text(encoding="utf-8")
    blob = report._run_blob(run)
    js_block = html.split("<script type='application/json' id='report-data'>", 1)[1].split("</script><script>", 1)[1].split("</script></body>", 1)[0]
    fn_start = js_block.index("function judgeCardLine(")
    fn_end = js_block.index("function renderInDepth(")
    extracted_js = js_block[fn_start:fn_end]
    node_script = f"""
const run = {json.dumps(blob)};
function htmlEsc(s) {{ return String(s == null ? '' : s); }}
function fmt10(v) {{ return v == null ? '—' : Number(v).toFixed(1); }}
function armTitle(b) {{ return String(b); }}
function bpShort(b) {{ return String(b); }}
function makeSortable() {{}}
function el(tag, cls) {{
  return {{
    tag, cls, _html: '', children: [], dataset: {{}},
    set innerHTML(v) {{
      this._html = String(v);
      this._note = {{ innerHTML: '' }};
      this._cells = [];
      const tdRe = /<td class="jh [^"]*"[^>]*data-det="([^"]*)"[^>]*data-note="([^"]*)"[^>]*data-sid="([^"]*)"[^>]*data-arm="([^"]*)"/g;
      let m;
      while ((m = tdRe.exec(this._html)) !== null) {{
        this._cells.push({{ dataset: {{ det: m[1], note: m[2], sid: m[3], arm: m[4] }}, onclick: null }});
      }}
    }},
    get innerHTML() {{ return this._html; }},
    appendChild(ch) {{ this.children.push(ch); }},
    querySelectorAll(sel) {{ return sel === 'td.jh' ? (this._cells || []) : []; }},
    querySelector(sel) {{ return sel === '#jh-note' ? this._note : null; }}
  }};
}}
{extracted_js}
const wrap = judgeHeatmap(run);
wrap.querySelectorAll('td.jh')[0].onclick();
const sec = renderJudge(run);
const tblHtml = sec.children.map(c => c.innerHTML || '').join('\\n');
console.log(JSON.stringify({{
  noteHtml: wrap.querySelector('#jh-note').innerHTML,
  secHtml: sec.innerHTML,
  tblHtml: tblHtml
}}));
"""
    rendered = json.loads(
        subprocess.run(["node", "-e", node_script], check=True, capture_output=True, text=True).stdout
    )
    assert "Each pass:" in rendered["noteHtml"]
    assert "codex-gpt-6-astra-high-p1" in rendered["noteHtml"]
    assert "pass one note" in rendered["noteHtml"]
    assert "pass two note" in rendered["noteHtml"]
    assert "one judge across 2 passes" in rendered["secHtml"]
    assert "Canonical judgment (median/majority across 2 passes)" in rendered["tblHtml"]


def test_finalizing_an_actor_invalidates_stale_consensus_and_combined_files(tmp_path):
    from harness.validate.judging import judge_summary

    run = _run_dir(tmp_path)
    for actor, acc in (("p1", 2), ("p2", 8)):
        rows = tmp_path / f"{actor}.json"
        rows.write_text(json.dumps([{
            "scenario_id": "s1", "backend_id": "b1", "accuracy": acc, "completeness": acc,
            "relevance": acc, "abstention_outcome": "n-a", "citation_groundedness": "supported",
            "harm": False, "note": actor,
        }]))
        _finalize(str(run), str(rows), "--actor", actor, "--model", "gpt-6-astra")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run), "--actor", "p1", "--actor", "p2"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    assert judge_summary(run)["consensus"]["actors"] == ["p1", "p2"]

    rescored = tmp_path / "p1-new.json"
    rescored.write_text(json.dumps([{
        "scenario_id": "s1", "backend_id": "b1", "accuracy": 10, "completeness": 10,
        "relevance": 10, "abstention_outcome": "n-a", "citation_groundedness": "supported",
        "harm": False, "note": "updated",
    }]))
    # Rescoring a canonical actor without --promote must be rejected so canonical.json and judge.jsonl stay aligned
    unpromoted_rescore = subprocess.run(
        [sys.executable, str(FINALIZE), str(run), str(rescored), "--actor", "p1", "--model", "gpt-6-astra"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert unpromoted_rescore.returncode != 0

    # Adding a brand-new unpromoted actor pass invalidates stale consensus/combined files
    p3_rows = tmp_path / "p3.json"
    p3_rows.write_text(json.dumps([{
        "scenario_id": "s1", "backend_id": "b1", "accuracy": 6, "completeness": 6,
        "relevance": 6, "abstention_outcome": "n-a", "citation_groundedness": "supported",
        "harm": False, "note": "p3",
    }]))
    _finalize(str(run), str(p3_rows), "--actor", "p3", "--model", "gpt-6-astra")
    assert not (run / "judges" / "consensus.json").exists()
    assert not (run / "judges" / "combined.json").exists()

    # Promoting the rescored pass updates canonical.json cleanly
    _finalize(str(run), str(rescored), "--actor", "p1", "--model", "gpt-6-astra", "--promote")

    summary = judge_summary(run)
    assert summary["canonical"] == ["p1"]
    assert summary["consensus"] == {}
    assert not (run / "judges" / "consensus.json").exists()
    assert not (run / "judges" / "combined.json").exists()


def test_finalize_normalizes_absolute_rubric_path_in_manifest(tmp_path):
    run = _run_dir(tmp_path)
    custom_rubric = tmp_path / "private-dir" / "custom-rubric.md"
    custom_rubric.parent.mkdir(parents=True)
    custom_rubric.write_text("# Custom rubric\n")
    card = tmp_path / "card.json"
    card.write_text(json.dumps({
        "agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high",
        "rubric": str(custom_rubric),
    }))
    _finalize(str(run), str(_rows(tmp_path)), "--card", str(card), "--promote")
    manifest = json.loads((run / "judges" / "codex-gpt-6-astra-high-p1" / "manifest.json").read_text())
    assert manifest["rubric"] == "custom-rubric.md"
    assert str(tmp_path) not in json.dumps(manifest)
    assert len(manifest["rubric_sha256"]) == 64


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
