MODEL (
  name refapp_28_demo.stg_person,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_id),
  audits (unique_values(columns := (person_id)))
);

SELECT
  src.person_id,
  src.gender,
  @shift_date(src.birthdate) AS birthdate,
  src.birthdate_estimated,
  src.dead,
  @shift_date(src.death_date) AS death_date,
  src.cause_of_death,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.uuid,
  src.deathdate_estimated,
  src.birthtime,
  src.cause_of_death_non_coded
FROM legacy_27_raw.person src

;
