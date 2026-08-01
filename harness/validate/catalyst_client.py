"""HTTP client that drives Catalyst's real /v1/chat/completions API (feature 011).

Implements the same `_Client` Protocol (harness/validate/runner.py) that
ChartSearchAiClient (client.py) implements — see
specs/011-catalyst-fhir-sidecar-poc/contracts/catalyst_adapter_client.profile.md
for why this Protocol, not harness/adapters/*.py, is the interface reused
from feature 004.

Catalyst's M0.0/M0.1 gateway is stateless per request (no server-side session
or patient-context concept) and has no product-profile or engine-parity
notion — those are chartsearchai-specific. `new_session` is therefore a
client-side no-op; `profile` is accepted (Protocol compatibility) but
unused.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import requests

from .client import ChatResult

_RETRYABLE = frozenset({429, 500, 502, 503, 504})


def _default_endpoint_url() -> str:
    return os.environ.get(
        "CATALYST_GATEWAY_URL", "http://localhost:8000/v1/chat/completions"
    )


class CatalystClient:
    def __init__(
        self,
        endpoint_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 2,
        retry_wait_s: float = 3.0,
    ) -> None:
        # Like ChartSearchAiClient/MedAgentHubClient, one client targets one
        # fixed endpoint for the whole run — the runner varies `profile` per
        # backend, it does not switch endpoint_url per backend (see
        # harness/validate/runner.py: chat_kwargs always carries
        # profile=backend.model_name, never re-targets the HTTP call).
        self.endpoint_url = endpoint_url or _default_endpoint_url()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_wait_s = retry_wait_s
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def new_session(self, patient: str) -> str:
        """No server-side session exists for Catalyst's gateway (stateless
        per request) — returns a locally-generated id only so this client
        satisfies the same Protocol chartsearchai's client does."""
        return str(uuid.uuid4())

    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        profile: str | None = None,
        request_id: str | None = None,
    ) -> ChatResult:
        """One turn against Catalyst's OpenAI-compatible /v1/chat/completions.

        Patient identity is folded into the question text (Catalyst's own
        agent resolves it via its `search_patient`/`get_patient_context` MCP
        tools from the question, not a wire-level `patient` parameter — see
        the source brief and fhir_grounding.py in targets/catalyst). Never
        raises on a non-200 — the turn is recorded with its status so a
        failed turn still produces a result line, matching
        ChartSearchAiClient's contract."""
        del profile  # accepted for Protocol compatibility; Catalyst has no product-profile concept
        body: dict[str, Any] = {
            "id": request_id or str(uuid.uuid4()),
            "messages": [{"role": "user", "content": question}],
        }

        attempt = 0
        while True:
            start = time.monotonic()
            try:
                resp = self._session.post(self.endpoint_url, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_wait_s)
                    continue
                return ChatResult(
                    status=0,
                    envelope=None,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    raw_text=repr(exc),
                )
            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code in _RETRYABLE and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.retry_wait_s)
                continue
            if resp.status_code != 200:
                return ChatResult(
                    status=resp.status_code,
                    envelope=None,
                    latency_ms=latency_ms,
                    raw_text=resp.text,
                )
            return ChatResult(
                status=200,
                envelope=resp.json(),
                latency_ms=latency_ms,
                raw_text="",
            )
