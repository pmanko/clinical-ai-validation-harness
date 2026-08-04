"""Read + correlate the hub's per-turn reasoning-trace artifact to a results.jsonl cell.

The med-agent-hub appends one structured package per turn to ``artifacts/hub-trace/trace.jsonl``
(``team._write_trace``): the shipped answer + in-depth claims + per-section confidence {level, note}
+ the ordered call steps. New traces carry the request session as an exact correlation key. Older
traces are matched by level, exact question, and the timestamp nearest the cell completion time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl


def trace_model_for_result(result: dict[str, Any], fallback_model: str) -> str:
    """Return the model/profile identity recorded with a result, if available.

    Historical reports must not depend on today's backend registry: aliases may be
    renamed or deleted after a run while its trace still uses the original profile.
    """
    response_model = str((result.get("response") or {}).get("model") or "").strip()
    return response_model or fallback_model


def load_traces(trace_file: Path) -> list[dict[str, Any]]:
    """Parse the trace JSONL; tolerant of partial/malformed lines; [] if absent."""
    return read_jsonl(trace_file, strict=False)


def match_trace(
    traces,
    backend,
    started_at,
    ended_at,
    *,
    question=None,
    session=None,
    request_id=None,
):
    """Return the trace for one result cell without borrowing an adjacent turn.

    Prefer a turn-unique request id, then the stable request session, then the exact
    question (needed for historical traces), and finally the timestamp nearest the
    response completion. An explicit mismatching key returns no trace. The bounded
    time window remains a guard against stale runs.
    """
    import datetime as _dt

    def _p(v):
        try:
            return _dt.datetime.fromisoformat(v)
        except (ValueError, TypeError):
            return None

    def _request_key(tr):
        return str(
            ((tr.get("correlation") or {}).get("request_id"))
            or tr.get("request_id")
            or ""
        ).strip()

    def _session_key(tr):
        return str(
            ((tr.get("correlation") or {}).get("session"))
            or tr.get("session")
            or ""
        ).strip()

    def _question_key(tr):
        return str(tr.get("question") or "").strip()

    def _apply_explicit_key(candidates, wanted, key):
        if not wanted:
            return candidates
        keyed = [item for item in candidates if key(item[0])]
        matches = [item for item in keyed if key(item[0]) == wanted]
        if matches:
            return matches
        if keyed:
            return []
        return candidates

    backend_traces = [tr for tr in traces if tr.get("level_id") == backend]
    wanted_request_id = str(request_id or "").strip()
    wanted_session = str(session or "").strip()
    wanted_question = str(question or "").strip()
    if wanted_request_id:
        request_matches = [
            (tr, _p(tr.get("ts")))
            for tr in backend_traces
            if _request_key(tr) == wanted_request_id
        ]
        if request_matches:
            request_matches = _apply_explicit_key(
                request_matches, wanted_session, _session_key
            )
            request_matches = _apply_explicit_key(
                request_matches, wanted_question, _question_key
            )
            if not request_matches:
                return None
            en = _p(ended_at)
            if en:
                dated = [
                    item for item in request_matches if item[1] is not None
                ]
                if dated:
                    return min(dated, key=lambda item: abs(item[1] - en))[0]
            return request_matches[-1][0]

    st, en = _p(started_at), _p(ended_at)
    if not st or not en:
        return None
    lo, hi = st - _dt.timedelta(seconds=5), en + _dt.timedelta(seconds=5)
    candidates = []
    for tr in backend_traces:
        ts = _p(tr.get("ts"))
        if ts and lo <= ts <= hi:
            candidates.append((tr, ts))
    if not candidates:
        return None

    if wanted_request_id:
        request_candidates = [item for item in candidates if _request_key(item[0])]
        if request_candidates:
            return None

    candidates = _apply_explicit_key(candidates, wanted_session, _session_key)
    candidates = _apply_explicit_key(candidates, wanted_question, _question_key)
    if not candidates:
        return None

    return min(candidates, key=lambda item: abs(item[1] - en))[0]
