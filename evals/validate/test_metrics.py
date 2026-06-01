from harness.validate.metrics import compute_metrics

# A realistic chartsearchai /chat envelope (the real references[] shape).
REAL_ENVELOPE = {
    "answer": "Lisinopril 10 mg [1] and metformin 500 mg [2].",
    "disclaimer": "AI-generated; verify against the record.",
    "references": [
        {"index": 1, "resourceType": "MedicationRequest", "resourceUuid": "u1", "date": "2026-01-01"},
        {"index": 2, "resourceType": "MedicationRequest", "resourceUuid": "u2", "date": "2026-01-02"},
    ],
    "blocks": [],
    "session": "s",
    "messageId": "m",
}

_DEFERRED = ("gen_ai.response.model", "tokens_in", "tokens_out", "finish_reasons")


def test_metrics_from_real_envelope():
    m = compute_metrics(envelope=REAL_ENVELOPE, latency_ms=8421, http_status=200, first_turn=True)
    assert m["json_valid"] is True
    assert m["citation_count"] == 2
    assert m["references_empty"] is False
    assert m["abstained"] is False
    assert m["answer_chars"] > 0
    assert m["latency_ms"] == 8421
    assert m["first_turn"] is True
    # Fields chartsearchai's /chat doesn't surface are present + null (OTel-deferred).
    for key in _DEFERRED:
        assert key in m and m[key] is None


def test_abstained_is_the_references_empty_proxy():
    env = {"answer": "I can't determine that from this chart.", "references": [], "blocks": []}
    m = compute_metrics(envelope=env, latency_ms=100, http_status=200, first_turn=False)
    assert m["citation_count"] == 0
    assert m["references_empty"] is True
    assert m["abstained"] is True  # heuristic proxy == references_empty


def test_metrics_on_http_error():
    m = compute_metrics(envelope=None, latency_ms=50, http_status=500, first_turn=False)
    assert m["json_valid"] is False
    assert m["citation_count"] == 0
    assert m["answer_chars"] == 0
    assert m["http_status"] == 500
