MODEL (
  name refapp_28_demo.stg_patient_state,
  kind FULL,
  description 'ALL legacy patient enrollment-states (id-space preserved with patient_program and program_workflow_state). Nothing dropped — cohort GROUP assignments and PATIENT DIED are preserved; their state concepts resolve via stg_concept_carryforward.',
  tags (policy_bucket:passthrough),
  grain (patient_state_id),
  audits (unique_values(columns := (patient_state_id)))
);

SELECT
  src.patient_state_id,
  src.patient_program_id,
  src.state,
  @shift_date(src.start_date) AS start_date,
  @shift_date(src.end_date) AS end_date,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.uuid,
  src.form_namespace_and_path,
  src.encounter_id
FROM legacy_27_raw.patient_state src
;
