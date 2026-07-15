#!/usr/bin/env python3
"""Exercise a staged hub profile until its fast Answer or complete response."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def discover_default_profile(hub_url: str, *, timeout: int) -> str:
    suffix = "/v1/chat/completions"
    normalized = hub_url.rstrip("/")
    if not normalized.endswith(suffix):
        raise RuntimeError(
            f"hub URL must end with {suffix!r} to discover its product profiles"
        )
    models_url = f"{normalized[:-len(suffix)]}/v1/models"
    with urllib.request.urlopen(models_url, timeout=timeout) as response:
        payload = json.loads(response.read())
    defaults = [
        item
        for item in payload.get("data", [])
        if item.get("visibility") == "product"
        and item.get("available") is True
        and item.get("default") is True
    ]
    if len(defaults) != 1 or not str(defaults[0].get("id") or "").strip():
        raise RuntimeError(
            "hub must advertise exactly one available default product profile; "
            f"found {defaults!r}"
        )
    return str(defaults[0]["id"])


def warm_profile(
    hub_url: str,
    profile: str,
    *,
    stop_after_answer: bool,
    timeout: int,
    patient: str | None = None,
    question: str = "What was the latest visit date?",
) -> dict:
    if patient:
        messages = [{"role": "user", "content": question}]
        context = {"require_product_profile": True}
        context_mode = "patient"
    else:
        messages = [
            {
                "role": "user",
                "content": (
                    "Patient records (most recent first):\n"
                    "[1] (2026-07-10) Encounter: routine follow-up.\n"
                ),
            },
            {"role": "user", "content": question},
        ]
        context = {"source": "inline", "require_product_profile": True}
        context_mode = "inline"

    payload = {
        "model": profile,
        "stream": True,
        "messages": messages,
        "context": context,
    }
    if patient:
        payload["patient"] = patient
    request = urllib.request.Request(
        hub_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.monotonic()
    answer_ms = None
    final_event = None
    event = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode(errors="replace").strip()
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:") or event is None:
                continue
            final_event = event
            if event == "error":
                raise RuntimeError(line.split(":", 1)[1].strip())
            if event == "answer_done" and answer_ms is None:
                answer_ms = round((time.monotonic() - started) * 1000)
                if stop_after_answer:
                    break
            if event == "done":
                break
    if answer_ms is None:
        raise RuntimeError(f"Profile {profile!r} did not emit answer_done (last event: {final_event!r}).")
    return {
        "schema_version": "chartsearchai_local_warmup.v1",
        "profile": profile,
        "context_mode": context_mode,
        "answer_done_ms": answer_ms,
        "stop_after": "answer_done" if stop_after_answer else "done",
        "last_event": final_event,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-url", default="http://127.0.0.1:18081/v1/chat/completions")
    parser.add_argument("--profile")
    parser.add_argument("--mode", choices=("answer", "full"), default="answer")
    parser.add_argument("--patient")
    parser.add_argument("--question", default="What was the latest visit date?")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    profile = args.profile or discover_default_profile(args.hub_url, timeout=args.timeout)
    result = warm_profile(
        args.hub_url,
        profile,
        stop_after_answer=args.mode == "answer",
        timeout=args.timeout,
        patient=args.patient,
        question=args.question,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
