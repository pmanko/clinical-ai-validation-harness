MODEL (
  name refapp_28_demo.terminology__encounter_role_map,
  kind VIEW,
  description 'FK reconciliation map: legacy encounter_role_id ↔ openmrs encounter_role_id. Default policy: identity (legacy verbatim). See research.md §R-load-pattern.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  encounter_role_id AS source_id,
  encounter_role_id AS target_id
FROM refapp_28_demo.stg_encounter_role
;
