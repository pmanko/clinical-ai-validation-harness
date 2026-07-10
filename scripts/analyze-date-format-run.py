#!/usr/bin/env python3
"""Quick malformed-date and temporal-gate scan for a validate run.

Usage:
  python scripts/analyze-date-format-run.py <run_id-or-run-dir>
"""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
BAD_DATE_PATTERNS = [
    re.compile(r"\bD\d{4}_\d{2}_\d{2}\b"),
    re.compile(r"\b(?:3025|205|25)-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{4}[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d]\d{2}[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d]\d{2}\b"),
    re.compile(r"\b\d{4}\s*[-_/]\s*\d{1,2}\s*[-_/]{2,}\s*\d{1,4}\b"),
    re.compile(r"\b\d{4}\s*[-_/]\s*\d{1,2}\s*[-_/]\s*\[[^\]\s]{1,8}\]"),
    re.compile(r"\b\d{4}-\d{1,2}\b(?!-)"),
    re.compile(r"(?<!D)\b\d{4}[_/]\d{1,2}[-_/]\d{1,2}\b"),
    re.compile(r"\b\d{4}-\d{1,2}[_/\s]\d{1,2}\b"),
    re.compile(
        r"\b(?=[\d\u0660-\u0669\u0966-\u096F/_-]*[\u0660-\u0669\u0966-\u096F])"
        r"[\d\u0660-\u0669\u0966-\u096F]{1,4}[-_/][\d\u0660-\u0669\u0966-\u096F]{1,2}"
        r"[-_/][\d\u0660-\u0669\u0966-\u096F]{1,4}\b"
    ),
]
SHORT_ISO_RE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")
EXACT_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LOCALIZED_DIGIT_RE = re.compile(r"[\u0660-\u0669\u0966-\u096F]+")


def _run_dir(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    return ROOT / "artifacts" / "validate" / arg


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)
    elif isinstance(value, str):
        yield value


def _answer_text(row: dict[str, Any]) -> str:
    resp = row.get("response") or {}
    if not isinstance(resp, dict):
        return str(resp)
    return "\n".join(_walk_strings({
        "answer": resp.get("answer") or "",
        "blocks": resp.get("blocks") or [],
    }))


def _bad_date_hits(text: str) -> list[str]:
    hits: set[str] = set()
    for pattern in BAD_DATE_PATTERNS:
        hits.update(pattern.findall(text))
    for match in SHORT_ISO_RE.findall(text):
        if not EXACT_ISO_RE.fullmatch(match):
            hits.add(match)
    return sorted(hits)


def _report_data(run_dir: Path) -> dict[str, Any]:
    report = run_dir / "report.html"
    if not report.exists():
        return {}
    text = report.read_text(encoding="utf-8")
    m = re.search(r"<script type='application/json' id='report-data'>(.*?)</script>", text, re.S)
    if not m:
        return {}
    return json.loads(html.unescape(m.group(1)))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    run_dir = _run_dir(argv[1])
    rows_path = run_dir / "results.jsonl"
    if not rows_path.exists():
        print(f"results not found: {rows_path}", file=sys.stderr)
        return 1

    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"run: {run_dir.name}")
    print(f"cells: {len(rows)}  errors: {sum(1 for r in rows if r.get('error'))}")

    print("\nMalformed date hits")
    by_backend: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    localized_digits_by_backend: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for row in rows:
        text = _answer_text(row)
        hits = _bad_date_hits(text)
        if hits:
            by_backend[row.get("backend_id", "")].append((row.get("scenario_id", ""), hits))
        localized_digits = sorted(set(LOCALIZED_DIGIT_RE.findall(text)))
        if localized_digits:
            localized_digits_by_backend[row.get("backend_id", "")].append(
                (row.get("scenario_id", ""), localized_digits)
            )
    for backend in sorted({r.get("backend_id", "") for r in rows}):
        cells = by_backend.get(backend, [])
        print(f"- {backend}: {len(cells)} cells, {sum(len(h) for _, h in cells)} hits")
        for scenario, hits in cells:
            print(f"  {scenario}: {', '.join(hits)}")

    if localized_digits_by_backend:
        print("\nLocalized non-ASCII digit hits (not counted as date hits)")
        for backend in sorted(localized_digits_by_backend):
            cells = localized_digits_by_backend[backend]
            print(f"- {backend}: {len(cells)} cells, {sum(len(h) for _, h in cells)} hits")
            for scenario, hits in cells:
                print(f"  {scenario}: {', '.join(hits)}")

    data = _report_data(run_dir)
    runs = data.get("runs") or []
    if not runs:
        return 0

    print("\nTemporal gate")
    run = runs[0]
    status_by: dict[str, Counter[str]] = defaultdict(Counter)
    applied_by: dict[str, Counter[str]] = defaultdict(Counter)
    checks_by: dict[str, Counter[str]] = defaultdict(Counter)
    examples: list[tuple[str, str, str, str, str, str]] = []
    for scenario in run.get("scenarios", []):
        sid = scenario.get("scenario_id", "")
        for turn in scenario.get("turns", []):
            for backend, cell in (turn.get("cells") or {}).items():
                gate = cell.get("temporal_gate") or {}
                status_by[backend][str(gate.get("status"))] += 1
                applied_by[backend][str(gate.get("applied"))] += 1
                for check in gate.get("checks") or []:
                    if check.get("status") != "pass":
                        cid = str(check.get("id"))
                        checks_by[backend][cid] += 1
                        examples.append((
                            backend,
                            sid,
                            cid,
                            str(check.get("status")),
                            str(gate.get("applied")),
                            str(check.get("reason") or "")[:180],
                        ))
    for backend in sorted(status_by):
        print(
            f"- {backend}: status={dict(status_by[backend])} "
            f"applied={dict(applied_by[backend])} checks={dict(checks_by[backend])}"
        )
    if examples:
        print("\nNon-pass examples")
        for backend, scenario, cid, status, applied, reason in examples[:40]:
            print(f"- {backend} / {scenario}: {cid} {status}, applied={applied}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
