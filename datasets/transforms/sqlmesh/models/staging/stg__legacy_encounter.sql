MODEL (
  name refapp_28_demo.staging.stg__legacy_encounter,
  kind FULL,
  description 'Staging copy of legacy_27_raw.encounter with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (encounter_id),
  audits (unique_values(columns := (encounter_id)))
);

SELECT
  src.encounter_id,
  src.encounter_type,
  src.patient_id,
  src.location_id,
  src.form_id,
  src.encounter_datetime,
  src.creator,
  src.date_created,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.uuid,
  src.changed_by,
  src.date_changed,
  src.visit_id
FROM legacy_27_raw.encounter src

;
