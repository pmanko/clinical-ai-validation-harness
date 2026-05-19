MODEL (
  name refapp_28_demo.stg_drug,
  kind FULL,
  description 'Drug catalog augmentation for promoted drug orders. Preserves legacy drug rows under non-colliding deterministic IDs and adds one minimal concept-level catalog row for each promoted Drug-class obs.value_coded concept.',
  tags (policy_bucket:passthrough),
  grain (drug_id),
  audits (unique_values(columns := (drug_id)))
);

-- ID policy:
--   200000 + legacy drug_id: preserve source drug formulations without colliding
--     with stock RefApp drug IDs (legacy drug_id 5 was Acyclovir in stock).
--   300000 + source_value_coded: one generated concept-level drug row for each
--     promoted medication concept. drug_order uses these rows because the source
--     obs has no value_drug signal to pick a specific formulation/strength.
--
-- UUID policy:
--   legacy rows preserve source drug.uuid.
--   generated concept rows use deterministic UUIDv5-style name-based UUIDs from
--   namespace 2f56d7b8-8f8f-5d3a-9f52-002002800001 and name
--   feature-002:drug-catalog:<source concept id>.
SELECT
  200000 + src.drug_id AS drug_id,
  ct_0.target_concept_id AS concept_id,
  src.name,
  src.combination,
  ct_dosage.target_concept_id AS dosage_form,
  src.maximum_daily_dose,
  src.minimum_daily_dose,
  ct_route.target_concept_id AS route,
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
  ct_dose_units.target_concept_id AS dose_limit_units
FROM legacy_27_raw.drug src
JOIN refapp_28_demo.seed__concept_translation ct_0
  ON ct_0.source_concept_id = src.concept_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct_dosage
  ON ct_dosage.source_concept_id = src.dosage_form
LEFT JOIN refapp_28_demo.seed__concept_translation ct_route
  ON ct_route.source_concept_id = src.route
LEFT JOIN refapp_28_demo.seed__concept_translation ct_dose_units
  ON ct_dose_units.source_concept_id = src.dose_limit_units

UNION ALL

SELECT
  300000 + meds.source_value_coded AS drug_id,
  meds.target_concept_id AS concept_id,
  COALESCE(cn.name, CONCAT('Concept ', meds.target_concept_id)) AS name,
  0 AS combination,
  CAST(NULL AS INT) AS dosage_form,
  CAST(NULL AS DOUBLE) AS maximum_daily_dose,
  CAST(NULL AS DOUBLE) AS minimum_daily_dose,
  CAST(NULL AS INT) AS route,
  1 AS creator,
  MIN(meds.first_date_created) AS date_created,
  0 AS retired,
  CAST(NULL AS INT) AS retired_by,
  CAST(NULL AS DATETIME) AS date_retired,
  CAST(NULL AS VARCHAR) AS retire_reason,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:drug-catalog:', meds.source_value_coded))), 21, 12)
  )) AS uuid,
  CAST(NULL AS DATETIME) AS date_changed,
  CAST(NULL AS INT) AS changed_by,
  CAST(NULL AS VARCHAR) AS strength,
  CAST(NULL AS INT) AS dose_limit_units
FROM (
  SELECT
    s.source_value_coded,
    ct.target_concept_id,
    MIN(s.date_created) AS first_date_created
  FROM refapp_28_demo.stg_obs s
  JOIN legacy_27_raw.concept c
    ON c.concept_id = s.source_value_coded
  JOIN legacy_27_raw.concept_class cc
    ON cc.concept_class_id = c.class_id
  JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.source_concept_id = s.source_value_coded
  WHERE cc.name = 'Drug'
  GROUP BY s.source_value_coded, ct.target_concept_id
) meds
LEFT JOIN openmrs.concept_name cn
  ON cn.concept_id = meds.target_concept_id
 AND cn.locale = 'en'
 AND cn.locale_preferred = 1
 AND cn.voided = 0
GROUP BY meds.source_value_coded, meds.target_concept_id, cn.name
;
