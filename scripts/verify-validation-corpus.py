#!/usr/bin/env python3
"""Fail when a comparison set's live ledgers do not match its chart fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.validate.corpus_alignment import (
    alignment_issues,
    expected_record_dates,
    live_record_dates,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--data-root", type=Path, default=Path("datasets/validation")
    )
    args = parser.parse_args()

    expected = expected_record_dates(args.data_root, args.set)
    live = {
        patient: live_record_dates(
            args.endpoint, patient, args.username, args.password
        )
        for patient in expected
    }
    issues = alignment_issues(expected, live)
    if issues:
        print("ERROR: live validation corpus does not match committed chart fixtures:")
        for issue in issues:
            print(f"  - {issue}")
        print("Restore/reindex the intended corpus before running an evaluation.")
        return 1
    for patient, records in sorted(expected.items()):
        dated = [date for date in records.values() if date]
        print(
            f"    {patient}: {len(records)} fixture/live records; "
            f"latest {max(dated) if dated else 'undated'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
