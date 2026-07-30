"""Tests for scripts/judge-prep.py — the deterministic judge-cell prep.

The script is loaded by path (hyphenated filename) via importlib, mirroring the existing
evals/validate/test_dev_eval_team.py pattern. The behaviors pinned here are the ones that
had real bugs to cover: the Answer/In-Depth section split (real **In Depth** heading vs a
bare "in depth" mention), the two-call nested-indepth -> in_depth_section promotion, and
the expectations.should_abstain read. The dataset dirs (SCEN_DIR/CHART_DIR) are
monkeypatched to tmp fixtures so the test is hermetic.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "judge-prep.py"


def _load():
    assert _MOD_PATH.exists(), "scripts/judge-prep.py missing"
    spec = importlib.util.spec_from_file_location("judge_prep", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# split_sections — Answer vs In-Depth heading split
# --------------------------------------------------------------------------- #
def test_split_sections_real_heading():
    jp = _load()
    answer = "**Answer**\nShe is on ART.\n\n**In Depth**\nPer WHO guidance, ART is..."
    ans, indepth = jp.split_sections(answer)
    assert ans == "**Answer**\nShe is on ART."
    assert indepth.startswith("**In Depth**")


def test_split_sections_no_heading_returns_whole_as_answer():
    jp = _load()
    ans, indepth = jp.split_sections("Just a single-model answer, no in-depth.")
    assert ans == "Just a single-model answer, no in-depth."
    assert indepth == ""


def test_split_sections_ignores_bare_in_depth_mention():
    jp = _load()
    # "in depth" appearing in prose (not a **heading**) must NOT trigger a split.
    answer = "We looked at this in depth and found the value is 70 kg."
    ans, indepth = jp.split_sections(answer)
    assert ans == answer
    assert indepth == ""


def test_split_sections_non_string_input():
    jp = _load()
    assert jp.split_sections(None) == ("", "")
    assert jp.split_sections(123)[0] == "123"


def test_render_blocks_uses_row_sources_without_repeating_cell_refs():
    jp = _load()
    blocks = [{
        "kind": "table",
        "title": "Weights",
        "columns": [{"key": "date", "label": "Date"}, {"key": "weight", "label": "Weight"}],
        "rows": [{"cells": {
            "date": {"text": "2026-01-26", "refs": [1]},
            "weight": {"text": "71 kg", "refs": [1]},
        }}],
    }]
    sources = {"sources": [{"record_index": 1, "source_id": "S1"}]}
    rendered = jp.render_blocks(blocks, sources)
    assert "Date: 2026-01-26" in rendered
    assert "Weight: 71 kg" in rendered
    assert "Sources: S1" in rendered
    assert "[1]" not in rendered


# --------------------------------------------------------------------------- #
# main — the full cell build (nested in-depth promotion + should_abstain)
# --------------------------------------------------------------------------- #
def _fixture_run(tmp_path: Path, jp, monkeypatch, *, results: list[dict],
                 scenario: dict, chart: dict) -> Path:
    scen_dir = tmp_path / "scenarios"
    chart_dir = tmp_path / "charts"
    scen_dir.mkdir()
    chart_dir.mkdir()
    (scen_dir / f"{scenario['id']}.json").write_text(json.dumps(scenario), encoding="utf-8")
    (chart_dir / "p.json").write_text(json.dumps(chart), encoding="utf-8")
    monkeypatch.setattr(jp, "SCEN_DIR", scen_dir)
    monkeypatch.setattr(jp, "CHART_DIR", chart_dir)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    return run_dir


def _read_cells(run_dir: Path) -> list[dict]:
    return [json.loads(ln) for ln in
            (run_dir / "judge-cells.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_main_promotes_nested_indepth_into_in_depth_section(tmp_path, monkeypatch):
    jp = _load()
    chart = {"patient": {"uuid": "u1", "slug": "p", "name": "Pat", "gender": "F",
                         "birthdate": "1986-01-01"},
             "valid_uuids": ["ref-1"], "chart_snapshot": "Patient: 40F\n[1] Weight 70 kg"}
    scenario = {"id": "s1", "patient_ref": "u1",
                "turns": [{"n": 1, "question": "What is the weight?"}],
                "expectations": {"should_abstain": True}}
    # a single-model row whose ANSWER has no In-Depth, but a SEPARATE nested indepth artifact
    results = [{
        "scenario_id": "s1", "backend_id": "b1", "turn": 1, "error": None,
        "response": {"answer": "Weight is 70 kg.", "references": [{"index": 1, "uuid": "ref-1"}]},
        "indepth": {"response": {"answer": "In-depth: the 70 kg reading is from 2026-01."},
                    "latency_ms": 4200},
    }]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()

    cells = _read_cells(run_dir)
    assert len(cells) == 1
    cell = cells[0]
    # the nested in-depth artifact is promoted into in_depth_section (so the arm is judged on it)
    assert cell["in_depth_section"] == "In-depth: the 70 kg reading is from 2026-01."
    assert cell["turns"][0]["indepth_latency_ms"] == 4200
    # a single-model arm that ships an in-depth IS treated as a team-shaped (background-judged) cell
    assert cell["is_team"] is True
    # expectations.should_abstain is read from the nested expectations block
    assert cell["should_abstain"] is True
    # the snapshot file was dumped under <run>/charts/
    assert (run_dir / "charts" / "p.snapshot.txt").read_text(encoding="utf-8").startswith("Patient: 40F")


def test_main_includes_canonical_sources_in_judge_cell(tmp_path, monkeypatch):
    jp = _load()
    chart = {"patient": {"uuid": "u1", "slug": "p", "name": "Pat"},
             "valid_uuids": ["ref-1"],
             "chart_snapshot": "Patient: 40F\n[1] (2026-01-26) Finding — Weight: 70 kg",
             "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "ref-1"}]}
    scenario = {"id": "s1", "patient_ref": "u1",
                "turns": [{"n": 1, "question": "What is the weight?"}]}
    results = [{
        "scenario_id": "s1", "backend_id": "b1", "turn": 1, "error": None,
        "response": {"answer": "Weight is 70 kg [1].",
                     "references": [{"index": 1, "resourceUuid": "ref-1"}],
                     "blocks": []},
    }]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()
    cell = _read_cells(run_dir)[0]
    assert cell["sources"][0]["source_id"] == "S1"
    assert cell["source_diagnostics"]["answer_inline_refs"] == [1]
    assert "[Evidence Used]" in cell["answer_section"]
    assert "S1 = cite [1] chart [1] obs" in cell["answer_section"]


def test_main_excludes_review_only_model_text_from_judge_cell(tmp_path, monkeypatch):
    jp = _load()
    chart = {
        "patient": {"uuid": "u1", "slug": "p", "name": "Pat"},
        "valid_uuids": ["ref-1"],
        "chart_snapshot": "Patient: 40F\n[1] (2026-01-26) Weight: 70 kg",
        "mappings": [
            {"index": 1, "resourceType": "obs", "resourceUuid": "ref-1"}
        ],
    }
    scenario = {
        "id": "s1",
        "patient_ref": "u1",
        "turns": [{"n": 1, "question": "What is the weight?"}],
    }
    results = [
        {
            "scenario_id": "s1",
            "backend_id": "b1",
            "turn": 1,
            "error": None,
            "response": {
                "answer": "Checked answer [1].",
                "references": [{"index": 1, "resourceUuid": "ref-1"}],
                "answerValidation": {
                    "status": "edited",
                    "summary": "LEAKED ANSWER SUMMARY",
                    "originalAnswer": "Discarded original answer [99].",
                    "issues": [
                        {
                            "id": "date_value_binding",
                            "status": "fail",
                            "severity": "block",
                            "claim": "LEAKED ANSWER CLAIM",
                            "reason": "LEAKED REJECTED REASON 2026-02-02 6.2 kg",
                            "source_indices": [99],
                            "chart": "LEAKED REVIEW CHART TEXT",
                            "fix": "LEAKED REVIEW FIX",
                        }
                    ],
                },
                "inDepth": {
                    "status": "needs_review",
                    "answer": "",
                    "reviewDraft": "Rejected In-Depth draft [99].",
                    "reviewReferences": [{"index": 99}],
                    "validation": {
                        "schema_version": "indepth_temporal_gate.v1",
                        "status": "needs_review",
                        "claims": ["LEAKED REJECTED CLAIM"],
                        "checks": [
                            {
                                "claim": "LEAKED NESTED CLAIM",
                                "claim_index": 1,
                                "gate": {
                                    "status": "fail",
                                    "patch_answer": "LEAKED PATCH ANSWER",
                                    "checks": [
                                        {
                                            "id": "upcoming_date",
                                            "status": "fail",
                                            "reason": "The date is historical.",
                                            "source_indices": [99],
                                            "claim": "LEAKED DEEP CLAIM",
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                },
            },
        }
    ]
    run_dir = _fixture_run(
        tmp_path, jp, monkeypatch, results=results, scenario=scenario, chart=chart
    )
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()

    cell = _read_cells(run_dir)[0]
    serialized = json.dumps(cell)
    assert "Checked answer" in cell["answer_section"]
    assert cell["in_depth_section"] == ""
    assert cell["answer_validation"] == {
        "status": "edited",
        "issues": [
            {
                "id": "date_value_binding",
                "status": "fail",
                "severity": "block",
                "source_indices": [99],
            }
        ],
    }
    assert "Discarded original answer" not in serialized
    assert "Rejected In-Depth draft" not in serialized
    assert "LEAKED" not in serialized
    assert cell["in_depth_validation"]["checks"][0]["gate"]["status"] == "fail"
    assert [reference["index"] for reference in cell["references"]] == [1]


def test_main_should_abstain_false_when_unset(tmp_path, monkeypatch):
    jp = _load()
    chart = {"patient": {"uuid": "u1", "slug": "p"}, "valid_uuids": [],
             "chart_snapshot": "snap"}
    scenario = {"id": "s2", "patient_ref": "u1",
                "turns": [{"n": 1, "question": "q?"}]}  # no expectations block
    results = [{"scenario_id": "s2", "backend_id": "b1", "turn": 1, "error": None,
                "response": {"answer": "an answer", "references": []}}]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()
    cell = _read_cells(run_dir)[0]
    assert cell["should_abstain"] is False
    # no in-depth and not a team-prefixed backend -> NOT a team cell
    assert cell["is_team"] is False
    assert cell["in_depth_section"] == ""


def test_run_dir_resolves_id_under_artifacts_and_exits_on_missing(tmp_path, monkeypatch):
    jp = _load()
    # a bare run-id is resolved under <ROOT>/artifacts/validate/<id>
    art = tmp_path / "artifacts" / "validate" / "run-id-7"
    art.mkdir(parents=True)
    monkeypatch.setattr(jp, "ROOT", tmp_path)
    assert jp.run_dir("run-id-7") == art
    # a direct path is returned as-is
    assert jp.run_dir(str(art)) == art
    # an unresolvable id exits (no run dir)
    with pytest.raises(SystemExit):
        jp.run_dir("no-such-run")


def test_main_warns_and_skips_when_no_chart_fixture(tmp_path, monkeypatch, capsys):
    jp = _load()
    # the scenario references patient uuid 'u-missing' for which NO chart fixture exists
    chart = {"patient": {"uuid": "u1", "slug": "p"}, "valid_uuids": [], "chart_snapshot": "x"}
    scenario = {"id": "s1", "patient_ref": "u-missing",
                "turns": [{"n": 1, "question": "q?"}]}
    results = [{"scenario_id": "s1", "backend_id": "b1", "turn": 1, "error": None,
                "response": {"answer": "a", "references": []}}]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()
    # no cell produced (chart missing) + a WARN on stderr
    assert _read_cells(run_dir) == []
    assert "no chart fixture" in capsys.readouterr().err


def test_main_parses_string_response_json(tmp_path, monkeypatch):
    jp = _load()
    chart = {"patient": {"uuid": "u1", "slug": "p"}, "valid_uuids": ["ref-1"],
             "chart_snapshot": "snap"}
    scenario = {"id": "s1", "patient_ref": "u1", "turns": [{"n": 1, "question": "q?"}]}
    # the response is a JSON STRING (not a dict) -> the prep must parse it before splitting
    results = [{"scenario_id": "s1", "backend_id": "b1", "turn": 1, "error": None,
                "response": json.dumps({"answer": "parsed answer text",
                                        "references": [{"index": 1, "uuid": "ref-1"}]})}]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()
    cell = _read_cells(run_dir)[0]
    assert cell["answer_section"].startswith("parsed answer text")
    assert "[Evidence Used]" in cell["answer_section"]


def test_main_skips_error_rows(tmp_path, monkeypatch):
    jp = _load()
    chart = {"patient": {"uuid": "u1", "slug": "p"}, "valid_uuids": [],
             "chart_snapshot": "snap"}
    scenario = {"id": "s3", "patient_ref": "u1", "turns": [{"n": 1, "question": "q?"}]}
    results = [
        {"scenario_id": "s3", "backend_id": "berr", "turn": 1, "error": "timeout",
         "response": None},
        {"scenario_id": "s3", "backend_id": "bok", "turn": 1, "error": None,
         "response": {"answer": "ok", "references": []}},
    ]
    run_dir = _fixture_run(tmp_path, jp, monkeypatch, results=results,
                           scenario=scenario, chart=chart)
    monkeypatch.setattr("sys.argv", ["judge-prep.py", str(run_dir)])
    jp.main()
    cells = _read_cells(run_dir)
    # only the non-error backend produced a cell
    assert [c["backend_id"] for c in cells] == ["bok"]
