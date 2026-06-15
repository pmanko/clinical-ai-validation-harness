MODEL (
  name refapp_28_demo.stg_person,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_id),
  audits (
    unique_values(columns := (person_id)),
    audit_no_pregnant_male,
    audit_no_child_with_adult_weight,
    audit_no_adult_with_child_weight
  )
);

-- birthdate/gender: normally passed through (birthdate uniformly date-transplanted).
-- The de-id scrambled DOB and sex independently of clinical content, so
-- stg_demographics_reconcile supplies a weight-derived birthdate and/or a
-- pregnancy-derived gender for patients whose recorded values contradict the clinical
-- evidence; those take precedence. Corrected birthdates are marked estimated.
SELECT
  src.person_id,
  COALESCE(d.corrected_gender, src.gender) AS gender,
  COALESCE(d.corrected_birthdate, @shift_date(src.birthdate)) AS birthdate,
  CASE WHEN d.corrected_birthdate IS NOT NULL THEN 1 ELSE src.birthdate_estimated END AS birthdate_estimated,
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
LEFT JOIN refapp_28_demo.stg_demographics_reconcile d
  ON d.person_id = src.person_id
;
