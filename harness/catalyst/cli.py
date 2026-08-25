"""CLI wiring for Catalyst notebook validation and report rendering."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SUITE = "datasets/validation/catalyst/catalyst-notebook-t094-v1.json"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:18000"
DEFAULT_OUTPUT_DIR = "artifacts/catalyst-notebook-validation"
DEFAULT_POSTGRES_DSN = (
    "postgresql://catalyst_readonly:demo-readonly-change-me@"
    "127.0.0.1:15443/catalyst_analytics"
)


def configure_parser(parent: argparse._SubParsersAction[Any]) -> None:
    catalyst = parent.add_parser(
        "catalyst", help="Run and report Catalyst iterative-query validation"
    )
    sub = catalyst.add_subparsers(dest="catalyst_action", required=True)
    run = sub.add_parser(
        "run", help="Run the real Catalyst notebook acceptance matrix"
    )
    run.add_argument("--suite", default=DEFAULT_SUITE)
    run.add_argument(
        "--run-config",
        help="resolve and freeze one run seed before discovery or model calls",
    )
    run.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL)
    run.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    run.add_argument("--scenario", action="append", dest="scenarios")
    run.add_argument("--repetitions", type=int)
    run.add_argument(
        "--include-manual",
        action="store_true",
        help="include scenarios requiring an operator-controlled external failure",
    )
    run.add_argument(
        "--postgres-dsn",
        default=os.environ.get("CATALYST_VALIDATION_POSTGRES_DSN", DEFAULT_POSTGRES_DSN),
    )
    run.add_argument(
        "--no-postgres-cross-check",
        action="store_true",
        help="skip independent DB comparison (not valid for T094 acceptance)",
    )
    run.add_argument(
        "--resume",
        dest="resume_from",
        help=(
            "continue an interrupted run directory: every (team, scenario) "
            "already recorded there is reused and only the rest is run"
        ),
    )
    run.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="whole-request observation window; reviewed turns invoke roles sequentially",
    )

    report = sub.add_parser(
        "report", help="Render report.html from a completed Catalyst run"
    )
    report.add_argument("run_dir")


def _manual_checkpoint(scenario: Any, session_id: str) -> None:
    print(
        f"\nManual checkpoint for {scenario.id} (session {session_id}).\n"
        "Apply the bounded isolated Hub/tool failure now, then press Enter.\n"
        "Restore the Hub immediately after this scenario completes."
    )
    input()


def dispatch(args: argparse.Namespace, *, project_root: Path) -> int:
    if args.catalyst_action == "report":
        from .report import build_report

        out = build_report(Path(args.run_dir))
        print(f"report -> {out}")
        return 0

    if args.catalyst_action != "run":
        raise ValueError(f"unknown Catalyst action: {args.catalyst_action}")

    from .notebook_validation import (
        NotebookHttpClient,
        PostgresGoldExecutionChecker,
        PostgresReadOnlyChecker,
        run_notebook_suite,
    )
    from .run_config import postgres_dsn, publishable, resolve

    frozen_config = None
    warmup_question = None
    if args.run_config:
        config = resolve(args.run_config)
        invocation = config["invocation"]
        args.suite = config["suite"]
        args.gateway_url = config["gatewayUrl"]
        args.output_dir = config["outputDir"]
        args.postgres_dsn = postgres_dsn(config)
        if args.scenarios is None:
            args.scenarios = invocation["scenarios"] or None
        if args.repetitions is None:
            args.repetitions = invocation["repetitions"]
        args.include_manual = args.include_manual or invocation["includeManual"]
        args.no_postgres_cross_check = (
            args.no_postgres_cross_check or not invocation["postgresCrossCheck"]
        )
        if args.timeout_seconds is None:
            args.timeout_seconds = invocation["timeoutSeconds"]
        config["invocation"] = {
            "scenarios": list(args.scenarios or []),
            "repetitions": args.repetitions,
            "includeManual": args.include_manual,
            "postgresCrossCheck": not args.no_postgres_cross_check,
            "timeoutSeconds": args.timeout_seconds,
        }
        frozen_config = publishable(config)
        warmup_question = config.get("warmupQuestion") or None
    if args.timeout_seconds is None:
        args.timeout_seconds = 900

    checker = None
    gold_checker = None
    if not args.no_postgres_cross_check:
        checker = PostgresReadOnlyChecker(args.postgres_dsn)
        gold_checker = PostgresGoldExecutionChecker(args.postgres_dsn)

    result = run_notebook_suite(
        suite_path=Path(args.suite),
        client=NotebookHttpClient(
            args.gateway_url,
            timeout_seconds=args.timeout_seconds,
        ),
        output_dir=Path(args.output_dir),
        project_root=project_root,
        scenario_ids=set(args.scenarios) if args.scenarios else None,
        repetitions=args.repetitions,
        include_manual=args.include_manual,
        postgres_checker=checker,
        gold_checker=gold_checker,
        manual_checkpoint=_manual_checkpoint if args.include_manual else None,
        resume_from=Path(args.resume_from) if args.resume_from else None,
        frozen_config=frozen_config,
        warmup_question=warmup_question,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "run_dir": str(result.run_dir),
                "passed": result.passed_count,
                "total": result.result_count,
                "skipped": result.skipped_count,
                "complete": result.complete,
                "measurement_valid": result.measurement_valid,
            },
            indent=2,
        )
    )
    return 0 if result.complete and result.measurement_valid else 1
