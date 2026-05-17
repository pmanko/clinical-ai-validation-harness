MODEL (
  name refapp_28_demo.stg_field_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.field_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (field_type_id),
  audits (unique_values(columns := (field_type_id)))
);

SELECT
  src.field_type_id,
  src.name,
  src.description,
  src.is_set,
  src.creator,
  src.date_created,
  src.uuid
FROM legacy_27_raw.field_type src

;
