MODEL (
  name refapp_28_demo.clinical.obs,
  kind FULL,
  description 'Rebound obs that stays in obs (89.9% of legacy obs). Drug-class answers, PROBLEM ADDED answers, allergy-Boolean YES answers, and Test+Coded questions are promoted out via clinical.drug_order, clinical.conditions, clinical.allergy, and clinical.test_order respectively.',
  tags (policy_bucket:passthrough),
  grain (obs_id),
  audits (
    unique_values(columns := (obs_id))
  )
);

WITH promoted_drug AS (
  SELECT obs_id
  FROM refapp_28_demo.staging.stg__legacy_obs s
  JOIN legacy_27_raw.concept c ON c.concept_id = s.value_coded
  JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
  WHERE cc.name = 'Drug'
),
promoted_dx AS (
  SELECT obs_id FROM refapp_28_demo.staging.stg__legacy_obs
  WHERE concept_id = 6042 AND value_coded IS NOT NULL
),
promoted_allergy AS (
  SELECT obs_id FROM refapp_28_demo.staging.stg__legacy_obs
  WHERE concept_id IN (6011, 6012, 1083) AND value_coded = 1065
),
promoted_test AS (
  SELECT s.obs_id
  FROM refapp_28_demo.staging.stg__legacy_obs s
  JOIN legacy_27_raw.concept c  ON c.concept_id = s.concept_id
  JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
  JOIN legacy_27_raw.concept_datatype cd ON cd.concept_datatype_id = c.datatype_id
  WHERE cc.name = 'Test' AND cd.name = 'Coded'
)
SELECT s.*
FROM refapp_28_demo.staging.stg__legacy_obs s
LEFT JOIN promoted_drug    pd ON pd.obs_id = s.obs_id
LEFT JOIN promoted_dx      px ON px.obs_id = s.obs_id
LEFT JOIN promoted_allergy pa ON pa.obs_id = s.obs_id
LEFT JOIN promoted_test    pt ON pt.obs_id = s.obs_id
WHERE pd.obs_id IS NULL
  AND px.obs_id IS NULL
  AND pa.obs_id IS NULL
  AND pt.obs_id IS NULL
;
