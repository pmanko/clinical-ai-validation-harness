MODEL (
  name refapp_28_demo.stg_drug,
  kind FULL,
  description 'Staging copy of legacy_27_raw.drug with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (drug_id),
  audits (unique_values(columns := (drug_id)))
);

SELECT
  src.drug_id,
  COALESCE(ct_0.target_concept_id, src.concept_id) AS concept_id,
  src.name,
  src.combination,
  src.dosage_form,
  src.maximum_daily_dose,
  src.minimum_daily_dose,
  src.route,
  src.creator,
  src.date_created,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid,
  src.date_changed,
  src.changed_by,
  src.strength,
  src.dose_limit_units
FROM legacy_27_raw.drug src
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
;
