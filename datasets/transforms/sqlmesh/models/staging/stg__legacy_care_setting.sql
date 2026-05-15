MODEL (
  name refapp_28_demo.staging.stg__legacy_care_setting,
  kind FULL,
  description 'Staging copy of legacy_27_raw.care_setting with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (care_setting_id),
  audits (unique_values(columns := (care_setting_id)))
);

SELECT
  src.care_setting_id,
  src.name,
  src.description,
  src.care_setting_type,
  src.creator,
  src.date_created,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.changed_by,
  src.date_changed,
  src.uuid
FROM legacy_27_raw.care_setting src

;
