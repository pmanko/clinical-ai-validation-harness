#!/usr/bin/env python3
"""Engine-parity probe (AC-2): one identical turn through each provider, verbatim
engine-request artifacts out, then replay them against the engine from the host.

Per arm (bundled, hub):
  1. POST /chat/new {patient, provider} then /chat {patient, question, session,
     provider} through the product REST boundary — the same path the scored harness
     uses, so the captured traffic is exactly what production issues.
  2. Correlate the engine-tap captures for that arm's ingress (attribution is by
     ingress port; see scripts/engine-tap.py) taken since the turn started.
  3. Select the ANSWER-LEG request: among captures whose user messages contain the
     verbatim question, the largest body wins (a small query-rewrite call may also
     quote the question; the answer call carries the full serialized chart).
  4. Copy its exact bytes to <out_dir>/engine_request.<arm>.json and record every
     capture of the turn in <out_dir>/probe-manifest.json.
  5. Replay the artifact byte-for-byte against the engine endpoint; require a
     non-empty completion. This proves the captured interface is complete and
     externally queryable — including the bundled arm's.

Exit 0 only if both arms produced an artifact and both replays returned a
non-empty completion.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, NamedTuple
from uuid import uuid4

import requests


class Capture(NamedTuple):
    stem: str
    meta: dict[str, Any]
    body_path: Path


def new_captures(capture_dir: Path | str, arm: str, since_ns: int) -> list[Capture]:
    """All captures on `arm`'s ingress taken at or after `since_ns`, oldest first."""
    capture_dir = Path(capture_dir)
    out: list[Capture] = []
    for meta_path in capture_dir.glob("*.meta.json"):
        stem = meta_path.name[: -len(".meta.json")]
        try:
            t_ns = int(stem.split("-", 1)[0])
        except ValueError:
            continue
        if t_ns < since_ns:
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("arm") != arm:
            continue
        body_path = capture_dir / meta["body_file"]
        if body_path.exists():
            out.append(Capture(stem=stem, meta=meta, body_path=body_path))
    return sorted(out, key=lambda c: c.stem)


def select_answer_leg(captures: list[Capture], question: str) -> Capture:
    """The answer-generation engine call: contains the verbatim question in a user
    message; among candidates the largest body wins (ties -> earliest)."""
    candidates: list[tuple[int, int, Capture]] = []
    for i, capture in enumerate(captures):
        raw = capture.body_path.read_bytes()
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        messages = body.get("messages") if isinstance(body, dict) else None
        if not isinstance(messages, list):
            continue
        if any(
            m.get("role") == "user" and question in str(m.get("content", ""))
            for m in messages
            if isinstance(m, dict)
        ):
            candidates.append((len(raw), -i, capture))
    if not candidates:
        raise ValueError(
            f"no engine request contains the question verbatim among {len(captures)} capture(s)"
        )
    return max(candidates)[2]


def parse_completion(content_type: str, body: bytes) -> str:
    """Completion text from either a buffered chat.completions JSON or an SSE stream.
    Raises ValueError on an empty completion — replay must prove a real answer."""
    text = ""
    if (content_type or "").startswith("text/event-stream"):
        for line in body.decode("utf-8", errors="replace").splitlines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if not data or data == "[DONE]":
                continue
            try:
                frame = json.loads(data)
            except ValueError:
                continue
            for choice in frame.get("choices", []):
                delta = choice.get("delta") or choice.get("message") or {}
                text += str(delta.get("content") or "")
    else:
        payload = json.loads(body)
        choices = payload.get("choices") or []
        if choices:
            text = str((choices[0].get("message") or {}).get("content") or "")
    if not text:
        raise ValueError(f"empty completion (content-type {content_type!r})")
    return text


def replay(body: bytes, endpoint: str, timeout: float = 600.0, *, http: Any = requests) -> str:
    """`http` defaults to the real `requests` module; tests inject a fake with the same
    `.post()` surface so the request-building/response-parsing logic itself is exercised
    without a live engine (same pattern as harness.validate.client.MedAgentHubClient)."""
    resp = http.post(
        endpoint, data=body, headers={"Content-Type": "application/json"},
        timeout=timeout, stream=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"replay -> HTTP {resp.status_code}: {resp.text[:300]}")
    return parse_completion(resp.headers.get("Content-Type", ""), resp.content)


def parse_turn_stream(raw: str) -> dict[str, Any]:
    """Collapse a canonical /chat/stream SSE body into {events, answer, provider}.
    Raises on turn_error (the provider surfaced a failure — no silent fallback) and
    when the stream ends without an answer_done."""
    events: list[str] = []
    answer = ""
    provider = None
    event = ""
    for line in raw.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event:
            data = line.split(":", 1)[1].strip()
            try:
                payload = json.loads(data) if data else {}
            except ValueError:
                payload = {}
            events.append(event)
            if event in ("turn_error", "error"):
                raise RuntimeError(
                    f"turn_error: {payload.get('message') or payload.get('error') or data}"
                )
            if event == "turn_started":
                provider = payload.get("provider")
            if event == "answer_done":
                answer = str(payload.get("answer") or "")
            event = ""
    if "answer_done" not in events:
        raise RuntimeError(f"stream ended before answer_done (events: {events})")
    return {"events": events, "answer": answer, "provider": provider}


def run_turn(
    base_url: str, auth: tuple[str, str], patient: str, question: str, provider: str,
    profile: str | None = None, timeout: float = 2400.0,
    *, session_factory: Any = requests.Session,
) -> dict[str, Any]:
    """One product turn via the canonical SSE boundary, bound to `provider`. The
    rebuilt module is stream-only (POST /chat/stream; there is no buffered /chat).
    The hub provider requires a product profile; bundled takes none.

    `session_factory` defaults to the real `requests.Session`; tests inject a fake
    with the same `.post()` surface (same pattern as `replay`/`MedAgentHubClient`)."""
    session_obj = session_factory()
    session_obj.auth = auth
    rest = f"{base_url.rstrip('/')}/ws/rest/v1/chartsearchai"
    resp = session_obj.post(
        f"{rest}/chat/new",
        json={"patient": patient, "provider": provider},
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"[{provider}] /chat/new -> HTTP {resp.status_code}: {resp.text[:300]}")
    session = resp.json().get("session")
    body: dict[str, Any] = {
        "patient": patient,
        "question": question,
        "session": session,
        "provider": provider,
        "requestId": str(uuid4()),
    }
    if profile:
        body["profile"] = profile
    resp = session_obj.post(
        f"{rest}/chat/stream",
        json=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        stream=True,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"[{provider}] /chat/stream -> HTTP {resp.status_code}: {resp.text[:300]}")
    return parse_turn_stream(resp.content.decode("utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--base-url", default=os.environ.get(
        "CHARTSEARCH_BASE_URL",
        f"http://localhost:{os.environ.get('HARNESS_PROXY_HTTP_PORT', '8088')}/openmrs",
    ))
    parser.add_argument("--user", default=os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("CHARTSEARCH_ADMIN_PASSWORD", "Admin123"))
    parser.add_argument("--arms", default="bundled,hub")
    parser.add_argument(
        "--hub-profile",
        default=os.environ.get("PARITY_HUB_PROFILE", "single-e4b-checked"),
        help="product profile for the hub arm (must resolve to the shared engine model)",
    )
    parser.add_argument("--capture-dir", default="artifacts/parity-engine/captures")
    parser.add_argument("--out-dir", default="artifacts/parity-engine")
    parser.add_argument(
        "--replay-endpoint",
        default=os.environ.get("PARITY_REPLAY_ENDPOINT", "http://localhost:8077/v1/chat/completions"),
        help="engine endpoint captured bodies are replayed against, from the host",
    )
    parser.add_argument("--skip-replay", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    auth = (args.user, args.password)
    manifest: dict[str, Any] = {
        "patient": args.patient,
        "question": args.question,
        "replay_endpoint": None if args.skip_replay else args.replay_endpoint,
        "arms": {},
    }
    failures: list[str] = []

    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        print(f"== arm {arm}: running one turn via /chat (provider={arm}) ==")
        since_ns = time.time_ns()
        entry: dict[str, Any] = {"since_ns": since_ns}
        manifest["arms"][arm] = entry
        try:
            envelope = run_turn(
                args.base_url, auth, args.patient, args.question, arm,
                profile=args.hub_profile if arm == "hub" else None,
            )
            entry["answer_chars"] = len(str(envelope.get("answer") or ""))
            entry["provider"] = envelope.get("provider")
            entry["lifecycle"] = envelope.get("events")
            captures = new_captures(args.capture_dir, arm, since_ns)
            entry["engine_calls"] = [c.meta | {"bytes": c.body_path.stat().st_size} for c in captures]
            chosen = select_answer_leg(captures, args.question)
            artifact = out_dir / f"engine_request.{arm}.json"
            shutil.copyfile(chosen.body_path, artifact)
            entry["answer_leg"] = chosen.meta["body_file"]
            entry["artifact"] = str(artifact)
            body = json.loads(artifact.read_bytes())
            entry["model"] = body.get("model")
            print(f"   engine calls captured: {len(captures)}; answer leg: {chosen.stem} "
                  f"({chosen.body_path.stat().st_size} bytes, model={entry['model']})")
            if not args.skip_replay:
                completion = replay(artifact.read_bytes(), args.replay_endpoint)
                entry["replay_ok"] = True
                entry["replay_chars"] = len(completion)
                print(f"   replay -> 200, {len(completion)} chars")
        except Exception as exc:  # noqa: BLE001 - every arm failure must be reported
            entry["error"] = str(exc)
            failures.append(f"{arm}: {exc}")
            print(f"   FAIL: {exc}")

    (out_dir / "probe-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"\nmanifest -> {out_dir / 'probe-manifest.json'}")
    if failures:
        print("PROBE FAILED:\n  " + "\n  ".join(failures))
        return 1
    models = {a: e.get("model") for a, e in manifest["arms"].items()}
    print(f"PROBE PASSED — models per arm: {models}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
