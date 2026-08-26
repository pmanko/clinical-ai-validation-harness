"""CLI wiring for Catalyst notebook validation and report rendering."""

from __future__ import annotations

import argparse
import hashlib
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


def _reader_led_run(run_dir: Path) -> bool:
    """Return whether the frozen suite asks for the reader-led presentation."""

    try:
        suite = json.loads((run_dir / "suite.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(suite, dict) and suite.get("reportMode") == "reader-led"


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
    reader_rubric_path = None
    if args.run_config:
        # Read the public seed first so a deliberately disabled database
        # cross-check does not require a password it will never use.
        config = resolve(args.run_config, require_secrets=False)
        invocation = config["invocation"]
        args.suite = config["suite"]
        args.gateway_url = config["gatewayUrl"]
        args.output_dir = config["outputDir"]
        if args.scenarios is None:
            args.scenarios = invocation["scenarios"] or None
        if args.repetitions is None:
            args.repetitions = invocation["repetitions"]
        args.include_manual = args.include_manual or invocation["includeManual"]
        args.no_postgres_cross_check = (
            args.no_postgres_cross_check or not invocation["postgresCrossCheck"]
        )
        if not args.no_postgres_cross_check:
            config = resolve(args.run_config)
            args.postgres_dsn = postgres_dsn(config)
        if args.timeout_seconds is None:
            args.timeout_seconds = invocation["timeoutSeconds"]
        effective_scenarios = list(dict.fromkeys(args.scenarios or []))
        args.scenarios = effective_scenarios or None
        config["invocation"] = {
            "scenarios": effective_scenarios,
            "repetitions": args.repetitions,
            "includeManual": args.include_manual,
            "postgresCrossCheck": not args.no_postgres_cross_check,
            "timeoutSeconds": args.timeout_seconds,
        }
        if config.get("readerRubric"):
            candidate = Path(str(config["readerRubric"]))
            if not candidate.is_absolute():
                candidate = project_root / candidate
            if args.resume_from:
                frozen_candidate = Path(args.resume_from) / "reader-rubric.md"
                if frozen_candidate.is_file():
                    candidate = frozen_candidate
            try:
                rubric_bytes = candidate.read_bytes()
            except OSError as error:
                raise SystemExit(
                    f"cannot read reader rubric {candidate}: {error}"
                ) from error
            rubric_sha256 = hashlib.sha256(rubric_bytes).hexdigest()
            recorded_rubric_sha256 = str(config.get("readerRubricSha256") or "")
            if (
                recorded_rubric_sha256
                and recorded_rubric_sha256 != rubric_sha256
            ):
                raise SystemExit(
                    "reader rubric bytes differ from the frozen run configuration"
                )
            config["readerRubricSha256"] = rubric_sha256
            reader_rubric_path = candidate
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
        reader_rubric_path=reader_rubric_path,
    )
    if _reader_led_run(Path(result.run_dir)):
        summary = {
            "run_id": result.run_id,
            "run_dir": str(result.run_dir),
            "recorded_conversations": result.result_count,
            "skipped_conversations": result.skipped_count,
            "collection_complete": result.complete,
            "evidence_valid": result.measurement_valid,
        }
    else:
        # Older suites retain their historical command output for reproducibility.
        summary = {
            "run_id": result.run_id,
            "run_dir": str(result.run_dir),
            "passed": result.passed_count,
            "total": result.result_count,
            "skipped": result.skipped_count,
            "complete": result.complete,
            "measurement_valid": result.measurement_valid,
        }
    print(json.dumps(summary, indent=2))
    return 0 if result.complete and result.measurement_valid else 1
