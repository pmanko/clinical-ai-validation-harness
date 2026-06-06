MODEL (
  name refapp_28_demo.stg_order_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.order_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (order_type_id),
  audits (unique_values(columns := (order_type_id)))
);

SELECT
  src.order_type_id,
  src.name,
  src.description,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  src.uuid,
  src.java_class_name,
  src.parent,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed
FROM legacy_27_raw.order_type src

;
