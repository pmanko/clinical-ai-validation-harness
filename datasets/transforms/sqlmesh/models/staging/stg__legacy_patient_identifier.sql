MODEL (
  name refapp_28_demo.staging.stg__legacy_patient_identifier,
  kind FULL,
  description 'Staging copy of legacy_27_raw.patient_identifier with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (patient_identifier_id),
  audits (unique_values(columns := (patient_identifier_id)))
);

SELECT
  src.patient_identifier_id,
  src.patient_id,
  src.identifier,
  src.identifier_type,
  src.preferred,
  src.location_id,
  src.creator,
  src.date_created,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.uuid,
  src.date_changed,
  src.changed_by,
  src.patient_program_id
FROM legacy_27_raw.patient_identifier src

;
