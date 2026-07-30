#!/usr/bin/env python3
"""Build a deterministic per-cell consensus from independent judge actor files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build(actor_paths: dict[str, Path]) -> dict:
    from harness.validate.reconcile import cell_benchmark_score, combined_judge_summary

    actor_rows = {actor: _rows(path) for actor, path in sorted(actor_paths.items())}
    keys = {
        (row["scenario_id"], row["backend_id"])
        for rows in actor_rows.values()
        for row in rows
    }
    if any(
        {(row["scenario_id"], row["backend_id"]) for row in rows} != keys
        for rows in actor_rows.values()
    ):
        raise ValueError("Independent actors did not judge the same cell matrix.")
    by_actor = {
        actor: {
            (row["scenario_id"], row["backend_id"]): row for row in rows
        }
        for actor, rows in actor_rows.items()
    }
    cells = []
    for scenario, backend in sorted(keys):
        scores = {
            actor: cell_benchmark_score(rows[(scenario, backend)])
            for actor, rows in by_actor.items()
        }
        if any(score is None for score in scores.values()):
            raise ValueError(f"A judge row cannot be scored: {scenario}/{backend}")
        values = [float(score) for score in scores.values() if score is not None]
        cells.append(
            {
                "scenario_id": scenario,
                "backend_id": backend,
                "actor_scores": scores,
                "consensus_score": round(sum(values) / len(values), 1),
                "actor_range": round(max(values) - min(values), 1),
            }
        )
    backends = sorted({backend for _scenario, backend in keys})
    return {
        "schema_version": "combined_judgment.v1",
        "actors": sorted(actor_rows),
        "cells": cells,
        "backend_summary": combined_judge_summary(actor_rows, backends),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--actor",
        action="append",
        required=True,
        metavar="ID=PATH",
        help="Independent actor id and judge.jsonl path; repeat at least twice.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actor_paths = {}
    for value in args.actor:
        actor, separator, path = value.partition("=")
        if not separator or not actor or actor in actor_paths:
            parser.error(f"invalid or duplicate --actor value: {value}")
        actor_paths[actor] = Path(path)
    if len(actor_paths) < 2:
        parser.error("at least two independent actors are required")
    result = build(actor_paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
