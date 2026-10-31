#!/usr/bin/env python3
"""Score every product check in a judged run against the judge rows.

Reads <run>/results.jsonl, the canonical <run>/judge.jsonl, every pass under
<run>/judges/<actor>/judge.jsonl and, when present, <run>/adjudication.jsonl. Writes
<run>/judges/check-precision.json and prints the table (per check: items marked, judged
errors, hits, precision, recall; overall and per arm; In-Depth per point when the judge
rows carry per-point verdicts). See harness/validate/check_precision.py for how each mark
and each judged error is read.

A run with no judge rows is reported and left unchanged; the exit status is 0 so the
judging pipeline never fails on this step.

Usage: scripts/check-precision.py <run_dir-or-id> [--accuracy-threshold 7] [--quiet]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.validate.check_precision import (  # noqa: E402
    DEFAULT_ACCURACY_THRESHOLD,
    score_run,
    table_text,
    write_scores,
)


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts/validate" / arg
    if cand.is_dir():
        return cand
    sys.exit(f"no run dir for {arg!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run", help="Run id or artifacts/validate/<run> directory")
    parser.add_argument(
        "--accuracy-threshold",
        type=float,
        default=DEFAULT_ACCURACY_THRESHOLD,
        help="A judged accuracy below this counts as a judged error (default %(default)s).",
    )
    parser.add_argument("--quiet", action="store_true", help="Write the file without the table.")
    args = parser.parse_args()
    rd = run_dir(args.run)
    data = score_run(rd, args.accuracy_threshold)
    if data is None:
        print(f"{rd.name}: no judge rows (judge.jsonl or judges/*/judge.jsonl); nothing scored")
        return 0
    path = write_scores(rd, data)
    if not args.quiet:
        print(table_text(data))
        print()
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
