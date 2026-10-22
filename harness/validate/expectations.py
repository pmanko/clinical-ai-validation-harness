"""Deterministic checks of a run's answers against per-turn `checks` in its scenarios.

A turn may carry:

- `cite_types`: resource types that must each appear among the answer's references;
- `cite_nothing`: true when the answer must carry no reference (an out-of-chart
  question); this is the zero-citation proxy, not a judgement of abstention;
- `answer_includes` / `answer_excludes`: case-insensitive regular expressions the
  answer text must or must not match.

Checks read only the run directory (its frozen scenarios and results), so they can be
re-run offline. They are deterministic findings, separate from judges and human review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import load_scenario

KNOWN = {"cite_types", "cite_nothing", "answer_includes", "answer_excludes"}


def check_turn(checks: dict[str, Any], row: dict[str, Any]) -> list[str]:
    unknown = set(checks) - KNOWN
    if unknown:
        return [f"unknown check(s): {', '.join(sorted(unknown))}"]
    envelope = row.get("response") if isinstance(row.get("response"), dict) else None
    if row.get("error") or envelope is None:
        return [f"no answer: {row.get('error') or 'empty response'}"]
    answer = envelope.get("answer") if isinstance(envelope.get("answer"), str) else ""
    refs = envelope.get("references") if isinstance(envelope.get("references"), list) else []
    cited = {r.get("resourceType") for r in refs if isinstance(r, dict)}
    failures = []
    missing = [t for t in checks.get("cite_types", []) if t not in cited]
    if missing:
        failures.append(f"no {', '.join(missing)} reference (cited: {', '.join(sorted(c for c in cited if c)) or 'nothing'})")
    if checks.get("cite_nothing") and refs:
        failures.append(f"{len(refs)} reference(s) on a question the chart cannot answer")
    for pattern in checks.get("answer_includes", []):
        if not re.search(pattern, answer, re.I):
            failures.append(f"answer does not match /{pattern}/")
    for pattern in checks.get("answer_excludes", []):
        if re.search(pattern, answer, re.I):
            failures.append(f"answer matches excluded /{pattern}/")
    return failures


def check_run(run_dir: Path) -> list[dict[str, Any]]:
    """Check every result row whose turn has checks; write expectations.jsonl."""
    scenarios = {}
    for path in sorted((run_dir / "inputs" / "scenarios").glob("*.json")):
        scenario = load_scenario(path)
        scenarios[scenario.id] = {t.n: t.checks for t in scenario.turns}
    outcomes = []
    results = run_dir / "results.jsonl"
    for line in results.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        checks = scenarios.get(row.get("scenario_id"), {}).get(row.get("turn"))
        if not checks:
            continue
        failures = check_turn(checks, row)
        outcomes.append({"scenario_id": row["scenario_id"], "backend_id": row.get("backend_id"),
                         "turn": row["turn"], "passed": not failures, "failures": failures})
    with (run_dir / "expectations.jsonl").open("w", encoding="utf-8") as fh:
        for outcome in outcomes:
            fh.write(json.dumps(outcome) + "\n")
    return outcomes
