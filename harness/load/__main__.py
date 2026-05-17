"""CLI entry: python -m harness.load run [--target SCHEMA]"""

from __future__ import annotations

import argparse
import json
import sys

from harness.load.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.load")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run the loadback pipeline.")
    run.add_argument("--target", default="openmrs_test",
                     help="Target schema (default: openmrs_test).")
    args = p.parse_args(argv)

    if args.cmd == "run":
        report = run_pipeline(target_schema=args.target)
        print(json.dumps(report, indent=2, default=str))
        return 0
    p.error("unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
