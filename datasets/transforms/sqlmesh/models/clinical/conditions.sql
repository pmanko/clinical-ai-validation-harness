MODEL (
  name refapp_28_demo.clin__conditions,
  kind FULL,
  description 'P2 — obs whose question concept is 6042 (PROBLEM ADDED), promoted to conditions with condition_coded rebound via the bridge rule. Expected ~3,642 rows.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid)),
    audit_conditions_row_count_min
  )
);

SELECT
  s.person_id AS patient_id,
  s.encounter_id,
  COALESCE(ct.target_concept_id, s.value_coded) AS condition_coded,
  CAST(NULL AS INT) AS condition_coded_name_id,
  CAST(NULL AS VARCHAR) AS condition_non_coded,
  'ACTIVE' AS clinical_status,
  CAST(NULL AS VARCHAR) AS verification_status,
  CAST(NULL AS INT) AS previous_version,
  CAST(NULL AS DATE) AS onset_date,
  s.obs_datetime AS date_created,
  s.creator,
  0 AS voided,
  CAST(NULL AS INT) AS voided_by,
  CAST(NULL AS DATETIME) AS date_voided,
  CAST(NULL AS VARCHAR) AS void_reason,
  UUID() AS uuid,
  s.obs_id AS source_obs_id
FROM refapp_28_demo.stg_obs s
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.value_coded
WHERE s.concept_id = 6042
  AND s.value_coded IS NOT NULL
;
