#!/usr/bin/env python3
"""Prove that the local llama.cpp router keeps E2B and E4B resident together.

This is an explicit test/demo control, not a product warmup. It invokes each
configured small model once and then records the router's observable model
state so co-residency is proved rather than inferred from ``--models-max``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MODELS = ("gemma-e2b", "gemma-e4b")
ROOT = Path(__file__).resolve().parent.parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise RuntimeError(f"Expected a JSON object from {url}")
    return body


def _model_states(router_url: str, *, timeout: float) -> dict[str, str]:
    response = _request_json(f"{router_url}/v1/models", timeout=timeout)
    states: dict[str, str] = {}
    for item in response.get("data") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        status = item.get("status") or {}
        states[str(item["id"])] = str(status.get("value") or "unknown")
    return states


def _invoke_model(router_url: str, model: str, *, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    response = _request_json(
        f"{router_url}/v1/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 1,
            "temperature": 0,
            "stream": False,
        },
        timeout=timeout,
    )
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError(f"Router returned no completion choice for {model}")
    return {
        "model": model,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "response_id": response.get("id"),
        "response_model": response.get("model"),
        "usage": response.get("usage") or {},
    }


def verify_residency(
    router_url: str,
    models: tuple[str, ...] = DEFAULT_MODELS,
    *,
    timeout: float = 180.0,
) -> dict[str, Any]:
    normalized_url = router_url.rstrip("/")
    if len(models) < 2 or len(set(models)) != len(models):
        raise ValueError("At least two distinct model IDs are required")

    before = _model_states(normalized_url, timeout=timeout)
    missing = [model for model in models if model not in before]
    if missing:
        raise RuntimeError(f"Router does not advertise: {', '.join(missing)}")

    calls = [
        _invoke_model(normalized_url, model, timeout=timeout) for model in models
    ]
    after = _model_states(normalized_url, timeout=timeout)
    observed = {model: after.get(model, "missing") for model in models}
    passed = all(status == "loaded" for status in observed.values())
    return {
        "schema_version": "llama_router_small_model_residency.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "router_url": normalized_url,
        "inputs": {
            "script": {
                "path": "scripts/verify-small-model-residency.py",
                "sha256": _sha256(Path(__file__).resolve()),
            },
            "router_preset": {
                "path": "scripts/llama-router.ini",
                "sha256": _sha256(ROOT / "scripts/llama-router.ini"),
            },
        },
        "models": list(models),
        "before": {model: before[model] for model in models},
        "calls": calls,
        "after": observed,
        "passed": passed,
        "failure": None
        if passed
        else "Both small models were not resident after sequential invocation.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router-url", default="http://127.0.0.1:8077")
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/chartsearchai-local/small-model-residency.json"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = verify_residency(
        args.router_url,
        tuple(args.models or DEFAULT_MODELS),
        timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
