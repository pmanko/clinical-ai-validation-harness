"""Deterministic, no-LLM metrics derived from one chartsearchai /chat turn
(spec 006 FR-006.4). Pure function of the response envelope + timing — no model
call, no judgment.
"""

from __future__ import annotations

from typing import Any

# chartsearchai's /chat response returns only answer/disclaimer/references/blocks/
# session/messageId — it does NOT surface token counts, finish reasons, or the
# resolved model. Those are emitted null in v1 and back-filled from the OTel
# GenAI span when that correlation is wired (spec 006 SC-006.3, OTel-deferred).
_DEFERRED: dict[str, Any] = {
    "gen_ai.response.model": None,
    "tokens_in": None,
    "tokens_out": None,
    "finish_reasons": None,
}


def compute_metrics(
    *,
    envelope: dict[str, Any] | None,
    latency_ms: int,
    http_status: int,
    first_turn: bool,
) -> dict[str, Any]:
    ok = http_status == 200 and isinstance(envelope, dict)
    env = envelope if ok else {}
    answer = env.get("answer")
    answer_text = answer if isinstance(answer, str) else ""
    references = env.get("references")
    references = references if isinstance(references, list) else []
    citation_count = len(references)

    metrics: dict[str, Any] = {
        "latency_ms": latency_ms,
        "http_status": http_status,
        # Transport-level: chartsearchai returned a well-formed envelope. This is
        # NOT the LLM's own JSON adherence (that is parsed inside chartsearchai).
        "json_valid": ok and "answer" in env,
        "answer_chars": len(answer_text),
        "citation_count": citation_count,
        "references_empty": citation_count == 0,
        # Heuristic PROXY only: chartsearchai emits no answer-level abstention
        # flag, so abstention cannot be detected deterministically. references_empty
        # is the closest signal; the authoritative call is the human
        # abstention_outcome in the feedback doc (spec 006 FR-006.5).
        "abstained": citation_count == 0,
        # The first turn per (scenario, backend) carries model warmup / cold-start
        # latency; flag it so latency_ms isn't misread (spec 006 risk note).
        "first_turn": first_turn,
    }
    metrics.update(_DEFERRED)
    return metrics
