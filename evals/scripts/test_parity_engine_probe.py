"""Red-first tests for scripts/parity-engine-probe.py (engine-parity AC-2).

One turn per arm through the product /chat boundary; the probe then correlates the
tap captures, selects the answer-leg engine request, writes engine_request.<arm>.json
verbatim, and replays it. These tests pin the correlation/selection/parse logic the
live probe runs on.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "parity-engine-probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("parity_engine_probe", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _write_capture(
    capture_dir: Path, stem: str, arm: str, body: dict | bytes, *, path: str = "/v1/chat/completions"
) -> None:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    (capture_dir / f"{stem}.body.json").write_bytes(raw)
    (capture_dir / f"{stem}.meta.json").write_text(
        json.dumps(
            {"arm": arm, "path": path, "method": "POST", "body_file": f"{stem}.body.json",
             "received_at": "2026-07-22T00:00:00+00:00"}
        ),
        encoding="utf-8",
    )


QUESTION = "What was the most recent weight?"


def test_new_captures_filters_by_arm_and_marker(tmp_path):
    mod = _load()
    _write_capture(tmp_path, "100-0000-bundled", "bundled", {"messages": []})
    _write_capture(tmp_path, "200-0001-hub", "hub", {"messages": []})
    _write_capture(tmp_path, "300-0002-hub", "hub", {"messages": []})
    got = mod.new_captures(tmp_path, "hub", since_ns=150)
    assert [c.stem for c in got] == ["200-0001-hub", "300-0002-hub"]
    assert mod.new_captures(tmp_path, "hub", since_ns=250) and \
        [c.stem for c in mod.new_captures(tmp_path, "hub", since_ns=250)] == ["300-0002-hub"]
    assert mod.new_captures(tmp_path, "bundled", since_ns=150) == []


def test_answer_leg_is_largest_body_containing_verbatim_question(tmp_path):
    mod = _load()
    # A small query-generation call also contains the question — must NOT win.
    _write_capture(
        tmp_path, "100-0000-hub", "hub",
        {"model": "gemma-e4b",
         "messages": [{"role": "user", "content": f"Rewrite as search query: {QUESTION}"}]},
    )
    # The answer call: contains the question AND the big serialized chart.
    _write_capture(
        tmp_path, "200-0001-hub", "hub",
        {"model": "gemma-e4b",
         "messages": [
             {"role": "system", "content": "You are a clinical assistant."},
             {"role": "user", "content": ("CHART:\n" + "obs line\n" * 500) + QUESTION},
         ]},
    )
    # Entailment/grounding call: no verbatim question — never a candidate.
    _write_capture(
        tmp_path, "300-0002-hub", "hub",
        {"model": "gemma-e4b",
         "messages": [{"role": "user", "content": "Verify claim: weight was 70 kg" * 100}]},
    )
    captures = mod.new_captures(tmp_path, "hub", since_ns=0)
    chosen = mod.select_answer_leg(captures, QUESTION)
    assert chosen.stem == "200-0001-hub"


def test_answer_leg_requires_a_candidate(tmp_path):
    mod = _load()
    _write_capture(
        tmp_path, "100-0000-bundled", "bundled",
        {"messages": [{"role": "user", "content": "Verify claim: BP was 120/80"}]},
    )
    captures = mod.new_captures(tmp_path, "bundled", since_ns=0)
    with pytest.raises(ValueError, match="no engine request contains the question"):
        mod.select_answer_leg(captures, QUESTION)


def test_answer_leg_ignores_unparseable_bodies(tmp_path):
    mod = _load()
    _write_capture(tmp_path, "100-0000-hub", "hub", b"\x00not json")
    _write_capture(
        tmp_path, "200-0001-hub", "hub",
        {"messages": [{"role": "user", "content": QUESTION}]},
    )
    captures = mod.new_captures(tmp_path, "hub", since_ns=0)
    assert mod.select_answer_leg(captures, QUESTION).stem == "200-0001-hub"


def test_parse_completion_buffered_json():
    mod = _load()
    body = json.dumps(
        {"choices": [{"message": {"content": "The most recent weight was 70 kg."}}]}
    ).encode()
    assert mod.parse_completion("application/json", body) == "The most recent weight was 70 kg."


def test_parse_completion_sse_stream():
    mod = _load()
    frames = (
        b'data: {"choices": [{"delta": {"content": "Weight "}}]}\n\n'
        b'data: {"choices": [{"delta": {"content": "70 kg"}}]}\n\n'
        b'data: {"choices": [{"delta": {}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    assert mod.parse_completion("text/event-stream", frames) == "Weight 70 kg"


def test_parse_completion_empty_is_an_error():
    mod = _load()
    with pytest.raises(ValueError, match="empty completion"):
        mod.parse_completion(
            "application/json",
            json.dumps({"choices": [{"message": {"content": ""}}]}).encode(),
        )


def test_parse_turn_stream_collects_lifecycle_and_answer():
    mod = _load()
    raw = (
        "event: turn_started\n"
        'data: {"provider": "hub"}\n'
        "\n"
        "event: answer_done\n"
        'data: {"answer": "Weight was 70 kg on 2026-01-28.", "messageId": "m-1"}\n'
        "\n"
        "event: turn_done\n"
        'data: {}\n'
        "\n"
    )
    turn = mod.parse_turn_stream(raw)
    assert turn["events"] == ["turn_started", "answer_done", "turn_done"]
    assert turn["answer"] == "Weight was 70 kg on 2026-01-28."
    assert turn["provider"] == "hub"


def test_parse_turn_stream_raises_on_turn_error():
    mod = _load()
    raw = (
        "event: turn_started\n"
        'data: {"provider": "bundled"}\n'
        "\n"
        "event: turn_error\n"
        'data: {"error": "provider_failure", "message": "engine unreachable"}\n'
        "\n"
    )
    with pytest.raises(RuntimeError, match="engine unreachable"):
        mod.parse_turn_stream(raw)


def test_parse_turn_stream_requires_answer_done():
    mod = _load()
    raw = "event: turn_started\ndata: {}\n\n"
    with pytest.raises(RuntimeError, match="ended before answer_done"):
        mod.parse_turn_stream(raw)


def test_new_captures_skips_files_with_a_non_numeric_timestamp_stem(tmp_path):
    """A capture file that doesn't start with `<epoch_ns>-...` (e.g. a stray/manual
    file dropped in the capture dir) must be skipped, not crash the correlation pass."""
    mod = _load()
    (tmp_path / "not-a-timestamp.meta.json").write_text(
        json.dumps({"arm": "hub", "body_file": "missing.body.json"}), encoding="utf-8"
    )
    _write_capture(tmp_path, "100-0000-hub", "hub", {"messages": []})
    got = mod.new_captures(tmp_path, "hub", since_ns=0)
    assert [c.stem for c in got] == ["100-0000-hub"]


def test_answer_leg_skips_bodies_whose_messages_field_is_not_a_list(tmp_path):
    """A malformed/atypical capture body ({"messages": "oops"}) must be skipped by the
    candidate scan rather than raising on the `role`/`content` field access."""
    mod = _load()
    _write_capture(tmp_path, "100-0000-hub", "hub", {"messages": "not-a-list"})
    _write_capture(
        tmp_path, "200-0001-hub", "hub",
        {"messages": [{"role": "user", "content": QUESTION}]},
    )
    captures = mod.new_captures(tmp_path, "hub", since_ns=0)
    assert mod.select_answer_leg(captures, QUESTION).stem == "200-0001-hub"


def test_parse_completion_sse_skips_an_unparseable_frame():
    """One malformed `data:` frame in an SSE stream must not abort collection of the
    valid frames around it."""
    mod = _load()
    frames = (
        b'data: {"choices": [{"delta": {"content": "Weight "}}]}\n\n'
        b"data: {not json}\n\n"
        b'data: {"choices": [{"delta": {"content": "70 kg"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    assert mod.parse_completion("text/event-stream", frames) == "Weight 70 kg"


def test_parse_turn_stream_treats_unparseable_data_as_an_empty_payload():
    """A malformed `data:` line for a known event must not crash the collapse — it is
    treated as an empty payload and the event name is still recorded."""
    mod = _load()
    raw = (
        "event: turn_started\n"
        "data: {not json}\n"
        "\n"
        "event: answer_done\n"
        'data: {"answer": "Weight was 70 kg."}\n'
        "\n"
    )
    turn = mod.parse_turn_stream(raw)
    assert turn["events"] == ["turn_started", "answer_done"]
    assert turn["provider"] is None
    assert turn["answer"] == "Weight was 70 kg."


class _Response:
    def __init__(self, status_code, *, json_body=None, content=b"", headers=None, text=""):
        self.status_code = status_code
        self._json_body = json_body
        self.content = content
        self.headers = headers or {}
        self.text = text or (json.dumps(json_body) if json_body is not None else "")

    def json(self):
        return self._json_body


class _Http:
    """Fake replacing the `requests` module surface `replay()` calls (`.post()`)."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, endpoint, *, data, headers, timeout, stream):
        self.calls.append({"endpoint": endpoint, "data": data, "headers": headers,
                            "timeout": timeout, "stream": stream})
        return self.response


def test_replay_posts_the_body_verbatim_and_parses_the_completion():
    mod = _load()
    response = _Response(
        200, content=json.dumps(
            {"choices": [{"message": {"content": "Weight was 70 kg."}}]}
        ).encode(), headers={"Content-Type": "application/json"},
    )
    http = _Http(response)
    body = b'{"model": "gemma-e4b", "messages": []}'
    result = mod.replay(body, "http://localhost:8077/v1/chat/completions", http=http)
    assert result == "Weight was 70 kg."
    assert http.calls[0]["endpoint"] == "http://localhost:8077/v1/chat/completions"
    assert http.calls[0]["data"] == body


def test_replay_raises_on_a_non_200_response():
    mod = _load()
    http = _Http(_Response(500, text="engine crashed"))
    with pytest.raises(RuntimeError, match="replay -> HTTP 500"):
        mod.replay(b"{}", "http://localhost:8077/v1/chat/completions", http=http)


class _Session:
    """Fake replacing `requests.Session()` for `run_turn()` — one `.post()` per call,
    responses consumed in order (chat/new, then chat/stream)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.auth = None

    def post(self, url, *, json=None, headers=None, timeout=None, stream=False):
        self.requests.append({"url": url, "json": json, "headers": headers,
                               "timeout": timeout, "stream": stream})
        return self.responses.pop(0)


TURN_STREAM_BODY = (
    "event: turn_started\n"
    'data: {"provider": "hub"}\n'
    "\n"
    "event: answer_done\n"
    'data: {"answer": "Weight was 70 kg on 2026-01-28."}\n'
    "\n"
).encode()


def test_run_turn_calls_chat_new_then_chat_stream_and_returns_the_parsed_turn():
    mod = _load()
    session = _Session([
        _Response(200, json_body={"session": "session-1"}),
        _Response(200, content=TURN_STREAM_BODY),
    ])
    turn = mod.run_turn(
        "http://localhost:8088/openmrs", ("admin", "Admin123"),
        "patient-1", "What was the most recent weight?", "hub",
        profile="single-e4b-checked", session_factory=lambda: session,
    )
    assert turn["answer"] == "Weight was 70 kg on 2026-01-28."
    assert turn["provider"] == "hub"
    assert session.auth == ("admin", "Admin123")
    new_call, stream_call = session.requests
    assert new_call["url"].endswith("/ws/rest/v1/chartsearchai/chat/new")
    assert new_call["json"]["provider"] == "hub"
    assert stream_call["url"].endswith("/ws/rest/v1/chartsearchai/chat/stream")
    assert stream_call["json"]["session"] == "session-1"
    assert stream_call["json"]["profile"] == "single-e4b-checked"


def test_run_turn_omits_profile_for_the_bundled_provider():
    mod = _load()
    session = _Session([
        _Response(200, json_body={"session": "session-1"}),
        _Response(200, content=TURN_STREAM_BODY),
    ])
    mod.run_turn(
        "http://localhost:8088/openmrs", ("admin", "Admin123"),
        "patient-1", "q", "bundled", session_factory=lambda: session,
    )
    _, stream_call = session.requests
    assert "profile" not in stream_call["json"]


def test_run_turn_raises_when_chat_new_fails():
    mod = _load()
    session = _Session([_Response(500, text="boom")])
    with pytest.raises(RuntimeError, match=r"\[hub\] /chat/new -> HTTP 500"):
        mod.run_turn(
            "http://localhost:8088/openmrs", ("admin", "Admin123"),
            "patient-1", "q", "hub", session_factory=lambda: session,
        )


def test_run_turn_raises_when_chat_stream_fails():
    mod = _load()
    session = _Session([
        _Response(200, json_body={"session": "session-1"}),
        _Response(503, text="engine overloaded"),
    ])
    with pytest.raises(RuntimeError, match=r"\[hub\] /chat/stream -> HTTP 503"):
        mod.run_turn(
            "http://localhost:8088/openmrs", ("admin", "Admin123"),
            "patient-1", "q", "hub", session_factory=lambda: session,
        )


def test_main_runs_every_arm_correlates_captures_and_writes_a_passing_manifest(
    monkeypatch, tmp_path,
):
    """The real CLI entrypoint end to end: run_turn/replay are the only network calls
    (stubbed here, same as the dedicated run_turn/replay tests above), but capture
    correlation, answer-leg selection, artifact copying, and manifest assembly all run
    for real against real files on disk."""
    mod = _load()
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    out_dir = tmp_path / "out"

    def fake_run_turn(base_url, auth, patient, question, provider, profile=None, timeout=2400.0):
        since_ns = mod.time.time_ns()
        _write_capture(
            capture_dir, f"{since_ns}-0000-{provider}", provider,
            {"model": f"model-{provider}",
             "messages": [{"role": "user", "content": f"CHART...\n{question}"}]},
        )
        return {"answer": f"answer from {provider}", "provider": provider,
                "events": ["turn_started", "answer_done"]}

    monkeypatch.setattr(mod, "run_turn", fake_run_turn)
    monkeypatch.setattr(mod, "replay", lambda body, endpoint, timeout=600.0: "replayed completion")
    monkeypatch.setattr(
        "sys.argv",
        ["parity-engine-probe.py", "--patient", "p1", "--question", QUESTION,
         "--arms", "bundled,hub", "--capture-dir", str(capture_dir), "--out-dir", str(out_dir)],
    )

    exit_code = mod.main()

    assert exit_code == 0
    manifest = json.loads((out_dir / "probe-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["arms"]) == {"bundled", "hub"}
    for arm in ("bundled", "hub"):
        entry = manifest["arms"][arm]
        assert entry["provider"] == arm
        assert entry["model"] == f"model-{arm}"
        assert entry["replay_ok"] is True
        assert (out_dir / f"engine_request.{arm}.json").exists()


def test_main_skip_replay_never_calls_replay(monkeypatch, tmp_path):
    mod = _load()
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    out_dir = tmp_path / "out"

    def fake_run_turn(base_url, auth, patient, question, provider, profile=None, timeout=2400.0):
        since_ns = mod.time.time_ns()
        _write_capture(
            capture_dir, f"{since_ns}-0000-{provider}", provider,
            {"model": "m", "messages": [{"role": "user", "content": question}]},
        )
        return {"answer": "a", "provider": provider, "events": ["answer_done"]}

    replay_calls = []
    monkeypatch.setattr(mod, "run_turn", fake_run_turn)
    monkeypatch.setattr(mod, "replay", lambda *a, **k: replay_calls.append(1) or "unused")
    monkeypatch.setattr(
        "sys.argv",
        ["parity-engine-probe.py", "--patient", "p1", "--question", QUESTION,
         "--arms", "bundled", "--capture-dir", str(capture_dir), "--out-dir", str(out_dir),
         "--skip-replay"],
    )

    exit_code = mod.main()

    assert exit_code == 0
    assert replay_calls == []
    manifest = json.loads((out_dir / "probe-manifest.json").read_text(encoding="utf-8"))
    assert "replay_ok" not in manifest["arms"]["bundled"]
    assert manifest["replay_endpoint"] is None


def test_main_records_a_per_arm_failure_and_returns_1(monkeypatch, tmp_path):
    """A run_turn failure on one arm must be caught, recorded in the manifest, and
    fail the whole probe (exit 1) — a partial/silent probe result is never acceptable."""
    mod = _load()
    out_dir = tmp_path / "out"

    def failing_run_turn(base_url, auth, patient, question, provider, profile=None, timeout=2400.0):
        raise RuntimeError(f"[{provider}] /chat/new -> HTTP 500: boom")

    monkeypatch.setattr(mod, "run_turn", failing_run_turn)
    monkeypatch.setattr(
        "sys.argv",
        ["parity-engine-probe.py", "--patient", "p1", "--question", QUESTION,
         "--arms", "bundled", "--out-dir", str(out_dir), "--skip-replay"],
    )

    exit_code = mod.main()

    assert exit_code == 1
    manifest = json.loads((out_dir / "probe-manifest.json").read_text(encoding="utf-8"))
    assert "boom" in manifest["arms"]["bundled"]["error"]
