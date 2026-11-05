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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import requests

_REST = "/ws/rest/v1/chartsearchai"
_DELTA_EVENTS = frozenset({"preliminary_delta", "reasoning_delta", "answer_delta"})

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


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return round(sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight, 2)


def _compute_stream_timings(
    event_timings: Sequence[tuple[str, float]],
    *,
    total_latency_ms: int | None = None,
    raw_delta_count: int = 0,
    raw_answer_delta_count: int = 0,
) -> dict[str, Any]:
    first_by_event: dict[str, float] = {}
    last_by_event: dict[str, float] = {}
    delta_times: list[float] = []
    answer_delta_times: list[float] = []
    for event_name, elapsed_ms in event_timings:
        first_by_event.setdefault(event_name, elapsed_ms)
        last_by_event[event_name] = elapsed_ms
        if event_name in _DELTA_EVENTS:
            delta_times.append(elapsed_ms)
        if event_name == "answer_delta":
            answer_delta_times.append(elapsed_ms)

    def _ms(val: float | None) -> int | None:
        return round(val) if val is not None else None

    preliminary_start = _ms(first_by_event.get("preliminary_delta"))
    reasoning_start = _ms(first_by_event.get("reasoning_delta"))
    answer_delta_start = _ms(first_by_event.get("answer_delta"))
    answer_done = _ms(first_by_event.get("answer_done"))
    answer_validation = _ms(last_by_event.get("answer_validation"))
    evidence_updated = _ms(last_by_event.get("evidence_updated"))
    indepth_done = _ms(
        last_by_event.get("indepth_done")
        if "indepth_done" in last_by_event
        else last_by_event.get("indepth_error")
    )
    turn_done = _ms(
        last_by_event.get("turn_done")
        if "turn_done" in last_by_event
        else last_by_event.get("turn_error")
    )
    if turn_done is None and total_latency_ms is not None:
        turn_done = total_latency_ms

    first_delta_candidates = [
        ts
        for ts in (
            first_by_event.get("preliminary_delta"),
            first_by_event.get("reasoning_delta"),
            first_by_event.get("answer_delta"),
        )
        if ts is not None
    ]
    ttft_ms = (
        round(min(first_delta_candidates))
        if first_delta_candidates
        else answer_done
    )

    token_times = answer_delta_times if len(answer_delta_times) >= 2 else delta_times
    if len(token_times) >= 2:
        intervals = sorted(
            max(0.0, token_times[i] - token_times[i - 1])
            for i in range(1, len(token_times))
        )
        itl_p50_ms = _percentile(intervals, 50.0)
        itl_p95_ms = _percentile(intervals, 95.0)
        tpot_ms = round(
            (token_times[-1] - token_times[0]) / (len(token_times) - 1), 2
        )
    else:
        itl_p50_ms = None
        itl_p95_ms = None
        tpot_ms = None

    return {
        "ttft_ms": ttft_ms,
        "preliminary_start_ms": preliminary_start,
        "reasoning_start_ms": reasoning_start,
        "answer_delta_start_ms": answer_delta_start,
        "answer_done_ms": answer_done,
        "answer_validation_ms": answer_validation,
        "evidence_updated_ms": evidence_updated,
        "indepth_done_ms": indepth_done,
        "turn_done_ms": turn_done,
        "delta_count": len(delta_times) if event_timings else raw_delta_count,
        "answer_delta_count": (
            len(answer_delta_times) if event_timings else raw_answer_delta_count
        ),
        "itl_p50_ms": itl_p50_ms,
        "itl_p95_ms": itl_p95_ms,
        "tpot_ms": tpot_ms,
    }


def collapse_turn_stream(
    raw: str,
    *,
    event_timings: Sequence[tuple[str, float]] | None = None,
    total_latency_ms: int | None = None,
) -> dict[str, Any]:
    """Collapse a canonical /chat/stream SSE body into the classic /chat envelope.

    The answer_done payload IS the envelope (the module hydrates the full answer —
    answer/references/blocks/session/messageId — into it). Every later event that carries
    an ``answer`` is the same envelope as it settles: the answer check's result, the
    In-Depth nested under ``inDepth`` and its confidence arrive on answer_validation,
    indepth_done/indepth_error and turn_done, so each one replaces what came before. An
    In-Depth event without an ``answer`` is a bare In-Depth object and nests under
    ``inDepth`` as it is. The lifecycle (minus per-token ``*_delta`` noise) is recorded
    under ``events``. When ``event_timings`` (monotonic ``(event_name, elapsed_ms)`` pairs
    captured while consuming the live SSE stream) are supplied, ``stream_timings`` is
    attached with TTFT, stage milestone latencies, and inter-token latency percentiles.
    A turn_error before any answer yields its payload verbatim, with no
    ``answer`` key — downstream completeness checks treat that as not-done."""
    envelope: dict[str, Any] = {}
    indepth: dict[str, Any] | None = None
    events: list[str] = []
    raw_delta_count = 0
    raw_answer_delta_count = 0
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
            if event in _DELTA_EVENTS:
                raw_delta_count += 1
                if event == "answer_delta":
                    raw_answer_delta_count += 1
            elif not event.endswith("_delta"):
                events.append(event)
            if isinstance(payload, dict):
                if event == "answer_done" or (
                    "answer" in envelope
                    and "answer" in payload
                    and event not in ("turn_error", "error")
                ):
                    envelope.update(payload)
                elif event == "indepth_done":
                    indepth = payload
                elif event == "indepth_error":
                    indepth = (
                        payload
                        if "error" in payload
                        else {
                            "error": payload.get("message") or "in-depth failed",
                            **payload,
                        }
                    )
                elif event in ("turn_error", "error") and "answer" not in envelope:
                    envelope.update(payload)
            event = ""
    out = dict(envelope)
    if indepth is not None and "inDepth" not in out:
        out["inDepth"] = indepth
    out["events"] = events
    if event_timings is not None or total_latency_ms is not None:
        out["stream_timings"] = _compute_stream_timings(
            event_timings or (),
            total_latency_ms=total_latency_ms,
            raw_delta_count=raw_delta_count,
            raw_answer_delta_count=raw_answer_delta_count,
        )
    return out


class ChartSearchAiClient:
    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
        location_uuid: str | None = None,
        timeout: float = 2400.0,  # HIGH tier serial-loads 3-4 big GGUFs/turn (~17 min) at router models-max=1
        min_interval_s: float | None = None,
        max_retries: int | None = None,
        retry_wait_s: float | None = None,
        session: requests.Session | None = None,
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
        self.location_uuid = (
            location_uuid
            if location_uuid is not None
            else os.environ.get("CHARTSEARCH_LOCATION_UUID")
        )
        self._location_applied = False
        self._last_call = 0.0
        self._session = session or requests.Session()
        self._session.auth = (
            user
            or os.environ.get("CHARTSEARCH_USER")
            or os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"),
            password
            or os.environ.get("CHARTSEARCH_PASSWORD")
            or os.environ.get("CHARTSEARCH_ADMIN_PASSWORD", "Admin123"),
        )
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{_REST}{path}"

    def _ensure_session_location(self) -> None:
        if not self.location_uuid or self._location_applied:
            return
        attempt = 0
        while True:
            resp = self._session.post(
                f"{self.base_url}/ws/rest/v1/session",
                json={"location": self.location_uuid},
                timeout=self.timeout,
            )
            if resp.status_code in _RETRYABLE and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.retry_wait_s)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"session location({self.location_uuid!r}) failed [{resp.status_code}]: {resp.text[:300]}"
                )
            self._location_applied = True
            return

    def new_session(self, patient: str, provider: str | None = None) -> str:
        """Close the active session for this patient and open a fresh one — bound to
        `provider` when pinned (engine-parity arms). Retries a transient
        gateway/rate-limit status (the backend may be restarting) up to
        max_retries before raising, so a single blip doesn't abort the whole run."""
        self._ensure_session_location()
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

    @staticmethod
    def _consume_sse_response(
        resp: Any, start_ns: int
    ) -> tuple[str, list[tuple[str, float]]]:
        """Incrementally read SSE lines as they arrive and stamp monotonic event timings."""
        event_timings: list[tuple[str, float]] = []
        if hasattr(resp, "iter_lines"):
            lines: list[str] = []
            current_event = ""
            event_stamped = False
            try:
                line_iter = resp.iter_lines(chunk_size=1, decode_unicode=False)
            except TypeError:
                line_iter = resp.iter_lines(decode_unicode=False)
            for raw_line in line_iter:
                line = (
                    raw_line.decode("utf-8", errors="replace")
                    if isinstance(raw_line, (bytes, bytearray))
                    else str(raw_line)
                )
                lines.append(line)
                if not line:
                    current_event = ""
                    event_stamped = False
                elif line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    event_stamped = False
                elif line.startswith("data:") and current_event and not event_stamped:
                    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
                    event_timings.append((current_event, elapsed_ms))
                    event_stamped = True
            return "\n".join(lines), event_timings
        raw_bytes = getattr(resp, "content", b"")
        raw_text = (
            raw_bytes.decode("utf-8", errors="replace")
            if isinstance(raw_bytes, (bytes, bytearray))
            else str(raw_bytes or getattr(resp, "text", ""))
        )
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        current_event = ""
        for line in raw_text.splitlines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current_event:
                event_timings.append((current_event, elapsed_ms))
                current_event = ""
        return raw_text, event_timings

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
        consumed incrementally as events arrive and collapsed into the classic
        envelope via :func:`collapse_turn_stream` with ``stream_timings`` attached.
        Never raises on a non-200 — the turn is recorded with its status so a failed
        turn still produces a result line. Paces to stay under the rate limit and
        retries on 429 (the recorded latency_ms is the final attempt's, not the wait).

        ``profile`` selects a hub-advertised product profile; ``provider`` pins the
        ChartSearchAI provider (bundled|hub) for engine-parity arms. Without either,
        ChartSearchAI uses its configured defaults."""
        self._ensure_session_location()
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
            start_ns = time.perf_counter_ns()
            try:
                resp = self._session.post(
                    self._url("/chat/stream"),
                    json=body,
                    timeout=self.timeout,
                    headers={"Accept": "text/event-stream"},
                    stream=True,
                )
                if resp.status_code == 200:
                    raw_text, event_timings = self._consume_sse_response(resp, start_ns)
                else:
                    raw_text = getattr(resp, "text", "") or ""
                    event_timings = []
            except requests.RequestException:
                # Dropped connection / read timeout: retry the transient, then let it
                # propagate (the runner records it and moves on).
                self._last_call = time.monotonic()
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_wait_s)
                    continue
                raise
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
                    raw_text=raw_text,
                )
            return ChatResult(
                status=200,
                envelope=collapse_turn_stream(
                    raw_text,
                    event_timings=event_timings,
                    total_latency_ms=latency_ms,
                ),
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
        self._chart_client = chart_client

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
            if isinstance(completion.get("usage"), dict) and "usage" not in envelope:
                envelope["usage"] = completion["usage"]
            if isinstance(completion.get("timings"), dict) and "timings" not in envelope:
                envelope["timings"] = completion["timings"]
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
        if self._chart_client is None:
            self._chart_client = ChartSearchAiClient()
        return self._chart_client.get_patient_profile(patient)


def _coerce_openai_content_to_envelope(content: Any) -> dict[str, Any]:
    """Normalize an OpenAI assistant completion content (JSON object or plain text)
    into the validation envelope shape expected by downstream metrics and reports."""
    if isinstance(content, dict):
        envelope = dict(content)
        envelope.setdefault("answer", str(envelope.get("answer") or ""))
        envelope.setdefault("references", envelope.get("citations") or [])
        envelope.setdefault("blocks", [])
        return envelope
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    parsed = dict(parsed)
                    parsed.setdefault("answer", str(parsed.get("answer") or ""))
                    parsed.setdefault("references", parsed.get("citations") or [])
                    parsed.setdefault("blocks", [])
                    return parsed
            except ValueError:
                pass
        return {
            "answer": content,
            "references": [],
            "blocks": [],
        }
    return {
        "answer": "" if content is None else str(content),
        "references": [],
        "blocks": [],
    }


class OpenAICompatibleClient:
    """General-purpose client for any OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Supports arbitrary LLM servers and agent gateways (vLLM, llama-server, LiteLLM,
    Ollama, Med Agent Hub, etc.) with either plain-text/Markdown or JSON-envelope
    responses, optional SSE token streaming (recording ``ttft_ms``, ``answer_done_ms``,
    ``turn_done_ms``, ``itl_p50_ms``, ``itl_p95_ms``, and ``tpot_ms``), and per-backend
    ``endpoint_url`` overrides so a single comparison run can evaluate heterogeneous
    model endpoints without requiring OpenMRS.
    """

    _RETRYABLE = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        system_prompt: str | None = None,
        stream: bool | None = None,
        timeout: float = 2400.0,
        min_interval_s: float | None = None,
        max_retries: int | None = None,
        retry_wait_s: float | None = None,
        session: requests.Session | None = None,
        chart_client: ChartSearchAiClient | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get("OPENAI_COMPATIBLE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "http://127.0.0.1:8080/v1/chat/completions"
        ).rstrip("/")
        self.system_prompt = system_prompt or os.environ.get("VALIDATE_SYSTEM_PROMPT")
        if stream is not None:
            self.stream = stream
        else:
            self.stream = os.environ.get("VALIDATE_OPENAI_STREAM", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }
        self.timeout = timeout
        self.min_interval_s = (
            min_interval_s
            if min_interval_s is not None
            else float(os.environ.get("VALIDATE_MIN_INTERVAL_S", "0"))
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
        resolved_key = (
            api_key
            or os.environ.get("VALIDATE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if resolved_key:
            self._session.headers.update({"Authorization": f"Bearer {resolved_key}"})
        self._conversations: dict[str, dict[str, Any]] = {}
        self._chart_client = chart_client

    def new_session(self, patient: str) -> str:
        session = str(uuid4())
        initial_messages: list[dict[str, str]] = []
        if self.system_prompt:
            initial_messages.append({"role": "system", "content": self.system_prompt})
        self._conversations[session] = {"patient": patient, "messages": initial_messages}
        return session

    def _throttle(self) -> None:
        if self.min_interval_s > 0:
            wait = self.min_interval_s - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)

    def _consume_sse_stream(
        self, response: Any, started: float
    ) -> tuple[str, str | None, dict[str, Any] | None, dict[str, Any]]:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        delta_timestamps_ms: list[int] = []
        ttft_ms: int | None = None
        last_delta_ms: int | None = None
        model_name: str | None = None
        usage: dict[str, Any] | None = None

        if hasattr(response, "iter_lines"):
            try:
                lines_iter = response.iter_lines(chunk_size=1, decode_unicode=True)
            except TypeError:
                lines_iter = response.iter_lines(decode_unicode=True)
        else:
            lines_iter = str(getattr(response, "text", "") or "").splitlines()
        for raw_line in lines_iter:
            if not raw_line:
                continue
            line = (
                raw_line.decode("utf-8", errors="replace")
                if isinstance(raw_line, bytes)
                else str(raw_line)
            ).strip()
            if not line.startswith("data:"):
                continue
            payload_str = line[5:].strip()
            if payload_str == "[DONE]":
                break
            try:
                chunk = json.loads(payload_str)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            now_ms = int(round((time.monotonic() - started) * 1000))
            if chunk.get("model") and not model_name:
                model_name = str(chunk["model"])
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            delta = (
                choices[0].get("delta")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                else None
            )
            if not isinstance(delta, dict):
                continue
            c_piece = delta.get("content")
            r_piece = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(r_piece, str) and r_piece:
                reasoning_parts.append(r_piece)
                if ttft_ms is None:
                    ttft_ms = now_ms
            if isinstance(c_piece, str) and c_piece:
                content_parts.append(c_piece)
                if ttft_ms is None:
                    ttft_ms = now_ms
                delta_timestamps_ms.append(now_ms)
                last_delta_ms = now_ms

        turn_done_ms = int(round((time.monotonic() - started) * 1000))
        answer_done_ms = last_delta_ms if last_delta_ms is not None else turn_done_ms
        if ttft_ms is None:
            ttft_ms = answer_done_ms

        itl_deltas = [
            float(b - a)
            for a, b in zip(delta_timestamps_ms, delta_timestamps_ms[1:])
            if b >= a
        ]
        stream_timings: dict[str, Any] = {
            "ttft_ms": ttft_ms,
            "answer_done_ms": answer_done_ms,
            "turn_done_ms": turn_done_ms,
            "answer_delta_count": len(delta_timestamps_ms),
            "itl_p50_ms": _percentile(itl_deltas, 0.50),
            "itl_p95_ms": _percentile(itl_deltas, 0.95),
            "tpot_ms": (
                round(
                    (delta_timestamps_ms[-1] - delta_timestamps_ms[0])
                    / (len(delta_timestamps_ms) - 1),
                    2,
                )
                if len(delta_timestamps_ms) >= 2
                and delta_timestamps_ms[-1] >= delta_timestamps_ms[0]
                else None
            ),
        }
        if reasoning_parts:
            stream_timings["reasoning_chars"] = sum(len(p) for p in reasoning_parts)
        return "".join(content_parts), model_name, usage, stream_timings

    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        profile: str | None = None,
        endpoint_url: str | None = None,
        request_id: str | None = None,
    ) -> ChatResult:
        if not profile:
            raise ValueError("OpenAI-compatible comparisons require an explicit model profile")
        if not session:
            session = self.new_session(patient)
        conversation = self._conversations.setdefault(
            session, {"patient": patient, "messages": []}
        )
        if conversation["patient"] != patient:
            raise ValueError("session cannot be reused for a different patient/context")

        target_url = (endpoint_url or self.base_url).rstrip("/")
        messages = [*conversation["messages"], {"role": "user", "content": question}]
        body: dict[str, Any] = {
            "model": profile,
            "stream": self.stream,
            "messages": messages,
        }
        if request_id:
            body["user"] = request_id

        attempt = 0
        started = time.monotonic()
        while True:
            self._throttle()
            try:
                if self.stream:
                    try:
                        response = self._session.post(
                            target_url, json=body, timeout=self.timeout, stream=True
                        )
                    except TypeError:
                        response = self._session.post(
                            target_url, json=body, timeout=self.timeout
                        )
                else:
                    response = self._session.post(
                        target_url, json=body, timeout=self.timeout
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
            if response.status_code != 200:
                latency_ms = int((time.monotonic() - started) * 1000)
                return ChatResult(
                    status=response.status_code,
                    envelope=None,
                    latency_ms=latency_ms,
                    raw_text=getattr(response, "text", ""),
                )

            if self.stream:
                content_str, model_name, usage, stream_timings = self._consume_sse_stream(
                    response, started
                )
                latency_ms = int(stream_timings["turn_done_ms"])
                envelope = _coerce_openai_content_to_envelope(content_str)
                envelope["session"] = session
                envelope["model"] = model_name or profile
                if usage:
                    envelope["usage"] = usage
                envelope["stream_timings"] = stream_timings
                conversation["messages"] = [
                    *messages,
                    {"role": "assistant", "content": str(envelope.get("answer") or "")},
                ]
                return ChatResult(
                    status=200,
                    envelope=envelope,
                    latency_ms=latency_ms,
                    raw_text=content_str,
                )

            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                completion = response.json()
                content = completion["choices"][0]["message"]["content"]
                envelope = _coerce_openai_content_to_envelope(content)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                return ChatResult(
                    status=502,
                    envelope=None,
                    latency_ms=latency_ms,
                    raw_text=f"invalid openai completion: {exc}: {response.text[:500]}",
                )

            envelope["session"] = session
            envelope["model"] = str(completion.get("model") or profile)
            if isinstance(completion.get("usage"), dict) and "usage" not in envelope:
                envelope["usage"] = completion["usage"]
            if isinstance(completion.get("timings"), dict) and "timings" not in envelope:
                envelope["timings"] = completion["timings"]
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
        if self._chart_client is None:
            return {}
        return self._chart_client.get_patient_profile(patient)
