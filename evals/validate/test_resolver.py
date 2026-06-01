import json

import pytest

from harness.validate.resolver import resolve_backends


def test_resolve_maps_ids_in_order(tmp_path):
    reg = tmp_path / "backends.json"
    reg.write_text(
        json.dumps(
            {
                "a": {"endpointUrl": "http://a/v1/chat/completions", "modelName": "ma"},
                "b": {"endpointUrl": "http://b/v1/chat/completions", "modelName": "mb"},
            }
        ),
        encoding="utf-8",
    )
    out = resolve_backends(["b", "a"], reg)
    assert [x.id for x in out] == ["b", "a"]
    assert out[0].model_name == "mb"


def test_resolve_unknown_id_raises(tmp_path):
    reg = tmp_path / "backends.json"
    reg.write_text('{"a":{"endpointUrl":"http://a/v1","modelName":"m"}}', encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_backends(["a", "missing"], reg)
