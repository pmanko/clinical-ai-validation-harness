from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .config import HarnessConfig
from .import_smoke import run_import_smoke_stub
from .metadata import RunManifest, append_event, write_manifest
from .schema_diff import write_schema_diff
from .submodules import read_harness_git_sha


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clinical AI validation harness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema-diff", help="Emit schema diff artifacts")
    schema.add_argument(
        "--output-dir",
        default="artifacts/schema-diff",
        help="Directory to write schema diff artifacts",
    )

    smoke = sub.add_parser("import-smoke", help="Run import smoke checks")
    smoke.add_argument(
        "--output-dir",
        default="artifacts/import-smoke",
        help="Directory to write smoke artifacts",
    )

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
    val = sub.add_parser("validate", help="Scenario × backend comparison through chartsearchai")
    val_sub = val.add_subparsers(dest="validate_action", required=True)
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
    val_report = val_sub.add_parser("report", help="Render report.html from a completed run")
    val_report.add_argument("run_id", nargs="?", help="Run id under <output-dir>/")
    val_report.add_argument("--run-dir", help="Explicit run directory (overrides run_id)")
    val_report.add_argument("--output-dir", default="artifacts/validate")

    return parser


def _not_yet_implemented(command: str) -> int:
    print(
        f"{command}: not yet implemented",
        file=__import__("sys").stderr,
    )
    return 2


def _start_run(output_dir: Path, component: str, project_root: Path) -> tuple[Path, Path]:
    run_id = str(uuid4())
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component=component,
        git_sha=read_harness_git_sha(project_root),
        dataset_id="large-demo-data-2-7-0",
        dataset_version="2.7.0",
        schema_mapping_version="openmrs-2.7-to-2.8@v0",
        gen_ai_provider_name="lmstudio",
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


def main() -> int:
    import sys
    args = _build_parser().parse_args()
    config = HarnessConfig.from_defaults(Path("."))
    if args.command == "schema-diff":
        output_dir = Path(args.output_dir)
        _manifest, events = _start_run(output_dir, "schema-diff", config.project_root)
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
        _manifest, events = _start_run(output_dir, "import-smoke", config.project_root)
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

    if args.command == "validate":
        if args.validate_action == "run":
            from .validate.client import ChartSearchAiClient
            from .validate.runner import run_comparison

            result = run_comparison(
                comparison_set_id=args.comparison_set,
                client=ChartSearchAiClient(),
                data_root=args.data_root,
                output_dir=args.output_dir,
                project_root=config.project_root,
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
        return _not_yet_implemented(f"validate {args.validate_action}")

    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
