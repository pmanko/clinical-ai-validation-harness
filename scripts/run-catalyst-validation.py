#!/usr/bin/env python3
"""Run a governed Catalyst text-to-SQL experiment suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from harness.catalyst.validation import CatalystHttpClient, run_suite  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        default="datasets/validation/catalyst/catalyst-mvp-v1.json",
    )
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18000")
    parser.add_argument("--output-dir", default="artifacts/catalyst-validation")
    parser.add_argument("--scenario", action="append", dest="scenarios")
    parser.add_argument("--repetitions", type=int)
    args = parser.parse_args()
    result = run_suite(
        suite_path=Path(args.suite),
        client=CatalystHttpClient(args.gateway_url),
        output_dir=Path(args.output_dir),
        scenario_ids=set(args.scenarios) if args.scenarios else None,
        repetitions=args.repetitions,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "run_dir": str(result.run_dir),
                "passed": result.passed_count,
                "total": result.result_count,
            },
            indent=2,
        )
    )
    return 0 if result.passed_count == result.result_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
