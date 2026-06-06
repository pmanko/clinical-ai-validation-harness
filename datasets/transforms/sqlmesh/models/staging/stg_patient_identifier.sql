MODEL (
  name refapp_28_demo.stg_patient_identifier,
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
  @shift_date(src.date_created) AS date_created,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.uuid,
  @shift_date(src.date_changed) AS date_changed,
  src.changed_by,
  src.patient_program_id
FROM legacy_27_raw.patient_identifier src

;
