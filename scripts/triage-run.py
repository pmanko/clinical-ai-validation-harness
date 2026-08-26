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


def _reader_led_run(run_dir: Path) -> bool:
    try:
        suite = json.loads((run_dir / "suite.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(suite, dict) and suite.get("reportMode") == "reader-led"


def _evidence_gaps(row: dict) -> list[str]:
    names = {_SLOT.sub("", a["name"]) for a in row.get("assertions") or []}
    gaps: list[str] = []
    if "token_evidence_recorded" not in names:
        gaps.append("token evidence never asserted")
    measurement = row.get("measurementEvidence") or {}
    query_paths = [measurement.get("base") or {}, *(measurement.get("turns") or [])]
    for index, query_path in enumerate(query_paths, start=1):
        if (
            query_path.get("outcome") == "ready"
            and query_path.get("oracleResult") != "recorded"
        ):
            label = "opening" if index == 1 else f"follow-up {index - 1}"
            gaps.append(f"{label} has no independent answer check")
    scenario = str(row.get("scenarioId"))
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
    run_dir = Path(args.run_dir)
    rows_path = run_dir / "rows.jsonl"
    reader_led = _reader_led_run(run_dir)
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
    answer_differences = 0
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
        answer_differences += 1
        signature = _signature(row)
        entry = vetted.get(signature)
        if entry is not None:
            dispositions[entry["disposition"]] += 1

    evidence_gaps = [
        (row, gaps)
        for row in rows
        if (reader_led or row.get("passed"))
        and (gaps := _evidence_gaps(row))
    ]

    if reader_led:
        incomplete_ids = {id(row) for row in invalid}
        incomplete_ids.update(id(row) for row, _ in evidence_gaps)
        complete_evidence = len(rows) - len(incomplete_ids)
        print(
            f"{len(rows)} conversations collected: "
            f"{complete_evidence} with complete evidence, "
            f"{len(evidence_gaps)} with evidence gaps, "
            f"{len(invalid)} invalid measurements"
        )
    else:
        passed = sum(1 for r in rows if r.get("passed"))
        print(
            f"{len(rows)} conversations: {passed} passed, "
            f"{answer_differences} judged failures, "
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
    for row, gaps in evidence_gaps:
        label = "EVIDENCE GAP" if reader_led else "VACUOUS PASS"
        print(
            f"\n{label} {row.get('profileId','?')} × "
            f"{row.get('scenarioId')} run {row.get('repetition')}: {gaps}"
        )
    if invalid or evidence_gaps:
        if reader_led:
            print(
                "\nTRIAGE FAILED: repair every invalid measurement (fix the "
                "cause, then resume the run) and close every evidence gap. "
                "Answer differences and database diagnostics remain evidence "
                "and never block a finish."
            )
        else:
            print(
                "\nTRIAGE FAILED: re-grade every invalid measurement (fix the "
                "cause, then resume the run) and close every vacuous pass. "
                "Judged failures are the data and never block a finish."
            )
        return 1
    if reader_led:
        print(
            "triage clean: every conversation has complete, internally "
            "consistent evidence"
        )
    else:
        print("triage clean: every conversation conformed, every pass exercised")
    return 0


if __name__ == "__main__":
    sys.exit(main())
