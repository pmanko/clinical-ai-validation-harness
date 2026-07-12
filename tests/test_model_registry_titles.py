import json

from harness.validate.model_registry import arm_card


def _write_title_fixtures(tmp_path):
    registry = tmp_path / "model_registry.json"
    registry.write_text(json.dumps({
        "models": {
            "gemma-e4b-q8": {"family": "Gemma 4", "params": "4B", "quant": "Q8_0"},
            "gemma-e4b": {"family": "Gemma 4", "params": "4B (E4B)", "quant": "Q4_K_M"},
            "gemma-4-12b": {"family": "Gemma 4", "params": "12B", "quant": "Q8_0"},
            "qwen2.5-14b": {"family": "Qwen2.5", "params": "14B", "quant": "Q4_K_M"},
            "gemma-31b": {"family": "Gemma 4", "params": "31B", "quant": "Q4_K_M"},
            "medgemma-27b": {"family": "MedGemma", "params": "27B", "quant": "Q4_K_M"},
            "qwen3.6-35b-q6": {
                "family": "Qwen3.6",
                "params": "35B (3B active, MoE)",
                "quant": "Q6_K",
            },
        }
    }), encoding="utf-8")

    levels = tmp_path / "levels.yaml"
    levels.write_text(
        "profiles:\n"
        "  med-agent-team-low:\n"
        "    label: Low team\n"
        "    topology: team\n"
        "    stages: [context, gather, answer, gate, review, gate]\n"
        "    models: {orchestrator: gemma-e4b-q8, answer: gemma-4-12b, review: qwen2.5-14b}\n"
        "  med-agent-team-high:\n"
        "    label: High team\n"
        "    topology: team\n"
        "    stages: [context, gather, answer, gate, review, gate]\n"
        "    models: {orchestrator: gemma-31b, expert: medgemma-27b, answer: qwen3.6-35b-q6, review: gemma-31b}\n"
        "  single-e4b-checked:\n"
        "    label: Fast checked answer (E4B)\n"
        "    topology: single\n"
        "    stages: [context, answer, gate, review, gate, indepth]\n"
        "    models: {answer: gemma-e4b, review: gemma-e4b, indepth: gemma-e4b}\n",
        encoding="utf-8",
    )

    backends = tmp_path / "backends.json"
    backends.write_text(json.dumps({
        "wide-team-12b-contract-warn": {
            "endpointUrl": "http://host:8080/v1/chat/completions",
            "modelName": "med-agent-team-low",
        },
        "wide-team-high-contract-warn": {
            "endpointUrl": "http://host:8080/v1/chat/completions",
            "modelName": "med-agent-team-high",
        },
        "product-e4b-checked": {
            "endpointUrl": "http://host:8080/v1/chat/completions",
            "modelName": "single-e4b-checked",
            "label": "Fast checked answer (E4B)",
        },
    }), encoding="utf-8")

    ini = tmp_path / "llama-router.ini"
    ini.write_text("", encoding="utf-8")
    return backends, registry, levels, ini


def test_wide_team_titles_include_role_model_sizes(tmp_path):
    backends, registry, levels, ini = _write_title_fixtures(tmp_path)
    kwargs = {
        "backends_path": backends,
        "registry_path": registry,
        "levels_path": levels,
        "llama_ini_path": ini,
    }

    low = arm_card("wide-team-12b-contract-warn", **kwargs)
    assert low["title"] == "Gemma 4B coord · Gemma 12B writer · Qwen 14B val"
    assert low["short_title"] == low["title"]

    high = arm_card("wide-team-high-contract-warn", **kwargs)
    assert high["title"] == (
        "Gemma 31B coord · MedGemma 27B expert · Qwen 35B writer · Gemma 31B val"
    )
    assert high["short_title"] == high["title"]


def test_product_single_profile_uses_topology_not_endpoint_guess(tmp_path):
    backends, registry, levels, ini = _write_title_fixtures(tmp_path)
    card = arm_card(
        "product-e4b-checked",
        backends_path=backends,
        registry_path=registry,
        levels_path=levels,
        llama_ini_path=ini,
    )

    assert card["kind"] == "single"
    assert card["path"] == "med-agent-hub single"
    assert card["models"][0]["id"] == "gemma-e4b"
    assert card["title"].endswith("single")


def test_team_with_unknown_model_metadata_uses_profile_label(tmp_path):
    backends, registry, levels, ini = _write_title_fixtures(tmp_path)
    levels.write_text(
        levels.read_text(encoding="utf-8")
        + "  custom-team:\n"
        + "    label: Focused clinical team\n"
        + "    topology: team\n"
        + "    stages: [context, gather, answer, gate]\n"
        + "    models: {orchestrator: custom-coordinator, answer: custom-writer}\n",
        encoding="utf-8",
    )
    body = json.loads(backends.read_text(encoding="utf-8"))
    body["custom-team-arm"] = {
        "endpointUrl": "http://host:8080/v1/chat/completions",
        "modelName": "custom-team",
        "label": "Focused clinical team setup",
    }
    backends.write_text(json.dumps(body), encoding="utf-8")

    card = arm_card(
        "custom-team-arm",
        backends_path=backends,
        registry_path=registry,
        levels_path=levels,
        llama_ini_path=ini,
    )

    assert card["kind"] == "team"
    assert card["title"] == "Focused clinical team"
    assert card["short_title"] == "Focused clinical team"


def test_configured_profile_is_recognized_on_nonstandard_hub_endpoint(tmp_path):
    backends, registry, levels, ini = _write_title_fixtures(tmp_path)
    body = json.loads(backends.read_text(encoding="utf-8"))
    body["product-e4b-checked"]["endpointUrl"] = "http://host:9999/v1/chat/completions"
    backends.write_text(json.dumps(body), encoding="utf-8")

    card = arm_card(
        "product-e4b-checked",
        backends_path=backends,
        registry_path=registry,
        levels_path=levels,
        llama_ini_path=ini,
    )

    assert card["kind"] == "single"
    assert card["path"] == "med-agent-hub single"
