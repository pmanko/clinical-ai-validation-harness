import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "datasets/validation/conformance/dual-provider-conformance.v1.json"
CONTRACT = ROOT / "specs/artifacts/planning/openmrs-dual-provider-conformance-contract.md"


def test_dual_provider_fixture_has_stable_non_overlapping_case_ids():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "dual_provider_conformance.v1"
    families = {
        "provider_lifecycle",
        "provider_capabilities",
        "querystore_records",
        "context_policy",
        "temporal_gate",
        "drug_safety_status",
    }
    assert families <= set(payload)

    identifiers = [case["id"] for family in families for case in payload[family]]
    assert len(identifiers) == len(set(identifiers))
    assert all(identifier.count(".") >= 1 for identifier in identifiers)


def test_conformance_contract_maps_every_fixture_family_to_an_owner():
    text = CONTRACT.read_text(encoding="utf-8")

    for family in (
        "provider_lifecycle",
        "provider_capabilities",
        "querystore_records",
        "context_policy",
        "temporal_gate",
        "drug_safety_status",
    ):
        assert f"`{family}`" in text
    assert "Red-First Test Procedure" in text
