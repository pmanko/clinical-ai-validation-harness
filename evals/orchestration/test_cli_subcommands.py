"""Argparse-level smoke for the harness CLI subcommands.

The scaffolded subcommands (conceptmap / transform / sample / ocl /
manifest) print "not yet implemented" and exit 2 — these tests assert
the argument parsing and dispatch shape, not the future behavior.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.cli import _build_parser, main


def test_help_top_level(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    assert exc_info.value.code == 0
    for expected in (
        "schema-diff",
        "import-smoke",
        "conceptmap",
        "transform",
        "sample",
        "ocl",
        "manifest",
        "catalyst",
    ):
        assert expected in out


def test_validate_run_accepts_resume_dir():
    p = _build_parser()
    args = p.parse_args(["validate", "run", "priority-run-high", "--resume", "artifacts/validate/abc"])
    assert args.validate_action == "run"
    assert args.comparison_set == "priority-run-high"
    assert args.resume == "artifacts/validate/abc"
    # absent -> None (a full run, no carry-over)
    assert p.parse_args(["validate", "run", "cs"]).resume is None


def test_validate_run_passes_resume_to_run_comparison(monkeypatch):
    captured = {}

    class _Comparison:
        id = "cs"
        transport = "chartsearchai"
        backend_ids = []

    class _Result:
        result_count = 0
        results_path = "r.jsonl"
        report_path = "report.html"

    def fake_run_comparison(**kw):
        captured.update(kw)
        return _Result()

    monkeypatch.setattr(
        "harness.validate.models.load_comparison_set", lambda _path: _Comparison()
    )
    monkeypatch.setattr(
        "harness.validate.resolver.resolve_backends", lambda _ids, _path: []
    )
    monkeypatch.setattr(
        "harness.validate.execution.validate_execution_contract",
        lambda _comparison, _backends: None,
    )
    monkeypatch.setattr("harness.validate.runner.run_comparison", fake_run_comparison)
    monkeypatch.setattr("harness.validate.client.ChartSearchAiClient", lambda *a, **k: object())
    monkeypatch.setattr(
        sys, "argv",
        ["harness-cli", "validate", "run", "cs", "--resume", "artifacts/validate/abc"])
    assert main() == 0
    assert str(captured["resume_from"]) == "artifacts/validate/abc"


@pytest.mark.parametrize("argv,expected_attr,expected_value", [
    (["conceptmap", "validate"],  "conceptmap_action", "validate"),
    (["conceptmap", "seed-emit"], "conceptmap_action", "seed-emit"),
    (["conceptmap", "candidates"],"conceptmap_action", "candidates"),
    (["transform", "run"],        "transform_action", "run"),
    (["ocl", "refresh"],          "ocl_action",       "refresh"),
    (["manifest", "finalize"],    "manifest_action",  "finalize"),
])
def test_subcommand_parses(argv, expected_attr, expected_value):
    args = _build_parser().parse_args(argv)
    assert getattr(args, expected_attr) == expected_value


def test_sample_flags():
    args = _build_parser().parse_args(["sample", "--seed", "7", "--records-per-bucket", "10"])
    assert args.seed == 7
    assert args.records_per_bucket == 10


def test_missing_action_for_grouped_subcommand_errors():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["conceptmap"])


@pytest.mark.parametrize("argv,label", [
    (["conceptmap", "validate"], "conceptmap validate"),
    (["sample"],                 "sample"),
    (["ocl",        "refresh"],  "ocl refresh"),
    (["manifest",   "finalize"], "manifest finalize"),
])
def test_scaffolded_subcommands_return_exit_2_and_print_to_stderr(argv, label, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["harness-cli", *argv])
    rc = main()
    err = capsys.readouterr().err
    assert rc == 2
    assert label in err
    assert "not yet implemented" in err


# --------------------------------------------------------------------------- #
# validate adjudicate — the CLI branch (review-mode parsing + --from + dispatch)
# --------------------------------------------------------------------------- #
def _write_judged_run(out_dir: Path, run_id: str) -> Path:
    """A minimal judged run dir the adjudicate CLI can drive non-interactively."""
    rd = out_dir / run_id
    rd.mkdir(parents=True)
    judge = {"scenario_id": "s1", "backend_id": "b1", "accuracy": 8, "completeness": 7,
             "relevance": 9, "harm": False, "abstention_outcome": "n-a",
             "citation_groundedness": "supported", "note": "j"}
    (rd / "judge.jsonl").write_text(json.dumps(judge) + "\n", encoding="utf-8")
    cell = {"scenario_id": "s1", "backend_id": "b1", "answer_section": "70 kg.",
            "turns": [{"n": 1, "question": "weight?", "answer_section": "70 kg."}]}
    (rd / "judge-cells.jsonl").write_text(json.dumps(cell) + "\n", encoding="utf-8")
    return rd


def test_adjudicate_review_named_mode_parses():
    p = _build_parser()
    args = p.parse_args(["validate", "adjudicate", "run-7", "--review", "full",
                         "--reviewer", "alice", "--tier", "clinical", "--seed", "3"])
    assert args.validate_action == "adjudicate"
    assert args.run_id == "run-7"
    assert args.review == "full"
    assert args.reviewer == "alice"
    assert args.tier == "clinical"
    assert args.seed == 3


def test_adjudicate_numeric_review_is_a_budget(tmp_path, monkeypatch, capsys):
    # --review 5 -> a bare integer means mode="budget", n=5 (the CLI's isdigit() branch).
    out_dir = tmp_path / "art"
    _write_judged_run(out_dir, "run-b")
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(
        {"s1|b1": {"accuracy": 6, "completeness": 6, "relevance": 6, "harm": False,
                   "note": "scripted"}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "harness-cli", "validate", "adjudicate", "run-b",
        "--output-dir", str(out_dir), "--review", "5",
        "--from", str(answers), "--reviewer", "rev", "--tier", "owner"])
    rc = main()
    assert rc == 0
    # the adjudication was written to <run>/adjudication.jsonl with the scripted scores
    adj = (out_dir / "run-b" / "adjudication.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(adj) == 1
    rec = json.loads(adj[0])
    assert (rec["scenario_id"], rec["backend_id"]) == ("s1", "b1")
    assert rec["axes"]["accuracy"] == 6
    assert "1 cell(s) reviewed" in capsys.readouterr().out


def test_adjudicate_named_mode_from_answers_dispatches(tmp_path, monkeypatch):
    # the non-digit --review path (mode=<name>, n=None) + --from answers loading.
    out_dir = tmp_path / "art"
    _write_judged_run(out_dir, "run-f")
    answers = tmp_path / "a.json"
    answers.write_text(json.dumps(
        {"s1|b1": {"harm": True, "note": "human flagged harm"}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "harness-cli", "validate", "adjudicate", "run-f",
        "--output-dir", str(out_dir), "--review", "full", "--from", str(answers)])
    assert main() == 0
    rec = json.loads(
        (out_dir / "run-f" / "adjudication.jsonl").read_text(encoding="utf-8").splitlines()[0])
    # omitted axes fall back to the judge's; harm overridden to True
    assert rec["axes"]["accuracy"] == 8  # judge value carried through
    assert rec["harm"] is True


def test_transform_run_dispatches_to_orchestrator(monkeypatch):
    """`harness-cli transform run` must invoke the transform orchestrator,
    not the not-yet-implemented stub."""
    monkeypatch.setattr(sys, "argv", ["harness-cli", "transform", "run"])
    called_with: list[list[str]] = []
    def fake_main(argv):
        called_with.append(list(argv))
        return 0
    monkeypatch.setattr("harness.transform.run.main", fake_main)
    rc = main()
    assert rc == 0
    assert called_with, "transform.run.main was not invoked"
    invoked = called_with[0]
    assert "--project-dir" in invoked
    assert "--conceptmap" in invoked
    assert "datasets/transforms/sqlmesh" in invoked
    assert "datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json" in invoked


def test_catalyst_run_parser_exposes_every_compatibility_script_flag():
    args = _build_parser().parse_args(
        [
            "catalyst",
            "run",
            "--suite",
            "suite.json",
            "--gateway-url",
            "http://gateway",
            "--output-dir",
            "out",
            "--scenario",
            "s1",
            "--scenario",
            "s2",
            "--repetitions",
            "3",
            "--include-manual",
            "--timeout-seconds",
            "42",
        ]
    )
    assert args.catalyst_action == "run"
    assert args.suite == "suite.json"
    assert args.gateway_url == "http://gateway"
    assert args.output_dir == "out"
    assert args.scenarios == ["s1", "s2"]
    assert args.repetitions == 3
    assert args.include_manual is True
    assert args.timeout_seconds == 42


def test_catalyst_run_dispatches_every_runner_option(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="run-1",
            run_dir=tmp_path / "run-1",
            passed_count=1,
            result_count=1,
            skipped_count=0,
            complete=True,
            measurement_valid=True,
        )

    monkeypatch.setattr("harness.catalyst.notebook_validation.run_notebook_suite", fake_run)
    monkeypatch.setattr(
        "harness.catalyst.notebook_validation.NotebookHttpClient",
        lambda url, timeout_seconds: (url, timeout_seconds),
    )

    assert (
        main(
            [
                "catalyst",
                "run",
                "--suite",
                "suite.json",
                "--gateway-url",
                "http://gateway",
                "--output-dir",
                str(tmp_path),
                "--scenario",
                "s1",
                "--repetitions",
                "2",
                "--timeout-seconds",
                "45",
            ]
        )
        == 0
    )
    assert captured["suite_path"] == Path("suite.json")
    assert captured["client"] == ("http://gateway", 45)
    assert captured["output_dir"] == tmp_path
    assert captured["scenario_ids"] == {"s1"}
    assert captured["repetitions"] == 2
    assert captured["include_manual"] is False
    assert captured["manual_checkpoint"] is None
    assert captured["frozen_config"] is None
    assert captured["warmup_question"] is None
    assert captured["project_root"] == Path.cwd().resolve()
    assert json.loads(capsys.readouterr().out)["run_id"] == "run-1"


def test_catalyst_report_dispatches_directly_to_report_builder(
    monkeypatch, tmp_path, capsys
):
    report_path = tmp_path / "report.html"
    called = []
    monkeypatch.setattr(
        "harness.catalyst.report.build_report",
        lambda run_dir: called.append(run_dir) or report_path,
    )

    assert main(["catalyst", "report", str(tmp_path)]) == 0
    assert called == [tmp_path]
    assert str(report_path) in capsys.readouterr().out
