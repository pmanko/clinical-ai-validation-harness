MODEL (
  name refapp_28_demo.stg_person_attribute,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person_attribute with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_attribute_id),
  audits (unique_values(columns := (person_attribute_id)))
);

SELECT
  src.person_attribute_id,
  src.person_id,
  src.value,
  src.person_attribute_type_id,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.uuid
FROM legacy_27_raw.person_attribute src

;
