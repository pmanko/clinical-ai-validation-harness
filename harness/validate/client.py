"""HTTP client that drives chartsearchai's real REST API (spec 006 FR-006.1): the
backend is selected PER REQUEST — `{endpointUrl, modelName}` are sent in each
`POST /chat` body as a per-request override (chartsearchai's `RequestLlmOverride`;
used for that request only, the config-global default untouched) — replaying turns
in one session. No bypass of chartsearchai.

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
        min_interval_s: float | None = None,
        max_retries: int | None = None,
        retry_wait_s: float | None = None,
    ) -> None:
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        self.timeout = timeout
        # chartsearchai rate-limits per user (GP chartsearchai.rateLimitPerMinute,
        # default 10/min). Space chat calls just under that to avoid 429s, and
        # retry-on-429 as a backstop. Raise the GP + set VALIDATE_MIN_INTERVAL_S=0
        # for full-speed runs.
        self.min_interval_s = (
            min_interval_s if min_interval_s is not None
            else float(os.environ.get("VALIDATE_MIN_INTERVAL_S", "6.5"))
        )
        self.max_retries = (
            max_retries if max_retries is not None
            else int(os.environ.get("VALIDATE_MAX_RETRIES", "3"))
        )
        self.retry_wait_s = (
            retry_wait_s if retry_wait_s is not None
            else float(os.environ.get("VALIDATE_RETRY_WAIT_S", "7.0"))
        )
        self._last_call = 0.0
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

    def _throttle(self) -> None:
        if self.min_interval_s > 0:
            wait = self.min_interval_s - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)

    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        endpoint_url: str | None = None,
        model_name: str | None = None,
    ) -> ChatResult:
        """One chat turn. Never raises on a non-200 — the turn is recorded with
        its status so a failed turn still produces a result line. Paces to stay
        under the rate limit and retries on 429 (the recorded latency_ms is the
        final attempt's, not the wait).

        When endpoint_url + model_name are given they are sent as a per-request
        backend override — chartsearchai uses that backend for THIS request only,
        leaving its config-controlled global default untouched (so a run can't
        collide with the UI or another run)."""
        body: dict[str, str] = {"patient": patient, "question": question}
        if session:
            body["session"] = session
        if endpoint_url and model_name:
            body["endpointUrl"] = endpoint_url
            body["modelName"] = model_name
        attempt = 0
        while True:
            self._throttle()
            start = time.monotonic()
            resp = self._session.post(self._url("/chat"), json=body, timeout=self.timeout)
            latency_ms = int((time.monotonic() - start) * 1000)
            self._last_call = time.monotonic()
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.retry_wait_s)
                continue
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
