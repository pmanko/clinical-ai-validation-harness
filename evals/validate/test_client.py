import json

from harness.validate.client import ChartSearchAiClient


def _sse(events):
    out = []
    for name, payload in events:
        out.append(f"event: {name}\ndata: {json.dumps(payload)}\n\n")
    return "".join(out).encode()


_OK_STREAM = _sse([
    ("turn_started", {"provider": "bundled"}),
    ("answer_done", {"answer": "ok", "references": [], "session": "sess-server", "messageId": "m1"}),
    ("turn_done", {}),
])


class FakeResp:
    """Non-200 or JSON response (new_session, retry paths)."""

    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.content = text.encode()
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeStreamResp:
    """A 200 SSE response from POST /chat/stream."""

    def __init__(self, body=_OK_STREAM):
        self.status_code = 200
        self.content = body
        self.text = body.decode()
        self.headers = {"Content-Type": "text/event-stream"}

    def json(self):
        raise ValueError("SSE body is not JSON")


def _client():
    # No throttle, no real backoff sleep — exercise the retry control flow only.
    return ChartSearchAiClient(
        base_url="http://x/openmrs", min_interval_s=0, max_retries=3, retry_wait_s=0
    )


def test_chat_posts_the_stream_endpoint_and_collapses_the_lifecycle():
    c = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        captured["url"] = url
        captured["body"] = json
        return FakeStreamResp(_sse([
            ("turn_started", {"provider": "hub"}),
            ("answer_delta", {"delta": "ok"}),
            ("answer_done", {"answer": "ok", "references": [{"index": 1}],
                             "session": "sess-server", "messageId": "m1"}),
            ("indepth_done", {"content": "background", "messageId": "m1"}),
            ("turn_done", {}),
        ]))

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert captured["url"].endswith("/chat/stream")
    assert res.status == 200
    assert res.envelope["answer"] == "ok"
    assert res.envelope["references"] == [{"index": 1}]
    assert res.envelope["session"] == "sess-server"
    assert res.envelope["inDepth"] == {"content": "background", "messageId": "m1"}
    # lifecycle recorded without the per-token delta noise
    assert res.envelope["events"] == ["turn_started", "answer_done", "indepth_done", "turn_done"]


def test_chat_turn_error_yields_envelope_without_answer():
    c = _client()

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        return FakeStreamResp(_sse([
            ("turn_started", {"provider": "hub"}),
            ("turn_error", {"problemCode": "provider_failure"}),
        ]))

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 200
    assert "answer" not in res.envelope  # _row_is_good must treat this as not-done
    assert res.envelope["problemCode"] == "provider_failure"


def test_chat_retries_on_429_then_succeeds():
    c = _client()
    seq = [
        FakeResp(429, {"error": "Rate limit exceeded"}, '{"error":"Rate limit exceeded"}'),
        FakeStreamResp(),
    ]
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        resp = seq[calls["n"]]
        calls["n"] += 1
        return resp

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 200 and res.envelope["answer"] == "ok"
    assert calls["n"] == 2  # retried once after the 429


def test_chat_sends_per_request_product_profile_in_body():
    c = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        captured.clear()
        captured.update(json or {})
        return FakeStreamResp()

    c._session.post = fake_post

    c.chat("pat", "sess", "q", profile="single-e4b-checked")
    assert captured["profile"] == "single-e4b-checked"
    assert "endpointUrl" not in captured and "modelName" not in captured

    # Without an override, the body carries no backend keys (the server uses its
    # config-controlled global default).
    c.chat("pat", "sess", "q")
    assert "profile" not in captured


def test_chat_sends_provider_in_body_only_when_pinned():
    c = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        captured.clear()
        captured.update(json or {})
        return FakeStreamResp()

    c._session.post = fake_post

    c.chat("pat", "sess", "q", provider="bundled")
    assert captured["provider"] == "bundled"

    c.chat("pat", "sess", "q")
    assert "provider" not in captured


def test_new_session_sends_provider_only_when_pinned():
    c = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        captured.clear()
        captured.update(json or {})
        return FakeResp(200, {"session": "sess-1"}, "{}")

    c._session.post = fake_post

    assert c.new_session("pat", provider="hub") == "sess-1"
    assert captured["provider"] == "hub"

    c.new_session("pat")
    assert "provider" not in captured


def test_chat_records_429_after_exhausting_retries():
    c = ChartSearchAiClient(base_url="http://x/openmrs", min_interval_s=0, max_retries=2, retry_wait_s=0)

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        return FakeResp(429, {"error": "Rate limit exceeded"}, '{"error":"Rate limit exceeded"}')

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 429  # recorded as a failed turn, never raised


def test_chat_retries_on_502_then_succeeds():
    # A transient gateway error (backend restarting) must be retried, not surfaced as
    # a failed turn on the first hit.
    c = _client()
    seq = [FakeResp(502, None, ""), FakeStreamResp()]
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        resp = seq[calls["n"]]
        calls["n"] += 1
        return resp

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 200 and calls["n"] == 2  # retried once after the 502


def test_new_session_retries_on_502_then_succeeds():
    # new_session was the un-retried, run-aborting call: a single 502 used to raise and
    # kill the whole run. It must retry the transient and recover.
    c = _client()
    seq = [FakeResp(502, None, ""), FakeResp(200, {"session": "sess-1"}, "{}")]
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        resp = seq[calls["n"]]
        calls["n"] += 1
        return resp

    c._session.post = fake_post
    assert c.new_session("pat") == "sess-1" and calls["n"] == 2


def test_chat_retries_on_connection_error_then_succeeds():
    # A dropped connection / read timeout (requests raises) must be retried too, not
    # propagated on the first hit.
    import requests

    c = _client()
    state = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None, stream=None):
        state["n"] += 1
        if state["n"] == 1:
            raise requests.ConnectionError("connection refused")
        return FakeStreamResp()

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 200 and state["n"] == 2  # retried once after the connection error


class _GetResp:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self.ok = ok

    def json(self):
        return self._payload


def test_get_patient_profile_assembles_demographics_meds_counts_vitals():
    c = _client()

    def fake_get(url, timeout=None):
        if "/rest/v1/patient/" in url:
            return _GetResp({
                "identifiers": [{"identifier": "2428TU-4", "identifierType": {"name": "OpenMRS ID"}}],
                "person": {"display": "Zabella", "gender": "F", "age": 47,
                           "birthdate": "1978-10-08T00:00:00.000+0000"},
            })
        if "MedicationRequest" in url:
            return _GetResp({"entry": [
                {"resource": {"status": "active", "medicationReference": {"display": "Stavudine"}}},
                {"resource": {"status": "active", "medicationReference": {"display": "Lamivudine"}}},
                {"resource": {"status": "stopped", "medicationReference": {"display": "OldDrug"}}},
            ]})
        if "/rest/v1/encounter" in url:
            return _GetResp({"totalCount": 11})
        if "Observation" in url:
            return _GetResp({"total": 303, "entry": [
                {"resource": {"code": {"text": "Pulse"}, "valueQuantity": {"value": 69, "unit": "beats/min"}}},
                {"resource": {"code": {"text": "Arterial blood oxygen saturation (pulse oximeter)"},
                              "valueQuantity": {"value": 93, "unit": "%"}}},
            ]})
        return _GetResp(None, ok=False)

    c._session.get = fake_get
    prof = c.get_patient_profile("uuid-1")
    assert prof["display"] == "Zabella" and prof["identifier"] == "2428TU-4"
    assert prof["gender"] == "F" and prof["age"] == 47 and prof["birthdate"] == "1978-10-08"
    # active meds only, deduped + sorted; the stopped order is dropped
    assert prof["medications"] == ["Lamivudine", "Stavudine"]
    assert prof["encounter_count"] == 11 and prof["observation_count"] == 303
    # the SpO2 obs ("...pulse oximeter") must NOT also fill Pulse with the saturation value
    assert prof["vitals"]["Pulse"] == "69 beats/min"
    assert prof["vitals"]["SpO2"] == "93%"


def test_get_patient_profile_is_best_effort_and_never_raises():
    c = _client()

    def boom(url, timeout=None):
        raise RuntimeError("network down")

    c._session.get = boom
    assert c.get_patient_profile("uuid-1") == {}  # total failure -> empty, not an exception
