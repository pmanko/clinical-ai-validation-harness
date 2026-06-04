from harness.validate.client import ChartSearchAiClient


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client():
    # No throttle, no real backoff sleep — exercise the retry control flow only.
    return ChartSearchAiClient(
        base_url="http://x/openmrs", min_interval_s=0, max_retries=3, retry_wait_s=0
    )


def test_chat_retries_on_429_then_succeeds():
    c = _client()
    seq = [
        FakeResp(429, {"error": "Rate limit exceeded"}, '{"error":"Rate limit exceeded"}'),
        FakeResp(200, {"answer": "ok", "references": []}, "{}"),
    ]
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        resp = seq[calls["n"]]
        calls["n"] += 1
        return resp

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 200 and res.envelope["answer"] == "ok"
    assert calls["n"] == 2  # retried once after the 429


def test_chat_sends_per_request_backend_override_in_body():
    c = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.clear()
        captured.update(json or {})
        return FakeResp(200, {"answer": "ok", "references": []}, "{}")

    c._session.post = fake_post

    c.chat("pat", "sess", "q",
           endpoint_url="http://hub:8080/v1/chat/completions", model_name="med-agent-team")
    assert captured["endpointUrl"] == "http://hub:8080/v1/chat/completions"
    assert captured["modelName"] == "med-agent-team"

    # Without an override, the body carries no backend keys (the server uses its
    # config-controlled global default).
    c.chat("pat", "sess", "q")
    assert "endpointUrl" not in captured and "modelName" not in captured


def test_chat_records_429_after_exhausting_retries():
    c = ChartSearchAiClient(base_url="http://x/openmrs", min_interval_s=0, max_retries=2, retry_wait_s=0)

    def fake_post(url, json=None, timeout=None):
        return FakeResp(429, {"error": "Rate limit exceeded"}, '{"error":"Rate limit exceeded"}')

    c._session.post = fake_post
    res = c.chat("p", "s", "q")
    assert res.status == 429  # recorded as a failed turn, never raised


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
