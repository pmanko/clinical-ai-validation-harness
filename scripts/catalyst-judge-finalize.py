#!/usr/bin/env python3
"""Finalize three catalyst-judge-v1 pass files into judge.jsonl + judge_manifest.json.

P2 scope (D6/D12): validate passes, require identical provider/model/model_version,
median-finalize axes, recompute composites. Does not require or mutate events.jsonl;
P4 appends evaluation events when a notebook events file is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.catalyst.reconcile import finalize_judge_row  # noqa: E402
from harness.common.jsonl import read_jsonl  # noqa: E402
from harness.metadata import append_event  # noqa: E402

JUDGE_SCHEMA_PATH = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "catalyst-judge-v1.schema.json"
)
MANIFEST_SCHEMA_PATH = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "catalyst-judge-manifest-v1.schema.json"
)
PASS_NAMES = ("judge.pass-1.jsonl", "judge.pass-2.jsonl", "judge.pass-3.jsonl")
EVENT_SCHEMA_VERSION = "harness.catalyst-notebook.event.v1"


def _load_validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_row(row: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate one judge row; raise ValueError with a useful message on failure."""
    try:
        Draft202012Validator(schema).validate(row)
    except ValidationError as exc:
        path = ".".join(str(p) for p in exc.path) or "row"
        raise ValueError(f"{path}: {exc.message}") from exc


def _cell_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (str(row["scenario_id"]), int(row["turn"]), str(row["version_id"]))


def _cell_key_str(key: tuple[str, int, str]) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def load_and_validate_passes(
    run_dir: Path,
    row_schema: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    passes: list[list[dict[str, Any]]] = []
    for name in PASS_NAMES:
        path = run_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing required pass file: {path}")
        rows = read_jsonl(path)
        if not rows:
            raise ValueError(f"pass file is empty: {path}")
        for idx, row in enumerate(rows, start=1):
            try:
                _validate_row(row, row_schema)
            except ValueError as exc:
                raise ValueError(f"{path}: line {idx}: {exc}") from exc
            expected_rep = PASS_NAMES.index(name) + 1
            if int(row.get("repetition", -1)) != expected_rep:
                raise ValueError(
                    f"{path}: line {idx}: repetition must be {expected_rep}, "
                    f"got {row.get('repetition')!r}"
                )
        passes.append(rows)
    return passes


def assert_identical_judge_identity(
    passes: list[list[dict[str, Any]]],
) -> tuple[str, str, str, str]:
    identities: set[tuple[str, str, str, str]] = set()
    for rows in passes:
        for row in rows:
            identities.add(
                (
                    str(row["provider"]),
                    str(row["model"]),
                    str(row["model_version"]),
                    str(row["rubric_sha256"]),
                )
            )
    if len(identities) != 1:
        raise ValueError(
            "mixed judge identity across passes; "
            "provider/model/model_version/rubric_sha256 must be identical: "
            f"{sorted(identities)}"
        )
    return next(iter(identities))


def group_cells(
    passes: list[list[dict[str, Any]]],
) -> dict[tuple[str, int, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for rows in passes:
        seen: set[tuple[str, int, str]] = set()
        for row in rows:
            key = _cell_key(row)
            if key in seen:
                raise ValueError(f"duplicate cell in one pass file: {key}")
            seen.add(key)
            grouped[key].append(row)
    for key, rows in grouped.items():
        if len(rows) != 3:
            raise ValueError(
                f"cell {key} must appear in all three passes, found {len(rows)}"
            )
    expected = set(grouped)
    for idx, rows in enumerate(passes, start=1):
        keys = {_cell_key(row) for row in rows}
        if keys != expected:
            raise ValueError(
                f"judge.pass-{idx}.jsonl cell set differs from the union of all passes"
            )
    return dict(grouped)


def _append_judge_evaluation_events(
    run_dir: Path,
    finalized_rows: list[dict[str, Any]],
) -> int:
    """Append one idempotent evaluation event per finalized judge cell.

    P2 fixtures without an event stream remain supported. Once a notebook
    stream exists, however, its run manifest and every judge evidence link are
    part of the publish contract and must resolve inside the run directory.
    """

    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return 0
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "events.jsonl is present but run_manifest.json is missing"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_manifest.json must contain a non-empty run_id")

    root = run_dir.resolve()
    for row in finalized_rows:
        for relative in row["evidence_paths"]:
            path = (run_dir / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError(
                    f"judge evidence path escapes the run directory: {relative}"
                )
            if not path.is_file():
                raise FileNotFoundError(f"judge evidence path not found: {relative}")

    existing = read_jsonl(events_path)
    existing_ids = {
        str(event["evaluation_id"])
        for event in existing
        if event.get("event_type") == "evaluation"
        and event.get("evaluation_type") == "catalyst_sql_judge"
        and event.get("evaluation_id")
    }
    appended = 0
    for row in finalized_rows:
        identity = ":".join(
            (
                run_id,
                str(row["scenario_id"]),
                str(row["turn"]),
                str(row["version_id"]),
                str(row["provider"]),
                str(row["model"]),
                str(row["model_version"]),
                str(row["rubric_sha256"]),
            )
        )
        evaluation_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if evaluation_id in existing_ids:
            continue
        axes = {
            name: int(row[name])
            for name in (
                "intent_fidelity",
                "sql_quality",
                "schema_discipline",
                "followup_coherence",
            )
            if name in row
        }
        rationales = {
            name: str(row[name])
            for name in (
                "intent_fidelity_rationale",
                "sql_quality_rationale",
                "schema_discipline_rationale",
                "followup_coherence_rationale",
            )
            if name in row
        }
        append_event(
            events_path,
            {
                "schema_version": EVENT_SCHEMA_VERSION,
                "event_type": "evaluation",
                "evaluation_type": "catalyst_sql_judge",
                "evaluation_id": evaluation_id,
                "run_id": run_id,
                "scenario_id": row["scenario_id"],
                "turn": row["turn"],
                "version_id": row["version_id"],
                "provider": row["provider"],
                "model": row["model"],
                "model_version": row["model_version"],
                "rubric_sha256": row["rubric_sha256"],
                "composite": row["composite"],
                "axes": axes,
                "rationales": rationales,
                "evidence_paths": [
                    "judge.jsonl",
                    "judge_manifest.json",
                    *row["evidence_paths"],
                ],
            },
        )
        existing_ids.add(evaluation_id)
        appended += 1
    return appended


def finalize(run_dir: Path | str) -> dict[str, Any]:
    """Finalize three pass files. Returns judge rows + manifest payload."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    row_schema = json.loads(JUDGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest_validator = _load_validator(MANIFEST_SCHEMA_PATH)
    passes = load_and_validate_passes(run_dir, row_schema)
    provider, model, model_version, rubric_sha256 = assert_identical_judge_identity(passes)
    grouped = group_cells(passes)

    finalized_rows: list[dict[str, Any]] = []
    axis_medians: dict[str, dict[str, int]] = {}
    composites: dict[str, int] = {}
    for key in sorted(grouped):
        row = finalize_judge_row(grouped[key])
        _validate_row(row, row_schema)
        finalized_rows.append(row)
        key_s = _cell_key_str(key)
        axes = {
            name: int(row[name])
            for name in (
                "intent_fidelity",
                "sql_quality",
                "schema_discipline",
                "followup_coherence",
            )
            if name in row
        }
        axis_medians[key_s] = axes
        composites[key_s] = int(row["composite"])

    judge_path = run_dir / "judge.jsonl"
    with judge_path.open("w", encoding="utf-8") as fh:
        for row in finalized_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    manifest = {
        "schema": "catalyst-judge-manifest-v1",
        "pass_paths": list(PASS_NAMES),
        "provider": provider,
        "model": model,
        "model_version": model_version,
        "rubric_sha256": rubric_sha256,
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "axis_medians": axis_medians,
        "composites": composites,
    }
    manifest_validator.validate(manifest)
    manifest_path = run_dir / "judge_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    appended_event_count = _append_judge_evaluation_events(run_dir, finalized_rows)
    return {
        "judge_rows": finalized_rows,
        "manifest": manifest,
        "judge_path": str(judge_path),
        "manifest_path": str(manifest_path),
        "appended_event_count": appended_event_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize catalyst-judge-v1 three-pass scores into judge.jsonl"
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Run directory containing judge.pass-1.jsonl .. judge.pass-3.jsonl",
    )
    args = parser.parse_args()
    try:
        result = finalize(args.run_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"wrote {result['judge_path']}")
    print(f"wrote {result['manifest_path']}")


if __name__ == "__main__":
    main()
