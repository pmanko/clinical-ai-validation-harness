#!/usr/bin/env python3
"""Run the real Catalyst iterative-query notebook acceptance matrix."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from harness.catalyst.notebook_validation import (  # noqa: E402
    NotebookHttpClient,
    PostgresGoldExecutionChecker,
    PostgresReadOnlyChecker,
    run_notebook_suite,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        default="datasets/validation/catalyst/catalyst-notebook-t094-v1.json",
    )
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18000")
    parser.add_argument(
        "--output-dir", default="artifacts/catalyst-notebook-validation"
    )
    parser.add_argument("--scenario", action="append", dest="scenarios")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument(
        "--include-manual",
        action="store_true",
        help="include scenarios requiring an operator-controlled external failure",
    )
    parser.add_argument(
        "--postgres-dsn",
        default=os.environ.get(
            "CATALYST_VALIDATION_POSTGRES_DSN",
            "postgresql://catalyst_readonly:demo-readonly-change-me@"
            "127.0.0.1:15443/catalyst_analytics",
        ),
    )
    parser.add_argument(
        "--no-postgres-cross-check",
        action="store_true",
        help="skip independent DB comparison (not valid for T094 acceptance)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="whole-request observation window; reviewed turns invoke roles sequentially",
    )
    args = parser.parse_args()

    checker = None
    gold_checker = None
    if not args.no_postgres_cross_check:
        checker = PostgresReadOnlyChecker(args.postgres_dsn)
        gold_checker = PostgresGoldExecutionChecker(args.postgres_dsn)

    def manual_checkpoint(scenario, session_id: str) -> None:
        print(
            f"\nManual checkpoint for {scenario.id} (session {session_id}).\n"
            "Apply the bounded isolated Hub/tool failure now, then press Enter.\n"
            "Restore the Hub immediately after this scenario completes."
        )
        input()

    result = run_notebook_suite(
        suite_path=Path(args.suite),
        client=NotebookHttpClient(
            args.gateway_url, timeout_seconds=args.timeout_seconds
        ),
        output_dir=Path(args.output_dir),
        project_root=ROOT_DIR,
        scenario_ids=set(args.scenarios) if args.scenarios else None,
        repetitions=args.repetitions,
        include_manual=args.include_manual,
        postgres_checker=checker,
        gold_checker=gold_checker,
        manual_checkpoint=manual_checkpoint if args.include_manual else None,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "run_dir": str(result.run_dir),
                "passed": result.passed_count,
                "total": result.result_count,
                "skipped": result.skipped_count,
            },
            indent=2,
        )
    )
    return 0 if result.passed_count == result.result_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
