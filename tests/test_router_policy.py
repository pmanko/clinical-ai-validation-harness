from __future__ import annotations

import json
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from harness.validate import router_policy
from harness.validate.client import ChatResult
from harness.validate.models import Backend
from harness.validate.router_policy import effective_llama_router_models_max


def test_backend_parses_explicit_llama_router_models_max():
    backend = Backend.from_dict(
        "high",
        {
            "label": "High team",
            "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
            "modelName": "med-agent-team-high",
            "llamaRouterModelsMax": 1,
        },
    )

    assert backend.llama_router_models_max == 1
    assert effective_llama_router_models_max(backend) == 1


def test_llama_backed_backend_defaults_to_warm_cache_cap():
    backend = Backend.from_dict(
        "normal",
        {
            "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
            "modelName": "answer:gemma-4-12b",
        },
    )

    assert backend.llama_router_models_max is None
    assert effective_llama_router_models_max(backend) == 4


def _backend(
    *,
    endpoint: str = "http://med-agent-hub:8080/v1/chat/completions",
    model: str = "single-e4b-checked",
    models_max: int | None = None,
) -> Backend:
    return Backend(
        id="test",
        label="Test",
        endpoint_url=endpoint,
        model_name=model,
        llama_router_models_max=models_max,
    )


def test_remote_backend_does_not_manage_the_local_router(tmp_path):
    backend = _backend(
        endpoint="https://models.example/v1/chat/completions",
        model="answer:gemma-4-12b",
        models_max=1,
    )

    assert effective_llama_router_models_max(backend) is None
    assert router_policy.reconcile_llama_router_for_backend(
        backend, project_root=tmp_path
    ) is None


@pytest.mark.parametrize(
    ("endpoint", "model", "expected"),
    [
        ("http://localhost:8077/v1/chat/completions", "model", True),
        ("http://localhost:8080/v1/chat/completions", "single-e4b-checked", True),
        ("http://med-agent-hub:8080/v1/chat/completions", "profile", True),
        ("https://models.example/v1", "answer:gemma-4-12b", False),
        ("https://models.example/v1", "indepth-only:gemma-e4b", False),
        ("https://models.example/v1", "med-agent-team-high", False),
        ("https://models.example:8077/v1", "answer:gemma-4-12b", False),
        ("http://localhost:not-a-port/v1", "answer:gemma-4-12b", False),
        ("https://models.example/v1", "remote-model", False),
    ],
)
def test_local_router_detection(endpoint, model, expected):
    assert router_policy._uses_local_llama_router(
        _backend(endpoint=endpoint, model=model)
    ) is expected


def test_reconciliation_can_be_explicitly_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("VALIDATE_MANAGE_LLAMA_ROUTER", "off")

    result = router_policy.reconcile_llama_router_for_backend(
        _backend(models_max=1), project_root=tmp_path
    )

    assert result == {
        "schema_version": "llama_router_policy.v1",
        "action": "skipped",
        "status": "disabled",
        "requested_models_max": 1,
        "current_models_max": None,
        "pid": None,
        "detail": "VALIDATE_MANAGE_LLAMA_ROUTER disabled local router reconciliation.",
    }


def test_reconciliation_is_noop_when_reachable_policy_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(router_policy, "_router_parent_processes", lambda *_: [{"pid": 41}])
    monkeypatch.setattr(router_policy, "_current_models_max", lambda *_: 1)
    monkeypatch.setattr(router_policy, "_router_reachable", lambda *_: True)
    monkeypatch.setattr(
        router_policy,
        "_start_router",
        lambda *_: pytest.fail("matching router must not restart"),
    )

    result = router_policy.reconcile_llama_router_for_backend(
        _backend(models_max=1), project_root=tmp_path
    )

    assert result["action"] == "noop"
    assert result["status"] == "ready"
    assert result["current_models_max"] == 1
    assert result["pid"] == 41


def test_reachable_unmanaged_router_fails_with_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(router_policy, "_router_parent_processes", lambda *_: [])
    monkeypatch.setattr(router_policy, "_current_models_max", lambda *_: None)
    monkeypatch.setattr(router_policy, "_router_reachable", lambda *_: True)

    with pytest.raises(RuntimeError, match="stop it manually"):
        router_policy.reconcile_llama_router_for_backend(
            _backend(models_max=1), project_root=tmp_path
        )


@pytest.mark.parametrize(
    ("reachable", "parents", "expected_action"),
    [(False, [], "started"), (True, [{"pid": 44}], "restarted")],
)
def test_reconciliation_starts_or_restarts_with_requested_cap(
    monkeypatch, tmp_path, reachable, parents, expected_action
):
    calls: list[tuple] = []
    monkeypatch.setattr(router_policy, "_router_parent_processes", lambda *_: parents)
    monkeypatch.setattr(router_policy, "_current_models_max", lambda *_: 4 if parents else None)
    monkeypatch.setattr(router_policy, "_router_reachable", lambda *_: reachable)
    monkeypatch.setattr(router_policy, "_stop_router_tree", lambda rows: calls.append(("stop", rows)))
    monkeypatch.setattr(
        router_policy,
        "_start_router",
        lambda root, cap: calls.append(("start", root, cap)) or 99,
    )
    monkeypatch.setattr(
        router_policy,
        "_wait_for_router",
        lambda port, timeout: calls.append(("wait", port, timeout)),
    )
    monkeypatch.setattr(
        router_policy,
        "_write_marker",
        lambda root, cap, pid: calls.append(("marker", root, cap, pid)),
    )

    result = router_policy.reconcile_llama_router_for_backend(
        _backend(models_max=1), project_root=tmp_path, port=9000, startup_timeout_s=12
    )

    assert result["action"] == expected_action
    assert result["requested_models_max"] == 1
    assert result["pid"] == 99
    assert ("start", tmp_path.resolve(), 1) in calls
    assert ("wait", 9000, 12) in calls
    assert ("marker", tmp_path.resolve(), 1, 99) in calls
    assert any(call[0] == "stop" for call in calls) is bool(parents)


def test_router_reachability_handles_success_and_connection_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: SimpleNamespace(ok=True))
    assert router_policy._router_reachable(8077) is True

    def unavailable(*_args, **_kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", unavailable)
    assert router_policy._router_reachable(8077) is False


def test_process_rows_parse_valid_lines_and_fail_safe(monkeypatch):
    output = "  12  1 llama-server --port 8077\ninvalid\n 20 12 worker\n"
    monkeypatch.setattr(
        router_policy.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=output),
    )
    assert router_policy._ps_rows() == [
        {"pid": 12, "ppid": 1, "command": "llama-server --port 8077"},
        {"pid": 20, "ppid": 12, "command": "worker"},
    ]

    def failed_ps(*_args, **_kwargs):
        raise OSError("ps unavailable")

    monkeypatch.setattr(router_policy.subprocess, "run", failed_ps)
    assert router_policy._ps_rows() == []


def test_router_process_and_models_max_discovery(monkeypatch, tmp_path):
    preset = tmp_path / "scripts" / "llama-router.ini"
    rows = [
        {"pid": 10, "ppid": 1, "command": "unrelated"},
        {"pid": 11, "ppid": 1, "command": "llama-server --port 8077 --models-max=2"},
        {
            "pid": 12,
            "ppid": 1,
            "command": f"llama-server --models-preset {preset} --models-max 3",
        },
    ]
    monkeypatch.setattr(router_policy, "_ps_rows", lambda: rows)

    parents = router_policy._router_parent_processes(tmp_path, 8077)
    assert [row["pid"] for row in parents] == [11, 12]
    assert router_policy._current_models_max(tmp_path, parents) == 2

    marker = tmp_path / "artifacts" / "llama-router.models-max"
    marker.parent.mkdir()
    marker.write_text("4\n", encoding="utf-8")
    assert router_policy._current_models_max(tmp_path, []) == 4
    marker.write_text("not-an-int", encoding="utf-8")
    assert router_policy._current_models_max(tmp_path, []) is None


def test_descendant_walk_and_router_tree_shutdown(monkeypatch):
    monkeypatch.setattr(
        router_policy,
        "_ps_rows",
        lambda: [
            {"pid": 2, "ppid": 1, "command": "child"},
            {"pid": 3, "ppid": 2, "command": "grandchild"},
            {"pid": 9, "ppid": 8, "command": "unrelated"},
        ],
    )
    assert router_policy._descendant_pids({1}) == {2, 3}

    killed: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(router_policy.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(router_policy, "_pid_alive", lambda _pid: False)
    router_policy._stop_router_tree([{"pid": 1}])
    assert killed == [(3, signal.SIGTERM), (2, signal.SIGTERM), (1, signal.SIGTERM)]


def test_pid_alive_distinguishes_missing_and_inaccessible_processes(monkeypatch):
    monkeypatch.setattr(router_policy.os, "kill", lambda *_: None)
    assert router_policy._pid_alive(1) is True

    def missing(*_args):
        raise ProcessLookupError

    monkeypatch.setattr(router_policy.os, "kill", missing)
    assert router_policy._pid_alive(1) is False

    def inaccessible(*_args):
        raise PermissionError

    monkeypatch.setattr(router_policy.os, "kill", inaccessible)
    assert router_policy._pid_alive(1) is True


def test_start_wait_and_marker_helpers(monkeypatch, tmp_path):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(pid=321)

    monkeypatch.setattr(router_policy.subprocess, "Popen", fake_popen)
    pid = router_policy._start_router(tmp_path, 1)
    assert pid == 321
    assert captured["kwargs"]["env"]["LLAMA_ROUTER_MODELS_MAX"] == "1"
    assert captured["kwargs"]["start_new_session"] is True

    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: SimpleNamespace(ok=True))
    router_policy._wait_for_router(8077, 1)

    times = iter([0.0, 0.1, 2.0])
    monkeypatch.setattr(router_policy.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(router_policy.time, "sleep", lambda _seconds: None)

    def unavailable(*_args, **_kwargs):
        raise requests.ConnectionError("not ready")

    monkeypatch.setattr(requests, "get", unavailable)
    with pytest.raises(RuntimeError, match="not ready"):
        router_policy._wait_for_router(8077, 1)

    router_policy._write_marker(tmp_path, 2, 321)
    assert (tmp_path / "artifacts" / "llama-router.models-max").read_text() == "2\n"
    assert (tmp_path / "artifacts" / "llama-router.pid").read_text() == "321\n"


class _StubClient:
    def new_session(self, patient: str) -> str:
        return f"sess-{patient}"

    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        endpoint_url: str | None = None,
        model_name: str | None = None,
    ) -> ChatResult:
        return ChatResult(
            status=200,
            envelope={"answer": f"answer from {model_name}", "session": session},
            latency_ms=1,
            raw_text="ok",
        )


def _write_mini_data(root: Path) -> None:
    (root / "comparison_sets").mkdir(parents=True)
    (root / "scenarios").mkdir()
    (root / "comparison_sets" / "mini.json").write_text(
        json.dumps({
            "id": "mini",
            "scenario_ids": ["s1"],
            "backend_ids": ["normal", "high"],
        }),
        encoding="utf-8",
    )
    (root / "scenarios" / "s1.json").write_text(
        json.dumps({
            "id": "s1",
            "patient_ref": "patient-1",
            "turns": [{"n": 1, "question": "What happened?"}],
        }),
        encoding="utf-8",
    )
    (root / "backends.json").write_text(
        json.dumps({
            "normal": {
                "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                "modelName": "answer:gemma-4-12b",
            },
            "high": {
                "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                "modelName": "med-agent-team-high",
                "llamaRouterModelsMax": 1,
            },
        }),
        encoding="utf-8",
    )


def test_runner_records_router_policy_event_per_backend(tmp_path):
    from harness.validate.runner import run_comparison

    data = tmp_path / "data"
    _write_mini_data(data)
    calls: list[tuple[str, int | None]] = []

    def policy(backend: Backend) -> dict:
        requested = effective_llama_router_models_max(backend)
        calls.append((backend.id, requested))
        return {
            "schema_version": "llama_router_policy.v1",
            "action": "noop",
            "status": "ready",
            "requested_models_max": requested,
        }

    res = run_comparison(
        comparison_set_id="mini",
        client=_StubClient(),
        data_root=data,
        output_dir=tmp_path / "runs",
        router_policy=policy,
    )

    assert calls == [("normal", 4), ("high", 1)]
    events = [
        json.loads(line)
        for line in (res.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    policy_events = [e for e in events if e["event_type"] == "llama_router_policy"]
    assert [(e["backend_id"], e["requested_models_max"]) for e in policy_events] == [
        ("normal", 4),
        ("high", 1),
    ]
