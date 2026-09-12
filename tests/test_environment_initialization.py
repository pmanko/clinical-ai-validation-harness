"""Run the existing configuration script with an isolated settings transport."""

import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configure(tmp_path):
    script = tmp_path / "chartsearch-configure.sh"
    shutil.copy(ROOT / "scripts/chartsearch-configure.sh", script)
    (tmp_path / "openmrs-settings-lib.sh").write_text(
        "OPENMRS_SETTINGS_BASE_URL=http://example.invalid/openmrs\n"
        "OPENMRS_SETTINGS_USER=test\n"
        'set_openmrs_property() { printf "%s=%s\\n" "$1" "$2" >> "$TEST_SETTINGS"; }\n'
        'openmrs_curl() { printf \'{"version":"test","started":true}\'; }\n'
    )
    settings = tmp_path / "settings.txt"

    def run(*args):
        result = subprocess.run(
            ["bash", str(script), *args],
            env={
                **os.environ,
                "TEST_SETTINGS": str(settings),
                "OPENMRS_SETTINGS_PASS": secrets.token_urlsafe(24),
                "CHARTSEARCH_HUB_ENDPOINT_URL": "http://med-agent-hub:8080/v1/chat/completions",
                "CHARTSEARCH_PROVIDERS_ENABLED": "bundled,hub",
                "CHARTSEARCH_PROVIDERS_DEFAULT": "bundled",
                "LLAMA_ROUTER_PORT": "19077",
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        written = (
            dict(line.split("=", 1) for line in settings.read_text().splitlines())
            if settings.exists()
            else {}
        )
        return result, written

    return run


def test_explicit_local_baseline_configures_both_pipelines_with_e4b(configure):
    result, settings = configure("--local-evaluation")
    assert result.returncode == 0, result.stdout + result.stderr
    assert settings == {
        "chartsearchai.providers.enabled": "bundled,hub",
        "chartsearchai.providers.default": "bundled",
        "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        "chartsearchai.llm.engine": "remote",
        "chartsearchai.llm.remote.endpointUrl": "http://host.docker.internal:19077/v1/chat/completions",
        "chartsearchai.llm.remote.modelName": "gemma-e4b",
    }
    assert not any("prompt" in key.lower() for key in settings)


def test_existing_configuration_mode_does_not_change_the_bundled_engine(configure):
    result, settings = configure()
    assert result.returncode == 0
    assert settings == {
        "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        "chartsearchai.providers.enabled": "bundled,hub",
        "chartsearchai.providers.default": "bundled",
    }


def test_unknown_option_cannot_write_settings(configure):
    result, settings = configure("--guess-model")
    assert result.returncode == 2
    assert settings == {}
