MODEL (
  name refapp_28_demo.staging.stg__legacy_encounter_role,
  kind FULL,
  description 'Staging copy of legacy_27_raw.encounter_role with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (encounter_role_id),
  audits (unique_values(columns := (encounter_role_id)))
);

SELECT
  src.encounter_role_id,
  src.name,
  src.description,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid
FROM legacy_27_raw.encounter_role src

;
