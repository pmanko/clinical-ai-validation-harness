#!/usr/bin/env python
"""Dev-eval instrument for the Tune phase (built incrementally under tdd-guard)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Reuse the harness client so the chartsearchai path is byte-for-byte the call
# the validation runner makes (new_session + basic auth + per-request override +
# envelope parse + rate-limit throttle).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.validate.client import ChartSearchAiClient  # noqa: E402

# Zabella Halambe — the demo patient the validation scenarios use.
DEFAULT_PATIENT = "dd75c020-1691-11df-97a5-7038c432aabf"

# The three representative questions, each probing a different answer shape.
QUESTIONS: list[tuple[str, str]] = [
    ("medications (table-worthy)", "What medications is this patient on?"),
    (
        "treatment + evidence (reasoning/KB)",
        "What is this patient being treated for, and is that regimen still "
        "guideline-recommended?",
    ),
    ("blood type (honest abstention)", "What is this patient's ABO blood type?"),
]

# A minimal synthetic chart for the raw direct-probe path only. med-agent-hub
# derives "the chart" from the first user message; with no OpenMRS behind it
# there is nothing real to send, so this stand-in just gives synthesis a target.
# It is deliberately thin and clearly NOT this patient's record.
_SYNTHETIC_CHART = (
    "Patient chart (SYNTHETIC — not a real record):\n"
    "[1] Order: Lamivudine 150 mg, route oral, 2006-06-06\n"
    "[2] Order: Nevirapine 200 mg, route oral, 2006-06-06\n"
    "[3] Order: Stavudine 30 mg, route oral, 2006-06-06\n"
    "[4] Condition: HIV disease, confirmed\n"
)


def _via_chartsearchai(
    base_url: str | None, patient: str, endpoint_url: str, model_name: str
) -> list[dict[str, Any]]:
    """Faithful path: real chart + schema assembled by chartsearchai; the
    downstream LLM is overridden to (endpoint_url, model_name) per request. Opens
    one session and threads the returned session id across the three turns."""
    client = ChartSearchAiClient(base_url=base_url)
    session = client.new_session(patient)
    out: list[dict[str, Any]] = []
    for label, question in QUESTIONS:
        res = client.chat(
            patient, session, question,
            endpoint_url=endpoint_url, model_name=model_name,
        )
        if res.envelope and res.envelope.get("session"):
            session = res.envelope["session"]  # adopt the server's session id
        out.append(
            {
                "label": label,
                "question": question,
                "status": res.status,
                "latency_ms": res.latency_ms,
                "envelope": res.envelope,
                "parsed_ok": isinstance(res.envelope, dict),
                "raw_text": res.raw_text,
            }
        )
    return out


def _via_openai_compat(endpoint_url: str, model_name: str) -> list[dict[str, Any]]:
    """Raw structure-only probe: POST straight at the bridge with a synthetic
    chart + the chart_answer schema; parse the envelope out of the OpenAI-compat
    content string. A non-JSON content reply is recorded (parsed_ok False) with
    the raw content kept — the probe never raises."""
    response_format = _chart_answer_response_format()
    out: list[dict[str, Any]] = []
    for label, question in QUESTIONS:
        body = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": f"{_SYNTHETIC_CHART}\nQuestion: {question}"}
            ],
            "response_format": response_format,
        }
        start = time.monotonic()
        try:
            resp = requests.post(endpoint_url, json=body, timeout=300.0)
            latency_ms = int((time.monotonic() - start) * 1000)
            status = resp.status_code
            raw_text = resp.text
            envelope: dict[str, Any] | None = None
            parsed_ok = False
            if status == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        envelope = parsed
                        parsed_ok = True
                    else:
                        raw_text = content
                except (json.JSONDecodeError, TypeError):
                    raw_text = content  # show the non-JSON content for debugging
        except requests.RequestException as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            status, raw_text, envelope, parsed_ok = -1, str(e), None, False
        out.append(
            {
                "label": label,
                "question": question,
                "status": status,
                "latency_ms": latency_ms,
                "envelope": envelope,
                "parsed_ok": parsed_ok,
                "raw_text": raw_text,
            }
        )
    return out


def _select_mode(url: str, direct: bool) -> str:
    """Dispatch on the --direct FLAG, not the URL. The positional endpoint_url is
    ALWAYS the downstream LLM target (LM Studio or med-agent-hub /v1/chat/completions);
    by default it is forwarded to chartsearchai as the per-request override (the
    faithful path the validation runner uses, with a real chart + the chart_answer
    schema chartsearchai assembles). --direct POSTs straight at it with a synthetic
    chart — a structure-only probe that skips chartsearchai. `url` is unused here on
    purpose: the endpoint is the LLM, never chartsearchai, so it can't disambiguate."""
    return "raw-openai-compat" if direct else "chartsearchai"


def _chart_answer_response_format() -> dict[str, Any]:
    """The exact chart_answer json_schema chartsearchai injects downstream
    (mirrors ChartAnswerResponseFormat.java). Sent on the raw direct path so
    synthesis is schema-constrained there too — otherwise 'envelope valid'
    would fail for a missing-schema reason rather than a prompt reason."""
    cell = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "refs": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["text", "refs"],
        "additionalProperties": False,
    }
    column = {
        "type": "object",
        "properties": {"key": {"type": "string"}, "label": {"type": "string"}},
        "required": ["key", "label"],
        "additionalProperties": False,
    }
    row = {
        "type": "object",
        "properties": {"cells": {"type": "object", "additionalProperties": cell}},
        "required": ["cells"],
        "additionalProperties": False,
    }
    block = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["table"]},
            "title": {"type": "string"},
            "columns": {"type": "array", "items": column},
            "rows": {"type": "array", "items": row},
        },
        "required": ["kind", "title", "columns", "rows"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citations": {"type": "array", "items": {"type": "integer"}},
            "blocks": {"type": "array", "items": block},
        },
        "required": ["answer", "citations", "blocks"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {"name": "chart_answer", "strict": True, "schema": schema},
    }


def _shape_check(envelope: dict[str, Any] | None, parsed_ok: bool) -> dict[str, bool]:
    """The Tune-phase signal: booleans only, never an assertion.

    - has_answer_section / has_in_depth_section: lenient look for the markdown
      headers the new structure is meant to carry (expect False on today's
      prompt — that's the point).
    - has_table: any block with kind == "table".
    - envelope_valid: parsed at all + answer is a str + blocks is a list.
    """
    env = envelope or {}
    answer = env.get("answer")
    blocks = env.get("blocks")
    answer_str = answer if isinstance(answer, str) else ""
    return {
        "has_answer_section": bool(re.search(r"\*\*\s*answer\s*\*\*", answer_str, re.I)),
        "has_in_depth_section": bool(
            re.search(r"\*\*\s*in[\s\-]?depth\s*\*\*", answer_str, re.I)
        ),
        "has_table": isinstance(blocks, list)
        and any(isinstance(b, dict) and b.get("kind") == "table" for b in blocks),
        "envelope_valid": parsed_ok
        and isinstance(answer, str)
        and isinstance(blocks, list),
    }


def render(results: list[dict[str, Any]]) -> str:
    """Format the per-question Tune-phase report as a single string.

    Per question: the label + question, HTTP status + latency, the four
    `_shape_check` booleans (the signal), and the RAW envelope answer + blocks
    (so a degraded/over-structured answer is visible verbatim). When the envelope
    never parsed, fall back to status + raw_text so an error turn still says
    something useful instead of a blank section.
    """
    lines: list[str] = []
    for r in results:
        envelope = r.get("envelope")
        parsed_ok = bool(r.get("parsed_ok"))
        sig = _shape_check(envelope, parsed_ok)
        lines.append("=" * 72)
        lines.append(f"[{r.get('label')}] {r.get('question')}")
        lines.append(
            f"  http_status={r.get('status')}  latency_ms={r.get('latency_ms')}  "
            f"parsed_ok={parsed_ok}"
        )
        lines.append(
            "  shape: "
            + "  ".join(f"{k}={str(v).lower()}" for k, v in sig.items())
        )
        if isinstance(envelope, dict):
            answer = envelope.get("answer")
            blocks = envelope.get("blocks")
            lines.append("  answer:")
            lines.append(_indent(answer if isinstance(answer, str) else json.dumps(answer)))
            lines.append("  blocks:")
            lines.append(_indent(json.dumps(blocks, indent=2, ensure_ascii=False)))
        else:
            lines.append("  (no parsed envelope — raw response below)")
            lines.append(_indent(str(r.get("raw_text", ""))))
    return "\n".join(lines)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + ln for ln in text.splitlines()) or prefix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("endpoint_url")
    parser.add_argument("model_name")
    parser.add_argument("--patient", default=DEFAULT_PATIENT)
    parser.add_argument("--chartsearch-base-url", default=None)
    parser.add_argument("--direct", action="store_true")
    args = parser.parse_args(argv)

    mode = _select_mode(args.endpoint_url, args.direct)
    if mode == "chartsearchai":
        results = _via_chartsearchai(
            args.chartsearch_base_url, args.patient, args.endpoint_url, args.model_name
        )
    else:
        results = _via_openai_compat(args.endpoint_url, args.model_name)

    print(f"mode={mode}  endpoint={args.endpoint_url}  model={args.model_name}")
    if mode == "chartsearchai":
        print(f"patient={args.patient}  (real chart + schema assembled by chartsearchai)")
    else:
        print("(--direct: synthetic chart, raw OpenAI-compat probe — NOT this patient's record)")
    print(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
