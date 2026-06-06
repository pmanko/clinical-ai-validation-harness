MODEL (
  name refapp_28_demo.stg_encounter_provider,
  kind FULL,
  description 'Staging copy of legacy_27_raw.encounter_provider with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (encounter_provider_id),
  audits (unique_values(columns := (encounter_provider_id)))
);

SELECT
  src.encounter_provider_id,
  src.encounter_id,
  src.provider_id,
  src.encounter_role_id,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.voided,
  @shift_date(src.date_voided) AS date_voided,
  src.voided_by,
  src.void_reason,
  src.uuid
FROM legacy_27_raw.encounter_provider src

;
