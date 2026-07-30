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
from harness.validate.hub_trace import load_traces, match_trace  # noqa: E402
from harness.validate.model_registry import arm_model_name  # noqa: E402
from harness.validate.sources import build_sources, render_sources_for_judge, source_ref_labels  # noqa: E402
from harness.validate.response_artifacts import (  # noqa: E402
    in_depth_artifact,
    response_for_displayed_evidence,
    split_answer_sections,
)


def split_sections(answer: str) -> tuple[str, str]:
    """Historical script API; new consumers use ``split_answer_sections``."""
    direct, background = split_answer_sections(answer)
    return direct, (f"**In Depth**\n{background}" if background else "")


_SAFE_VALIDATION_KEYS = {
    "schema_version",
    "mode",
    "status",
    "applied",
    "id",
    "severity",
    "source_indices",
    "claim_index",
    "removed",
    "review_status",
    "review_removed",
    "review_attempts",
    "issues",
    "checks",
    "citation_checks",
    "gate",
}


def validation_metadata(value):
    """Keep deterministic lifecycle facts without exposing rejected model text."""
    if isinstance(value, list):
        return [
            sanitized
            for item in value
            if (sanitized := validation_metadata(item)) not in (None, {}, [])
        ]
    if not isinstance(value, dict):
        return value if isinstance(value, (bool, int, float)) else None
    sanitized = {}
    for key, item in value.items():
        if key not in _SAFE_VALIDATION_KEYS:
            continue
        if key in {"issues", "checks", "citation_checks"}:
            nested = validation_metadata(item)
            if nested:
                sanitized[key] = nested
        elif key == "gate":
            nested = validation_metadata(item)
            if nested:
                sanitized[key] = nested
        elif key in {"source_indices", "removed"}:
            sanitized[key] = [
                entry
                for entry in (item if isinstance(item, list) else [])
                if isinstance(entry, int) and not isinstance(entry, bool)
            ]
        elif isinstance(item, (str, bool, int, float)) or item is None:
            sanitized[key] = item
    return sanitized


def answer_validation_metadata(validation):
    """Compatibility name for the sanitized answer-validation metadata view."""
    return validation_metadata(validation)


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


def render_blocks(blocks: list, sources_v1: dict | None = None) -> str:
    """Flatten the envelope's structured `blocks` (tables) into readable text for the judge.

    The synthesis prompts instruct the model to put enumerations (medications, labs, problems, orders)
    in a `table` block and keep the prose `answer` a one-line summary — so for list questions the SUBSTANCE
    lives in `blocks`, not the prose. Without this, the judge sees only the prose and scores completeness as
    if the list were absent (the dominant completeness-deflation bug). Each row renders as
    "col=value; ..." plus one row-level Sources field. The canonical Evidence
    section carries source details separately, avoiding repeated per-cell refs.
    """
    if not isinstance(blocks, list):
        return ""
    labels_by_ref = source_ref_labels(sources_v1)
    out = []
    for b in blocks:
        if not isinstance(b, dict) or b.get("kind") != "table":
            continue
        cols = b.get("columns") or []
        labels = {c.get("key"): (c.get("label") or c.get("key")) for c in cols if isinstance(c, dict)}
        keys = [c.get("key") for c in cols if isinstance(c, dict) and c.get("key")]
        title = (b.get("title") or "Table").strip()
        lines = [f"[Table: {title}]"]
        for row in (b.get("rows") or []):
            cells = (row or {}).get("cells") or {}
            parts = []
            row_refs: list[int] = []
            for k in (keys or cells.keys()):
                cell = cells.get(k) or {}
                if not isinstance(cell, dict):
                    continue
                text = str(cell.get("text", "")).strip()
                if not text:
                    continue
                row_refs.extend(n for n in (cell.get("refs") or []) if isinstance(n, int))
                parts.append(f"{labels.get(k, k)}: {text}")
            if parts:
                source_labels = []
                seen = set()
                for ref in row_refs:
                    label = labels_by_ref.get(ref, f"[{ref}]")
                    if label not in seen:
                        seen.add(label)
                        source_labels.append(label)
                if source_labels:
                    parts.append("Sources: " + ", ".join(source_labels))
                lines.append("- " + "; ".join(parts))
        if len(lines) > 1:
            out.append("\n".join(lines))
    return "\n\n".join(out)


def main() -> None:
    rd = run_dir(sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: judge-prep.py <run>"))
    results = [json.loads(l) for l in open(rd / "results.jsonl")]
    traces = load_traces(rd.parent.parent / "hub-trace" / "trace.jsonl")
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
            ans, indepth = split_answer_sections(resp.get("answer"))
            indepth_artifact = in_depth_artifact(r, resp, indepth)
            evidence_response = response_for_displayed_evidence(
                resp, ans, indepth_artifact, indepth
            )
            sources_v1 = build_sources(evidence_response, chart)
            # Fold the structured table blocks into the answer the judge scores — for list questions the
            # substance lives in `blocks`, and the judge must see it or completeness is scored as absent.
            rendered = render_blocks(resp.get("blocks"), sources_v1)
            if rendered:
                ans = (ans + "\n\n" + rendered).strip() if ans else rendered
            evidence = render_sources_for_judge(sources_v1)
            if evidence:
                ans = (ans + "\n\n" + evidence).strip() if ans else evidence
            indepth = indepth_artifact["answer"]
            turns.append({
                "n": r.get("turn", 1),
                "question": next((t.get("question") for t in scen.get("turns", []) if t.get("n") == r.get("turn", 1)),
                                 (scen.get("turns") or [{}])[0].get("question")),
                "answer_section": ans,
                "in_depth_section": indepth,
                "answer_validation": answer_validation_metadata(
                    resp.get("answerValidation")
                ),
                "in_depth_status": indepth_artifact["status"],
                "in_depth_validation": validation_metadata(
                    indepth_artifact["validation"]
                ),
                "indepth_latency_ms": indepth_artifact["latency_ms"],
                "references": evidence_response.get("references") or [],
                "sources": sources_v1.get("sources") or [],
                "source_diagnostics": sources_v1.get("diagnostics") or {},
            })
        final = turns[-1]
        final_row = rows[-1]
        trace = match_trace(
            traces,
            arm_model_name(backend_id),
            final_row.get("started_at"),
            final_row.get("ended_at"),
            question=(final_row.get("request") or {}).get("question"),
            session=(final_row.get("request") or {}).get("session"),
            request_id=(final_row.get("request") or {}).get("request_id"),
        ) or {}
        cres = resolve_citations(final["references"], valid)
        has_in_depth = bool(final["in_depth_section"])
        is_team = has_in_depth or backend_id.startswith("med-agent-team")  # legacy field name
        p = chart.get("patient") or {}
        out.append({
            "scenario_id": scenario_id,
            "backend_id": backend_id,
            "is_team": is_team,
            "has_in_depth": has_in_depth,
            "score_background": has_in_depth,
            "patient": {k: p.get(k) for k in ("name", "gender", "birthdate", "slug")},
            "snapshot_file": str((snap_dir / f"{chart['_slug']}.snapshot.txt")),
            "should_abstain": ((scen.get("expectations") or {}).get("should_abstain")
                               or scen.get("should_abstain") or scen.get("expect_abstain") or False),
            "n_turns": len(turns),
            "turns": turns,
            "answer_section": final["answer_section"],
            "in_depth_section": final["in_depth_section"],
            "answer_validation": final.get("answer_validation"),
            "in_depth_status": final.get("in_depth_status"),
            "in_depth_validation": final.get("in_depth_validation"),
            "references": final["references"],
            "citation_resolution": cres,
            "sources": final.get("sources") or [],
            "source_diagnostics": final.get("source_diagnostics") or {},
            "temporal_gate": validation_metadata(trace.get("temporal_gate")),
            "temporal_facts_summary": trace.get("temporal_facts_summary"),
        })

    cells_path = rd / "judge-cells.jsonl"
    with open(cells_path, "w") as fh:
        for c in out:
            fh.write(json.dumps(c) + "\n")
    background = sum(1 for c in out if c.get("score_background"))
    print(f"wrote {len(out)} cells ({background} with In-Depth / {len(out)-background} answer-only) -> {cells_path}")
    print(f"snapshots -> {snap_dir}/*.snapshot.txt")


if __name__ == "__main__":
    main()
