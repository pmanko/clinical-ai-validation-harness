"""Unit tests for the arm-makeup resolver (harness/validate/model_registry.py).

The resolver turns a `backend_id` into a structured "arm card" — engine path (single
vanilla-chartsearchai vs the med-agent-hub team), per-model family/size/quant, the
team role->model lineup, the merged sampler knobs (from llama-router.ini), the per-role
prompts, and the human-readable title. Every reader takes an explicit path, so these
tests drive HERMETIC fixtures written to tmp_path — no dependence on the live
datasets/validation/* files. Each assertion is red-when-broken: change the INI merge,
the team-title shape, the quant-token split, or the endpoint->kind derivation and a
specific assertion fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.validate import model_registry as mr


# --------------------------------------------------------------------------- #
# fixtures: tiny on-disk backends.json / model_registry.json / levels.yaml / ini
# --------------------------------------------------------------------------- #
@pytest.fixture
def registry_json(tmp_path: Path) -> Path:
    p = tmp_path / "model_registry.json"
    p.write_text(json.dumps({
        "models": {
            "gemma-4-12b": {"family": "Gemma 4", "params": "12B", "quant": "Q8_0",
                            "note": "strong single"},
            "gemma-4-12b-q4": {"family": "Gemma 4", "params": "12B", "quant": "Q4_K_M",
                               "note": "quant control"},
            "lfm2-2.6b": {"family": "Liquid LFM2", "params": "2.6B", "quant": "Q4_K_M"},
            "qwen2.5-32b": {"family": "Qwen2.5", "params": "32B", "quant": "Q4_K_M"},
            "medgemma-1.5-4b": {"family": "MedGemma", "params": "4B", "quant": "Q4_K_S"},
        }
    }), encoding="utf-8")
    return p


@pytest.fixture
def ini_file(tmp_path: Path) -> Path:
    p = tmp_path / "llama-router.ini"
    # `*` shared defaults + a per-model override + the three dry-* keys (collapse to "dry")
    # + a `;` comment line (configparser would choke; the reader must skip it).
    p.write_text(
        "; a llama-router config\n"
        "[*]\n"
        "temp = 0.0\n"
        "top-p = 0.9\n"
        "seed = 7\n"
        "dry-multiplier = 0.8\n"
        "dry-base = 1.75\n"
        "dry-allowed-length = 2\n"
        "\n"
        "# the writer model bumps temperature\n"
        "[qwen2.5-32b]\n"
        "temp = 0.4\n"
        "max-tokens = 2048\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def prompts_dir(tmp_path: Path, monkeypatch) -> Path:
    """Point the module's _PROMPTS at a tmp dir with role prompt files."""
    pd = tmp_path / "prompts"
    pd.mkdir()
    (pd / "orchestrator.txt").write_text("Drive the tool calls.", encoding="utf-8")
    (pd / "medical_expert.txt").write_text("Read the chart.", encoding="utf-8")
    (pd / "synthesis-answer.txt").write_text("Write the direct answer.", encoding="utf-8")
    (pd / "validation-answer.txt").write_text("Cross-check the answer.", encoding="utf-8")
    (pd / "synthesis-chartsearchai.txt").write_text(
        "OVERRIDE writer prompt " + ("x" * 200), encoding="utf-8")
    monkeypatch.setattr(mr, "_PROMPTS", pd)
    return pd


def _levels_file(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "levels.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _backends_file(tmp_path: Path, mapping: dict) -> Path:
    p = tmp_path / "backends.json"
    p.write_text(json.dumps(mapping), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# _parse_ini
# --------------------------------------------------------------------------- #
def test_parse_ini_merges_sections_and_skips_comments(ini_file):
    ini = mr._parse_ini(ini_file)
    assert ini["*"]["temp"] == "0.0"
    assert ini["*"]["seed"] == "7"
    assert ini["qwen2.5-32b"]["temp"] == "0.4"
    # the `;` and `#` comment lines never became keys
    assert all(";" not in k and "#" not in k for sec in ini.values() for k in sec)


def test_parse_ini_missing_file_returns_empty(tmp_path):
    # read error path (lines 101-102): a non-existent path -> {} not an exception
    assert mr._parse_ini(tmp_path / "nope.ini") == {}


# --------------------------------------------------------------------------- #
# _resolve_knobs — the [*] + [model] merge + dry-* collapse
# --------------------------------------------------------------------------- #
def test_resolve_knobs_merges_star_then_model_and_collapses_dry(ini_file):
    ini = mr._parse_ini(ini_file)
    knobs = mr._resolve_knobs("qwen2.5-32b", ini)
    # per-model override wins over the shared [*] default
    assert knobs["temp"] == "0.4"
    # shared defaults still present
    assert knobs["top_p"] == "0.9"
    assert knobs["seed"] == "7"
    # the model-only key
    assert knobs["max_tokens"] == "2048"
    # the three dry-* keys collapse into one human "dry" summary line
    assert knobs["dry"] == "multiplier 0.8 · base 1.75 · allowed-length 2"


def test_resolve_knobs_unknown_model_uses_star_only(ini_file):
    ini = mr._parse_ini(ini_file)
    knobs = mr._resolve_knobs("not-in-ini", ini)
    assert knobs["temp"] == "0.0"  # falls back to [*]
    assert "max_tokens" not in knobs  # the qwen-only key does NOT leak in


def test_resolve_knobs_empty_ini_returns_empty():
    # the `if not merged: return {}` branch (line 124)
    assert mr._resolve_knobs("any", {}) == {}


# --------------------------------------------------------------------------- #
# _short_family + _single_title — quant token + family shortening
# --------------------------------------------------------------------------- #
def test_short_family_maps_known_prefixes_and_falls_back():
    assert mr._short_family("Gemma 4") == "Gemma"
    assert mr._short_family("Liquid LFM2.5") == "Liquid"   # substring prefix match
    assert mr._short_family("Qwen3.6") == "Qwen"
    assert mr._short_family("MedGemma") == "MedGemma"
    # unmapped family falls back to the raw string (line 291)
    assert mr._short_family("IBM Granite") == "IBM Granite"
    assert mr._short_family(None) == ""


def test_single_title_quant_token_split_and_essence():
    card = {"family": "Gemma 4", "params": "12B", "quant": "Q8_0"}
    title, short = mr._single_title(card)
    # Q8_0 -> Q8 (token before the first underscore)
    assert title == "Gemma 4 12B · Q8 · single"
    assert short == "Gemma 4 12B · Q8"


def test_single_title_q4_distinguished_from_q8():
    # the whole reason quant is in the title: a same-family/size arm differing only by quant
    q8, _ = mr._single_title({"family": "Gemma 4", "params": "12B", "quant": "Q8_0"})
    q4, _ = mr._single_title({"family": "Gemma 4", "params": "12B", "quant": "Q4_K_M"})
    assert q8 != q4
    assert "Q8" in q8 and "Q4" in q4


def test_single_title_falls_back_to_id_when_no_family():
    title, short = mr._single_title({"id": "mystery-model"})
    assert title == "mystery-model · single"
    assert short == "mystery-model"


# --------------------------------------------------------------------------- #
# _team_title
# --------------------------------------------------------------------------- #
def test_team_title_coord_writer_and_validated_suffix():
    roles = {
        "orchestrator": {"family": "Liquid LFM2"},
        "synthesizer": {"family": "Qwen2.5"},
        "validator": {"family": "Gemma 4"},
    }
    title, short = mr._team_title(roles)
    assert title == "Liquid coord · Qwen writer · Gemma val"
    assert short == title


def test_team_title_without_validator_has_no_suffix():
    roles = {"orchestrator": {"family": "Gemma 4"}, "synthesizer": {"family": "Gemma 4"}}
    title, short = mr._team_title(roles)
    assert title == "Gemma coord · Gemma writer"
    assert "validated" not in title


def test_team_title_empty_roles_is_team():
    title, short = mr._team_title({})
    assert short == "team"


# --------------------------------------------------------------------------- #
# _load_levels / _load_levels_raw — the indent-aware YAML-ish reader
# --------------------------------------------------------------------------- #
LEVELS_BODY = """\
# med-agent-hub levels
other_top_key: ignored
levels:
  med-agent-team-low:
    orchestrator: lfm2-2.6b
    synthesizer: qwen2.5-32b
    validator: gemma-4-12b
    synthesis_prompt: synthesis-chartsearchai
    not_a_role: should-be-skipped-by-role-filter
  med-agent-team-bad:
    synthesizer: null
"""


def test_load_levels_extracts_only_role_keys(tmp_path):
    lv = mr._load_levels(_levels_file(tmp_path, LEVELS_BODY))
    assert lv["med-agent-team-low"] == {
        "orchestrator": "lfm2-2.6b",
        "synthesizer": "qwen2.5-32b",
        "validator": "gemma-4-12b",
    }
    # synthesis_prompt and not_a_role are NOT role keys -> excluded by _load_levels
    assert "synthesis_prompt" not in lv["med-agent-team-low"]
    # a `null` value is dropped
    assert lv["med-agent-team-bad"] == {}


def test_load_levels_raw_captures_every_scalar_including_prompt_override(tmp_path):
    raw = mr._load_levels_raw(_levels_file(tmp_path, LEVELS_BODY))
    lvl = raw["med-agent-team-low"]
    # raw keeps the prompt override + non-role scalars, unlike _load_levels
    assert lvl["synthesis_prompt"] == "synthesis-chartsearchai"
    assert lvl["not_a_role"] == "should-be-skipped-by-role-filter"


def test_load_levels_missing_file_returns_empty(tmp_path):
    assert mr._load_levels(tmp_path / "absent.yaml") == {}
    assert mr._load_levels_raw(tmp_path / "absent.yaml") == {}


# --------------------------------------------------------------------------- #
# _prompt_entry — override file, default file, missing file, summary truncation
# --------------------------------------------------------------------------- #
def test_prompt_entry_default_file_for_role(prompts_dir):
    entry = mr._prompt_entry("orchestrator", {}, "Orchestrator")
    assert entry["source"] == "prompts/orchestrator.txt"
    assert entry["text"] == "Drive the tool calls."


def test_prompt_entry_honors_override_and_truncates_summary(prompts_dir):
    # synthesis_prompt override -> synthesis-chartsearchai.txt (a >160-char file)
    entry = mr._prompt_entry("synthesizer", {"synthesis_prompt": "synthesis-chartsearchai"},
                             "Synthesizer")
    assert entry["source"] == "prompts/synthesis-chartsearchai.txt"
    # summary is truncated with an ellipsis when the prompt is long
    assert entry["summary"].endswith("…")
    assert len(entry["summary"]) <= 158


def test_prompt_entry_missing_file_returns_none(prompts_dir):
    # an override pointing at a file that doesn't exist -> None (role had no prompt)
    assert mr._prompt_entry("synthesizer", {"synthesis_prompt": "does-not-exist"},
                            "Synthesizer") is None


# --------------------------------------------------------------------------- #
# arm_card — end-to-end single / team / unknown derivation
# --------------------------------------------------------------------------- #
def test_arm_card_single_from_8077_endpoint(tmp_path, registry_json, ini_file):
    backends = _backends_file(tmp_path, {
        "g12": {"label": "Gemma 12B", "endpointUrl": "http://host:8077/v1/chat/completions",
                "modelName": "gemma-4-12b"},
    })
    card = mr.arm_card("g12", backends_path=backends, registry_path=registry_json,
                       levels_path=tmp_path / "no-levels.yaml", llama_ini_path=ini_file)
    assert card["kind"] == "single"
    assert card["path"] == "direct model endpoint"
    assert card["title"] == "Gemma 4 12B · Q8 · single"
    assert card["models"][0]["family"] == "Gemma 4"
    # the single config carries the chartsearchai DEFAULT_SYSTEM_PROMPT + merged knobs
    assert card["config"]["prompts"][0]["source"] == "LlmProvider.DEFAULT_SYSTEM_PROMPT"
    assert card["config"]["knobs"]["gemma-4-12b"]["temp"] == "0.0"
    assert card["config"]["retrieval"]["threshold"] == 0.47


def test_arm_card_team_from_8080_endpoint(tmp_path, registry_json, ini_file, prompts_dir):
    levels = _levels_file(tmp_path, LEVELS_BODY)
    backends = _backends_file(tmp_path, {
        "teamlow": {"label": "Team LOW", "endpointUrl": "http://host:8080/v1/chat/completions",
                    "modelName": "med-agent-team-low"},
    })
    card = mr.arm_card("teamlow", backends_path=backends, registry_path=registry_json,
                       levels_path=levels, llama_ini_path=ini_file)
    assert card["kind"] == "team"
    assert card["path"] == "med-agent-hub team"
    assert card["n_models"] == 3
    assert set(card["roles"]) == {"orchestrator", "synthesizer", "validator"}
    assert card["roles"]["synthesizer"]["family"] == "Qwen2.5"
    assert card["title"] == "Liquid 2.6B coord · Qwen 32B writer · Gemma 12B val"
    # the synthesizer prompt OVERRIDE from levels.yaml is honored in the team config
    sources = {p["source"] for p in card["config"]["prompts"]}
    assert "prompts/synthesis-chartsearchai.txt" in sources


def test_arm_card_team_derived_from_modelname_prefix_without_8080(
        tmp_path, registry_json, ini_file, prompts_dir):
    # kind=team is also derived from a `med-agent-team*` modelName even on a non-8080 endpoint
    levels = _levels_file(tmp_path, LEVELS_BODY)
    backends = _backends_file(tmp_path, {
        "t": {"endpointUrl": "http://host:9999/x", "modelName": "med-agent-team-low"},
    })
    card = mr.arm_card("t", backends_path=backends, registry_path=registry_json,
                       levels_path=levels, llama_ini_path=ini_file)
    assert card["kind"] == "team"


def test_arm_card_unknown_when_no_endpoint(tmp_path, registry_json, ini_file):
    backends = _backends_file(tmp_path, {
        "bare": {"label": "Bare", "modelName": "gemma-4-12b"},  # no endpointUrl
    })
    card = mr.arm_card("bare", backends_path=backends, registry_path=registry_json,
                       levels_path=tmp_path / "x.yaml", llama_ini_path=ini_file)
    assert card["kind"] == "unknown"
    assert card["path"] is None
    # still resolves a best-effort title + model card
    assert card["title"] == "Gemma 4 12B · Q8 · single"


def test_arm_card_unknown_backend_id_never_raises(tmp_path, registry_json, ini_file):
    backends = _backends_file(tmp_path, {})
    card = mr.arm_card("ghost", backends_path=backends, registry_path=registry_json,
                       levels_path=tmp_path / "x.yaml", llama_ini_path=ini_file)
    # modelName falls back to backend_id; no registry entry -> empty model card, still no raise
    assert card["backend_id"] == "ghost"
    assert card["models"][0]["family"] is None


def test_load_json_bad_file_returns_empty(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert mr._load_json(bad) == {}
