MODEL (
  name refapp_28_demo.clinical.allergy,
  kind FULL,
  description 'P3 — drug-allergy boolean obs answered YES, promoted to allergy. Source questions: 6011 PENICILLIN, 6012 SULFA, 1083 OTHER MEDICINE. The allergen-substance pick per question concept is hand-curated at acceptance (placeholder concept_id 162523 used here; reviewer adjusts in datasets/mappings/openmrs-2.7-to-2.8.review.md). Expected ~7 rows.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid))
  )
);

SELECT
  s.person_id AS patient_id,
  CAST(NULL AS INT) AS severity_concept_id,
  CASE
    WHEN s.concept_id = 6011 THEN 162523  -- pending: real CIEL allergen concept
    WHEN s.concept_id = 6012 THEN 162523
    ELSE 162523
  END AS coded_allergen,
  CAST(NULL AS VARCHAR) AS non_coded_allergen,
  'DRUG' AS allergen_type,
  CAST(NULL AS VARCHAR) AS comments,
  s.creator,
  s.obs_datetime AS date_created,
  CAST(NULL AS INT) AS changed_by,
  CAST(NULL AS DATETIME) AS date_changed,
  1 AS voided,
  CAST(NULL AS INT) AS voided_by,
  CAST(NULL AS DATETIME) AS date_voided,
  CAST(NULL AS VARCHAR) AS void_reason,
  UUID() AS uuid,
  CAST(NULL AS VARCHAR) AS form_namespace_and_path,
  s.encounter_id,
  s.obs_id AS source_obs_id
FROM refapp_28_demo.staging.stg__legacy_obs s
WHERE s.concept_id IN (6011, 6012, 1083)
  AND s.value_coded = 1065
;
