import configparser
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "compose" / "catalyst-model-router.yml"
PRESET_PATH = ROOT / "scripts" / "catalyst-model-router.ini"
MODELS_PATH = ROOT / "scripts" / "catalyst-model-router.models.tsv"
SCRIPT_PATH = ROOT / "scripts" / "catalyst-model-router.sh"


def model_records() -> dict[str, dict[str, str]]:
    records = {}
    for line in MODELS_PATH.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        alias, filename, sha256, source = line.split("\t")
        records[alias] = {
            "filename": filename,
            "sha256": sha256,
            "source": source,
        }
    return records


def test_router_compose_is_pinned_private_and_capacity_configurable():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    service = compose["services"]["model-router"]

    assert re.fullmatch(r"ghcr\.io/ggml-org/llama\.cpp@sha256:[a-f0-9]{64}", service["image"])
    command = service["command"]
    assert command[command.index("--models-max") + 1] == "${CATALYST_ROUTER_MODELS_MAX:-1}"
    assert "--models-autoload" in command
    assert "--warmup" in command
    assert service["ports"] == ["127.0.0.1:${CATALYST_ROUTER_PORT:-8077}:8077"]
    assert all(volume.endswith(":ro") for volume in service["volumes"])
    for network in ("public", "application"):
        assert service["networks"][network]["aliases"] == [
            "${CATALYST_ROUTER_NETWORK_ALIAS:-model-router-candidate}"
        ]
        assert compose["networks"][network]["external"] is True


def test_router_presets_and_verified_sources_describe_the_same_models():
    presets = configparser.ConfigParser(interpolation=None)
    presets.read(PRESET_PATH)
    records = model_records()

    assert set(presets.sections()) - {"*"} == set(records)
    for alias, record in records.items():
        assert presets[alias]["model"] == f"/models/{record['filename']}"
        assert re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
        assert re.fullmatch(
            r"https://huggingface\.co/[^/]+/[^/]+/resolve/[a-f0-9]{40}/[^/]+\.gguf",
            record["source"],
        )


def test_router_wrapper_verifies_before_start_and_checks_loaded_state():
    script = SCRIPT_PATH.read_text()

    verify_position = script.index("    verify_models\n", script.index("  up)"))
    start_position = script.index("    compose up -d model-router\n")
    assert verify_position < start_position
    assert '"${ROUTER_URL}/models/load"' in script
    assert '"${ROUTER_URL}/v1/chat/completions"' in script
    assert 'get("value") == "loaded"' in script
    assert "model-router-candidate" in script
