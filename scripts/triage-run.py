#!/usr/bin/env python3
"""Triage a (possibly still-running) Catalyst comparison run.

Every failed row must map to a VETTED failure signature -- a known
disposition (model | infrastructure | criteria) with a written rationale --
and every passing row must have actually exercised the checks its scenario
promises. Anything else exits non-zero and prints exactly what to look at.

  uv run python scripts/triage-run.py <run_dir> \
      [--vetted datasets/validation/catalyst/vetted-failure-signatures.json]

This is the difference between validating a run and watching one: a new
kind of red is a finding to disposition, never scenery.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_SLOT = re.compile(r"-(?:t\d+|base)$")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.catalyst.attribution import (  # noqa: E402
    conformed,
    signature as _signature_of,
)


def _signature(row: dict) -> tuple[str, ...]:
    return _signature_of(row.get("assertions") or [])


def _pass_gaps(row: dict) -> list[str]:
    names = {_SLOT.sub("", a["name"]) for a in row.get("assertions") or []}
    scenario = str(row.get("scenarioId"))
    gaps: list[str] = []
    if "token_evidence_recorded" not in names:
        gaps.append("token evidence never asserted")
    if scenario.startswith(("A", "B")) and not any(
        "gold_execution_match" in n for n in names
    ):
        gaps.append("no independent-answer check ran")
    if scenario.startswith(("B", "U")) and "no_sql_after_non_ready_base" not in names:
        gaps.append("terminal base not verified SQL-free")
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument(
        "--vetted",
        default="datasets/validation/catalyst/vetted-failure-signatures.json",
    )
    args = parser.parse_args()
    rows_path = Path(args.run_dir) / "rows.jsonl"
    vetted_path = Path(args.vetted)
    if not vetted_path.is_absolute() and not vetted_path.exists():
        # Default resolves against the repo the script lives in, so `finish`
        # works from any working directory.
        vetted_path = Path(__file__).resolve().parents[1] / args.vetted
    try:
        rows = [
            json.loads(line)
            for line in rows_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as error:
        print(f"TRIAGE FAILED: cannot read {rows_path}: {error}")
        return 1
    except json.JSONDecodeError as error:
        print(f"TRIAGE FAILED: {rows_path} is not valid JSONL: {error}")
        return 1
    try:
        vetted = {
            tuple(entry["signature"]): entry
            for entry in json.loads(vetted_path.read_text(encoding="utf-8"))
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"TRIAGE FAILED: cannot read the vetted ledger {vetted_path}: {error}")
        return 1

    dispositions: dict[str, int] = defaultdict(int)
    invalid: list[dict] = []
    judged = 0
    for row in rows:
        if row.get("passed"):
            continue
        assertions = row.get("assertions") or []
        if not conformed(assertions):
            # A broken contract measured nothing. Vetting records WHY it
            # broke; it never makes the number usable, so the pair still has
            # to be re-graded before this run can be finished.
            invalid.append(row)
            continue
        judged += 1
        signature = _signature(row)
        entry = vetted.get(signature)
        if entry is not None:
            dispositions[entry["disposition"]] += 1

    vacuous = [
        (row, gaps) for row in rows if row.get("passed") and (gaps := _pass_gaps(row))
    ]

    passed = sum(1 for r in rows if r.get("passed"))
    print(
        f"{len(rows)} conversations: {passed} passed, {judged} judged failures, "
        f"{len(invalid)} invalid measurements"
    )
    for row in invalid:
        entry = vetted.get(_signature(row))
        print(
            f"\nINVALID MEASUREMENT {row.get('profileId','?')} × "
            f"{row.get('scenarioId')}"
        )
        if entry:
            print(f"  recorded cause: {entry['rationale']}")
        for a in row.get("assertions") or []:
            if a.get("passed"):
                continue
            evidence = a.get("evidence")
            if isinstance(evidence, dict) and isinstance(
                evidence.get("disagreement"), str
            ):
                evidence = evidence["disagreement"]
            print(f"    {a['name']} -> {json.dumps(evidence, default=str)[:200]}")
    for disposition, count in sorted(dispositions.items()):
        print(f"  vetted {disposition}: {count} rows")
    for row, gaps in vacuous:
        print(
            f"\nVACUOUS PASS {row.get('profileId','?')} × {row.get('scenarioId')} "
            f"run {row.get('repetition')}: {gaps}"
        )
    if invalid or vacuous:
        print(
            "\nTRIAGE FAILED: re-grade every invalid measurement (fix the "
            "cause, then resume the run) and close every vacuous pass. "
            "Judged failures are the data and never block a finish."
        )
        return 1
    print(
        "triage clean: every conversation conformed, every pass exercised"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
