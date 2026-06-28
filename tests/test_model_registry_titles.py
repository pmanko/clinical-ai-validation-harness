import json

from harness.validate.model_registry import arm_card


def _write_title_fixtures(tmp_path):
    registry = tmp_path / "model_registry.json"
    registry.write_text(json.dumps({
        "models": {
            "gemma-e4b-q8": {"family": "Gemma 4", "params": "4B", "quant": "Q8_0"},
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
        "levels:\n"
        "  med-agent-team-low:\n"
        "    orchestrator: gemma-e4b-q8\n"
        "    synthesizer: gemma-4-12b\n"
        "    validator: qwen2.5-14b\n"
        "  med-agent-team-high:\n"
        "    orchestrator: gemma-31b\n"
        "    expert: medgemma-27b\n"
        "    synthesizer: qwen3.6-35b-q6\n"
        "    validator: gemma-31b\n",
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
