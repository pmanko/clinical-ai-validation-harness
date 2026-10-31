#!/usr/bin/env python3
"""Aggregate several judge passes over one run into the canonical judge.jsonl.

Each pass is an actor under <run>/judges/<actor>/judge.jsonl, scored over the same cells.
Per cell the canonical row takes the median of the 0-10 axes, the majority of each
categorical axis, and the note of the pass whose Benchmark is nearest the aggregate's. A tie
on harm counts as harmful; a tie on another categorical axis takes the worse outcome. The
deterministic citation_resolution is identical across passes and copied as it is.

Writes <run>/judge.jsonl, <run>/judges/canonical.json (which passes, which rule),
<run>/judges/combined.json (per-cell actor scores and spread, as combine-judge-actors does)
and <run>/judges/consensus.json (Krippendorff's alpha per axis across the passes, with the
thresholds the page states, and the cells whose scores spread most).

Usage: scripts/judge-aggregate.py <run_dir-or-id> --actor <id> --actor <id> [...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.validate.agreement import pass_agreement  # noqa: E402
from harness.validate.reconcile import cell_benchmark_score, scout_summary  # noqa: E402

NUMERIC = ("accuracy", "completeness", "relevance")
# Worse outcomes first: a tie resolves to the earlier one.
SEVERITY = {
    "abstention_outcome": ("failed-to-abstain", "over-abstained", "correct", "n-a"),
    "citation_groundedness": ("unsupported", "partly", "supported", "n-a"),
    "temporal_date_accuracy": ("wrong", "minor", "ok"),
    "temporal_window": ("over-claimed", "ok"),
    "temporal_trend": ("fabricated", "ok"),
}
TEMPORAL = ("temporal_date_accuracy", "temporal_window", "temporal_trend")


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts/validate" / arg
    if cand.is_dir():
        return cand
    sys.exit(f"no run dir for {arg!r}")


def _rows(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def majority(values: list[Any], order: tuple[str, ...] | None = None) -> Any:
    """The most common value; on a tie the worst by ``order``, else the first seen."""
    counts = Counter(values)
    top = max(counts.values())
    tied = [v for v in values if counts[v] == top]
    if order:
        ranked = sorted(set(tied), key=lambda v: order.index(v) if v in order else len(order))
        return ranked[0]
    return tied[0]


def aggregate_cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One canonical row from the same cell's rows across passes."""
    out: dict[str, Any] = {"scenario_id": rows[0]["scenario_id"], "backend_id": rows[0]["backend_id"]}
    for axis in NUMERIC:
        values = [r[axis] for r in rows if isinstance(r.get(axis), (int, float)) and not isinstance(r.get(axis), bool)]
        if values:
            median = statistics.median(values)
            out[axis] = int(median) if float(median).is_integer() else round(float(median), 1)
    for axis in ("abstention_outcome", "citation_groundedness"):
        values = [r[axis] for r in rows if r.get(axis) is not None]
        if values:
            out[axis] = majority(values, SEVERITY[axis])
    harms = [bool(r.get("harm")) for r in rows]
    out["harm"] = harms.count(True) * 2 >= len(harms)  # a tie counts as harmful
    claimed = [r for r in rows if any(k in r for k in TEMPORAL)]
    if claimed and len(claimed) * 2 >= len(rows):
        for axis in TEMPORAL:
            values = [r.get(axis, "ok") for r in claimed]
            out[axis] = majority(values, SEVERITY[axis])
    out["citation_resolution"] = rows[0].get("citation_resolution") or {
        "n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "unresolved": [], "rate": None}
    target = cell_benchmark_score(out)
    nearest = min(rows, key=lambda r: abs((cell_benchmark_score(r) or 0) - (target or 0)))
    out["note"] = nearest.get("note", "")
    if isinstance(nearest.get("background"), dict):
        out["background"] = nearest["background"]
    return out


def aggregate(actor_rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    keys = None
    by_actor = {}
    for actor, rows in actor_rows.items():
        index = {(r["scenario_id"], r["backend_id"]): r for r in rows}
        if keys is None:
            keys = set(index)
        elif set(index) != keys:
            raise ValueError(f"{actor} judged a different cell set than the first pass")
        by_actor[actor] = index
    out = []
    for key in sorted(keys or []):
        out.append(aggregate_cell([by_actor[a][key] for a in actor_rows]))
    return out


def judge_of(manifest: dict[str, Any]) -> str:
    """One judge across its passes: agent, model and effort, as the actor id without the pass."""
    parts = [str(manifest.get(k) or "") for k in ("agent", "model", "reasoning_effort")]
    return "-".join(p for p in parts if p).lower() or str(manifest.get("actor_id") or "judge")


def judges_block(rd: pathlib.Path, actor_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """When the passes come from more than one judge: each judge's passes aggregated into
    one rating, its per-arm scores, and the agreement between the judges."""
    from harness.validate.agreement import pass_agreement
    groups: dict[str, list[str]] = {}
    for actor in actor_rows:
        try:
            manifest = json.loads((rd / "judges" / actor / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"actor_id": actor}
        groups.setdefault(judge_of(manifest), []).append(actor)
    if len(groups) < 2:
        return {}
    per_judge_rows = {judge: aggregate({a: actor_rows[a] for a in actors}) for judge, actors in groups.items()}
    backends = sorted({r["backend_id"] for rows in per_judge_rows.values() for r in rows})
    agreement = pass_agreement(per_judge_rows)
    return {
        "per_judge": {judge: {"actors": actors, "scout": scout_summary(per_judge_rows[judge], backends)}
                      for judge, actors in groups.items()},
        "alpha": agreement["alpha"], "thresholds": agreement["thresholds"],
        "spread_cells": agreement["spread_cells"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("run")
    parser.add_argument("--actor", action="append", required=True, metavar="ID")
    args = parser.parse_args()
    if len(args.actor) < 2:
        parser.error("at least two passes are needed to aggregate")
    rd = run_dir(args.run)
    actor_rows = {a: _rows(rd / "judges" / a / "judge.jsonl") for a in args.actor}
    rows = aggregate(actor_rows)
    with open(rd / "judge.jsonl", "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    (rd / "judges" / "canonical.json").write_text(json.dumps({
        "schema_version": "judge_canonical.v1",
        "built_from": list(args.actor),
        "aggregation": "median-majority",
        "rules": {"numeric": "median", "categorical": "majority, tie to the worse outcome",
                  "harm": "majority, tie counts as harmful",
                  "note": "the pass whose Benchmark is nearest the aggregate's"},
        "written_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("combine_judge_actors", ROOT / "scripts" / "combine-judge-actors.py")
    assert spec and spec.loader
    combiner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(combiner)
    combined = combiner.build({a: rd / "judges" / a / "judge.jsonl" for a in args.actor})
    (rd / "judges" / "combined.json").write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    consensus = pass_agreement(actor_rows)
    judges = judges_block(rd, actor_rows)
    if judges:
        consensus["judges"] = judges
    (rd / "judges" / "consensus.json").write_text(json.dumps(consensus, indent=2) + "\n", encoding="utf-8")
    print(f"aggregated {len(rows)} cells from {len(args.actor)} passes -> {rd / 'judge.jsonl'}")


if __name__ == "__main__":
    main()
