MODEL (
  name refapp_28_demo.terminology__encounter_type_map,
  kind VIEW,
  description 'FK reconciliation map: legacy encounter_type_id ↔ openmrs encounter_type_id. Default policy: identity (legacy verbatim). See research.md §R-load-pattern.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  encounter_type_id AS source_id,
  encounter_type_id AS target_id
FROM refapp_28_demo.stg_encounter_type
;
