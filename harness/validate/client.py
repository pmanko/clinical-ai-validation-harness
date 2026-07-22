"""HTTP client that drives chartsearchai's real REST API (spec 006 FR-006.1).

Each ``POST /chat`` selects one hub product profile. ChartSearchAI owns patient
authorization/session persistence and relays that profile id to med-agent-hub; the
client cannot override the configured hub endpoint or compose low-level stages.

Base URL + Basic-auth credentials reuse the same env vars as
scripts/chartsearch-configure.sh so the two agree.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import requests

_REST = "/ws/rest/v1/chartsearchai"

# Transient HTTP statuses worth a limited retry: 429 (rate limit), the 5xx the proxy emits
# while the backend is restarting / an upstream momentarily times out, and 401 — an
# intermittent OpenMRS auth/session blip mid-run (the next request re-authenticates via the
# Session's basic-auth), seen nicking multi-turn cells; without the retry the whole cell is lost.
_RETRYABLE = frozenset({401, 429, 500, 502, 503, 504})


def _default_base_url() -> str:
    port = os.environ.get("HARNESS_PROXY_HTTP_PORT", "8088")
    return os.environ.get("CHARTSEARCH_BASE_URL", f"http://localhost:{port}/openmrs")


@dataclass
class ChatResult:
    status: int
    envelope: dict[str, Any] | None
    latency_ms: int
    raw_text: str = ""


def collapse_turn_stream(raw: str) -> dict[str, Any]:
    """Collapse a canonical /chat/stream SSE body into the classic /chat envelope.

    The answer_done payload IS the envelope (the module hydrates the full answer —
    answer/references/blocks/session/messageId — into it). In-Depth results nest
    under ``inDepth``; the lifecycle (minus per-token ``*_delta`` noise) is recorded
    under ``events``. A turn_error before any answer yields its payload verbatim,
    with no ``answer`` key — downstream completeness checks treat that as not-done."""
    envelope: dict[str, Any] = {}
    indepth: dict[str, Any] | None = None
    events: list[str] = []
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
            if not event.endswith("_delta"):
                events.append(event)
            if event == "answer_done":
                envelope.update(payload)
            elif event == "indepth_done":
                indepth = payload
            elif event == "indepth_error":
                indepth = payload if "error" in payload else {"error": payload.get("message") or "in-depth failed", **payload}
            elif event in ("turn_error", "error") and "answer" not in envelope:
                envelope.update(payload)
            event = ""
    out = dict(envelope)
    if indepth is not None:
        out["inDepth"] = indepth
    out["events"] = events
    return out


class ChartSearchAiClient:
    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 2400.0,  # HIGH tier serial-loads 3-4 big GGUFs/turn (~17 min) at router models-max=1
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

    def new_session(self, patient: str, provider: str | None = None) -> str:
        """Close the active session for this patient and open a fresh one — bound to
        `provider` when pinned (engine-parity arms). Retries a transient
        gateway/rate-limit status (the backend may be restarting) up to
        max_retries before raising, so a single blip doesn't abort the whole run."""
        body: dict[str, str] = {"patient": patient}
        if provider:
            body["provider"] = provider
        attempt = 0
        while True:
            resp = self._session.post(
                self._url("/chat/new"), json=body, timeout=self.timeout
            )
            if resp.status_code in _RETRYABLE and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.retry_wait_s)
                continue
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
        profile: str | None = None,
        provider: str | None = None,
        request_id: str | None = None,
    ) -> ChatResult:
        """One chat turn over the canonical SSE boundary (the rebuilt module is
        stream-only: POST /chat/stream; there is no buffered /chat). The stream is
        collapsed into the classic envelope via :func:`collapse_turn_stream`. Never
        raises on a non-200 — the turn is recorded with its status so a failed turn
        still produces a result line. Paces to stay under the rate limit and retries
        on 429 (the recorded latency_ms is the final attempt's, not the wait).

        ``profile`` selects a hub-advertised product profile; ``provider`` pins the
        ChartSearchAI provider (bundled|hub) for engine-parity arms. Without either,
        ChartSearchAI uses its configured defaults."""
        request_id = request_id or str(uuid4())
        body: dict[str, str] = {
            "patient": patient,
            "question": question,
            "requestId": request_id,
        }
        if session:
            body["session"] = session
        if profile:
            body["profile"] = profile
        if provider:
            body["provider"] = provider
        attempt = 0
        while True:
            self._throttle()
            start = time.monotonic()
            try:
                resp = self._session.post(
                    self._url("/chat/stream"),
                    json=body,
                    timeout=self.timeout,
                    headers={"Accept": "text/event-stream"},
                    stream=True,
                )
            except requests.RequestException:
                # Dropped connection / read timeout: retry the transient, then let it
                # propagate (the runner records it and moves on).
                self._last_call = time.monotonic()
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_wait_s)
                    continue
                raise
            # Drain the stream fully (the turn runs to turn_done server-side) before
            # stamping latency — the answer isn't done until the stream is.
            raw = resp.content
            latency_ms = int((time.monotonic() - start) * 1000)
            self._last_call = time.monotonic()
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
                envelope=collapse_turn_stream(raw.decode("utf-8", errors="replace")),
                latency_ms=latency_ms,
                raw_text="",
            )

    def get_patient_profile(self, patient: str) -> dict[str, Any]:
        """Best-effort rich patient snapshot for report grounding: demographics +
        identifiers + active regimen + chart counts + recent vitals, from the OpenMRS
        REST + FHIR APIs (same base + auth as the chat client). Never raises — returns a
        partial/empty dict on any failure, so a profile fetch can't block a run."""
        base = f"{self.base_url}/ws"

        def _get(path: str) -> Any:
            try:
                resp = self._session.get(base + path, timeout=self.timeout)
                return resp.json() if resp.ok else None
            except Exception:
                return None

        out: dict[str, Any] = {}
        demo = _get(
            f"/rest/v1/patient/{patient}?v=custom:(identifiers:(identifier,"
            "identifierType:(name)),person:(display,gender,age,birthdate))")
        if isinstance(demo, dict):
            person = demo.get("person") or {}
            out["display"] = person.get("display")
            out["gender"] = person.get("gender")
            out["age"] = person.get("age")
            out["birthdate"] = (person.get("birthdate") or "")[:10] or None
            ids = [
                {"id": i.get("identifier"), "type": (i.get("identifierType") or {}).get("name")}
                for i in (demo.get("identifiers") or []) if i.get("identifier")
            ]
            if ids:
                out["identifiers"] = ids
                out["identifier"] = ids[0]["id"]

        meds = _get(f"/fhir2/R4/MedicationRequest?patient={patient}")
        if isinstance(meds, dict):
            names = []
            for entry in (meds.get("entry") or []):
                res = entry.get("resource") or {}
                if res.get("status") == "active":
                    name = (res.get("medicationReference") or {}).get("display") or (
                        res.get("medicationCodeableConcept") or {}).get("text")
                    if name:
                        names.append(name)
            if names:
                out["medications"] = sorted(set(names))

        enc = _get(f"/rest/v1/encounter?patient={patient}&limit=1&totalCount=true")
        if isinstance(enc, dict) and enc.get("totalCount") is not None:
            out["encounter_count"] = enc["totalCount"]

        obs = _get(f"/fhir2/R4/Observation?patient={patient}&_count=120&_sort=-date")
        if isinstance(obs, dict):
            if obs.get("total") is not None:
                out["observation_count"] = obs["total"]
            # SpO2's concept text contains "pulse oximeter", so the loose "pulse" needle MUST
            # come last, and each obs matches at most one vital (break) — else the SpO2 obs
            # also fills Pulse with the saturation value.
            wanted = [
                ("arterial blood oxygen saturation", "SpO2"),
                ("systolic blood pressure", "Systolic BP"),
                ("diastolic blood pressure", "Diastolic BP"),
                ("temperature", "Temp"),
                ("weight", "Weight"),
                ("pulse", "Pulse"),
            ]
            vitals: dict[str, str] = {}
            for entry in (obs.get("entry") or []):
                res = entry.get("resource") or {}
                text = ((res.get("code") or {}).get("text") or "").lower()
                for needle, label in wanted:
                    if needle in text:
                        if label not in vitals:
                            q = res.get("valueQuantity") or {}
                            if q.get("value") is not None:
                                unit = (q.get("unit") or "").strip()
                                sep = "" if unit in ("%", "") else " "
                                vitals[label] = f"{q['value']}{sep}{unit}".strip()
                        break
            if vitals:
                out["vitals"] = vitals
        return out


class MedAgentHubClient:
    """Direct client for controlled profile/leg experiments through the hub.

    Product evaluation continues to use :class:`ChartSearchAiClient`. This client
    intentionally omits ``require_product_profile`` so checked-in comparison sets
    can exercise the hub's low-level legs without weakening the OpenMRS product
    boundary. Conversation history is maintained locally for multi-turn scenarios.
    """

    _RETRYABLE = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 2400.0,
        min_interval_s: float | None = None,
        max_retries: int | None = None,
        retry_wait_s: float | None = None,
        session: requests.Session | None = None,
        chart_client: ChartSearchAiClient | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get(
                "MED_AGENT_HUB_URL",
                "http://127.0.0.1:18081/v1/chat/completions",
            )
        ).rstrip("/")
        self.timeout = timeout
        self.min_interval_s = (
            min_interval_s
            if min_interval_s is not None
            else float(os.environ.get("VALIDATE_HUB_MIN_INTERVAL_S", "0"))
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(os.environ.get("VALIDATE_MAX_RETRIES", "3"))
        )
        self.retry_wait_s = (
            retry_wait_s
            if retry_wait_s is not None
            else float(os.environ.get("VALIDATE_RETRY_WAIT_S", "7.0"))
        )
        self._last_call = 0.0
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        api_key = os.environ.get("MED_AGENT_HUB_API_KEY")
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})
        self._conversations: dict[str, dict[str, Any]] = {}
        self._chart_client = chart_client or ChartSearchAiClient()

    def new_session(self, patient: str) -> str:
        session = str(uuid4())
        self._conversations[session] = {"patient": patient, "messages": []}
        return session

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
        profile: str | None = None,
        request_id: str | None = None,
    ) -> ChatResult:
        if not profile:
            raise ValueError("Med Agent Hub comparisons require an explicit profile")
        if not session:
            session = self.new_session(patient)
        conversation = self._conversations.setdefault(
            session, {"patient": patient, "messages": []}
        )
        if conversation["patient"] != patient:
            raise ValueError("hub session cannot be reused for a different patient")

        request_id = request_id or str(uuid4())
        messages = [*conversation["messages"], {"role": "user", "content": question}]
        body = {
            "model": profile,
            "stream": False,
            "patient": patient,
            "messages": messages,
            "context": {"session": session, "request_id": request_id},
        }
        attempt = 0
        started = time.monotonic()
        while True:
            self._throttle()
            try:
                response = self._session.post(
                    self.base_url, json=body, timeout=self.timeout
                )
            except requests.RequestException:
                self._last_call = time.monotonic()
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_wait_s)
                    continue
                raise
            self._last_call = time.monotonic()
            if response.status_code in self._RETRYABLE and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.retry_wait_s)
                continue
            latency_ms = int((time.monotonic() - started) * 1000)
            if response.status_code != 200:
                return ChatResult(
                    status=response.status_code,
                    envelope=None,
                    latency_ms=latency_ms,
                    raw_text=response.text,
                )
            try:
                completion = response.json()
                content = completion["choices"][0]["message"]["content"]
                envelope = json.loads(content) if isinstance(content, str) else content
                if not isinstance(envelope, dict):
                    raise ValueError("completion content is not an object")
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                return ChatResult(
                    status=502,
                    envelope=None,
                    latency_ms=latency_ms,
                    raw_text=f"invalid hub completion: {exc}: {response.text[:500]}",
                )

            envelope = dict(envelope)
            envelope["session"] = session
            if completion.get("model") and not envelope.get("model"):
                envelope["model"] = completion["model"]
            conversation["messages"] = [
                *messages,
                {"role": "assistant", "content": str(envelope.get("answer") or "")},
            ]
            return ChatResult(
                status=200,
                envelope=envelope,
                latency_ms=latency_ms,
                raw_text=response.text,
            )

    def get_patient_profile(self, patient: str) -> dict[str, Any]:
        return self._chart_client.get_patient_profile(patient)
