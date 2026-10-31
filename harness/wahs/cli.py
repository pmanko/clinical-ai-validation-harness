"""CLI subcommands for WAHS (Washington Health Summary) evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .evaluator import WahsHubClient, run_wahs_suite, score_wahs_run


def configure_parser(parent: argparse._SubParsersAction[Any]) -> None:
    wahs = parent.add_parser(
        "wahs",
        help="Run and score WAHS (Washington Health Summary) FHIR R4 condensation & Q&A evaluations",
    )
    sub = wahs.add_subparsers(dest="wahs_action", required=True)

    run_p = sub.add_parser("run", help="Run a WAHS evaluation suite against Med Agent Hub")
    run_p.add_argument(
        "--cases",
        required=True,
        help="Path to wahs_eval_cases.jsonl",
    )
    run_p.add_argument(
        "--hub-url",
        default=None,
        help="Med Agent Hub base URL (default: $MED_AGENT_HUB_BASE_URL or http://127.0.0.1:8000)",
    )
    run_p.add_argument(
        "--output-dir",
        default="artifacts/wahs",
        help="Directory to write the frozen WAHS run directory",
    )
    run_p.add_argument(
        "--budget",
        action="append",
        type=int,
        dest="budgets",
        help="Target token budget(s) to evaluate (repeatable; defaults to each case's primary budget)",
    )
    run_p.add_argument("--git-sha", help="Caller-supplied runner revision (optional)")
    run_p.add_argument(
        "--target-provenance",
        help="JSON file of caller-supplied target provenance objects",
    )

    score_p = sub.add_parser(
        "score",
        help="Re-score a completed WAHS run directory offline from its frozen inputs",
    )
    score_p.add_argument("run_dir", help="Completed WAHS run directory")


def dispatch(args: argparse.Namespace) -> int:
    if args.wahs_action == "score":
        summary = score_wahs_run(Path(args.run_dir))
        print(json.dumps(summary, indent=2))
        return 0 if summary["passed_cells"] == summary["total_cells"] else 1

    if args.wahs_action == "run":
        provenance = (
            json.loads(Path(args.target_provenance).read_text(encoding="utf-8"))
            if args.target_provenance
            else None
        )
        client = WahsHubClient(base_url=args.hub_url)
        result = run_wahs_suite(
            args.cases,
            client=client,
            output_dir=args.output_dir,
            budgets=args.budgets,
            git_sha=args.git_sha,
            target_provenance=provenance,
        )
        print(json.dumps(result.summary, indent=2))
        return 0 if result.passed_cells == result.total_cells else 1

    raise ValueError(f"Unknown wahs action: {args.wahs_action}")
