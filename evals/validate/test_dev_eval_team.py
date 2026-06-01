"""Red-first tests for the dev-eval instrument's pure logic
(scripts/dev_eval_team.py).

The instrument prints booleans; the logic worth pinning is `_shape_check` (the
Tune-phase signal) and `_chart_answer_response_format` (must mirror the schema
chartsearchai injects, so the raw probe stays schema-constrained). The import is
guarded so a missing module surfaces as a failing assertion (red), not a
collection error.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev_eval_team.py"


def _load():
    if not _MOD_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("dev_eval_team", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_shape_check_detects_new_structure():
    """An envelope that DOES carry the new structure flips every signal True."""
    mod = _load()
    assert mod is not None, "scripts/dev_eval_team.py not implemented yet"
    env = {
        "answer": "**Answer**\nShe is on ART.\n\n**In Depth**\nPer WHO guidance...",
        "blocks": [{"kind": "table", "title": "Meds", "columns": [], "rows": []}],
    }
    sc = mod._shape_check(env, parsed_ok=True)
    assert sc == {
        "has_answer_section": True,
        "has_in_depth_section": True,
        "has_table": True,
        "envelope_valid": True,
    }


def test_shape_check_today_prompt_is_all_false_except_validity():
    """Today's flat envelope: valid shape, but none of the new-structure markers.
    This is the expected instrument reading now — it must NOT report them True.
    The load-bearing negative: the checks read False when the structure is absent,
    which is the exact state the Tune phase measures against."""
    mod = _load()
    assert mod is not None
    env = {"answer": "The patient is on Lamivudine [29], Nevirapine [30].", "blocks": []}
    sc = mod._shape_check(env, parsed_ok=True)
    assert sc["envelope_valid"] is True
    assert sc["has_answer_section"] is False
    assert sc["has_in_depth_section"] is False
    assert sc["has_table"] is False


def test_shape_check_edges():
    """Edge surface: in-depth hyphen/space variants match; parsed_ok=False is never
    valid; wrong types are invalid + no table; None envelope is all-safe; a table
    among mixed blocks is still found."""
    mod = _load()
    assert mod is not None

    # in-depth header variants all match
    for variant in ("**In Depth**", "**In-Depth**", "**in depth**"):
        env = {"answer": f"text {variant} more", "blocks": []}
        assert mod._shape_check(env, parsed_ok=True)["has_in_depth_section"] is True

    # parsed_ok False -> never valid (non-JSON content reply)
    assert mod._shape_check({"answer": "x", "blocks": []}, parsed_ok=False)["envelope_valid"] is False

    # wrong types -> invalid; blocks not a list -> no table
    sc = mod._shape_check({"answer": 123, "blocks": {"kind": "table"}}, parsed_ok=True)
    assert sc["envelope_valid"] is False
    assert sc["has_table"] is False

    # None envelope -> all-safe, no crash
    sc = mod._shape_check(None, parsed_ok=False)
    assert sc["envelope_valid"] is False
    assert sc["has_table"] is False
    assert sc["has_answer_section"] is False

    # a table among non-table blocks is still detected
    env = {"answer": "x", "blocks": [{"kind": "note"}, {"kind": "table", "rows": []}]}
    assert mod._shape_check(env, parsed_ok=True)["has_table"] is True


def test_response_format_matches_chartsearch_schema():
    """The raw-probe schema must mirror ChartAnswerResponseFormat.java: a strict
    chart_answer json_schema requiring answer/citations/blocks, with a table block
    requiring kind/title/columns/rows. A drift here means the direct probe stops
    matching what chartsearchai injects, so 'envelope_valid' would read wrong."""
    mod = _load()
    assert mod is not None
    rf = mod._chart_answer_response_format()
    assert rf["type"] == "json_schema"
    js = rf["json_schema"]
    assert js["name"] == "chart_answer"
    assert js["strict"] is True
    schema = js["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"answer", "citations", "blocks"}
    props = schema["properties"]
    assert props["answer"]["type"] == "string"
    assert props["citations"]["items"]["type"] == "integer"
    block = props["blocks"]["items"]
    assert set(block["required"]) == {"kind", "title", "columns", "rows"}
    assert block["properties"]["kind"]["enum"] == ["table"]


def test_select_mode_dispatches_on_direct_flag():
    """The positional endpoint_url is ALWAYS the downstream LLM target (LM Studio /
    med-agent-hub /v1/chat/completions); chartsearchai is the separate
    --chartsearch-base-url (see _via_chartsearchai's signature). So the mode is
    decided by the --direct FLAG, not the URL: default = faithful (forward the LLM as
    chartsearchai's per-request override), --direct = raw OpenAI-compat probe with a
    synthetic chart. The URL can't disambiguate — it's the LLM either way."""
    mod = _load()
    assert mod is not None
    llm = "http://med-agent-hub:8080/v1/chat/completions"
    assert mod._select_mode(llm, direct=False) == "chartsearchai"
    assert mod._select_mode(llm, direct=True) == "raw-openai-compat"


def test_via_openai_compat_parses_envelope_from_content(monkeypatch):
    """The raw path must pull the envelope JSON out of choices[0].message.content
    and parse it; a non-JSON content reply is recorded as parsed_ok False with the
    raw content kept for debugging (never crashes the probe)."""
    mod = _load()
    assert mod is not None

    envelope = {"answer": "**Answer**\nx", "citations": [1], "blocks": []}
    # First call returns a valid envelope-as-content; second returns non-JSON.
    replies = [
        {"choices": [{"message": {"content": json.dumps(envelope)}}]},
        {"choices": [{"message": {"content": "sorry, not json"}}]},
        {"choices": [{"message": {"content": json.dumps(envelope)}}]},
    ]
    calls = {"n": 0}

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    def _fake_post(url, json=None, timeout=None):
        i = calls["n"]
        calls["n"] += 1
        return _Resp(replies[i])

    monkeypatch.setattr(mod.requests, "post", _fake_post)
    out = mod._via_openai_compat("http://x/v1/chat/completions", "med-agent-team")
    assert len(out) == 3  # one per question
    # Q1: parsed envelope
    assert out[0]["parsed_ok"] is True
    assert out[0]["envelope"] == envelope
    assert out[0]["status"] == 200
    # Q2: non-JSON content -> not parsed, raw content surfaced
    assert out[1]["parsed_ok"] is False
    assert out[1]["envelope"] is None
    assert "not json" in out[1]["raw_text"]


def test_via_chartsearchai_threads_session_and_override(monkeypatch):
    """The faithful path opens one session, sends each question with the
    (endpoint_url, model_name) override, and threads the returned session forward
    (so turn 2+ continue the same chat). It must pass the override on every turn,
    not just the first."""
    mod = _load()
    assert mod is not None

    class _FakeResult:
        def __init__(self, session):
            self.status = 200
            self.latency_ms = 10
            self.raw_text = ""
            self.envelope = {"answer": "a", "blocks": [], "session": session}

    seen = {"new": [], "chat": [], "base_url": None}

    class _FakeClient:
        def __init__(self, base_url=None):
            seen["base_url"] = base_url

        def new_session(self, patient):
            seen["new"].append(patient)
            return "S0"

        def chat(self, patient, session, question, *, endpoint_url=None, model_name=None):
            seen["chat"].append(
                {"patient": patient, "session": session, "question": question,
                 "endpoint_url": endpoint_url, "model_name": model_name}
            )
            # server hands back a new session id each turn; the caller must adopt it
            return _FakeResult(session="S1")

    monkeypatch.setattr(mod, "ChartSearchAiClient", _FakeClient)
    out = mod._via_chartsearchai(
        "http://base/openmrs", "PT-1",
        "http://med-agent-hub:8080/v1/chat/completions", "med-agent-team",
    )
    assert seen["base_url"] == "http://base/openmrs"
    assert seen["new"] == ["PT-1"]                       # exactly one session opened
    assert len(seen["chat"]) == len(mod.QUESTIONS)       # one chat per question
    # every turn carries the override pair
    for c in seen["chat"]:
        assert c["endpoint_url"] == "http://med-agent-hub:8080/v1/chat/completions"
        assert c["model_name"] == "med-agent-team"
    # session is threaded: first turn uses S0, later turns use the adopted S1
    assert seen["chat"][0]["session"] == "S0"
    assert seen["chat"][1]["session"] == "S1"
    assert len(out) == len(mod.QUESTIONS)
    assert out[0]["parsed_ok"] is True and out[0]["envelope"]["answer"] == "a"


def test_main_dispatches_to_the_selected_path(monkeypatch, capsys):
    """main routes the default (no --direct) to the faithful path — forwarding the
    LLM endpoint_url as chartsearchai's per-request override + the --chartsearch-base-url
    base — and --direct to the raw probe. endpoint_url is the LLM in BOTH paths."""
    mod = _load()
    assert mod is not None
    called = {"cs": None, "raw": None}

    def _fake_cs(base_url, patient, endpoint_url, model_name):
        called["cs"] = (base_url, patient, endpoint_url, model_name)
        return [{"label": "l", "question": "q", "status": 200, "latency_ms": 1,
                 "envelope": {"answer": "a", "blocks": []}, "parsed_ok": True, "raw_text": ""}]

    def _fake_raw(endpoint_url, model_name):
        called["raw"] = (endpoint_url, model_name)
        return [{"label": "l", "question": "q", "status": 200, "latency_ms": 1,
                 "envelope": {"answer": "a", "blocks": []}, "parsed_ok": True, "raw_text": ""}]

    monkeypatch.setattr(mod, "_via_chartsearchai", _fake_cs)
    monkeypatch.setattr(mod, "_via_openai_compat", _fake_raw)

    llm = "http://med-agent-hub:8080/v1/chat/completions"
    # default -> faithful: the LLM is forwarded as the override, base from the flag.
    rc = mod.main([llm, "med-agent-team", "--chartsearch-base-url", "http://b/openmrs"])
    assert rc == 0
    assert called["cs"] == ("http://b/openmrs", mod.DEFAULT_PATIENT, llm, "med-agent-team")
    assert called["raw"] is None

    # --direct -> raw probe straight at the LLM.
    called["cs"] = None
    rc = mod.main([llm, "med-agent-team", "--direct"])
    assert rc == 0
    assert called["raw"] == (llm, "med-agent-team")
    assert called["cs"] is None
