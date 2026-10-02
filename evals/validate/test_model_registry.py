"""Arm cards use explicit connection settings and caller-supplied metadata only."""

from pathlib import Path

from harness.validate.model_registry import arm_card
from harness.validate.models import Backend


def test_arm_card_uses_configured_label_kind_and_model_without_file_access(monkeypatch):
    def fail_read(*args, **kwargs):
        raise AssertionError("arm cards must not read local files")

    monkeypatch.setattr(Path, "read_text", fail_read)
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    backend = Backend(
        id="arm", label="Configured arm", endpoint_url="http://service:9999/v1",
        model_name="configured-profile", kind="product_profile",
    )
    card = arm_card("arm", backend=backend)
    assert card["title"] == card["short_title"] == card["label"] == "Configured arm"
    assert card["kind"] == "product_profile"
    assert card["models"] == [{"id": "configured-profile"}]
    assert card["roles"] == {}
    assert card["config"] == {}
    assert card["path"] is None


def test_arm_card_preserves_supplied_model_metadata_and_configuration():
    supplied = {
        "title": "Reviewed team", "short_title": "Team", "kind": "team",
        "models": [{"id": "writer", "params": "12B", "quant": "Q8_0"}],
        "roles": {"answer": {"id": "writer"}},
        "stages": ["answer", "gate"],
        "config": {"knobs": {"temperature": 0}, "prompts": ["supplied prompt"]},
    }
    card = arm_card("arm", metadata=supplied)
    assert all(card[key] == value for key, value in supplied.items())
    card["models"][0]["quant"] = "changed"
    card["config"]["knobs"]["temperature"] = 1
    assert supplied["models"][0]["quant"] == "Q8_0"
    assert supplied["config"]["knobs"]["temperature"] == 0


def test_missing_metadata_is_unknown_not_inferred_from_names():
    backend = Backend(
        id="med-agent-team-high", label="Experiment label",
        endpoint_url="http://med-agent-hub:8080/v1/chat/completions",
        model_name="med-agent-team-high",
    )
    card = arm_card(backend.id, backend=backend)
    assert card["kind"] == "unknown"
    assert card["title"] == "Experiment label"
    assert card["roles"] == {}
    assert "stages" not in card
    assert "params" not in card["models"][0]


def test_unknown_backend_has_no_fabricated_model_metadata():
    card = arm_card("unknown")
    assert card["title"] == "unknown"
    assert card["models"] == []
    assert card["kind"] == "unknown"
