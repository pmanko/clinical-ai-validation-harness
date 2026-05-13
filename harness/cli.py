from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .config import HarnessConfig
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

    smoke = sub.add_parser("import-smoke", help="Run import smoke checks")
    smoke.add_argument(
        "--output-dir",
        default="artifacts/import-smoke",
        help="Directory to write smoke artifacts",
    )

    return parser


def _start_run(output_dir: Path, component: str) -> tuple[Path, Path]:
    run_id = str(uuid4())
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component=component,
        git_sha="unknown",
        dataset_id="large-demo-data-2-7-0",
        dataset_version="2.7.0",
        schema_mapping_version="openmrs-2.7-to-2.8@v0",
        gen_ai_system="lmstudio",
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


def main() -> None:
    args = _build_parser().parse_args()
    config = HarnessConfig.from_defaults(Path("."))
    if args.command == "schema-diff":
        output_dir = Path(args.output_dir)
        _manifest, events = _start_run(output_dir, "schema-diff")
        diff_path, summary_path = write_schema_diff(output_dir)
        append_event(
            events,
            {
                "event_type": "evaluation",
                "check": "schema_diff",
                "diff_path": str(diff_path),
                "summary_path": str(summary_path),
                "legacy_sql_path": str(config.legacy_sql_path),
            },
        )
        return

    if args.command == "import-smoke":
        output_dir = Path(args.output_dir)
        _manifest, events = _start_run(output_dir, "import-smoke")
        result = run_import_smoke_stub()
        append_event(events, result.to_event())
        return


if __name__ == "__main__":
    main()
