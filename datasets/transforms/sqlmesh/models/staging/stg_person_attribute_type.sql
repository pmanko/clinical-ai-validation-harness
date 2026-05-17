MODEL (
  name refapp_28_demo.stg_person_attribute_type,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person_attribute_type with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_attribute_type_id),
  audits (unique_values(columns := (person_attribute_type_id)))
);

SELECT
  src.person_attribute_type_id,
  src.name,
  src.description,
  src.format,
  src.foreign_key,
  src.searchable,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.edit_privilege,
  src.uuid,
  src.sort_weight
FROM legacy_27_raw.person_attribute_type src

;
