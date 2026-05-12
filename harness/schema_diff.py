from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _stub_schema_snapshot(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "tables": [],
        "columns": [],
        "indexes": [],
        "foreign_keys": [],
        "metadata": {
            "note": "Replace stub with real DB inspection query output.",
        },
    }


def build_schema_diff() -> dict[str, Any]:
    legacy = _stub_schema_snapshot("legacy_27_raw")
    refapp = _stub_schema_snapshot("refapp_28_clean")
    return {
        "legacy": legacy,
        "refapp": refapp,
        "diff": {
            "added_tables": [],
            "removed_tables": [],
            "changed_columns": [],
            "changed_indexes": [],
            "changed_foreign_keys": [],
            "unresolved_metadata_mappings": [],
        },
    }


def write_schema_diff(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    diff = build_schema_diff()
    diff_path = output_dir / "schema_diff.json"
    summary_path = output_dir / "summary.md"
    diff_path.write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(
        "\n".join(
            [
                "# Schema Diff Summary",
                "",
                "- Legacy source: `legacy_27_raw` (stub snapshot placeholder).",
                "- Ref App baseline: `refapp_28_clean` (stub snapshot placeholder).",
                "- This report is intentionally deterministic and reviewable.",
                "- Replace stub inspectors with real SQL introspection in next iteration.",
                "",
                "## Unresolved Mapping Blockers",
                "",
                "- (none yet)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return diff_path, summary_path
