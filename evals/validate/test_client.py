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
