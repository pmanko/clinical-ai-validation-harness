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


def _signature(row: dict) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _SLOT.sub("", a["name"])
                for a in row.get("assertions") or []
                if not a.get("passed")
            }
        )
    )


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
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    vetted = {
        tuple(entry["signature"]): entry
        for entry in json.loads(Path(args.vetted).read_text(encoding="utf-8"))
    }

    unvetted: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    dispositions: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("passed"):
            continue
        signature = _signature(row)
        entry = vetted.get(signature)
        if entry is None:
            unvetted[signature].append(row)
        else:
            dispositions[entry["disposition"]] += 1

    vacuous = [
        (row, gaps) for row in rows if row.get("passed") and (gaps := _pass_gaps(row))
    ]

    passed = sum(1 for r in rows if r.get("passed"))
    print(f"{len(rows)} rows: {passed} passed, {len(rows) - passed} failed")
    for disposition, count in sorted(dispositions.items()):
        print(f"  vetted {disposition}: {count} rows")
    for signature, offenders in unvetted.items():
        cells = sorted(
            {(r.get("profileId", "?"), r.get("scenarioId")) for r in offenders}
        )
        print(f"\nUNVETTED signature {list(signature)}")
        print(f"  cells: {cells}")
        first = offenders[0]
        for a in first.get("assertions") or []:
            if not a.get("passed"):
                evidence = a.get("evidence")
                if isinstance(evidence, dict) and isinstance(
                    evidence.get("disagreement"), str
                ):
                    evidence = evidence["disagreement"]
                print(f"    {a['name']} -> {json.dumps(evidence, default=str)[:200]}")
    for row, gaps in vacuous:
        print(
            f"\nVACUOUS PASS {row.get('profileId','?')} × {row.get('scenarioId')} "
            f"rep{row.get('repetition')}: {gaps}"
        )
    if unvetted or vacuous:
        print(
            "\nTRIAGE FAILED: disposition every unvetted signature (add it to "
            "the vetted ledger with a rationale) and close every vacuous pass."
        )
        return 1
    print("triage clean: every failure vetted, every pass exercised")
    return 0


if __name__ == "__main__":
    sys.exit(main())
