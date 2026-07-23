#!/usr/bin/env python3
"""Build + stage the Catalyst profile-comparison report (local staging only).

Reads the 5 completed notebook-validation run directories, renders the
comparison report via harness.catalyst.profile_comparison_report, stages it
under artifacts/reports/<slug>/, writes meta.json, and upserts
reports-index.json. Does not rsync — that's a separate, explicit step
(matches how scripts/publish-landing.sh / validate-publish.sh keep the
network push as its own reviewable action).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.catalyst.profile_comparison_report import build_comparison_report  # noqa: E402

SLUG = "catalyst-profile-comparison-2026-07-23"

ENTRIES = [
    {
        "run_dir": None,  # filled from sys.argv
        "profile_id": "catalyst-query-gemma-4-12b",
        "profile_label": "Gemma 12B writer (default)",
    },
    {
        "run_dir": None,
        "profile_id": "catalyst-query-gemma-e4b-14b",
        "profile_label": "Gemma E4B writer",
    },
    {
        "run_dir": None,
        "profile_id": "catalyst-query-qwen-coder-1.5b-e4b",
        "profile_label": "Qwen Coder 1.5B + Gemma E4B (small-only)",
    },
    {
        "run_dir": None,
        "profile_id": "catalyst-query-gemma-4-12b-checked",
        "profile_label": "Gemma 12B (self-checked)",
    },
    {
        "run_dir": None,
        "profile_id": "catalyst-query-checked",
        "profile_label": "Qwen 14B (self-checked)",
    },
]


def main() -> None:
    run_dirs = sys.argv[1:]
    if len(run_dirs) != len(ENTRIES):
        raise SystemExit(f"usage: {sys.argv[0]} <run_dir_for_each_of_{len(ENTRIES)}_profiles_in_order>")
    for entry, run_dir in zip(ENTRIES, run_dirs):
        entry["run_dir"] = Path(run_dir)

    html = build_comparison_report(
        ENTRIES,
        title="Catalyst query profile comparison — 5 writer/reviewer pairings",
    )

    dest = ROOT / "artifacts" / "reports" / SLUG
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(html, encoding="utf-8")
    print(f"==> staged {dest / 'index.html'}")

    totals = []
    for entry in ENTRIES:
        results = json.loads((entry["run_dir"] / "results.json").read_text(encoding="utf-8"))
        totals.append((entry["profile_label"], results["passedCount"], results["resultCount"]))
    scoreline = " · ".join(f"{label}: {p}/{t}" for label, p, t in totals)
    scoreline += " · 5 profiles, 4 scenarios x 3 repetitions each, 23 Jul 2026"

    meta = {
        "slug": SLUG,
        "run_dirs": [str(e["run_dir"].name) for e in ENTRIES],
        "family": "catalyst-profile-comparison",
        "scoreline": scoreline,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"==> wrote {dest / 'meta.json'}")

    idx_path = ROOT / "reports-index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    runs = idx.setdefault("runs", [])
    entry = {
        "slug": SLUG,
        "title": "Catalyst query profiles compared: 5 writer/reviewer pairings on the same suite",
        "summary": (
            "The same notebook-validation suite (4 scenario families x 3 repetitions, "
            "gold execution-match + independent PostgreSQL cross-checks) run once per "
            "candidate query profile: Gemma 12B (the shipped default) and Gemma E4B "
            "writers each reviewed by Qwen 2.5 14B, a small-only pairing (Qwen 2.5 "
            "Coder 1.5B writer reviewed by Gemma E4B), and two self-checked baselines "
            "(Gemma 12B and Qwen 14B, each reviewing its own output)."
        ),
        "takeaway": scoreline,
    }
    if any(r.get("slug") == SLUG for r in runs):
        print(f"==> {SLUG} already curated in reports-index.json — left as-is")
    else:
        runs.insert(0, entry)
        idx_path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")
        print(f"==> inserted {SLUG} at the top of reports-index.json")


if __name__ == "__main__":
    main()
