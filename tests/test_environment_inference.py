"""Setup uses the saved provider choices; it does not replace them with defaults."""

import copy
import sys

import pytest

import harness.environment_setup as setup
from harness.evaluation_setup import SetupError


class Client:
    base_url = "http://127.0.0.1:8088/openmrs"

    def __init__(self, providers, settings=None):
        self.providers = providers
        self.settings = settings or {}
        self.calls = []
        self.existing_service_user = False

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        assert (
            method == "GET"
        ), "Preparation must not rewrite provider or prompt settings"
        if path == "chartsearchai/providers":
            return {
                "defaultProvider": self.providers[0]["id"],
                "providers": copy.deepcopy(self.providers),
            }
        if path == "chartsearchai/models":
            return {
                "data": [
                    {
                        "id": "custom-checked",
                        "visibility": "product",
                        "available": True,
                        "default": True,
                    }
                ]
            }
        raise AssertionError(path)

    def exact(self, resource, field, value):
        self.calls.append(("GET", resource, value))
        if resource == "systemsetting":
            return (
                {"property": value, "value": self.settings[value]}
                if value in self.settings
                else None
            )
        if resource == "user" and self.existing_service_user:
            return {"uuid": "existing-reader"}
        return None


def provider(name, ready=True):
    return {"id": name, "enabled": True, "ready": ready}


@pytest.fixture
def commands(monkeypatch):
    calls = []
    monkeypatch.setattr(
        setup, "command", lambda root, args, **kwargs: calls.append(args)
    )
    monkeypatch.setenv("MED_AGENT_LLM_BASE_URL", "http://host.docker.internal:8077")
    monkeypatch.setenv("LLAMA_ROUTER_PORT", "8077")
    for name in ("QUERYSTORE_BASE_URL", "QUERYSTORE_USERNAME", "QUERYSTORE_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    return calls


def test_native_bundled_does_not_start_hub_or_router(tmp_path, commands):
    client = Client([provider("bundled")])
    result = setup.prepare_inference(tmp_path, client)
    assert commands == []
    assert result["default_provider"] == "bundled"
    assert result["model_response"] == "not_checked"


def test_remote_providers_are_not_replaced_with_local_services(tmp_path, commands):
    client = Client(
        [provider("bundled"), provider("hub")],
        {
            "chartsearchai.llm.engine": "remote",
            "chartsearchai.llm.remote.endpointUrl": "https://models.example.org/v1/chat/completions",
            "chartsearchai.hub.endpointUrl": "https://hub.example.org/v1/chat/completions",
        },
    )
    result = setup.prepare_inference(tmp_path, client)
    assert commands == []
    assert result["hub_default_profile"] == "custom-checked"


def test_local_bundled_remote_engine_starts_only_existing_router_launcher(
    tmp_path, commands
):
    client = Client(
        [provider("bundled")],
        {
            "chartsearchai.llm.engine": "remote",
            "chartsearchai.llm.remote.endpointUrl": "http://host.docker.internal:8077/v1/chat/completions",
        },
    )
    setup.prepare_inference(tmp_path, client)
    assert commands == [["bash", "scripts/llama-router-up.sh", "--daemon"]]


def test_local_hub_reuses_saved_reader_credentials_and_startup(tmp_path, commands):
    credentials = tmp_path / "artifacts/chartsearchai-local/querystore-service.env"
    credentials.parent.mkdir(parents=True)
    credentials.write_text("# existing private configuration\n")
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        },
    )
    setup.prepare_inference(tmp_path, client)
    assert commands == [
        ["bash", "scripts/llama-router-up.sh", "--daemon"],
        ["make", "med-agent-hub-up"],
    ]
    assert credentials.read_text() == "# existing private configuration\n"


def test_missing_reader_credentials_never_rotate_an_existing_account(
    tmp_path, commands
):
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        },
    )
    client.existing_service_user = True
    with pytest.raises(SetupError, match="credentials"):
        setup.prepare_inference(tmp_path, client)
    assert commands == []


def test_unconfigured_hub_is_reported_not_configured_automatically(tmp_path, commands):
    client = Client([provider("hub", ready=False)])
    with pytest.raises(SetupError, match="endpoint"):
        setup.prepare_inference(tmp_path, client)
    assert commands == []


def test_disabled_hub_is_not_started_or_discovered(tmp_path, commands):
    client = Client(
        [provider("bundled"), {"id": "hub", "enabled": False, "ready": False}]
    )
    setup.prepare_inference(tmp_path, client)
    assert commands == []
    assert not any(path == "chartsearchai/models" for _, path, _ in client.calls)


def test_provider_failure_cannot_report_inference_prepared(
    tmp_path, commands, monkeypatch
):
    monkeypatch.setattr(setup.time, "sleep", lambda _: None)
    client = Client([provider("bundled", ready=False)])
    with pytest.raises(SetupError, match="bundled"):
        setup.prepare_inference(tmp_path, client)
    assert commands == []


def test_first_local_reader_uses_existing_provisioner(tmp_path, commands):
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        },
    )
    setup.prepare_inference(tmp_path, client)
    assert commands[0] == ["bash", "scripts/llama-router-up.sh", "--daemon"]
    assert commands[1][:2] == [
        "python3",
        "scripts/provision-querystore-service-account.py",
    ]
    assert commands[2] == ["make", "med-agent-hub-up"]


@pytest.mark.parametrize("external", [False, True])
def test_saved_source_credentials_are_not_overridden_by_empty_defaults(
    tmp_path, commands, monkeypatch, external
):
    source = tmp_path / "artifacts/chartsearchai-local/querystore-service.env"
    source.parent.mkdir(parents=True)
    source.write_text("# existing\n")
    keys = ("QUERYSTORE_BASE_URL", "QUERYSTORE_USERNAME", "QUERYSTORE_PASSWORD")
    for key in keys:
        monkeypatch.setenv(key, "operator-value" if external else "")
    captured = []
    monkeypatch.setattr(
        setup, "command", lambda root, args, **kw: captured.append((args, kw))
    )
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        },
    )
    setup.prepare_inference(tmp_path, client)
    assert captured[-1] == (
        ["make", "med-agent-hub-up"],
        {"extra_env": {} if external else {key: None for key in keys}},
    )


def test_command_can_unset_example_overrides_without_mutating_parent_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("QUERYSTORE_PASSWORD", "parent-private-value")
    output = setup.command(
        tmp_path,
        [sys.executable, "-c", "import os; print('QUERYSTORE_PASSWORD' in os.environ)"],
        capture=True,
        extra_env={"QUERYSTORE_PASSWORD": None},
    )
    assert output.strip() == "False"
    assert setup.os.environ["QUERYSTORE_PASSWORD"] == "parent-private-value"


def test_unavailable_profiles_never_trigger_a_default_model_substitution(
    tmp_path, commands, monkeypatch
):
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "https://hub.example.org/v1/chat/completions",
        },
    )
    original = client.request
    monkeypatch.setattr(
        client,
        "request",
        lambda method, path: {"data": []}
        if path == "chartsearchai/models"
        else original(method, path),
    )
    with pytest.raises(SetupError, match="default profile"):
        setup.prepare_inference(tmp_path, client)
    assert commands == []


def test_failed_router_start_does_not_continue_or_reset(
    tmp_path, commands, monkeypatch
):
    def fail(root, args, **kwargs):
        commands.append(args)
        raise SetupError("router could not start")

    monkeypatch.setattr(setup, "command", fail)
    client = Client(
        [provider("hub")],
        {
            "chartsearchai.hub.endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        },
    )
    with pytest.raises(SetupError, match="router could not start"):
        setup.prepare_inference(tmp_path, client)
    assert commands == [["bash", "scripts/llama-router-up.sh", "--daemon"]]
