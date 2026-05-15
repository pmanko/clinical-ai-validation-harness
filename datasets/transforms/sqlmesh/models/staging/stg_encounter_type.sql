MODEL (
  name refapp_28_demo.stg_encounter_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.encounter_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (encounter_type_id),
  audits (unique_values(columns := (encounter_type_id)))
);

SELECT
  src.encounter_type_id,
  src.name,
  src.description,
  src.creator,
  src.date_created,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid,
  src.view_privilege,
  src.edit_privilege,
  src.changed_by,
  src.date_changed
FROM legacy_27_raw.encounter_type src

;
