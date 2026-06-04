"""Argparse-level smoke for the harness CLI subcommands.

The scaffolded subcommands (conceptmap / transform / sample / ocl /
manifest) print "not yet implemented" and exit 2 — these tests assert
the argument parsing and dispatch shape, not the future behavior.
"""

from __future__ import annotations

import sys

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

    class _Result:
        result_count = 0
        results_path = "r.jsonl"
        report_path = "report.html"

    def fake_run_comparison(**kw):
        captured.update(kw)
        return _Result()

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
