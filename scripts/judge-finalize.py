#!/usr/bin/env python3
"""Finalize the judge fan-out into judge.jsonl.

Takes the judge agents' SEMANTIC scores (the fan-out workflow's return value, saved as a
JSON array of rows) and merges back the deterministic parts from judge-cells.jsonl
(citation_resolution), drops the temporal_* axes when the answer made no temporal claim,
and keeps the background block for any arm that shipped In-Depth material — emitting field
names PINNED by the clinical-answer-scoring spec so report.py/reconcile.py read them.

By default this writes the canonical <run>/judge.jsonl that the report renderer consumes.
Pass --actor <id> to also store the pass at <run>/judges/<id>/judge.jsonl; actor passes are
not promoted to the canonical report file unless --promote is supplied.

Usage: scripts/judge-finalize.py <run_dir-or-id> <workflow_rows.json> [--actor <id>] [--promote]
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts/validate" / arg
    if cand.is_dir():
        return cand
    sys.exit(f"no run dir for {arg!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize judge fan-out rows into judge.jsonl")
    parser.add_argument("run", help="Run id or artifacts/validate/<run> directory")
    parser.add_argument("rows", help="Workflow rows JSON array/dict")
    parser.add_argument(
        "--actor",
        help="Optional independent judge actor id; writes judges/<actor>/judge.jsonl",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="When --actor is set, also copy this actor pass to root judge.jsonl for report rendering.",
    )
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Do not write root judge.jsonl. Mainly useful for explicitness with --actor.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rd = run_dir(args.run)
    rows = json.load(open(args.rows))
    if isinstance(rows, dict):  # tolerate {result:[...]} or similar wrappers
        rows = rows.get("result") or rows.get("rows") or rows.get("return") or list(rows.values())

    # Deterministic side-data per cell: citation_resolution and whether a separate
    # Background/In-Depth block should be retained. Older judge-cells used the
    # overloaded name "is_team"; keep it as a fallback for old runs.
    cells = {}
    for line in open(rd / "judge-cells.jsonl"):
        c = json.loads(line)
        cells[(c["scenario_id"], c["backend_id"])] = c

    out, skipped = [], []
    for r in rows:
        # Skip error rows AND empty rows (a rate-limited agent returns null -> the row has only
        # scenario_id/backend_id and no scores; those cells must be re-judged, not written).
        if not isinstance(r, dict) or r.get("_error") or "accuracy" not in r:
            skipped.append(r.get("scenario_id", "?") + "/" + r.get("backend_id", "?") if isinstance(r, dict) else "?")
            continue
        sid, bid = r["scenario_id"], r["backend_id"]
        cell = cells.get((sid, bid), {})
        row = {
            "scenario_id": sid,
            "backend_id": bid,
            "accuracy": r["accuracy"],
            "completeness": r["completeness"],
            "relevance": r["relevance"],
            "abstention_outcome": r["abstention_outcome"],
            "citation_groundedness": r["citation_groundedness"],
            "harm": bool(r["harm"]),
        }
        # temporal axes only when the answer actually made a temporal claim
        if r.get("has_temporal_claim"):
            row["temporal_date_accuracy"] = r.get("temporal_date_accuracy", "ok")
            row["temporal_window"] = r.get("temporal_window", "ok")
            row["temporal_trend"] = r.get("temporal_trend", "ok")
        row["citation_resolution"] = cell.get("citation_resolution") or {
            "n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "unresolved": [], "rate": None}
        row["note"] = r.get("note", "")
        score_background = (
            cell.get("score_background")
            if "score_background" in cell
            else cell.get("has_in_depth", cell.get("is_team"))
        )
        if score_background and isinstance(r.get("background"), dict):
            row["background"] = r["background"]
        out.append(row)

    out.sort(key=lambda x: (x["scenario_id"], x["backend_id"]))
    destinations: list[tuple[pathlib.Path, bool]] = []
    if args.actor:
        actor_dir = rd / "judges" / args.actor
        actor_dir.mkdir(parents=True, exist_ok=True)
        destinations.append((actor_dir / "judge.jsonl", False))
        promote = args.promote and not args.no_promote
    else:
        promote = not args.no_promote
    if promote:
        destinations.append((rd / "judge.jsonl", True))
    if not destinations:
        sys.exit("no output destination selected; omit --no-promote or pass --actor")

    for jpath, canonical in destinations:
        with open(jpath, "w", encoding="utf-8") as fh:
            for row in out:
                fh.write(json.dumps(row) + "\n")
        print(f"wrote {len(out)} judge rows -> {jpath}")
        if args.actor and not canonical:
            manifest = {
                "schema_version": "judge_actor.v1",
                "actor_id": args.actor,
                "actor_type": "llm-judge",
                "run_id": rd.name,
                "source_cells": "judge-cells.jsonl",
                "source_rows": str(pathlib.Path(args.rows)),
                "output": "judge.jsonl",
                "promoted_to_canonical": promote,
                "n_rows": len(out),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rubric": "clinical-answer-scoring/rubric.md",
            }
            (jpath.parent / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    if skipped:
        print(f"  SKIPPED {len(skipped)} (judge error/missing): {', '.join(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
