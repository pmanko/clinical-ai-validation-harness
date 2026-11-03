"""Deterministic, no-LLM metrics derived from one chartsearchai /chat turn
(spec 006 FR-006.4). Pure function of the response envelope + timing — no model
call, no judgment.
"""

from __future__ import annotations

from typing import Any


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _first_int(*candidates: Any) -> int | None:
    for candidate in candidates:
        parsed = _int_or_none(candidate)
        if parsed is not None:
            return parsed
    return None


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
    usage = env.get("usage") if isinstance(env.get("usage"), dict) else {}
    context = env.get("context") if isinstance(env.get("context"), dict) else {}
    model = env.get("model") if isinstance(env.get("model"), str) and env.get("model") else None

    tokens_in = _first_int(
        env.get("inputTokens"),
        env.get("tokens_in"),
        usage.get("prompt_tokens"),
        usage.get("input_tokens"),
        context.get("input_tokens"),
    )
    tokens_out = _first_int(
        env.get("outputTokens"),
        env.get("tokens_out"),
        usage.get("completion_tokens"),
        usage.get("output_tokens"),
    )
    cached_tokens = _first_int(
        env.get("cachedTokens"),
        env.get("cached_tokens"),
        usage.get("cached_tokens"),
        usage.get("cache_n"),
    )

    cache_hit_ratio = (
        round(cached_tokens / tokens_in, 4)
        if tokens_in is not None and tokens_in > 0 and cached_tokens is not None
        else None
    )

    metrics: dict[str, Any] = {
        "latency_ms": latency_ms,
        "http_status": http_status,
        # Transport-level: chartsearchai returned a well-formed envelope. This is
        # NOT the LLM's own JSON adherence (that is parsed inside chartsearchai).
        "json_valid": ok and "answer" in env,
        "answer_chars": len(answer_text),
        "citation_count": citation_count,
        # The SOLE zero-citation proxy. chartsearchai emits no answer-level abstention flag, so
        # abstention cannot be detected deterministically — references_empty is only "the model
        # cited nothing," which also fires on a general/non-chart answer that legitimately needs no
        # citation. It must NOT be read as a real model abstention; the authoritative call is the
        # human abstention_outcome in the feedback doc (spec 006 FR-006.5). A former duplicate
        # `abstained` key (identical to this) was removed — it was unconsumed and inflated
        # apparent abstention rates in raw per-turn data.
        "references_empty": citation_count == 0,
        # The first turn per (scenario, backend) carries model warmup / cold-start
        # latency; flag it so latency_ms isn't misread (spec 006 risk note).
        "first_turn": first_turn,
        "gen_ai.response.model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cached_tokens": cached_tokens,
        "cache_hit_ratio": cache_hit_ratio,
        "finish_reasons": env.get("finish_reasons"),
    }

    stream_timings = env.get("stream_timings")
    if isinstance(stream_timings, dict):
        for key in (
            "ttft_ms",
            "preliminary_start_ms",
            "reasoning_start_ms",
            "answer_delta_start_ms",
            "answer_done_ms",
            "answer_validation_ms",
            "evidence_updated_ms",
            "indepth_done_ms",
            "turn_done_ms",
            "delta_count",
            "answer_delta_count",
            "itl_p50_ms",
            "itl_p95_ms",
            "tpot_ms",
        ):
            if key in stream_timings:
                metrics[key] = stream_timings[key]
    return metrics
