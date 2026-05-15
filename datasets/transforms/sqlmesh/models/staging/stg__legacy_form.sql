MODEL (
  name refapp_28_demo.staging.stg__legacy_form,
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
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retired_reason,
  src.uuid
FROM legacy_27_raw.form src

;
