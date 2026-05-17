MODEL (
  name refapp_28_demo.stg_patient_state,
  kind FULL,
  description 'Staging copy of legacy_27_raw.patient_state with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (patient_state_id),
  audits (unique_values(columns := (patient_state_id)))
);

SELECT
  src.patient_state_id,
  src.patient_program_id,
  src.state,
  src.start_date,
  src.end_date,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.uuid,
  src.form_namespace_and_path,
  src.encounter_id
FROM legacy_27_raw.patient_state src

;
