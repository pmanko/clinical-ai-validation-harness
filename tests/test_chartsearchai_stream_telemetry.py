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

