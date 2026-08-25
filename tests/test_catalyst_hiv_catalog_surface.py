"""Preserve the historical catalog v6 fixture without making it a product cap.

These assertions describe the committed v6 evidence. The active runtime
surface is every relation the configured read-only database role can read.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "catalyst-sources" / "openmrs-hiv"
CATALOG = SOURCE / "catalog" / "openmrs-hiv-catalog.json"
OVERLAY = SOURCE / "catalog-overlay.json"

CATALOG_V6_RELATIONS = {
    # Preferred clinical relations
    "analytics.hiv_observation_fact_v1",
    "analytics.hiv_medication_request_fact_v1",
    "analytics.hiv_visit_fact_v1",
    "analytics.hiv_concept_mapping_v1",
    "analytics.hiv_patient_dim_v1",
    # Raw fallbacks
    "public.patient_flat",
    "public.encounter_flat",
    "public.observation_flat",
    "public.medication_request_flat",
    "public.condition_flat",
    "public.medication_flat",
    # Operating records
    "analytics.pipeline_run_v1",
    "analytics.pipeline_freshness_v1",
}


def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_is_v6() -> None:
    catalog = _catalog()
    assert catalog["catalogVersion"] == "openmrs-hiv-catalog-v6"
    # The schema itself did not change; only which relations are exposed.
    assert catalog["schemaVersion"] == "analytics-v1"


def test_catalog_v6_records_its_historical_thirteen_relations() -> None:
    names = {view["name"] for view in _catalog()["views"]}
    assert names == CATALOG_V6_RELATIONS
    assert len(CATALOG_V6_RELATIONS) == 13


def test_the_overlay_and_the_generated_catalog_agree() -> None:
    """The overlay is the reviewed input; the catalog is what it produced."""
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    assert {entry["name"] for entry in overlay["approvedViews"]} == (
        CATALOG_V6_RELATIONS
    )
    assert overlay["catalogVersion"] == _catalog()["catalogVersion"]


def test_every_historical_v6_relation_was_marked_approved() -> None:
    assert all(view.get("approved") is True for view in _catalog()["views"])


def test_every_column_carries_a_reviewed_description() -> None:
    """Descriptions are the model's only schema context."""
    missing = [
        f"{view['name']}.{column['name']}"
        for view in _catalog()["views"]
        for column in view["columns"]
        if not (column.get("description") or "").strip()
    ]
    assert missing == []


def test_every_relation_states_its_grain() -> None:
    missing = [
        view["name"]
        for view in _catalog()["views"]
        if not (view.get("grain") or "").strip()
    ]
    assert missing == []


def test_the_patient_dimension_answers_who_a_patient_is() -> None:
    """The gap that made a patient-name request unanswerable in Phase 0."""
    dimension = next(
        view
        for view in _catalog()["views"]
        if view["name"] == "analytics.hiv_patient_dim_v1"
    )
    columns = {column["name"] for column in dimension["columns"]}
    assert {"family_name", "given_name"} <= columns


def test_every_raw_fallback_warns_about_its_fan_out() -> None:
    """The repetition is the dangerous part: a row here is not a resource."""
    for view in _catalog()["views"]:
        if not view["name"].startswith("public."):
            continue
        grain = view["grain"].lower()
        assert "one row per" in grain, view["name"]
        assert "repeat" in grain or "never count rows" in grain, view["name"]


def test_a_raw_fallback_with_a_curated_twin_names_it() -> None:
    """Four of the six have a curated view that answers the same question."""
    twins = {
        "public.patient_flat": "analytics.hiv_patient_dim_v1",
        "public.encounter_flat": "analytics.hiv_visit_fact_v1",
        "public.observation_flat": "analytics.hiv_observation_fact_v1",
        "public.medication_request_flat": "analytics.hiv_medication_request_fact_v1",
    }
    grains = {view["name"]: view["grain"] for view in _catalog()["views"]}
    for raw, curated in twins.items():
        assert curated in grains[raw], raw
        assert "prefer" in grains[raw].lower(), raw
