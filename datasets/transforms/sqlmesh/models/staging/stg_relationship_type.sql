MODEL (
  name refapp_28_demo.stg_relationship_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.relationship_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (relationship_type_id),
  audits (unique_values(columns := (relationship_type_id)))
);

SELECT
  src.relationship_type_id,
  src.a_is_to_b,
  src.b_is_to_a,
  src.preferred,
  src.weight,
  src.description,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.uuid,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  @shift_date(src.date_changed) AS date_changed,
  src.changed_by
FROM legacy_27_raw.relationship_type src

;
