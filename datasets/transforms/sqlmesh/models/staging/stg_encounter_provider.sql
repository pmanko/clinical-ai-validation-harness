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
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.voided,
  src.date_voided,
  src.voided_by,
  src.void_reason,
  src.uuid
FROM legacy_27_raw.encounter_provider src

;
