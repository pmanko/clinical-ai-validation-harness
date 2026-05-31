"""HTTP client that drives chartsearchai's real REST API exactly as the chat UI
does (spec 006 FR-006.1): select the backend with POST /endpoint, then replay
turns with POST /chat in one session. No bypass of chartsearchai.

Base URL + Basic-auth credentials reuse the same env vars as
scripts/chartsearch-configure.sh so the two agree.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

_REST = "/ws/rest/v1/chartsearchai"


def _default_base_url() -> str:
    port = os.environ.get("HARNESS_PROXY_HTTP_PORT", "8088")
    return os.environ.get("CHARTSEARCH_BASE_URL", f"http://localhost:{port}/openmrs")


@dataclass
class ChatResult:
    status: int
    envelope: dict[str, Any] | None
    latency_ms: int
    raw_text: str = ""


class ChartSearchAiClient:
    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = (
            user or os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"),
            password or os.environ.get("CHARTSEARCH_ADMIN_PASSWORD", "Admin123"),
        )
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{_REST}{path}"

    def set_endpoint(self, endpoint_url: str, model_name: str) -> dict[str, Any]:
        """Switch the active backend (endpoint + model) in one atomic call."""
        resp = self._session.post(
            self._url("/endpoint"),
            json={"endpointUrl": endpoint_url, "modelName": model_name},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"set_endpoint({endpoint_url!r}, {model_name!r}) failed "
                f"[{resp.status_code}]: {resp.text[:300]}"
            )
        return resp.json()

    def new_session(self, patient: str) -> str:
        """Close the active session for this patient and open a fresh one."""
        resp = self._session.post(
            self._url("/chat/new"), json={"patient": patient}, timeout=self.timeout
        )
        if resp.status_code != 200:
            raise RuntimeError(f"new_session({patient!r}) failed [{resp.status_code}]: {resp.text[:300]}")
        return resp.json().get("session")

    def chat(self, patient: str, session: str | None, question: str) -> ChatResult:
        """One chat turn. Never raises on a non-200 — the turn is recorded with
        its status so a failed turn still produces a result line."""
        body: dict[str, str] = {"patient": patient, "question": question}
        if session:
            body["session"] = session
        start = time.monotonic()
        resp = self._session.post(self._url("/chat"), json=body, timeout=self.timeout)
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        return ChatResult(
            status=resp.status_code,
            envelope=payload if isinstance(payload, dict) else None,
            latency_ms=latency_ms,
            raw_text=resp.text,
        )
