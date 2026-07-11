#!/usr/bin/env python3
"""Exercise a staged hub profile until its fast Answer or complete response."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def warm_profile(hub_url: str, profile: str, *, stop_after_answer: bool, timeout: int) -> dict:
    payload = {
        "model": profile,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Patient records (most recent first):\n"
                    "[1] (2026-07-10) Encounter: routine follow-up.\n"
                ),
            },
            {"role": "user", "content": "What was the latest visit date?"},
        ],
        "context": {"source": "inline"},
    }
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
        "answer_done_ms": answer_ms,
        "stop_after": "answer_done" if stop_after_answer else "done",
        "last_event": final_event,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-url", default="http://127.0.0.1:18081/v1/chat/completions")
    parser.add_argument("--profile", default="single-e4b-checked")
    parser.add_argument("--mode", choices=("answer", "full"), default="answer")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = warm_profile(
        args.hub_url,
        args.profile,
        stop_after_answer=args.mode == "answer",
        timeout=args.timeout,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
