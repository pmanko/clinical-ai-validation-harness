import importlib.util
import json
from pathlib import Path

from harness.validate.client import (
    ChartSearchAiClient,
    _compute_stream_timings,
    collapse_turn_stream,
)
from harness.validate.metrics import compute_metrics

ROOT = Path(__file__).parents[1]
TAP_SCRIPT = ROOT / "scripts" / "engine-tap.py"
TAP_SPEC = importlib.util.spec_from_file_location("engine_tap", TAP_SCRIPT)
assert TAP_SPEC and TAP_SPEC.loader
ENGINE_TAP = importlib.util.module_from_spec(TAP_SPEC)
TAP_SPEC.loader.exec_module(ENGINE_TAP)


class _StreamingResponse:
    def __init__(self, status_code: int, lines: list[str], *, on_line=None):
        self.status_code = status_code
        self._lines = list(lines)
        self._on_line = on_line
        self.text = "\n".join(lines)

    def iter_lines(self, decode_unicode: bool = False):
        for idx, line in enumerate(self._lines):
            if self._on_line is not None:
                self._on_line(idx, line)
            yield line if decode_unicode else line.encode("utf-8")


class _StubSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []
        self.auth = None
        self.headers = {}

    def post(self, url, *, json=None, timeout=None, headers=None, stream=False):
        self.posts.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
                "headers": headers,
                "stream": stream,
            }
        )
        return self.responses.pop(0)


def test_collapse_turn_stream_records_milestone_and_itl_timings():
    sse = "\n".join(
        [
            "event: turn_started",
            'data: {"session":"s1","messageId":"m1","provider":"bundled"}',
            "",
            "event: reasoning_delta",
            "data: Thinking...",
            "",
            "event: answer_delta",
            "data: Patient ",
            "",
            "event: answer_delta",
            "data: weight ",
            "",
            "event: answer_delta",
            "data: is 71 kg [1].",
            "",
            "event: answer_done",
            'data: {"answer":"Patient weight is 71 kg [1].","references":[{"index":1}],"inputTokens":4120,"outputTokens":42,"cachedTokens":3900,"model":"gemma-4-12b"}',
            "",
            "event: turn_done",
            'data: {"answer":"Patient weight is 71 kg [1].","references":[{"index":1}],"inputTokens":4120,"outputTokens":42,"cachedTokens":3900,"model":"gemma-4-12b"}',
            "",
        ]
    )
    event_timings = [
        ("turn_started", 5.0),
        ("reasoning_delta", 120.0),
        ("answer_delta", 200.0),
        ("answer_delta", 240.0),
        ("answer_delta", 300.0),
        ("answer_done", 315.0),
        ("turn_done", 320.0),
    ]

    envelope = collapse_turn_stream(
        sse, event_timings=event_timings, total_latency_ms=320
    )

    assert envelope["events"] == ["turn_started", "answer_done", "turn_done"]
    timings = envelope["stream_timings"]
    assert timings["ttft_ms"] == 120
    assert timings["reasoning_start_ms"] == 120
    assert timings["answer_delta_start_ms"] == 200
    assert timings["answer_done_ms"] == 315
    assert timings["turn_done_ms"] == 320
    assert timings["delta_count"] == 4
    assert timings["answer_delta_count"] == 3
    # Answer delta intervals are [40.0, 60.0] -> p50 = 50.0, tpot = 50.0
    assert timings["itl_p50_ms"] == 50.0
    assert timings["itl_p95_ms"] == 59.0
    assert timings["tpot_ms"] == 50.0

    metrics = compute_metrics(
        envelope=envelope,
        latency_ms=320,
        http_status=200,
        first_turn=False,
    )
    assert metrics["tokens_in"] == 4120
    assert metrics["tokens_out"] == 42
    assert metrics["cached_tokens"] == 3900
    assert metrics["gen_ai.response.model"] == "gemma-4-12b"
    assert metrics["ttft_ms"] == 120
    assert metrics["answer_done_ms"] == 315
    assert metrics["turn_done_ms"] == 320
    assert metrics["answer_delta_count"] == 3
    assert metrics["tpot_ms"] == 50.0


def test_stream_timings_fall_back_to_answer_done_when_no_deltas_emitted():
    timings = _compute_stream_timings(
        [
            ("turn_started", 4.0),
            ("answer_done", 850.0),
            ("answer_validation", 1420.0),
            ("indepth_done", 2310.0),
            ("turn_done", 2315.0),
        ],
        total_latency_ms=2315,
    )

    assert timings["ttft_ms"] == 850
    assert timings["answer_done_ms"] == 850
    assert timings["answer_validation_ms"] == 1420
    assert timings["indepth_done_ms"] == 2310
    assert timings["turn_done_ms"] == 2315
    assert timings["delta_count"] == 0
    assert timings["itl_p50_ms"] is None
    assert timings["tpot_ms"] is None


def test_chartsearch_client_streams_lines_and_applies_persona_and_location(monkeypatch):
    lines = [
        "event: turn_started",
        'data: {"session":"sess-1","messageId":"m-1","provider":"hub"}',
        "",
        "event: answer_delta",
        "data: Current ",
        "",
        "event: answer_delta",
        "data: regimen [1].",
        "",
        "event: answer_done",
        'data: {"answer":"Current regimen [1].","references":[{"index":1}],"context":{"input_tokens":8192}}',
        "",
        "event: turn_done",
        'data: {"answer":"Current regimen [1].","references":[{"index":1}],"context":{"input_tokens":8192}}',
        "",
    ]
    clock_ns = [1_000_000_000]

    def advance_clock(_idx: int, line: str) -> None:
        if line.startswith("data:"):
            clock_ns[0] += 25_000_000  # +25 ms per SSE frame

    monkeypatch.setattr("time.perf_counter_ns", lambda: clock_ns[0])
    session = _StubSession(
        [
            _StreamingResponse(200, []),  # /ws/rest/v1/session location post
            _StreamingResponse(200, lines, on_line=advance_clock),
        ]
    )
    client = ChartSearchAiClient(
        base_url="http://openmrs/openmrs",
        user="doctor",
        password="DocPassword123",
        location_uuid="loc-hiv-clinic",
        min_interval_s=0.0,
        session=session,
    )

    result = client.chat("patient-1", "sess-1", "What is the regimen?", profile="single-12b-bare")

    assert session.auth == ("doctor", "DocPassword123")
    assert session.posts[0]["url"] == "http://openmrs/openmrs/ws/rest/v1/session"
    assert session.posts[0]["json"] == {"location": "loc-hiv-clinic"}
    assert session.posts[1]["url"] == "http://openmrs/openmrs/ws/rest/v1/chartsearchai/chat/stream"
    assert session.posts[1]["stream"] is True
    assert result.status == 200
    assert result.envelope is not None
    timings = result.envelope["stream_timings"]
    assert timings["ttft_ms"] == 50
    assert timings["answer_delta_start_ms"] == 50
    assert timings["answer_done_ms"] == 100
    assert timings["turn_done_ms"] == 125
    assert timings["answer_delta_count"] == 2
    assert timings["tpot_ms"] == 25.0

    metrics = compute_metrics(
        envelope=result.envelope,
        latency_ms=result.latency_ms,
        http_status=result.status,
        first_turn=True,
    )
    assert metrics["tokens_in"] == 8192
    assert metrics["tokens_out"] is None
    assert metrics["cached_tokens"] is None


def test_engine_tap_simulates_local_llm_engine_conditional_dry():
    # System prompt mentions "Drug reference" and "Safety finding" in instructions,
    # which must NOT disable DRY when the user chart has no injected reference records.
    non_drug_request = json.dumps(
        {
            "model": "gemma-e4b",
            "messages": [
                {
                    "role": "system",
                    "content": 'Records beginning with "Drug reference" or "Safety finding" are special.',
                },
                {
                    "role": "user",
                    "content": "[1] (2026-01-10) Weight: 71 kg\n\nQuestion: What is the weight?",
                },
            ],
            "temperature": 0.0,
        }
    ).encode("utf-8")

    mutated_bytes, meta = ENGINE_TAP.apply_local_engine_dry_policy(non_drug_request)
    mutated = json.loads(mutated_bytes)

    assert meta == {
        "simulated_local_engine_dry": True,
        "reference_records": "absent",
        "dry_multiplier": 0.8,
    }
    assert mutated["samplers"] == ["dry", "temperature"]
    assert mutated["dry_multiplier"] == 0.8
    assert mutated["dry_base"] == 1.75
    assert mutated["dry_allowed_length"] == 8
    assert mutated["dry_penalty_last_n"] == -1

    # When the user message carries an injected Drug reference or Safety finding record,
    # LocalLlmEngine disables DRY and sends temperature alone.
    drug_request = json.dumps(
        {
            "model": "gemma-e4b",
            "messages": [
                {"role": "system", "content": "System prompt"},
                {
                    "role": "user",
                    "content": "[1] (2026-01-10) Order: Nevirapine\n[2] Drug reference — Nevirapine (ATC J05AG01): hepatotoxicity",
                },
            ],
            "dry_multiplier": 0.8,
        }
    ).encode("utf-8")

    drug_bytes, drug_meta = ENGINE_TAP.apply_local_engine_dry_policy(drug_request)
    drug_payload = json.loads(drug_bytes)

    assert drug_meta == {
        "simulated_local_engine_dry": True,
        "reference_records": "present",
        "dry_multiplier": 0.0,
    }
    assert drug_payload["samplers"] == ["temperature"]
    assert "dry_multiplier" not in drug_payload
    assert "dry_allowed_length" not in drug_payload


def test_engine_tap_extracts_upstream_llama_server_telemetry():
    sse_response = (
        b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
        b'"usage":{"prompt_tokens":12100,"completion_tokens":55,"total_tokens":12155},'
        b'"timings":{"prompt_n":2100,"cache_n":10000,"predicted_n":55,"prompt_ms":420.5,"predicted_ms":1100.2}}\n\n'
        b"data: [DONE]\n\n"
    )
    telemetry = ENGINE_TAP.extract_upstream_telemetry(sse_response)
    assert telemetry["usage"] == {
        "prompt_tokens": 12100,
        "completion_tokens": 55,
        "total_tokens": 12155,
    }
    assert telemetry["timings"]["prompt_n"] == 2100
    assert telemetry["timings"]["cache_n"] == 10000
    assert telemetry["timings"]["predicted_n"] == 55
