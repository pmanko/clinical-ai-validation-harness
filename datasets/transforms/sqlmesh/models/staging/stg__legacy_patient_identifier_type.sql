MODEL (
  name refapp_28_demo.staging.stg__legacy_patient_identifier_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.patient_identifier_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (patient_identifier_type_id),
  audits (unique_values(columns := (patient_identifier_type_id)))
);

SELECT
  src.patient_identifier_type_id,
  src.name,
  src.description,
  src.format,
  src.check_digit,
  src.creator,
  src.date_created,
  src.required,
  src.format_description,
  src.validator,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid,
  src.location_behavior,
  src.uniqueness_behavior,
  src.date_changed,
  src.changed_by
FROM legacy_27_raw.patient_identifier_type src

;
