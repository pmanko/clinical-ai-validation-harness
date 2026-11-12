from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from .import_smoke import run_import_smoke_stub
from .metadata import RunManifest, append_event, write_manifest
from .schema_diff import write_schema_diff


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clinical AI validation harness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema-diff", help="Emit schema diff artifacts")
    schema.add_argument(
        "--output-dir",
        default="artifacts/schema-diff",
        help="Directory to write schema diff artifacts",
    )

    schema.add_argument("--git-sha", help="Caller-supplied runner revision (optional)")

    smoke = sub.add_parser("import-smoke", help="Run import smoke checks")
    smoke.add_argument(
        "--output-dir",
        default="artifacts/import-smoke",
        help="Directory to write smoke artifacts",
    )

    smoke.add_argument("--git-sha", help="Caller-supplied runner revision (optional)")

    # conceptmap subcommands
    cm = sub.add_parser("conceptmap", help="ConceptMap authoring and validation")
    cm_sub = cm.add_subparsers(dest="conceptmap_action", required=True)
    cm_sub.add_parser("validate", help="Validate the accepted ConceptMap against the profile")
    cm_sub.add_parser("seed-emit", help="Emit SQLMesh seed CSVs from the accepted ConceptMap")
    cm_sub.add_parser("candidates", help="Mine OCL for candidate target concepts (advisory)")

    # transform
    tr = sub.add_parser("transform", help="Run the SQLMesh transform")
    tr_sub = tr.add_subparsers(dest="transform_action", required=True)
    tr_run = tr_sub.add_parser("run", help="Plan + run the SQLMesh project; emit refapp_28_demo.sql")
    tr_run.add_argument("--output-dir", default="artifacts/transform")

    # sample
    sample = sub.add_parser("sample", help="Translation-coverage sampler")
    sample.add_argument("--seed", type=int, default=42)
    sample.add_argument("--records-per-bucket", type=int, default=5)
    sample.add_argument("--output-dir", default="artifacts/sample")

    # ocl
    ocl = sub.add_parser("ocl", help="OCL collection management")
    ocl_sub = ocl.add_subparsers(dest="ocl_action", required=True)
    ocl_sub.add_parser("refresh", help="Pin a new OCL collection snapshot")

    # manifest
    mf = sub.add_parser("manifest", help="Run-manifest operations")
    mf_sub = mf.add_subparsers(dest="manifest_action", required=True)
    mf_sub.add_parser("finalize", help="Close out a run manifest with reviewer signoffs")

    # validate
    val = sub.add_parser("validate", help="Scenario × backend clinical-answer comparison")
    val_sub = val.add_subparsers(dest="validate_action", required=True)
    val_check = val_sub.add_parser(
        "check", help="Validate a comparison set's execution transport before a run"
    )
    val_check.add_argument("comparison_set")
    val_check.add_argument("--data-root", default="datasets/validation")
    val_run = val_sub.add_parser(
        "run", help="Replay a comparison set against each backend; write results.jsonl"
    )
    val_run.add_argument(
        "comparison_set",
        nargs="?",
        default="demo",
        help="Comparison-set id under <data-root>/comparison_sets/ (default: demo)",
    )
    val_run.add_argument("--data-root", default="datasets/validation")
    val_run.add_argument("--output-dir", default="artifacts/validate")
    val_run.add_argument("--git-sha", help="Caller-supplied runner revision (optional)")
    val_run.add_argument("--target-provenance", help="JSON file of supplied target identity objects")
    val_run.add_argument("--arm-metadata", help="JSON file of arm cards keyed by backend id")
    val_run.add_argument("--corpus-provenance", help="JSON file of the supplied corpus restore receipt")
    val_run.add_argument("--trace-file", help="Supplied trace JSONL export to capture with this run")
    val_run.add_argument(
        "--resume",
        help="Prior run dir to resume from: scenario×backend cells that completed cleanly "
        "are carried over; only missing/partial cells are re-run.",
    )
    val_run.add_argument(
        "--reference-date",
        metavar="YYYY-MM-DD",
        help="Explicit 'now' for downstream temporal scoring, recorded on every result "
        "row (and passed to the chat client if it accepts a date field). Unset -> "
        "today's behavior (temporal scoring falls back to the data era).",
    )
    val_report = val_sub.add_parser(
        "report",
        help="Emit v2 JSON report packet (report-data.json, run-summary.json, dashboard-data.json) from a completed run",
    )
    val_report.add_argument("run_id", nargs="?", help="Run id under <output-dir>/")
    val_report.add_argument("--run-dir", help="Explicit run directory (overrides run_id)")
    val_report.add_argument("--output-dir", default="artifacts/validate")

    val_judge = val_sub.add_parser(
        "judge",
        help="Run blind-session or multi-judge evaluation passes over a completed run and emit v2 JSON report packet",
    )
    val_judge.add_argument("run_id", nargs="?", help="Run id under <output-dir>/")
    val_judge.add_argument("--run-dir", help="Explicit run directory (overrides run_id)")
    val_judge.add_argument("--output-dir", default="artifacts/validate")
    val_judge.add_argument(
        "--judge",
        dest="judges",
        action="append",
        metavar="AGENT:MODEL:EFFORT[:PASSES]",
        help="Judge specification (repeatable); default uses --agent with REVIEW_MODEL/REVIEW_REASONING",
    )
    val_judge.add_argument("--judge-passes", type=int, default=1, help="Number of passes per judge (default: 1)")
    val_judge.add_argument("--blind", action="store_true", help="Letter the arms and judge one scenario bundle per session")
    val_judge.add_argument("--add", action="store_true", help="Add judge passes to existing headline rather than replacing")
    val_judge.add_argument("--agent", default="claude", choices=("claude", "codex", "gemini", "human"))
    val_judge.add_argument("--work-dir", help="Working directory for judge prompt/session artifacts")

    val_expect = val_sub.add_parser(
        "expect", help="Check a completed run's answers against its scenarios' turn checks"
    )
    val_expect.add_argument("run_id", nargs="?", help="Run id under <output-dir>/")
    val_expect.add_argument("--run-dir", help="Explicit run directory (overrides run_id)")
    val_expect.add_argument("--output-dir", default="artifacts/validate")

    val_cite = val_sub.add_parser(
        "score-citations", help="Score a run's citations against a gold file of on-topic records"
    )
    val_cite.add_argument("run_id", nargs="?", help="Run id under <output-dir>/")
    val_cite.add_argument("--run-dir", help="Explicit run directory (overrides run_id)")
    val_cite.add_argument("--output-dir", default="artifacts/validate")
    val_cite.add_argument("--gold", required=True, help="Gold file: per cell present/ontopic/focus_uuids")
    val_cite.add_argument("--adjudication", help="Adjudicated off- and on-topic citations")

    val_adj = val_sub.add_parser(
        "adjudicate",
        help="Guided human review of a judged run: sample cells, present each against "
        "the chart, record human scores to adjudication.jsonl (resumable).",
    )
    val_adj.add_argument("run_id", help="Run id under <output-dir>/")
    val_adj.add_argument("--output-dir", default="artifacts/validate")
    val_adj.add_argument(
        "--review", default="triage",
        help="Which cells to review: triage | standard | full | <N> (a budget of N "
        "most-informative cells). Default: triage.",
    )
    val_adj.add_argument("--reviewer", default="local", help="Reviewer id recorded on each record")
    val_adj.add_argument(
        "--tier", default="owner", choices=["owner", "domain", "clinical"],
        help="Reviewer escalation tier (default: owner).",
    )
    val_adj.add_argument("--seed", type=int, default=0, help="Seed for the random calibration draw")
    val_adj.add_argument(
        "--from", dest="from_answers", metavar="answers.json",
        help="Non-interactive: apply a {'scenario|backend': {accuracy,completeness,"
        "relevance,harm,note}} map without prompting (scripted/test use).",
    )

    val_conc = val_sub.add_parser(
        "concurrency",
        help="Run N concurrent OpenMRS clinical user sessions and emit concurrency_summary.json",
    )
    val_conc.add_argument(
        "comparison_set",
        nargs="?",
        default="demo",
        help="Comparison-set id under <data-root>/comparison_sets/ (default: demo)",
    )
    val_conc.add_argument("--users", type=int, default=1, help="Concurrent clinical user sessions (e.g. 1, 2, 4)")
    val_conc.add_argument("--turns-per-user", type=int, default=1, help="Turns per concurrent session")
    val_conc.add_argument("--backend-id", help="Backend id from the comparison set (defaults to first)")
    val_conc.add_argument("--data-root", default="datasets/validation")
    val_conc.add_argument("--output-dir", default="artifacts/concurrency")
    val_conc.add_argument("--reference-date", metavar="YYYY-MM-DD", help="Optional reference date")
    val_conc.add_argument("--hardware-metadata", help="Optional JSON file of hardware tier/GPU/slot metadata")
    val_conc.add_argument("--ttft-slo-ms", type=float, default=3000.0, help="TTFT SLO threshold in ms for goodput (default: 3000)")
    val_conc.add_argument("--answer-done-slo-ms", type=float, default=10000.0, help="Answer-done SLO threshold in ms for goodput (default: 10000)")
    val_conc.add_argument("--tpot-slo-ms", type=float, default=50.0, help="TPOT SLO threshold in ms/token for goodput (default: 50)")

    from .catalyst.cli import configure_parser as configure_catalyst_parser
    from .wahs.cli import configure_parser as configure_wahs_parser

    configure_catalyst_parser(sub)
    configure_wahs_parser(sub)

    return parser


def _not_yet_implemented(command: str) -> int:
    print(
        f"{command}: not yet implemented",
        file=__import__("sys").stderr,
    )
    return 2


def _start_run(
    output_dir: Path, component: str, git_sha: str | None = None
) -> tuple[Path, Path]:
    run_id = str(uuid4())
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component=component,
        git_sha=git_sha,
        dataset_id="large-demo-data-2-7-0",
        dataset_version="2.7.0",
        schema_mapping_version="openmrs-2.7-to-2.8@v0",
        gen_ai_provider_name=None,
        evidence_status="development",
        decision_rationale=None,
        target_provenance=[],
    )
    manifest_path = output_dir / "run_manifest.json"
    events_path = output_dir / "events.jsonl"
    write_manifest(manifest_path, manifest)
    append_event(
        events_path,
        {
            "event_type": "run",
            "run_id": run_id,
            "component": component,
        },
    )
    return manifest_path, events_path


def main(
    argv: list[str] | None = None,
    *,
    project_root: Path | None = None,
) -> int:
    import sys
    args = _build_parser().parse_args(argv)
    root = Path(project_root or ".").resolve()
    if args.command == "schema-diff":
        output_dir = Path(args.output_dir)
        _manifest, events = _start_run(output_dir, "schema-diff", args.git_sha)
        diff_path, summary_path = write_schema_diff(output_dir)
        append_event(
            events,
            {
                "event_type": "evaluation",
                "check": "schema_diff",
                "diff_path": str(diff_path),
                "summary_path": str(summary_path),
            },
        )
        return 0

    if args.command == "import-smoke":
        output_dir = Path(args.output_dir)
        _manifest, events = _start_run(output_dir, "import-smoke", args.git_sha)
        result = run_import_smoke_stub()
        append_event(events, result.to_event())
        return 0

    if args.command == "conceptmap":
        return _not_yet_implemented(f"conceptmap {args.conceptmap_action}")
    if args.command == "transform":
        if args.transform_action == "run":
            from .transform.run import main as transform_main
            return transform_main([
                "--project-dir", "datasets/transforms/sqlmesh",
                "--conceptmap", "datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json",
            ])
        return _not_yet_implemented(f"transform {args.transform_action}")
    if args.command == "sample":
        return _not_yet_implemented("sample")
    if args.command == "ocl":
        return _not_yet_implemented(f"ocl {args.ocl_action}")
    if args.command == "manifest":
        return _not_yet_implemented(f"manifest {args.manifest_action}")

    if getattr(args, f"{args.command}_action", None) == "run":
        from .validate.live_dashboard import ensure_live_dashboard

        ensure_live_dashboard(
            project_root=root,
            output_dir=getattr(args, "output_dir", None),
        )

    if args.command == "catalyst":
        from .catalyst.cli import dispatch as dispatch_catalyst

        return dispatch_catalyst(args, project_root=root)

    if args.command == "wahs":
        from .wahs.cli import dispatch as dispatch_wahs

        return dispatch_wahs(args)

    if args.command == "validate":
        if args.validate_action in {"check", "run"}:
            from .validate.execution import validate_execution_contract
            from .validate.models import load_comparison_set
            from .validate.resolver import resolve_backends

            data_root = Path(args.data_root)
            comparison = load_comparison_set(
                data_root / "comparison_sets" / f"{args.comparison_set}.json"
            )
            backends = resolve_backends(
                comparison.backend_ids, data_root / "backends.json"
            )
            validate_execution_contract(comparison, backends)
            if args.validate_action == "check":
                print(
                    f"validate check {comparison.id}: {comparison.transport} transport, "
                    f"{len(backends)} compatible arms"
                )
                return 0
        if args.validate_action == "run":
            from .validate.client import (
                ChartSearchAiClient,
                MedAgentHubClient,
                OpenAICompatibleClient,
            )
            from .validate.runner import run_comparison

            if comparison.transport == "med-agent-hub":
                client = MedAgentHubClient()
            elif comparison.transport == "openai-compatible":
                client = OpenAICompatibleClient()
            else:
                client = ChartSearchAiClient()
            result = run_comparison(
                comparison_set_id=args.comparison_set,
                client=client,
                data_root=args.data_root,
                output_dir=args.output_dir,
                git_sha=args.git_sha,
                target_provenance=(
                    json.loads(Path(args.target_provenance).read_text(encoding="utf-8"))
                    if args.target_provenance else None
                ),
                arm_metadata=(
                    json.loads(Path(args.arm_metadata).read_text(encoding="utf-8"))
                    if args.arm_metadata else None
                ),
                corpus_provenance=(
                    json.loads(Path(args.corpus_provenance).read_text(encoding="utf-8"))
                    if args.corpus_provenance else None
                ),
                resume_from=Path(args.resume) if args.resume else None,
                reference_date=args.reference_date,
                trace_file=args.trace_file,
            )
            print(
                f"validate run {args.comparison_set}: {result.result_count} results -> "
                f"{result.results_path}\nreport -> {result.report_path}"
            )
            return 0
        if args.validate_action == "report":
            from .validate.report import build_report

            run_dir = args.run_dir or str(Path(args.output_dir) / args.run_id)
            out = build_report(run_dir)
            print(f"report -> {out}")
            return 0
        if args.validate_action == "judge":
            from .validate.judge_runner import run_judge_command

            return run_judge_command(args)
        if args.validate_action == "expect":
            from .validate.expectations import check_run

            run_dir = Path(args.run_dir or Path(args.output_dir) / args.run_id)
            outcomes = check_run(run_dir)
            for o in outcomes:
                mark = "pass" if o["passed"] else "FAIL"
                print(f"{mark} {o['scenario_id']} turn {o['turn']} {o['backend_id']}"
                      + "".join(f"\n     {f}" for f in o["failures"]))
            failed = sum(not o["passed"] for o in outcomes)
            print(f"{len(outcomes) - failed} of {len(outcomes)} checked turns passed"
                  f" -> {run_dir / 'expectations.jsonl'}")
            return 1 if failed or not outcomes else 0
        if args.validate_action == "score-citations":
            from .validate.citations import score_run

            run_dir = Path(args.run_dir or Path(args.output_dir) / args.run_id)
            out = score_run(run_dir, Path(args.gold),
                            Path(args.adjudication) if args.adjudication else None)
            print(json.dumps(out["summary"], indent=1))
            return 0 if out["summary"] else 1
        if args.validate_action == "adjudicate":
            from .validate.adjudicate import run_adjudication

            run_dir = Path(args.output_dir) / args.run_id
            # --review is triage|standard|full or a bare integer budget (N).
            if args.review.isdigit():
                mode, n = "budget", int(args.review)
            else:
                mode, n = args.review, None
            answers = None
            if args.from_answers:
                answers = __import__("json").loads(
                    Path(args.from_answers).read_text(encoding="utf-8"))
            written = run_adjudication(
                run_dir=run_dir, mode=mode, n=n, reviewer_id=args.reviewer,
                reviewer_tier=args.tier, seed=args.seed, answers=answers,
            )
            print(
                f"adjudicate {args.run_id}: {written} cell(s) reviewed -> "
                f"{run_dir / 'adjudication.jsonl'}"
            )
            return 0
        if args.validate_action == "concurrency":
            from .validate.concurrency import run_concurrency_benchmark

            hw_meta = (
                json.loads(Path(args.hardware_metadata).read_text(encoding="utf-8"))
                if args.hardware_metadata
                else None
            )
            out = run_concurrency_benchmark(
                comparison_set_id=args.comparison_set,
                n_users=args.users,
                turns_per_user=args.turns_per_user,
                backend_id=args.backend_id,
                data_root=args.data_root,
                output_dir=args.output_dir,
                reference_date=args.reference_date,
                hardware_metadata=hw_meta,
                ttft_slo_ms=args.ttft_slo_ms,
                answer_done_slo_ms=args.answer_done_slo_ms,
                tpot_slo_ms=args.tpot_slo_ms,
            )
            print(json.dumps(out.summary, indent=2))
            return 0 if out.summary["error_turns"] == 0 else 1
        return _not_yet_implemented(f"validate {args.validate_action}")

    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
