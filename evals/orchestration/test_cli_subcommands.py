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
    (["transform",  "run"],      "transform run"),
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
