from __future__ import annotations

import hashlib
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


def _reader_run_config(
    tmp_path: Path,
    *,
    rubric: str,
    rubric_sha256: str = "",
) -> Path:
    path = tmp_path / "reader-run-config.json"
    path.write_text(
        json.dumps(
            {
                "suite": "datasets/reader-suite.json",
                "readerRubric": rubric,
                "readerRubricSha256": rubric_sha256,
                "gatewayUrl": "http://127.0.0.1:18000",
                "outputDir": "artifacts/reader-run",
                "warmupQuestion": "Warm the selected model team once.",
                "invocation": {
                    "scenarios": ["A1", "A1", "M1"],
                    "repetitions": 1,
                    "includeManual": False,
                    "timeoutSeconds": 45,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


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


def test_reader_cli_freezes_the_exact_configured_rubric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    rubric = tmp_path / "rubrics" / "reader.md"
    rubric.parent.mkdir()
    rubric.write_text("Review the complete evidence.\n", encoding="utf-8")
    config = _reader_run_config(tmp_path, rubric="rubrics/reader.md")
    result = _fake_result(tmp_path, reader_led=True)
    captured: dict[str, Any] = {}

    def fake_run_notebook_suite(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return result

    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        fake_run_notebook_suite,
    )
    args = _run_args(tmp_path)
    args.run_config = str(config)
    args.timeout_seconds = None

    assert dispatch(args, project_root=tmp_path) == 0
    capsys.readouterr()
    expected_digest = hashlib.sha256(rubric.read_bytes()).hexdigest()
    assert captured["reader_rubric_path"] == rubric
    assert captured["frozen_config"]["readerRubric"] == "rubrics/reader.md"
    assert captured["frozen_config"]["readerRubricSha256"] == expected_digest
    assert captured["warmup_question"] == "Warm the selected model team once."
    assert captured["scenario_ids"] == {"A1", "M1"}
    assert captured["repetitions"] == 1
    assert captured["client"].timeout_seconds == 45


def test_reader_cli_resume_uses_the_rubric_frozen_with_the_source_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    resume_dir = tmp_path / "source-run"
    resume_dir.mkdir()
    frozen_rubric = resume_dir / "reader-rubric.md"
    frozen_rubric.write_text("The source run's exact rubric.\n", encoding="utf-8")
    digest = hashlib.sha256(frozen_rubric.read_bytes()).hexdigest()
    config = _reader_run_config(
        tmp_path,
        rubric="rubrics/missing-current-copy.md",
        rubric_sha256=digest,
    )
    result = _fake_result(tmp_path, reader_led=True)
    captured: dict[str, Any] = {}

    def fake_run_notebook_suite(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return result

    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        fake_run_notebook_suite,
    )
    args = _run_args(tmp_path)
    args.run_config = str(config)
    args.resume_from = str(resume_dir)

    assert dispatch(args, project_root=tmp_path) == 0
    capsys.readouterr()
    assert captured["reader_rubric_path"] == frozen_rubric
    assert captured["resume_from"] == resume_dir
    assert captured["frozen_config"]["readerRubricSha256"] == digest


@pytest.mark.parametrize(
    ("create_rubric", "recorded_digest", "message"),
    [
        (False, "", "cannot read reader rubric"),
        (True, "0" * 64, "differ from the frozen run configuration"),
    ],
)
def test_reader_cli_refuses_a_missing_or_changed_rubric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    create_rubric: bool,
    recorded_digest: str,
    message: str,
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    rubric = tmp_path / "rubrics" / "reader.md"
    if create_rubric:
        rubric.parent.mkdir()
        rubric.write_text("Current rubric bytes.\n", encoding="utf-8")
    config = _reader_run_config(
        tmp_path,
        rubric="rubrics/reader.md",
        rubric_sha256=recorded_digest,
    )
    called = False

    def fake_run_notebook_suite(**_: Any) -> SimpleNamespace:
        nonlocal called
        called = True
        return _fake_result(tmp_path, reader_led=True)

    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        fake_run_notebook_suite,
    )
    args = _run_args(tmp_path)
    args.run_config = str(config)

    with pytest.raises(SystemExit, match=message):
        dispatch(args, project_root=tmp_path)
    assert called is False


def _prepare_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "scripts" / "prepare-catalyst-reader-review.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepare_reader_review_script_writes_the_requested_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _prepare_script("prepare_reader_input_test")
    run_dir = tmp_path / "run"
    rubric = tmp_path / "rubric.md"
    expected = run_dir / "reader-review-input.json"
    calls: list[tuple[Path, Path | None]] = []

    def prepare(path: Path, rubric_path: Path | None) -> Path:
        calls.append((path, rubric_path))
        return expected

    monkeypatch.setattr(module, "prepare_reader_review", prepare)
    monkeypatch.setattr(
        module,
        "validate_reader_reviews",
        lambda _: pytest.fail("attachment validation was not requested"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare-catalyst-reader-review.py",
            str(run_dir),
            "--rubric",
            str(rubric),
        ],
    )

    assert module.main() == 0
    assert calls == [(run_dir, rubric)]
    assert capsys.readouterr().out == f"reader review input -> {expected}\n"


def test_prepare_reader_review_script_checks_attached_reviews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _prepare_script("check_reader_reviews_test")
    run_dir = tmp_path / "run"
    expected = run_dir / "reader-review-input.json"
    monkeypatch.setattr(
        module,
        "prepare_reader_review",
        lambda path, rubric: expected,
    )
    checked: list[Path] = []

    def validate(path: Path) -> list[dict[str, str]]:
        checked.append(path)
        return [{"review": "one"}, {"review": "two"}]

    monkeypatch.setattr(module, "validate_reader_reviews", validate)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare-catalyst-reader-review.py",
            str(run_dir),
            "--check-attached",
        ],
    )

    assert module.main() == 0
    assert checked == [run_dir]
    assert capsys.readouterr().out == (
        f"reader review input -> {expected}\n"
        "reader reviews verified -> 2\n"
    )


def test_prepare_reader_review_script_reports_a_clean_one_line_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _prepare_script("prepare_reader_error_test")
    run_dir = tmp_path / "run"

    def refuse(*_: Any) -> Path:
        raise ValueError("the comparison collection is incomplete")

    monkeypatch.setattr(module, "prepare_reader_review", refuse)
    monkeypatch.setattr(
        "sys.argv",
        ["prepare-catalyst-reader-review.py", str(run_dir)],
    )

    assert module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: the comparison collection is incomplete\n"


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
