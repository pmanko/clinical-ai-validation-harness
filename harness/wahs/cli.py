"""CLI subcommands for WAHS (Washington Health Summary) evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .evaluator import (
    MAX_TOKEN_BUDGET,
    VALID_CONDENSE_MODES,
    VALID_CONTEXT_ARMS,
    VALID_EVALUATION_MODALITIES,
    WahsHubClient,
    build_wahs_report_packet,
    run_wahs_suite,
    score_wahs_run,
)


def _positive_token_budget(raw: str) -> int:
    try:
        val = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid token budget: {raw!r}") from exc
    if val <= 0 or val > MAX_TOKEN_BUDGET:
        raise argparse.ArgumentTypeError(
            f"token budget must be between 1 and {MAX_TOKEN_BUDGET} (got {val})"
        )
    return val


def _parse_seed_list(raw_seeds: list[str] | None) -> list[int] | None:
    if not raw_seeds:
        return None
    out: list[int] = []
    for item in raw_seeds:
        for tok in str(item).split(","):
            tok = tok.strip()
            if not tok:
                continue
            val = int(tok)
            if val not in out:
                out.append(val)
    return out or None


def configure_parser(parent: argparse._SubParsersAction[Any]) -> None:
    wahs = parent.add_parser(
        "wahs",
        help="Run and score WAHS (Washington Health Summary) FHIR R4 condensation & Q&A evaluations",
    )
    sub = wahs.add_subparsers(dest="wahs_action", required=True)

    run_p = sub.add_parser("run", help="Run a WAHS evaluation suite against WAHS Engine or Med Agent Hub")
    run_p.add_argument(
        "--cases",
        required=True,
        help="Path to wahs_eval_cases.jsonl",
    )
    run_p.add_argument(
        "--hub-url",
        default=None,
        help="WAHS Engine or Med Agent Hub base URL (default: $MED_AGENT_HUB_BASE_URL or http://127.0.0.1:8000)",
    )
    run_p.add_argument(
        "--direct-llm-url",
        default=None,
        help="Direct OpenAI /v1 LLM base URL for raw-fhir:* or direct-* baselines (default: $DIRECT_LLM_BASE_URL or --hub-url)",
    )
    run_p.add_argument(
        "--output-dir",
        default="artifacts/wahs",
        help="Directory to write the frozen WAHS run directory",
    )
    run_p.add_argument(
        "--budget",
        action="append",
        type=_positive_token_budget,
        dest="budgets",
        help=f"Target token budget(s) to evaluate in [1, {MAX_TOKEN_BUDGET}] (repeatable; defaults to each case's target_token_budgets)",
    )
    run_p.add_argument(
        "--context-arm",
        action="append",
        choices=VALID_CONTEXT_ARMS,
        dest="context_arms",
        help="Context representation arm(s) to evaluate (repeatable)",
    )
    run_p.add_argument(
        "--condense-mode",
        action="append",
        choices=VALID_CONDENSE_MODES,
        dest="condense_modes",
        help="Condensation mode(s) to evaluate (repeatable)",
    )
    run_p.add_argument(
        "--profile",
        action="append",
        dest="profiles",
        help="WAHS profile ID(s) (e.g. wahs-engine-kb:gemma-e4b@4k, wahs-engine-rag:qwen3.5-9b@4k, wahs-engine-tools:gemma-26b@4k, raw-fhir:gemma-e4b@4k) (repeatable)",
    )
    run_p.add_argument(
        "--seeds",
        "--seed",
        action="append",
        dest="seeds",
        help="Evaluation seed(s), comma-separated or repeatable (e.g. --seeds 42,43,44)",
    )
    run_p.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature override (defaults to 0.2 when --seeds is set)",
    )
    run_p.add_argument(
        "--evaluation-modality",
        choices=VALID_EVALUATION_MODALITIES,
        default="deterministic_pipeline",
        help="Evaluation modality controlling Hub condensation/lookup mode and run metadata",
    )
    run_p.add_argument(
        "--resume",
        default=None,
        help="Prior partial WAHS run directory to resume from",
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

    report_p = sub.add_parser(
        "report",
        help="Generate a reproducible OpenClinAI report packet (report-data.json, dashboard-data.json, run-summary.json) from a WAHS run directory",
    )
    report_p.add_argument("run_dir", help="Completed WAHS run directory")
    report_p.add_argument(
        "--patients",
        default=None,
        help="Optional summary label for the patient cohort in meta.json",
    )


def dispatch(args: argparse.Namespace) -> int:
    if args.wahs_action == "score":
        summary = score_wahs_run(Path(args.run_dir))
        print(json.dumps(summary, indent=2))
        return 0 if (summary["passed_cells"] == summary["total_cells"] and not summary.get("incomplete")) else 1

    if args.wahs_action == "report":
        packet = build_wahs_report_packet(
            Path(args.run_dir),
            patients_summary=getattr(args, "patients", None),
        )
        print(json.dumps(packet, indent=2))
        return 0

    if args.wahs_action == "run":
        provenance = (
            json.loads(Path(args.target_provenance).read_text(encoding="utf-8"))
            if args.target_provenance
            else None
        )
        parsed_seeds = _parse_seed_list(getattr(args, "seeds", None))
        client = WahsHubClient(
            base_url=args.hub_url,
            direct_llm_base_url=getattr(args, "direct_llm_url", None),
        )
        result = run_wahs_suite(
            args.cases,
            client=client,
            output_dir=args.output_dir,
            budgets=args.budgets,
            context_arms=getattr(args, "context_arms", None),
            condense_modes=getattr(args, "condense_modes", None),
            profiles=getattr(args, "profiles", None),
            seeds=parsed_seeds,
            temperature=getattr(args, "temperature", None),
            git_sha=args.git_sha,
            target_provenance=provenance,
            evaluation_modality=getattr(args, "evaluation_modality", "deterministic_pipeline"),
            resume_from=getattr(args, "resume", None),
        )
        print(json.dumps(result.summary, indent=2))
        return 0 if result.passed_cells == result.total_cells else 1

    raise ValueError(f"Unknown wahs action: {args.wahs_action}")
