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
