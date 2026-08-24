"""Catalog v6 is the reviewed Phase 1 data surface.

The writer, the editor, the validator, and the executor all read this one
list, so a relation appearing or disappearing is a reviewed catalog version
rather than a permissions change or a regeneration artifact. These assertions
read the committed catalog, not the database.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "catalyst-sources" / "openmrs-hiv"
CATALOG = SOURCE / "catalog" / "openmrs-hiv-catalog.json"
OVERLAY = SOURCE / "catalog-overlay.json"

PHASE_1_SURFACE = {
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


def test_catalog_exposes_exactly_the_reviewed_thirteen() -> None:
    names = {view["name"] for view in _catalog()["views"]}
    assert names == PHASE_1_SURFACE
    assert len(PHASE_1_SURFACE) == 13


def test_the_overlay_and_the_generated_catalog_agree() -> None:
    """The overlay is the reviewed input; the catalog is what it produced."""
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    assert {entry["name"] for entry in overlay["approvedViews"]} == PHASE_1_SURFACE
    assert overlay["catalogVersion"] == _catalog()["catalogVersion"]


def test_every_relation_is_approved_for_the_one_shared_surface() -> None:
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
