MODEL (
  name refapp_28_demo.staging.stg__legacy_patient_program,
  kind FULL,
  description 'Staging copy of legacy_27_raw.patient_program with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (patient_program_id),
  audits (unique_values(columns := (patient_program_id)))
);

SELECT
  src.patient_program_id,
  src.patient_id,
  src.program_id,
  src.date_enrolled,
  src.date_completed,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.uuid,
  src.location_id,
  src.outcome_concept_id
FROM legacy_27_raw.patient_program src

;
