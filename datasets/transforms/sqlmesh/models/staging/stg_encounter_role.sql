MODEL (
  name refapp_28_demo.stg_encounter_role,
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
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  src.uuid
FROM legacy_27_raw.encounter_role src

;
