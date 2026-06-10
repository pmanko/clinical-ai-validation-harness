MODEL (
  name refapp_28_demo.stg_care_setting,
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
  @shift_date(src.date_created) AS date_created,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.uuid
FROM legacy_27_raw.care_setting src

;
