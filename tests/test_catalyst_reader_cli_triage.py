from __future__ import annotations

import importlib.util
import json
import re
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from harness.catalyst.cli import dispatch


ROOT = Path(__file__).resolve().parents[1]
NON_NEUTRAL = re.compile(
    r"\b(?:pass|passed|score|scores|scored|judge|judged)\b",
    flags=re.IGNORECASE,
)


def _run_args(tmp_path: Path) -> Namespace:
    return Namespace(
        catalyst_action="run",
        run_config=None,
        suite="suite.json",
        gateway_url="http://gateway.example",
        output_dir=str(tmp_path),
        scenarios=None,
        repetitions=None,
        include_manual=False,
        no_postgres_cross_check=True,
        postgres_dsn="",
        resume_from=None,
        timeout_seconds=30,
    )


def _fake_result(tmp_path: Path, *, reader_led: bool) -> SimpleNamespace:
    run_dir = tmp_path / ("reader-run" if reader_led else "legacy-run")
    run_dir.mkdir()
    (run_dir / "suite.json").write_text(
        json.dumps(
            {
                "id": "suite-v1",
                **({"reportMode": "reader-led"} if reader_led else {}),
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(
        run_id=run_dir.name,
        run_dir=run_dir,
        passed_count=1,
        result_count=2,
        skipped_count=0,
        complete=True,
        measurement_valid=True,
    )


def test_reader_led_cli_reports_collection_and_evidence_without_score_terms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    result = _fake_result(tmp_path, reader_led=True)
    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        lambda **_: result,
    )

    assert dispatch(_run_args(tmp_path), project_root=tmp_path) == 0
    raw = capsys.readouterr().out
    assert json.loads(raw) == {
        "run_id": "reader-run",
        "run_dir": str(result.run_dir),
        "recorded_conversations": 2,
        "skipped_conversations": 0,
        "collection_complete": True,
        "evidence_valid": True,
    }
    assert NON_NEUTRAL.search(raw) is None


def test_legacy_cli_keeps_its_historical_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    result = _fake_result(tmp_path, reader_led=False)
    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        lambda **_: result,
    )

    assert dispatch(_run_args(tmp_path), project_root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {
        "run_id": "legacy-run",
        "run_dir": str(result.run_dir),
        "passed": 1,
        "total": 2,
        "skipped": 0,
        "complete": True,
        "measurement_valid": True,
    }


def _triage(
    run_dir: Path,
    rows: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    (run_dir / "rows.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    (run_dir / "suite.json").write_text(
        json.dumps({"id": "suite-v1", "reportMode": "reader-led"}),
        encoding="utf-8",
    )
    ledger = run_dir / "vetted.json"
    ledger.write_text("[]\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "reader_triage_test",
        ROOT / "scripts" / "triage-run.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        "sys.argv",
        ["triage-run.py", str(run_dir), "--vetted", str(ledger)],
    )
    code = module.main()
    return code, capsys.readouterr().out


def _complete_row(*, answer_matches: bool) -> dict[str, Any]:
    return {
        "scenarioId": "A1",
        "profileId": "team-a" if answer_matches else "team-b",
        "repetition": 1,
        "passed": answer_matches,
        "measurementEvidence": {
            "base": {"outcome": "ready", "oracleResult": "recorded"},
            "turns": [],
        },
        "assertions": [
            {
                "name": "base_gold_execution_match",
                "class": "evaluation",
                "passed": answer_matches,
            },
            {
                "name": "token_evidence_recorded-base",
                "class": "conformance",
                "passed": True,
            },
        ],
    }


def test_reader_led_triage_treats_answer_differences_as_complete_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    code, output = _triage(
        run_dir,
        [_complete_row(answer_matches=True), _complete_row(answer_matches=False)],
        monkeypatch,
        capsys,
    )

    assert code == 0
    assert "2 conversations collected: 2 with complete evidence" in output
    assert "triage clean: every conversation has complete" in output
    assert NON_NEUTRAL.search(output) is None


def test_reader_led_triage_names_missing_checks_as_evidence_gaps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    row = _complete_row(answer_matches=True)
    row["assertions"] = []

    code, output = _triage(run_dir, [row], monkeypatch, capsys)

    assert code == 1
    assert "EVIDENCE GAP team-a × A1" in output
    assert "close every evidence gap" in output
    assert NON_NEUTRAL.search(output) is None


def test_reader_led_triage_requires_checks_even_when_the_answer_is_wrong(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    row = _complete_row(answer_matches=False)
    row["measurementEvidence"]["base"]["oracleResult"] = "missing"

    code, output = _triage(run_dir, [row], monkeypatch, capsys)

    assert code == 1
    assert "EVIDENCE GAP team-b × A1" in output
    assert "opening has no independent answer check" in output
    assert NON_NEUTRAL.search(output) is None
