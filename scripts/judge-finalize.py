#!/usr/bin/env python3
"""Finalize the judge fan-out into judge.jsonl.

Takes the judge agents' SEMANTIC scores (the fan-out workflow's return value, saved as a
JSON array of rows) and merges back the deterministic parts from judge-cells.jsonl
(citation_resolution), drops the temporal_* axes when the answer made no temporal claim,
and keeps the background block only for team arms — emitting field names PINNED by the
clinical-answer-scoring spec so report.py/reconcile.py read them.

Usage: scripts/judge-finalize.py <run_dir-or-id> <workflow_rows.json>
"""
from __future__ import annotations
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts/validate" / arg
    if cand.is_dir():
        return cand
    sys.exit(f"no run dir for {arg!r}")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: judge-finalize.py <run_dir-or-id> <workflow_rows.json>")
    rd = run_dir(sys.argv[1])
    rows = json.load(open(sys.argv[2]))
    if isinstance(rows, dict):  # tolerate {result:[...]} or similar wrappers
        rows = rows.get("result") or rows.get("rows") or rows.get("return") or list(rows.values())

    # deterministic side-data per cell (citation_resolution, is_team)
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
        # background only for team arms that shipped an In-Depth section
        if cell.get("is_team") and isinstance(r.get("background"), dict):
            row["background"] = r["background"]
        out.append(row)

    out.sort(key=lambda x: (x["scenario_id"], x["backend_id"]))
    jpath = rd / "judge.jsonl"
    with open(jpath, "w") as fh:
        for row in out:
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {len(out)} judge rows -> {jpath}")
    if skipped:
        print(f"  SKIPPED {len(skipped)} (judge error/missing): {', '.join(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
