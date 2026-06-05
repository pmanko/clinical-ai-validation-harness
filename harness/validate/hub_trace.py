"""Read + correlate the hub's per-turn reasoning-trace artifact to a results.jsonl cell.

The med-agent-hub appends one structured package per turn to ``artifacts/hub-trace/trace.jsonl``
(``team._write_trace``): the shipped answer + in-depth claims + per-section confidence {level, note}
+ the ordered call steps, keyed by ``level_id`` + an ISO ``ts``. chartsearchai drops the structured
``confidence`` envelope field, so the report/dashboard read it from this trace and correlate a cell by
``level_id == backend_id`` AND the trace ``ts`` falling inside the cell's ``[started_at, ended_at]``
window (the runner is strictly sequential, so the window maps to exactly one turn).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_traces(trace_file: Path) -> list[dict[str, Any]]:
    """Parse the trace JSONL; tolerant of partial/malformed lines; [] if absent."""
    p = Path(trace_file)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def match_trace(traces, backend, started_at, ended_at):
    """The trace whose level_id == backend and whose ts is in [started_at, ended_at] (±5s slack).
    Returns the latest such match, or None."""
    import datetime as _dt

    def _p(v):
        try:
            return _dt.datetime.fromisoformat(v)
        except (ValueError, TypeError):
            return None

    st, en = _p(started_at), _p(ended_at)
    if not st or not en:
        return None
    lo, hi = st - _dt.timedelta(seconds=5), en + _dt.timedelta(seconds=5)
    best = None
    for tr in traces:
        if tr.get("level_id") != backend:
            continue
        ts = _p(tr.get("ts"))
        if ts and lo <= ts <= hi:
            best = tr
    return best
