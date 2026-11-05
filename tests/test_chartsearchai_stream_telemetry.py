import importlib.util
import json
from pathlib import Path
import re
import threading

from harness.validate.client import (
    ChartSearchAiClient,
    ChatResult,
    _compute_stream_timings,
    collapse_turn_stream,
)
from harness.validate.concurrency import run_concurrency_benchmark
from harness.validate.metrics import compute_metrics
from harness.validate.report import build_report
from harness.validate.runner import write_run_meta

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


def test_write_run_meta_and_report_surface_hardware_and_streaming_latency(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("VALIDATE_HARDWARE_TIER", "gpu_server")
    monkeypatch.setenv("VALIDATE_HARDWARE_GPU", "NVIDIA H200")
    monkeypatch.setenv("VALIDATE_HARDWARE_VRAM_GB", "141")
    monkeypatch.setenv("VALIDATE_SERVING_ENGINE", "vllm")
    monkeypatch.setenv("VALIDATE_PARALLEL_SLOTS", "4")

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    write_run_meta(
        run_dir,
        run_id="r1",
        backend_ids=["hub-profile-single-12b-bare"],
        reference_date="2026-06-20",
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "r1",
                "component": "validate",
                "git_sha": "abc123",
                "dataset_id": "demo",
                "otel": {"gen_ai.provider.name": "med-agent-hub"},
                "generated_at": "2026-11-03",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "backend_selected",
                "backend_id": "hub-profile-single-12b-bare",
                "modelName": "single-12b-bare",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    row = {
        "run_id": "r1",
        "scenario_id": "s1",
        "backend_id": "hub-profile-single-12b-bare",
        "turn": 1,
        "request": {"question": "What is the weight?"},
        "response": {
            "answer": "Weight is 71 kg [1].",
            "references": [{"index": 1, "resourceType": "Observation"}],
        },
        "metrics": {
            "latency_ms": 4100,
            "http_status": 200,
            "json_valid": True,
            "citation_count": 1,
            "references_empty": False,
            "first_turn": True,
            "ttft_ms": 480,
            "answer_done_ms": 1920,
            "turn_done_ms": 4100,
            "tpot_ms": 18.5,
            "cached_tokens": 10240,
        },
    }
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    html = build_report(run_dir).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>",
        html,
        re.DOTALL,
    ).group(1)
    run_blob = json.loads(body)["runs"][0]

    assert run_blob["hardware"] == {
        "tier": "gpu_server",
        "gpu": "NVIDIA H200",
        "vram_gb": 141,
        "serving_engine": "vllm",
        "parallel_slots": 4,
    }
    streaming = run_blob["summary"][0]["streaming_latency"]
    assert streaming["avg_ttft_ms"] == 480.0
    assert streaming["p95_ttft_ms"] == 480.0
    assert streaming["avg_answer_done_ms"] == 1920.0
    assert streaming["avg_turn_done_ms"] == 4100.0
    assert streaming["avg_tpot_ms"] == 18.5
    assert streaming["avg_cached_tokens"] == 10240.0

    cell = run_blob["scenarios"][0]["turns"][0]["cells"]["hub-profile-single-12b-bare"]
    assert "TTFT 0.5 s" in cell["chips_html"]
    assert "answer 1.9 s" in cell["chips_html"]
    assert "TPOT 18.5ms/tok" in cell["chips_html"]
    assert cell["metrics"]["ttft_ms"] == 480
    assert cell["metrics"]["answer_done_ms"] == 1920
    assert cell["metrics"]["tpot_ms"] == 18.5


def test_concurrency_benchmark_isolates_clinician_sessions_and_aggregates_percentiles(
    tmp_path,
):
    data_root = tmp_path / "datasets" / "validation"
    (data_root / "comparison_sets").mkdir(parents=True)
    (data_root / "scenarios").mkdir(parents=True)
    (data_root / "backends.json").write_text(
        json.dumps(
            {
                "hub-profile-single-12b-bare": {
                    "label": "Single 12B bare",
                    "kind": "openmrs-provider-profile",
                    "provider": "med-agent-hub",
                    "endpointUrl": "http://localhost:8080/openmrs/ws/rest/v1/chartsearchai/chat",
                    "modelName": "single-12b-bare",
                }
            }
        ),
        encoding="utf-8",
    )
    (data_root / "comparison_sets" / "conc-demo.json").write_text(
        json.dumps(
            {
                "id": "conc-demo",
                "transport": "chartsearchai",
                "scenario_ids": ["scen-a", "scen-b"],
                "backend_ids": ["hub-profile-single-12b-bare"],
            }
        ),
        encoding="utf-8",
    )
    for sid, pt in (("scen-a", "patient-a"), ("scen-b", "patient-b")):
        (data_root / "scenarios" / f"{sid}.json").write_text(
            json.dumps(
                {
                    "id": sid,
                    "patient_ref": pt,
                    "turns": [
                        {"n": 1, "question": "Current medications?"},
                        {"n": 2, "question": "Any recent viral load?"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    lock = threading.Lock()
    observed_users: list[str] = []

    class _WorkerClient:
        def __init__(self, user: str, password: str):
            self.user = user
            self.password = password

        def new_session(self, patient: str, *, provider: str | None = None) -> str:
            with lock:
                observed_users.append(self.user)
            return f"sess-{self.user}-{patient}-{provider}"

        def chat(
            self,
            patient: str,
            session: str | None,
            question: str,
            *,
            profile: str | None = None,
            provider: str | None = None,
            request_id: str | None = None,
            reference_date: str | None = None,
        ) -> ChatResult:
            envelope = {
                "session": session,
                "answer": f"Answered for {patient} by {self.user} [1].",
                "references": [{"index": 1, "resourceType": "MedicationRequest"}],
                "inputTokens": 4096,
                "outputTokens": 40,
                "cachedTokens": 3800,
                "stream_timings": {
                    "ttft_ms": 300,
                    "answer_done_ms": 900,
                    "turn_done_ms": 1500,
                    "tpot_ms": 15.0,
                },
            }
            return ChatResult(
                status=200,
                envelope=envelope,
                latency_ms=1500,
                raw_text="",
            )

    res = run_concurrency_benchmark(
        comparison_set_id="conc-demo",
        n_users=4,
        turns_per_user=2,
        data_root=data_root,
        output_dir=tmp_path / "out",
        client_factory=lambda u, p: _WorkerClient(u, p),
        hardware_metadata={"tier": "gpu_server", "gpu": "H200", "parallel_slots": 4},
    )

    assert set(observed_users) == {
        "eval-doctor",
        "eval-nurse",
        "eval-pharmacy",
        "eval-clerk",
    }
    assert res.summary["n_users"] == 4
    assert res.summary["turns_per_user"] == 2
    assert res.summary["total_turns"] == 8
    assert res.summary["ok_turns"] == 8
    assert res.summary["error_turns"] == 0
    assert res.summary["error_rate"] == 0.0
    assert res.summary["ttft_p50_ms"] == 300.0
    assert res.summary["turn_1_ttft_p50_ms"] == 300.0
    assert res.summary["turn_2plus_ttft_p50_ms"] == 300.0
    assert res.summary["answer_done_p50_ms"] == 900.0
    assert res.summary["turn_done_p50_ms"] == 1500.0
    assert res.summary["tpot_p50_ms"] == 15.0
    assert res.summary["cached_tokens_avg"] == 3800.0
    assert res.summary["cache_hit_ratio_avg"] == 0.9277
    assert res.summary["goodput_turns"] == 8
    assert res.summary["goodput_rate"] == 1.0
    assert res.summary["hardware"]["gpu"] == "H200"
    assert res.summary_path.exists()
    assert res.results_path.exists()


def test_openai_compatible_client_supports_plain_text_and_sse_streaming(monkeypatch):
    from harness.adapters import TARGET_ADAPTERS
    from harness.validate.client import OpenAICompatibleClient

    assert set(TARGET_ADAPTERS) >= {
        "chartsearchai",
        "med-agent-hub",
        "openai-compatible",
        "catalyst",
        "wahs",
    }

    # 1. Non-streaming plain-text completion with usage + endpoint_url override
    class _PlainResponse:
        status_code = 200
        text = '{"choices":[{"message":{"content":"Plain markdown answer."}}]}'

        def json(self):
            return {
                "model": "qwen2.5-14b-instruct",
                "choices": [{"message": {"content": "Plain markdown answer."}}],
                "usage": {
                    "prompt_tokens": 1200,
                    "completion_tokens": 25,
                    "prompt_tokens_details": {"cached_tokens": 900},
                },
            }

    class _PlainSession:
        def __init__(self):
            self.headers = {}
            self.calls = []

        def post(self, url, *, json, timeout, **kwargs):
            self.calls.append((url, json, timeout, kwargs))
            return _PlainResponse()

    plain_sess = _PlainSession()
    plain_client = OpenAICompatibleClient(
        base_url="http://default-llm:8000/v1/chat/completions",
        session=plain_sess,
        stream=False,
    )
    sid = plain_client.new_session("case-1")
    plain_res = plain_client.chat(
        "case-1",
        sid,
        "Summarize the lab trend.",
        profile="qwen2.5-14b-instruct",
        endpoint_url="http://vllm-a10g:8000/v1/chat/completions",
    )
    assert plain_res.status == 200
    assert plain_res.envelope is not None
    assert plain_res.envelope["answer"] == "Plain markdown answer."
    assert plain_res.envelope["references"] == []
    assert plain_sess.calls[0][0] == "http://vllm-a10g:8000/v1/chat/completions"
    plain_metrics = compute_metrics(
        envelope=plain_res.envelope,
        latency_ms=plain_res.latency_ms,
        http_status=plain_res.status,
        first_turn=True,
    )
    assert plain_metrics["tokens_in"] == 1200
    assert plain_metrics["tokens_out"] == 25
    assert plain_metrics["cached_tokens"] == 900

    # 2. Streaming SSE completion with TTFT / ITL / TPOT telemetry
    ticks = iter([10.000, 10.010, 10.020, 10.030, 10.040, 10.080, 10.120, 10.140])
    monkeypatch.setattr("harness.validate.client.time.monotonic", lambda: next(ticks))

    class _StreamResponse:
        status_code = 200
        text = ""

        def iter_lines(self, decode_unicode=True):
            yield ""
            yield ": keepalive"
            yield "data: {bad"
            yield "data: []"
            yield 'data: {"choices":[{}]}'
            yield 'data: {"model":"gemma-4-12b","choices":[{"delta":{"reasoning_content":"think"}}]}'
            yield 'data: {"model":"gemma-4-12b","choices":[{"delta":{"content":"First "}}]}'
            yield 'data: {"model":"gemma-4-12b","choices":[{"delta":{"content":"second "}}]}'
            yield 'data: {"model":"gemma-4-12b","choices":[{"delta":{"content":"third."}}],"usage":{"prompt_tokens":2048,"completion_tokens":12}}'
            yield "data: [DONE]"

    class _StreamSession:
        def __init__(self):
            self.headers = {}

        def post(self, url, *, json, timeout, stream=False):
            return _StreamResponse()

    stream_client = OpenAICompatibleClient(
        base_url="http://vllm:8000/v1/chat/completions",
        session=_StreamSession(),
        stream=True,
    )
    s_res = stream_client.chat(
        "case-2",
        stream_client.new_session("case-2"),
        "Question?",
        profile="gemma-4-12b",
    )
    assert s_res.status == 200
    assert s_res.envelope is not None
    assert s_res.envelope["answer"] == "First second third."
    st = s_res.envelope["stream_timings"]
    assert st["ttft_ms"] == 30
    assert st["answer_done_ms"] == 120
    assert st["turn_done_ms"] == 140
    assert st["answer_delta_count"] == 3
    assert st["tpot_ms"] == 40.0
    assert st["reasoning_chars"] == 5
    s_metrics = compute_metrics(
        envelope=s_res.envelope,
        latency_ms=s_res.latency_ms,
        http_status=s_res.status,
        first_turn=True,
    )
    assert s_metrics["ttft_ms"] == 30
    assert s_metrics["tpot_ms"] == 40.0
    assert s_metrics["tokens_in"] == 2048
    assert s_metrics["tokens_out"] == 12


def test_live_http_sse_stream_is_unbuffered_and_location_setup_checks_status():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import time as real_time
    import pytest

    class _SseHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):
            if self.path.endswith("/chat/stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                frames = [
                    b'event: answer_delta\ndata: {"delta":"First "}\n\n',
                    b'event: answer_done\ndata: {"answer":"First done.","references":[]}\n\n',
                    b'event: done\ndata: {"session":"s-http","answer":"First done.","references":[]}\n\n',
                ]
                for idx, frame in enumerate(frames):
                    if idx > 0:
                        real_time.sleep(0.06)
                    self.wfile.write(frame)
                    self.wfile.flush()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"session":"s-http"}')

    server = HTTPServer(("127.0.0.1", 0), _SseHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ChartSearchAiClient(
            base_url=f"http://127.0.0.1:{port}/openmrs",
            min_interval_s=0.0,
            max_retries=0,
        )
        res = client.chat("pt-1", "s-http", "Question?")
        assert res.status == 200
        assert res.envelope is not None
        timings = res.envelope["stream_timings"]
        # First frame arrives immediately (~0-30ms), whereas done arrives after ~120ms.
        # Without chunk_size=1, iter_lines buffers all 3 small frames until EOF (~120ms).
        assert timings["ttft_ms"] < timings["turn_done_ms"] - 60
    finally:
        server.shutdown()
        server.server_close()

    # Verify _ensure_session_location only marks applied after HTTP 2xx
    class _LocResp:
        def __init__(self, status_code: int, text: str = ""):
            self.status_code = status_code
            self.text = text

        def json(self):
            return {"session": "s-loc"}

    class _LocSession:
        def __init__(self):
            self.auth = None
            self.headers = {}
            self.responses = [
                _LocResp(503, "unavailable"),
                _LocResp(403, "forbidden"),
                _LocResp(200, "ok"),
                _LocResp(200, '{"session":"s-loc"}'),
            ]

        def post(self, url, *, json=None, timeout=None, stream=False):
            return self.responses.pop(0)

    loc_client = ChartSearchAiClient(
        base_url="http://openmrs.local/openmrs",
        location_uuid="loc-1",
        max_retries=1,
        retry_wait_s=0.0,
        session=_LocSession(),
    )
    with pytest.raises(RuntimeError, match="session location"):
        loc_client.new_session("pt-1")
    assert loc_client._location_applied is False
    # Subsequent call retries location setup and succeeds on 200
    assert loc_client.new_session("pt-1") == "s-loc"
    assert loc_client._location_applied is True


def test_openai_compatible_and_cli_concurrency_edge_branches(tmp_path, monkeypatch):
    import pytest
    from harness.cli import main as cli_main
    from harness.validate.client import (
        OpenAICompatibleClient,
        _coerce_openai_content_to_envelope,
    )
    from harness.validate.concurrency import (
        _make_transport_client_factory,
        _meets_slo,
        summarize_concurrency_rows,
    )

    # _coerce_openai_content_to_envelope branches
    assert _coerce_openai_content_to_envelope({"answer": "A", "citations": [1]}) == {
        "answer": "A",
        "citations": [1],
        "references": [1],
        "blocks": [],
    }
    assert _coerce_openai_content_to_envelope('{"answer": "B"}')["answer"] == "B"
    assert _coerce_openai_content_to_envelope("{not-json}")["answer"] == "{not-json}"
    assert _coerce_openai_content_to_envelope(None)["answer"] == ""

    # _meets_slo branches
    assert _meets_slo({"ttft_ms": 4000}, ttft_slo_ms=3000, answer_done_slo_ms=10000, tpot_slo_ms=50) is False
    assert _meets_slo({"answer_done_ms": 12000}, ttft_slo_ms=3000, answer_done_slo_ms=10000, tpot_slo_ms=50) is False
    assert _meets_slo({"tpot_ms": 80}, ttft_slo_ms=3000, answer_done_slo_ms=10000, tpot_slo_ms=50) is False
    assert summarize_concurrency_rows(
        [],
        run_id="r0",
        comparison_set_id="c0",
        backend_id="b0",
        n_users=1,
        turns_per_user=1,
        wall_clock_s=0.0,
    )["goodput_rate"] == 0.0

    # _make_transport_client_factory branches
    hub_f = _make_transport_client_factory("med-agent-hub", "http://hub/v1/chat/completions")
    oai_f = _make_transport_client_factory("openai-compatible", "http://vllm/v1/chat/completions")
    assert hub_f("u", "p").base_url == "http://hub/v1/chat/completions"
    assert oai_f("u", "p").base_url == "http://vllm/v1/chat/completions"

    # OpenAICompatibleClient error, retry, system_prompt, api_key, and profile branches
    class _ErrResp:
        def __init__(self, status_code: int, text: str = "err", payload=None):
            self.status_code = status_code
            self.text = text
            self._payload = payload

        def json(self):
            if self._payload is None:
                raise ValueError("bad json")
            return self._payload

    class _ErrSession:
        def __init__(self, responses):
            self.headers = {}
            self.responses = list(responses)

        def post(self, url, *, json=None, timeout=None, **kwargs):
            return self.responses.pop(0)

    c_err = OpenAICompatibleClient(
        base_url="http://vllm/v1/chat/completions",
        api_key="k",
        system_prompt="Be concise.",
        stream=False,
        max_retries=1,
        retry_wait_s=0.0,
        session=_ErrSession([_ErrResp(503), _ErrResp(400, "bad req"), _ErrResp(200, "not-json", None)]),
    )
    assert c_err.get_patient_profile("p1") == {}
    with pytest.raises(ValueError, match="profile"):
        c_err.chat("p1", None, "Q?")
    s1 = c_err.new_session("p1")
    with pytest.raises(ValueError, match="different patient"):
        c_err.chat("p2", s1, "Q?", profile="m")
    r_400 = c_err.chat("p1", None, "Q?", profile="m", request_id="req-1")
    assert r_400.status == 400
    r_502 = c_err.chat("p1", s1, "Q?", profile="m")
    assert r_502.status == 502

    # CLI validate run + validate concurrency on openai-compatible transport
    data_root = tmp_path / "validation"
    (data_root / "comparison_sets").mkdir(parents=True)
    (data_root / "scenarios").mkdir(parents=True)
    (data_root / "backends.json").write_text(
        json.dumps(
            {
                "oai-arm": {
                    "label": "OAI Arm",
                    "endpointUrl": "http://vllm:8000/v1/chat/completions",
                    "modelName": "gemma-4-12b",
                    "indepthEndpointUrl": "http://vllm:8000/v1/chat/completions",
                    "indepthModelName": "gemma-4-12b",
                }
            }
        ),
        encoding="utf-8",
    )
    (data_root / "comparison_sets" / "oai-set.json").write_text(
        json.dumps(
            {
                "id": "oai-set",
                "transport": "openai-compatible",
                "scenario_ids": ["s1"],
                "backend_ids": ["oai-arm"],
            }
        ),
        encoding="utf-8",
    )
    (data_root / "scenarios" / "s1.json").write_text(
        json.dumps(
            {
                "id": "s1",
                "patient_ref": "pt-1",
                "turns": [{"n": 1, "question": "Summarize chart."}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "harness.validate.client.OpenAICompatibleClient.chat",
        lambda self, patient, session, question, **kw: ChatResult(
            status=200,
            envelope={
                "session": session or "s-oai",
                "answer": "Summary [1].",
                "references": [{"index": 1}],
                "stream_timings": {"ttft_ms": 120, "answer_done_ms": 300, "turn_done_ms": 310, "tpot_ms": 12.0},
            },
            latency_ms=310,
            raw_text="",
        ),
    )
    rc_run = cli_main(
        [
            "validate",
            "run",
            "oai-set",
            "--data-root",
            str(data_root),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert rc_run == 0

    hw_file = tmp_path / "hw.json"
    hw_file.write_text(json.dumps({"tier": "gpu_server", "gpu": "H200"}), encoding="utf-8")
    rc_conc = cli_main(
        [
            "validate",
            "concurrency",
            "oai-set",
            "--users",
            "2",
            "--turns-per-user",
            "1",
            "--backend-id",
            "oai-arm",
            "--data-root",
            str(data_root),
            "--output-dir",
            str(tmp_path / "conc"),
            "--hardware-metadata",
            str(hw_file),
        ]
    )
    assert rc_conc == 0

    # Concurrency validation & worker failure branches
    with pytest.raises(ValueError, match="n_users"):
        run_concurrency_benchmark(comparison_set_id="oai-set", n_users=0, data_root=data_root)
    with pytest.raises(ValueError, match="turns_per_user"):
        run_concurrency_benchmark(comparison_set_id="oai-set", turns_per_user=0, data_root=data_root)
    with pytest.raises(ValueError, match="accounts"):
        run_concurrency_benchmark(comparison_set_id="oai-set", accounts=(), data_root=data_root)
    with pytest.raises(ValueError, match="backend_id"):
        run_concurrency_benchmark(comparison_set_id="oai-set", backend_id="missing", data_root=data_root)

    class _FaultyWorkerClient:
        def __init__(self, fail_session: bool):
            self.fail_session = fail_session

        def new_session(self, patient: str) -> str:
            if self.fail_session:
                raise RuntimeError("session boom")
            return "s-ok"

        def chat(self, patient: str, session: str | None, question: str, **kw) -> ChatResult:
            raise RuntimeError("chat boom")

    faulty_res = run_concurrency_benchmark(
        comparison_set_id="oai-set",
        n_users=2,
        turns_per_user=1,
        data_root=data_root,
        output_dir=tmp_path / "conc-faulty",
        client_factory=lambda u, _p: _FaultyWorkerClient(fail_session=(u == "eval-doctor")),
    )
    assert faulty_res.summary["error_turns"] == 2

    # Engine-tap edge cases + capture helpers
    raw_bad, meta_bad = ENGINE_TAP.apply_local_engine_dry_policy(b"not-json")
    assert raw_bad == b"not-json" and meta_bad == {"simulated_local_engine_dry": False}
    raw_nom, meta_nom = ENGINE_TAP.apply_local_engine_dry_policy(b'{"other": 1}')
    assert raw_nom == b'{"other": 1}' and meta_nom == {"simulated_local_engine_dry": False}
    assert ENGINE_TAP.extract_upstream_telemetry(b'{"usage":{"prompt_tokens":10},"timings":{"cache_n":5}}') == {
        "usage": {"prompt_tokens": 10},
        "timings": {"cache_n": 5},
    }
    assert ENGINE_TAP.extract_upstream_telemetry(b"{bad-json\ndata: {bad\n") == {}
    ENGINE_TAP._update_capture_meta(tmp_path / "missing.json", {"x": 1})
    cap_meta = ENGINE_TAP._capture(
        tmp_path / "caps",
        "bundled",
        "POST",
        "/v1/chat/completions",
        b'{"messages":[]}',
        extra_meta={"simulated_local_engine_dry": True},
    )
    ENGINE_TAP._update_capture_meta(cap_meta, {"upstream_status": 200})
    saved_meta = json.loads(cap_meta.read_text(encoding="utf-8"))
    assert saved_meta["simulated_local_engine_dry"] is True
    assert saved_meta["upstream_status"] == 200

    # Additional client branches for non-iter_lines SSE and chart_client delegation
    class _TextOnlyStreamResp:
        text = 'data: {"choices":[{"delta":{"content":"Text fallback"}}]}\ndata: [DONE]\n'

    text_content, _, _, text_st = c_err._consume_sse_stream(_TextOnlyStreamResp(), 0.0)
    assert text_content == "Text fallback"
    assert text_st["answer_delta_count"] == 1

    class _StubChartClient:
        def get_patient_profile(self, patient: str):
            return {"uuid": patient}

    c_with_chart = OpenAICompatibleClient(chart_client=_StubChartClient())
    assert c_with_chart.get_patient_profile("p-stub") == {"uuid": "p-stub"}




