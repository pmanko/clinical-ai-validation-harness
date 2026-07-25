#!/usr/bin/env python3
"""Read a Querystore /drift JSON payload from stdin and enforce one readiness rule."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.validate.querystore_drift import evaluate_drift, render_drift  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--percent",
        type=float,
        default=float(os.getenv("QUERYSTORE_DRIFT_PCT", "5")),
    )
    parser.add_argument(
        "--absolute",
        type=int,
        default=int(os.getenv("QUERYSTORE_DRIFT_ABS", "50")),
    )
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"ERROR: invalid Querystore drift response: {exc}", file=sys.stderr)
        return 2
    try:
        rows, issues = evaluate_drift(
            payload,
            percent_threshold=args.percent,
            absolute_threshold=args.absolute,
        )
    except ValueError as exc:
        print(f"ERROR: invalid Querystore drift response: {exc}", file=sys.stderr)
        return 2
    print(render_drift(rows))
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
