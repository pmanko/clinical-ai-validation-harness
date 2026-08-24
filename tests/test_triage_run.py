"""The triage gate: unvetted failures and vacuous passes refuse the run."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _triage(run_dir: Path, vetted: list[dict], monkeypatch, capsys) -> tuple[int, str]:
    spec = importlib.util.spec_from_file_location(
        "triage_run", ROOT / "scripts" / "triage-run.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger = run_dir.parent / "vetted.json"
    ledger.write_text(json.dumps(vetted), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["triage-run.py", str(run_dir), "--vetted", str(ledger)]
    )
    code = module.main()
    return code, capsys.readouterr().out


def _write_rows(tmp_path: Path, rows: list[dict]) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "rows.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return run_dir


def _pass_row(scenario: str = "A1") -> dict:
    return {
        "scenarioId": scenario,
        "profileId": "team-a",
        "repetition": 1,
        "passed": True,
        "assertions": [
            {"name": "token_evidence_recorded-base", "passed": True},
            {"name": "base_gold_execution_match", "passed": True},
            {"name": "no_sql_after_non_ready_base", "passed": True},
        ],
    }


def test_a_clean_run_passes_triage(tmp_path, monkeypatch, capsys):
    run_dir = _write_rows(tmp_path, [_pass_row()])
    code, out = _triage(run_dir, [], monkeypatch, capsys)
    assert code == 0
    assert "triage clean" in out


def test_an_unvetted_failure_signature_refuses_the_run(tmp_path, monkeypatch, capsys):
    row = _pass_row()
    row["passed"] = False
    row["assertions"].append({"name": "something_new", "passed": False,
                              "evidence": {"disagreement": "novel breakage"}})
    run_dir = _write_rows(tmp_path, [row])
    code, out = _triage(run_dir, [], monkeypatch, capsys)
    assert code == 1
    assert "UNVETTED" in out and "something_new" in out and "novel breakage" in out


def test_a_vetted_failure_is_dispositioned_not_flagged(tmp_path, monkeypatch, capsys):
    row = _pass_row()
    row["passed"] = False
    row["assertions"].append({"name": "writer_outcome", "passed": False})
    run_dir = _write_rows(tmp_path, [row])
    vetted = [{"signature": ["writer_outcome"], "disposition": "model",
               "rationale": "known"}]
    code, out = _triage(run_dir, vetted, monkeypatch, capsys)
    assert code == 0
    assert "vetted model: 1" in out


def test_a_vacuous_pass_refuses_the_run(tmp_path, monkeypatch, capsys):
    row = _pass_row()
    row["assertions"] = [a for a in row["assertions"]
                         if not a["name"].startswith("token_evidence")]
    run_dir = _write_rows(tmp_path, [row])
    code, out = _triage(run_dir, [], monkeypatch, capsys)
    assert code == 1
    assert "VACUOUS PASS" in out and "token evidence never asserted" in out


def test_missing_inputs_refuse_in_one_line_not_a_traceback(
    tmp_path, monkeypatch, capsys
):
    empty = tmp_path / "nothing"
    empty.mkdir()
    code, out = _triage(empty, [], monkeypatch, capsys)
    assert code == 1
    assert "TRIAGE FAILED: cannot read" in out
