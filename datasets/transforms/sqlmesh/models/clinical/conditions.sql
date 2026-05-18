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

-- uuid: deterministic UUIDv5-style name-based UUID with fixed namespace
-- 2f56d7b8-8f8f-5d3a-9f52-002002800001 and name
-- feature-002:conditions:<source obs uuid>.
SELECT
  s.person_id                       AS patient_id,
  s.encounter_id,
  ct.target_concept_id              AS condition_coded,       -- UUID-resolved local FK; no source-integer fallback
  CAST(NULL AS INT)                 AS condition_coded_name,  -- no concept_name FK signal in source
  CAST(NULL AS VARCHAR)             AS condition_non_coded,
  'ACTIVE'                          AS clinical_status,
  CAST(NULL AS VARCHAR)             AS verification_status,
  CAST(NULL AS INT)                 AS previous_version,
  s.obs_datetime                    AS onset_date,            -- best available signal from legacy obs
  s.obs_datetime                    AS date_created,
  s.creator,
  0                                 AS voided,
  CAST(NULL AS INT)                 AS voided_by,
  CAST(NULL AS DATETIME)            AS date_voided,
  CAST(NULL AS VARCHAR)             AS void_reason,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:conditions:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 21, 12)
  ))                                AS uuid,
  s.obs_id                          AS source_obs_id          -- staging lineage; dropped by promote column intersection
FROM refapp_28_demo.stg_obs s
JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.source_value_coded
WHERE s.source_concept_id = 6042
  AND s.source_value_coded IS NOT NULL
;
