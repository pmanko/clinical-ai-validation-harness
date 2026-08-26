#!/usr/bin/env python3
"""Prepare the full-evidence input for a Catalyst reader review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.catalyst.reader_review import (  # noqa: E402
    prepare_reader_review,
    validate_reader_reviews,
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--check-attached", action="store_true")
    args = parser.parse_args()
    try:
        out = prepare_reader_review(args.run_dir, args.rubric)
        if args.check_attached:
            reviews = validate_reader_reviews(args.run_dir)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"reader review input -> {out}")
    if args.check_attached:
        print(f"reader reviews verified -> {len(reviews)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
