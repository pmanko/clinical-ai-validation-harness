MODEL (
  name refapp_28_demo.stg_form,
  kind FULL,
  description 'Staging copy of legacy_27_raw.form with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (form_id),
  audits (unique_values(columns := (form_id)))
);

SELECT
  src.form_id,
  src.name,
  src.version,
  src.build,
  src.published,
  src.description,
  src.encounter_type,
  src.template,
  src.xslt,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.retired,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retired_reason,
  src.uuid
FROM legacy_27_raw.form src

;
