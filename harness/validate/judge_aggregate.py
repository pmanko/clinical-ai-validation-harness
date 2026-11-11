"""Aggregate several judge passes over one run into the canonical judge.jsonl."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import pathlib
import statistics
import sys
from typing import Any

from . import combine_judge_actors as combiner
from .agreement import pass_agreement
from .reconcile import (
    cell_benchmark_score,
    cell_indepth_benchmark_score,
    scout_summary,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]

NUMERIC = ("accuracy", "completeness", "relevance")
SEVERITY = {
    "abstention_outcome": ("failed-to-abstain", "over-abstained", "correct", "n-a"),
    "citation_groundedness": ("unsupported", "partly", "supported", "n-a"),
    "temporal_date_accuracy": ("wrong", "minor", "ok"),
    "temporal_window": ("over-claimed", "ok"),
    "temporal_trend": ("fabricated", "ok"),
}
TEMPORAL = ("temporal_date_accuracy", "temporal_window", "temporal_trend")
DEFAULT_CITATION_RESOLUTION = {
    "n_refs": 0,
    "n_resolved": 0,
    "n_unresolved": 0,
    "unresolved": [],
    "rate": None,
}


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    for base in (pathlib.Path.cwd(), ROOT):
        cand = base / "artifacts/validate" / arg
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


def _aggregate_background(bg_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate In-Depth (background) numeric and categorical axes across passes."""
    bg: dict[str, Any] = {}
    for axis in ("support", "added_value"):
        values = [
            b[axis]
            for b in bg_rows
            if isinstance(b.get(axis), (int, float)) and not isinstance(b.get(axis), bool)
        ]
        if values:
            med = statistics.median(values)
            bg[axis] = int(med) if float(med).is_integer() else round(float(med), 1)
    claims = [
        b["n_claims"]
        for b in bg_rows
        if isinstance(b.get("n_claims"), (int, float)) and not isinstance(b.get("n_claims"), bool)
    ]
    if claims:
        bg["n_claims"] = int(round(float(statistics.median(claims))))
    harm_votes = [b.get("no_new_harm") == "harm" for b in bg_rows if b.get("no_new_harm") is not None]
    if harm_votes:
        if sum(1 for h in harm_votes if h) * 2 >= len(harm_votes):
            bg["no_new_harm"] = "harm"
        else:
            safe_labels = [
                str(b["no_new_harm"]) for b in bg_rows if b.get("no_new_harm") not in (None, "harm")
            ]
            bg["no_new_harm"] = majority(safe_labels) if safe_labels else "none"
    conc = [str(b["conciseness"]) for b in bg_rows if b.get("conciseness") is not None]
    if conc:
        bg["conciseness"] = majority(conc, ("padded", "concise"))
    if any("note" in b for b in bg_rows):
        target = cell_indepth_benchmark_score(bg) or 0.0
        target_sup = float(bg.get("support") or 0.0)
        target_add = float(bg.get("added_value") or 0.0)
        nearest = min(
            bg_rows,
            key=lambda b: (
                abs((cell_indepth_benchmark_score(b) or 0.0) - target),
                abs(float(b.get("support") or 0.0) - target_sup)
                + abs(float(b.get("added_value") or 0.0) - target_add),
                str(b.get("note") or ""),
            ),
        )
        bg["note"] = nearest.get("note", "")
    return bg


_aggregate_indepth_records = _aggregate_background


def aggregate_cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One canonical row from the same cell's rows across passes."""
    if not rows:
        raise ValueError("cannot aggregate an empty cell")
    sid, bid = rows[0].get("scenario_id"), rows[0].get("backend_id")
    for r in rows:
        if cell_benchmark_score(r) is None or not isinstance(r.get("harm"), bool):
            raise ValueError(f"A judge row cannot be scored: {sid}/{bid}")
    out: dict[str, Any] = {"scenario_id": sid, "backend_id": bid}
    for axis in NUMERIC:
        values = [
            r[axis]
            for r in rows
            if isinstance(r.get(axis), (int, float)) and not isinstance(r.get(axis), bool)
        ]
        if values:
            median = statistics.median(values)
            out[axis] = int(median) if float(median).is_integer() else round(float(median), 1)
    for axis in ("abstention_outcome", "citation_groundedness"):
        values = [r[axis] for r in rows if r.get(axis) is not None]
        if values:
            out[axis] = majority(values, SEVERITY[axis])
    harms = [r["harm"] for r in rows]
    out["harm"] = harms.count(True) * 2 >= len(harms)
    claimed = [r for r in rows if any(k in r for k in TEMPORAL)]
    if claimed and len(claimed) * 2 >= len(rows):
        for axis in TEMPORAL:
            values = [r.get(axis, "ok") for r in claimed]
            out[axis] = majority(values, SEVERITY[axis])
    first_cr = rows[0].get("citation_resolution") or dict(DEFAULT_CITATION_RESOLUTION)
    for r in rows[1:]:
        other_cr = r.get("citation_resolution") or dict(DEFAULT_CITATION_RESOLUTION)
        if other_cr != first_cr:
            raise ValueError(f"conflicting citation_resolution for {sid}/{bid}")
    out["citation_resolution"] = first_cr
    target = cell_benchmark_score(out)
    if target is None:
        raise ValueError(f"A judge row cannot be scored: {sid}/{bid}")
    nearest = min(rows, key=lambda r: abs((cell_benchmark_score(r) or 0) - (target or 0)))
    out["note"] = nearest.get("note", "")
    bg_rows = [r["background"] for r in rows if isinstance(r.get("background"), dict)]
    if bg_rows and len(bg_rows) * 2 >= len(rows):
        out["background"] = _aggregate_background(bg_rows)
    return out


def aggregate(
    actor_rows: dict[str, list[dict[str, Any]]], *, allow_single: bool = False
) -> list[dict[str, Any]]:
    if not allow_single and len(actor_rows) < 2:
        raise ValueError("at least two distinct passes are needed to aggregate")
    keys = None
    by_actor = {}
    for actor, rows in actor_rows.items():
        index = {(r["scenario_id"], r["backend_id"]): r for r in rows}
        if len(index) != len(rows):
            raise ValueError(f"{actor} contains duplicate rows for the same cell")
        if keys is None:
            keys = set(index)
        elif set(index) != keys:
            raise ValueError(f"{actor} judged a different cell set than the first pass")
        by_actor[actor] = index
    if not keys:
        raise ValueError("cannot aggregate an empty cell matrix")
    out = []
    for key in sorted(keys):
        out.append(aggregate_cell([by_actor[a][key] for a in actor_rows]))
    return out


def validate_actor_provenance(rd: pathlib.Path, actors: list[str]) -> None:
    """Verify captured input hashes match across passes when recorded in actor manifests."""
    cell_hashes: dict[str, str] = {}
    for actor in actors:
        mpath = rd / "judges" / actor / "manifest.json"
        if not mpath.is_file():
            continue
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid manifest for {actor}: {exc}") from exc
        if isinstance(manifest, dict) and manifest.get("source_cells_sha256"):
            cell_hashes[actor] = str(manifest["source_cells_sha256"])
    if len(set(cell_hashes.values())) > 1:
        raise ValueError("passes were scored against different source_cells_sha256")
    cells_path = rd / "judge-cells.jsonl"
    if cell_hashes and cells_path.is_file():
        current_sha = hashlib.sha256(cells_path.read_bytes()).hexdigest()
        expected_sha = next(iter(cell_hashes.values()))
        if current_sha != expected_sha:
            raise ValueError("judge-cells.jsonl does not match actor source_cells_sha256")


def _commit_artifacts(rd: pathlib.Path, artifacts: dict[pathlib.Path, str]) -> None:
    """Atomically publish all aggregation artifacts under an exclusive lock, rolling back on failure."""
    judges_dir = rd / "judges"
    judges_dir.mkdir(parents=True, exist_ok=True)
    lock_path = judges_dir / ".aggregate.lock"
    with open(lock_path, "a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        backups: dict[pathlib.Path, bytes | None] = {}
        temps: dict[pathlib.Path, pathlib.Path] = {}
        replaced: list[pathlib.Path] = []
        try:
            for target, content in artifacts.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                backups[target] = target.read_bytes() if target.exists() else None
                tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(content)
                    fh.flush()
                    os.fsync(fh.fileno())
                temps[target] = tmp
            for target, tmp in temps.items():
                os.replace(tmp, target)
                replaced.append(target)
        except BaseException:
            for target in replaced:
                prev = backups.get(target)
                try:
                    if prev is None:
                        target.unlink(missing_ok=True)
                    else:
                        target.write_bytes(prev)
                except OSError:
                    pass
            for tmp in temps.values():
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            raise


def judge_of(manifest: dict[str, Any]) -> str:
    """One judge across its passes: agent, model and effort, as the actor id without the pass."""
    parts = [str(manifest.get(k) or "") for k in ("agent", "model", "reasoning_effort")]
    return "-".join(p for p in parts if p).lower() or str(manifest.get("actor_id") or "judge")


def judges_block(rd: pathlib.Path, actor_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for actor in actor_rows:
        try:
            manifest = json.loads((rd / "judges" / actor / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"actor_id": actor}
        groups.setdefault(judge_of(manifest), []).append(actor)
    if len(groups) < 2:
        return {}
    per_judge_rows = {
        judge: aggregate({a: actor_rows[a] for a in actors}, allow_single=True)
        for judge, actors in groups.items()
    }
    backends = sorted({r["backend_id"] for rows in per_judge_rows.values() for r in rows})
    agreement = pass_agreement(per_judge_rows)
    return {
        "per_judge": {
            judge: {"actors": actors, "scout": scout_summary(per_judge_rows[judge], backends)}
            for judge, actors in groups.items()
        },
        "alpha": agreement["alpha"],
        "thresholds": agreement["thresholds"],
        "spread_cells": agreement["spread_cells"],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("run")
    parser.add_argument("--actor", action="append", required=True, metavar="ID")
    args = parser.parse_args(argv)
    if len(args.actor) < 2:
        parser.error("at least two passes are needed to aggregate")
    if len(set(args.actor)) != len(args.actor):
        parser.error("duplicate --actor ids are not independent passes")
    rd = run_dir(args.run)
    validate_actor_provenance(rd, args.actor)
    actor_rows = {a: _rows(rd / "judges" / a / "judge.jsonl") for a in args.actor}
    rows = aggregate(actor_rows)
    combined = combiner.build({a: rd / "judges" / a / "judge.jsonl" for a in args.actor})
    consensus = pass_agreement(actor_rows)
    judges = judges_block(rd, actor_rows)
    if judges:
        consensus["judges"] = judges
    canonical_payload = {
        "schema_version": "judge_canonical.v1",
        "built_from": list(args.actor),
        "aggregation": "median-majority",
        "rules": {
            "numeric": "median",
            "categorical": "majority, tie to the worse outcome",
            "harm": "majority, tie counts as harmful",
            "background": "median numeric, majority categorical, harm tie counts as harmful",
            "note": "the pass whose Benchmark is nearest the aggregate's",
        },
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    _commit_artifacts(
        rd,
        {
            rd / "judge.jsonl": "".join(json.dumps(row) + "\n" for row in rows),
            rd / "judges" / "canonical.json": json.dumps(canonical_payload, indent=2) + "\n",
            rd / "judges" / "combined.json": json.dumps(combined, indent=2) + "\n",
            rd / "judges" / "consensus.json": json.dumps(consensus, indent=2) + "\n",
        },
    )
    print(f"aggregated {len(rows)} cells from {len(args.actor)} passes -> {rd / 'judge.jsonl'}")


if __name__ == "__main__":
    main()
