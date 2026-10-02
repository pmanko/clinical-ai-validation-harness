import math

import pytest

from harness.metadata import copy_target_provenance


@pytest.mark.parametrize("source", ["supplied", "observed_api", "unavailable"])
@pytest.mark.parametrize("revision", ["caller-revision", None])
def test_copies_valid_provenance_without_verifying_revision(source, revision):
    supplied = [{
        "target_id": "service", "target_source": source,
        "target_actual_sha": revision, "target_url": None,
        "evidence_status": "development", "decision_rationale": "Caller supplied",
        "runtime": {"models": ["writer"]},
    }]
    frozen = copy_target_provenance(supplied)
    assert frozen == supplied
    supplied[0]["runtime"]["models"].append("reviewer")
    assert frozen[0]["runtime"]["models"] == ["writer"]


@pytest.mark.parametrize("field", ["target_id", "target_source", "target_actual_sha"])
def test_rejects_missing_required_fields(field):
    item = {"target_id": "service", "target_source": "supplied", "target_actual_sha": None}
    del item[field]
    with pytest.raises(ValueError, match="target_provenance"):
        copy_target_provenance([item])


@pytest.mark.parametrize("field,value", [
    ("target_id", " "), ("target_id", 1),
    ("target_source", "unknown"), ("target_source", ["supplied"]),
    ("target_actual_sha", 1), ("target_actual_sha", False),
    ("target_url", 1), ("evidence_status", None), ("decision_rationale", []),
])
def test_rejects_invalid_field_values(field, value):
    item = {"target_id": "service", "target_source": "supplied", "target_actual_sha": None}
    item[field] = value
    with pytest.raises(ValueError, match="target_provenance"):
        copy_target_provenance([item])


@pytest.mark.parametrize("value", [{}, "service", [None]])
def test_rejects_non_object_lists(value):
    with pytest.raises(ValueError, match="target_provenance"):
        copy_target_provenance(value)


@pytest.mark.parametrize("extension", [math.nan, math.inf, object()])
def test_rejects_non_json_extensions(extension):
    item = {"target_id": "service", "target_source": "supplied", "target_actual_sha": None,
            "runtime": extension}
    with pytest.raises(ValueError, match="finite JSON"):
        copy_target_provenance([item])


def test_missing_provenance_is_explicitly_empty():
    assert copy_target_provenance(None) == []
    assert copy_target_provenance([]) == []
