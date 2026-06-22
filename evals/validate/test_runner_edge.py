"""Runner edge-path tests (harness/validate/runner.py) the happy-path suite
(test_runner.py / test_adjudicate_cli.py) doesn't reach:

  - a client whose `chat` is NOT introspectable by inspect.signature() must degrade to
    record-only (no reference_date kwarg) instead of aborting the run;
  - a write_run_meta failure must be swallowed (best-effort provenance, never fatal);
  - an In-Depth call that RAISES must be captured as a status-0 in-depth artifact, not
    propagate and kill the answer survey.

These mirror the defensive `except` blocks in run_comparison; each test breaks (the run
aborts / the row is missing) if the corresponding guard is removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.validate import runner
from harness.validate.client import ChatResult
from harness.validate.runner import run_comparison


def _envelope(n: int) -> dict:
    return {"answer": f"answer {n} [1]", "references": [], "blocks": [],
            "session": "sess-server", "messageId": f"m{n}"}


def _write_fixtures(root: Path, *, indepth: bool = False):
    (root / "scenarios").mkdir(parents=True)
    (root / "comparison_sets").mkdir(parents=True)
    (root / "scenarios" / "sc.json").write_text(
        json.dumps({"id": "sc", "patient_ref": "pat", "turns": [{"n": 1, "question": "q1"}]}),
        encoding="utf-8")
    (root / "comparison_sets" / "cs.json").write_text(
        json.dumps({"id": "cs", "scenario_ids": ["sc"], "backend_ids": ["arm"]}), encoding="utf-8")
    arm = {"label": "Arm", "endpointUrl": "http://router/v1/chat/completions", "modelName": "mm"}
    if indepth:
        arm["indepthEndpointUrl"] = "http://hub/v1/chat/completions"
        arm["indepthModelName"] = "indepth-mm"
    (root / "backends.json").write_text(json.dumps({"arm": arm}), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. non-introspectable client.chat -> degrade to record-only, run completes
# --------------------------------------------------------------------------- #
class _CallableChat:
    """A `chat` whose signature inspect.signature() cannot read (a C-extension-like
    callable). The runner's capability probe must catch the ValueError/TypeError and
    NOT pass a reference_date kwarg the call wouldn't accept."""
    def __init__(self):
        self.calls = []

    # No real signature; simulate inspect.signature raising by overriding __call__ on an
    # object whose signature lookup fails. We mark it so the runner can't introspect.
    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        return ChatResult(status=200, envelope=_envelope(1), latency_ms=5)


class _OddClient:
    def __init__(self, chat_obj):
        self.chat = chat_obj

    def new_session(self, patient):
        return "sess-initial"


def test_non_introspectable_chat_degrades_to_record_only(tmp_path, monkeypatch):
    data = tmp_path / "data"
    _write_fixtures(data)

    chat_obj = _CallableChat()
    client = _OddClient(chat_obj)

    # Force inspect.signature to raise for THIS chat (the documented degrade trigger).
    import inspect as _inspect
    real_sig = _inspect.signature

    def fake_sig(obj, *a, **k):
        if obj is chat_obj:
            raise ValueError("no signature for builtin-like callable")
        return real_sig(obj, *a, **k)

    monkeypatch.setattr(runner.inspect, "signature", fake_sig)

    out = run_comparison(comparison_set_id="cs", client=client, data_root=data,
                         output_dir=tmp_path / "art", reference_date="2026-03-15")
    # The run completed (a row was written) despite the un-introspectable chat...
    rows = out.results_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["metrics"]["http_status"] == 200
    # ...and reference_date was NOT passed to chat (record-only degrade), so the call
    # didn't blow up on an unexpected kwarg.
    assert all("reference_date" not in c for c in chat_obj.calls)


# --------------------------------------------------------------------------- #
# 2. write_run_meta failure is swallowed (best-effort), run still completes
# --------------------------------------------------------------------------- #
class _OkClient:
    def __init__(self):
        self.calls = []

    def new_session(self, patient):
        return "sess-initial"

    def chat(self, patient, session, question, *, endpoint_url=None, model_name=None,
             reference_date=None):
        self.calls.append(question)
        return ChatResult(status=200, envelope=_envelope(len(self.calls)), latency_ms=5)


def test_write_run_meta_failure_is_not_fatal(tmp_path, monkeypatch):
    data = tmp_path / "data"
    _write_fixtures(data)

    def boom(*a, **k):
        raise RuntimeError("levels.yaml unreadable mid-run")

    monkeypatch.setattr(runner, "write_run_meta", boom)

    out = run_comparison(comparison_set_id="cs", client=_OkClient(), data_root=data,
                         output_dir=tmp_path / "art")
    # The run produced results despite write_run_meta raising; run_meta.json is simply absent.
    assert out.result_count == 1
    assert not (out.run_dir / "run_meta.json").exists()


# --------------------------------------------------------------------------- #
# 3. an In-Depth call that RAISES -> captured as a status-0 in-depth artifact
# --------------------------------------------------------------------------- #
class _IndepthRaisesClient:
    """First chat (the answer) succeeds; the second (the In-Depth, to indepth-mm) raises."""
    def __init__(self):
        self.calls = []

    def new_session(self, patient):
        return "sess-initial"

    def chat(self, patient, session, question, *, endpoint_url=None, model_name=None,
             reference_date=None):
        self.calls.append(model_name)
        if model_name == "indepth-mm":
            raise RuntimeError("in-depth backend 503")
        return ChatResult(status=200, envelope=_envelope(1), latency_ms=5)


def test_indepth_request_failure_is_captured_not_fatal(tmp_path):
    data = tmp_path / "data"
    _write_fixtures(data, indepth=True)
    client = _IndepthRaisesClient()

    out = run_comparison(comparison_set_id="cs", client=client, data_root=data,
                         output_dir=tmp_path / "art")
    # both calls were attempted (answer + in-depth)
    assert client.calls == ["mm", "indepth-mm"]
    row = json.loads(out.results_path.read_text(encoding="utf-8").splitlines()[0])
    # the answer survived intact...
    assert row["response"]["answer"]
    # ...and the in-depth failure is recorded as a status-0 artifact, not an exception:
    # no envelope (response is None), and the failure message is in the artifact's error.
    assert row["indepth"]["http_status"] == 0
    assert row["indepth"]["response"] is None
    assert "in-depth request failed" in row["indepth"]["error"]
