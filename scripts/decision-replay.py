#!/usr/bin/env python3
"""Offline Phase 0a and 0b decision-layer extraction and replay CLI.

Extracts context-admission relevance pairs from ``gold.json`` (Phase 0a) and
Answer/In-Depth grounding, review-flag, and stage-timing items from captured
``full-default`` L5 ``trace.jsonl`` bundles (Phase 0b).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.validate.decision_replay import write_replay_bundle


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Phase 0a/0b decision-layer replay bundles (DECISION-LAYER-2026-10)."
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=None,
        help="Path to Phase 0a gold.json (5 patients x 8 topics).",
    )
    parser.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Path to Phase 0b trace.jsonl from a captured L5 validation run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where extracted JSONL/JSON artifacts and manifest.json are written.",
    )
    parser.add_argument(
        "--route",
        default="local/offline-extraction",
        help="Decision model route identifier (refuses typesafe/jev-router).",
    )
    parser.add_argument(
        "--model-version",
        default="laya-base-or-jev-1.13",
        help="Decision model version recorded in manifest.json.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = write_replay_bundle(
        args.output_dir,
        gold_path=args.gold,
        trace_path=args.trace,
        route=args.route,
        model_version=args.model_version,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
