MODEL (
  name refapp_28_demo.stg_field,
  kind FULL,
  description 'Staging copy of legacy_27_raw.field with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (field_id),
  audits (unique_values(columns := (field_id)))
);

SELECT
  src.field_id,
  src.name,
  src.description,
  src.field_type,
  COALESCE(ct_0.target_concept_id, src.concept_id) AS concept_id,
  src.table_name,
  src.attribute_name,
  src.default_value,
  src.select_multiple,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  src.uuid
FROM legacy_27_raw.field src
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
;
