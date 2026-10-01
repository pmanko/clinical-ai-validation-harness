from harness.validate.model_registry import arm_card
from harness.validate.models import Backend


def test_explicit_titles_are_not_recomputed_from_role_model_sizes():
    metadata = {
        "title": "Reviewed clinical team", "short_title": "Clinical team",
        "models": [{"id": "writer", "params": "12B"}],
        "roles": {"answer": {"id": "writer", "params": "12B"}},
    }
    card = arm_card("team", metadata=metadata)
    assert card["title"] == "Reviewed clinical team"
    assert card["short_title"] == "Clinical team"


def test_backend_label_is_used_when_model_metadata_is_unavailable():
    backend = Backend(
        id="custom-arm", label="Focused clinical experiment",
        endpoint_url="http://service:9999/v1", model_name="custom-profile",
    )
    card = arm_card(backend.id, backend=backend)
    assert card["title"] == card["short_title"] == backend.label
    assert card["models"] == [{"id": "custom-profile"}]
