MODEL (
  name refapp_28_demo.stg_form_field,
  kind FULL,
  description 'Staging copy of legacy_27_raw.form_field with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (form_field_id),
  audits (unique_values(columns := (form_field_id)))
);

SELECT
  src.form_field_id,
  src.form_id,
  src.field_id,
  src.field_number,
  src.field_part,
  src.page_number,
  src.parent_form_field,
  src.min_occurs,
  src.max_occurs,
  src.required,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.sort_weight,
  src.uuid
FROM legacy_27_raw.form_field src

;
