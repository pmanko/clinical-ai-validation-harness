#!/usr/bin/env python3
"""Audit citation/source shape for a completed validation run.

This is report-only: it reads results.jsonl plus scenario/chart fixtures and
prints deterministic counts for top-level refs, nested table refs, mismatches,
malformed tokens, unresolved refs, and table rows lacking refs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.common.jsonl import read_jsonl  # noqa: E402
from harness.validate.sources import audit_sources, build_sources, load_scenario_chart  # noqa: E402

DATA = ROOT / "datasets" / "validation"


def run_dir(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        return p
    cand = ROOT / "artifacts" / "validate" / arg
    if cand.is_dir():
        return cand
    raise SystemExit(f"no run dir for {arg!r}")


def summarize(rd: Path) -> dict:
    rows = read_jsonl(rd / "results.jsonl")
    cells = []
    totals = {
        "cells": 0,
        "top_level_refs": 0,
        "nested_refs": 0,
        "unique_nested_ref_sum": 0,
        "cells_with_top_nested_mismatch": 0,
        "cells_with_duplicated_nested_refs": 0,
        "malformed_tokens": 0,
        "unresolved_refs": 0,
        "rows_without_refs": 0,
    }
    chart_cache: dict[str, dict | None] = {}
    for row in rows:
        resp = row.get("response") if isinstance(row.get("response"), dict) else {}
        sid = row.get("scenario_id") or ""
        if sid not in chart_cache:
            chart_cache[sid] = load_scenario_chart(sid, DATA / "scenarios", DATA / "charts")
        sources_v1 = build_sources(resp, chart_cache[sid])
        d = audit_sources(resp, sources_v1)
        top = d.get("top_level_refs") or []
        nested = d.get("nested_refs") or []
        unique_nested = d.get("unique_nested_refs") or []
        mismatch = bool(d.get("top_only_refs") or d.get("nested_only_refs"))
        duplicated = bool(d.get("duplicated_nested_refs"))
        malformed = d.get("malformed_tokens") or []
        unresolved = d.get("unresolved_refs") or []
        rows_without = d.get("rows_without_refs") or []
        cell = {
            "scenario_id": sid,
            "backend_id": row.get("backend_id"),
            "top_level_refs": len(top),
            "nested_refs": len(nested),
            "unique_nested_refs": len(unique_nested),
            "top_only_refs": d.get("top_only_refs") or [],
            "nested_only_refs": d.get("nested_only_refs") or [],
            "duplicated_nested_refs": d.get("duplicated_nested_refs") or [],
            "malformed_tokens": malformed,
            "unresolved_refs": unresolved,
            "rows_without_refs": len(rows_without),
        }
        cells.append(cell)
        totals["cells"] += 1
        totals["top_level_refs"] += len(top)
        totals["nested_refs"] += len(nested)
        totals["unique_nested_ref_sum"] += len(unique_nested)
        totals["cells_with_top_nested_mismatch"] += int(mismatch)
        totals["cells_with_duplicated_nested_refs"] += int(duplicated)
        totals["malformed_tokens"] += len(malformed)
        totals["unresolved_refs"] += len(unresolved)
        totals["rows_without_refs"] += len(rows_without)
    return {"run_id": rd.name, "totals": totals, "cells": cells}


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit citation/source shape for a validate run")
    ap.add_argument("run", help="Run id or artifacts/validate/<run> directory")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()
    summary = summarize(run_dir(args.run))
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    t = summary["totals"]
    print(f"run {summary['run_id']} citation/source audit")
    print(
        "totals: "
        f"cells={t['cells']} top_level_refs={t['top_level_refs']} "
        f"nested_refs={t['nested_refs']} unique_nested_ref_sum={t['unique_nested_ref_sum']} "
        f"mismatch_cells={t['cells_with_top_nested_mismatch']} "
        f"duplicated_nested_cells={t['cells_with_duplicated_nested_refs']} "
        f"malformed_tokens={t['malformed_tokens']} unresolved_refs={t['unresolved_refs']} "
        f"rows_without_refs={t['rows_without_refs']}"
    )
    for c in summary["cells"]:
        flags = []
        if c["top_only_refs"]:
            flags.append(f"top_only={c['top_only_refs']}")
        if c["nested_only_refs"]:
            flags.append(f"nested_only={c['nested_only_refs']}")
        if c["duplicated_nested_refs"]:
            flags.append(f"dup_nested={c['duplicated_nested_refs']}")
        if c["malformed_tokens"]:
            flags.append(f"malformed={c['malformed_tokens']}")
        if c["rows_without_refs"]:
            flags.append(f"rows_without_refs={c['rows_without_refs']}")
        print(
            f"- {c['scenario_id']} / {c['backend_id']}: "
            f"top={c['top_level_refs']} nested={c['nested_refs']} "
            f"unique_nested={c['unique_nested_refs']}"
            + (f" | {'; '.join(flags)}" if flags else "")
        )


if __name__ == "__main__":
    main()
