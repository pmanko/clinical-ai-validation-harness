MODEL (
  name refapp_28_demo.stg_person_name,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person_name with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_name_id),
  audits (unique_values(columns := (person_name_id)))
);

SELECT
  src.person_name_id,
  src.preferred,
  src.person_id,
  src.prefix,
  src.given_name,
  src.middle_name,
  src.family_name_prefix,
  src.family_name,
  src.family_name2,
  src.family_name_suffix,
  src.degree,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.uuid
FROM legacy_27_raw.person_name src

;
