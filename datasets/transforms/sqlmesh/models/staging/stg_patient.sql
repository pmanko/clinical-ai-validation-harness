MODEL (
  name refapp_28_demo.stg_patient,
  kind FULL,
  description 'Staging copy of legacy_27_raw.patient with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (patient_id),
  audits (unique_values(columns := (patient_id)))
);

SELECT
  src.patient_id,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.allergy_status
FROM legacy_27_raw.patient src

;
