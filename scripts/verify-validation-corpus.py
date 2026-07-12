#!/usr/bin/env python3
"""Fail when a comparison set's live ledgers do not match its chart fixtures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.validate.corpus_alignment import (  # noqa: E402
    alignment_issues,
    expected_ledgers,
    live_records,
)

HUB_ROOT = ROOT / "targets" / "med-agent-hub"
sys.path.insert(0, str(HUB_ROOT))

from server.chart_serializer import render_chart  # noqa: E402  (hub package path above)


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

    expected = expected_ledgers(args.data_root, args.set)
    live = {}
    for patient in expected:
        snapshot, mappings = render_chart(
            live_records(args.endpoint, patient, args.username, args.password)
        )
        live[patient] = {"chart_snapshot": snapshot, "mappings": mappings}
    issues = alignment_issues(expected, live)
    if issues:
        print("ERROR: live validation corpus does not match committed chart fixtures:")
        for issue in issues:
            print(f"  - {issue}")
        print("Restore/reindex the intended corpus before running an evaluation.")
        return 1
    for patient, ledger in sorted(expected.items()):
        print(f"    {patient}: {len(ledger['mappings'])} exact fixture/live records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
