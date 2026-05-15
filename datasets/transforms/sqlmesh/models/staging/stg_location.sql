MODEL (
  name refapp_28_demo.stg_location,
  kind FULL,
  description 'Staging copy of legacy_27_raw.location with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (location_id),
  audits (unique_values(columns := (location_id)))
);

SELECT
  src.location_id,
  src.name,
  src.description,
  src.address1,
  src.address2,
  src.city_village,
  src.state_province,
  src.postal_code,
  src.country,
  src.latitude,
  src.longitude,
  src.creator,
  src.date_created,
  src.county_district,
  src.address3,
  src.address6,
  src.address5,
  src.address4,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.parent_location,
  src.uuid,
  src.changed_by,
  src.date_changed,
  src.address7,
  src.address8,
  src.address9,
  src.address10,
  src.address11,
  src.address12,
  src.address13,
  src.address14,
  src.address15,
  src.location_type_concept_id
FROM legacy_27_raw.location src

;
