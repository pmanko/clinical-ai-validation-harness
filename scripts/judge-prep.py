#!/usr/bin/env python3
"""Deterministic prep for the clinical-answer-scoring judge fan-out.

Turns a completed run's results.jsonl into one judge CELL per (scenario_id, backend_id):
splits the team Answer/In-Depth sections, runs the deterministic citation resolution
(Layer 1 — resolve_citations against the chart fixture's valid_uuids), and attaches the
question(s) + patient demographics. Writes:

  <run>/judge-cells.jsonl        one cell per (scenario, backend) — the fan-out work-list
  <run>/charts/<slug>.snapshot.txt   the chart_snapshot text each judge agent reads

The semantic scoring (the rubric) is done by a Claude judge agent per cell; this script
only does the parts that must be deterministic + identical every run.

Usage: scripts/judge-prep.py <run_dir-or-run_id>
"""
from __future__ import annotations
import json, sys, pathlib, glob

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.validate.reconcile import resolve_citations  # noqa: E402

SCEN_DIR = ROOT / "datasets/validation/scenarios"
CHART_DIR = ROOT / "datasets/validation/charts"


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts/validate" / arg
    if cand.is_dir():
        return cand
    sys.exit(f"no run dir for {arg!r}")


def load_charts() -> dict[str, dict]:
    """uuid -> chart fixture dict (with chart_snapshot, valid_uuids, patient)."""
    by_uuid = {}
    for f in glob.glob(str(CHART_DIR / "*.json")):
        c = json.load(open(f))
        uuid = (c.get("patient") or {}).get("uuid")
        if uuid:
            c["_slug"] = (c.get("patient") or {}).get("slug") or pathlib.Path(f).stem
            by_uuid[uuid] = c
    return by_uuid


def split_sections(answer: str) -> tuple[str, str]:
    """(answer_section, in_depth_section). Team format: **Answer** ... **In Depth** ...
    Single-model answers have no **In Depth** -> in_depth is ''."""
    if not isinstance(answer, str):
        answer = "" if answer is None else str(answer)
    low = answer.lower()
    i = low.find("**in depth**")
    if i == -1:
        i = low.find("in depth")
        if i != -1 and "**" not in answer[max(0, i - 3):i]:
            i = -1  # only split on a real heading
    if i == -1:
        return answer.strip(), ""
    return answer[:i].strip(), answer[i:].strip()


def main() -> None:
    rd = run_dir(sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: judge-prep.py <run>"))
    results = [json.loads(l) for l in open(rd / "results.jsonl")]
    charts = load_charts()

    # dump the snapshots the judges read (once per patient slug)
    snap_dir = rd / "charts"
    snap_dir.mkdir(exist_ok=True)
    for c in charts.values():
        (snap_dir / f"{c['_slug']}.snapshot.txt").write_text(c.get("chart_snapshot") or "", encoding="utf-8")

    # group result rows by (scenario, backend), ordered by turn
    cells: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        if r.get("error"):
            continue
        cells.setdefault((r["scenario_id"], r["backend_id"]), []).append(r)
    for rows in cells.values():
        rows.sort(key=lambda r: r.get("turn", 1))

    out = []
    for (scenario_id, backend_id), rows in sorted(cells.items()):
        scen = json.load(open(SCEN_DIR / f"{scenario_id}.json"))
        uuid = scen.get("patient_ref")
        chart = charts.get(uuid)
        if not chart:
            print(f"  WARN: no chart fixture for {scenario_id} (patient {uuid})", file=sys.stderr)
            continue
        valid = set(chart.get("valid_uuids") or [])

        # all turns (Q + A); the cell is scored on the FINAL turn's answer with the convo as context
        turns = []
        for r in rows:
            resp = r.get("response") or {}
            if isinstance(resp, str):
                try: resp = json.loads(resp)
                except Exception: resp = {"answer": resp}
            ans, indepth = split_sections(resp.get("answer"))
            # Two-call architecture: the In-Depth is a SEPARATE nested artifact (its own call +
            # latency), not concatenated into the answer — use it as the in_depth_section so the
            # arm is background-judged (and a single-model arm finally gets a background score).
            nested = (r.get("indepth") or {}).get("response") or {}
            if isinstance(nested, str):
                try: nested = json.loads(nested)
                except Exception: nested = {"answer": nested}
            if nested.get("answer"):
                indepth = nested["answer"]
            turns.append({
                "n": r.get("turn", 1),
                "question": next((t.get("question") for t in scen.get("turns", []) if t.get("n") == r.get("turn", 1)),
                                 (scen.get("turns") or [{}])[0].get("question")),
                "answer_section": ans,
                "in_depth_section": indepth,
                "indepth_latency_ms": (r.get("indepth") or {}).get("latency_ms"),
                "references": resp.get("references") or [],
            })
        final = turns[-1]
        cres = resolve_citations(final["references"], valid)
        is_team = bool(final["in_depth_section"]) or backend_id.startswith("med-agent-team")
        p = chart.get("patient") or {}
        out.append({
            "scenario_id": scenario_id,
            "backend_id": backend_id,
            "is_team": is_team,
            "patient": {k: p.get(k) for k in ("name", "gender", "birthdate", "slug")},
            "snapshot_file": str((snap_dir / f"{chart['_slug']}.snapshot.txt")),
            "should_abstain": scen.get("should_abstain") or scen.get("expect_abstain") or False,
            "n_turns": len(turns),
            "turns": turns,
            "answer_section": final["answer_section"],
            "in_depth_section": final["in_depth_section"],
            "references": final["references"],
            "citation_resolution": cres,
        })

    cells_path = rd / "judge-cells.jsonl"
    with open(cells_path, "w") as fh:
        for c in out:
            fh.write(json.dumps(c) + "\n")
    teams = sum(1 for c in out if c["is_team"])
    print(f"wrote {len(out)} cells ({teams} team / {len(out)-teams} single) -> {cells_path}")
    print(f"snapshots -> {snap_dir}/*.snapshot.txt")


if __name__ == "__main__":
    main()
