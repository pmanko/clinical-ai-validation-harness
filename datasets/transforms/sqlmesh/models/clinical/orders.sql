MODEL (
  name refapp_28_demo.clin__orders,
  kind FULL,
  description 'Parent orders rows for promoted drug_order + test_order (Hibernate joined-table inheritance: openmrs.orders is the parent of drug_order/test_order; child rows require a matching parent with the same order_id). One row per promoted obs. order_id = source obs_id (deterministic, traceable; no clinical relevance — clinical identity lives in uuid).',
  tags (policy_bucket:seed_augment),
  grain (order_id),
  audits (
    unique_values(columns := (order_id)),
    audit_orders_row_count_min,
    audit_clinical_fk_integrity,
    audit_parent_child_integrity
  )
);

-- Promotion selectors are source-ID-safe: class filtering uses legacy_27_raw.concept
-- (source concept IDs) not the rebound seed FKs. This keeps classification stable
-- regardless of which local target_concept_id the seed resolves to.
--
-- uuid: deterministic UUIDv5-style name-based UUID with fixed namespace
-- 2f56d7b8-8f8f-5d3a-9f52-002002800001 and names
-- feature-002:orders:drug:<source obs uuid> / feature-002:orders:test:<source obs uuid>.
SELECT
  s.obs_id                                      AS order_id,
  2                                             AS order_type_id,    -- 2 = Drug Order (openmrs.order_type)
  ct.target_concept_id                          AS concept_id,       -- UUID-resolved local FK; no source-integer fallback
  COALESCE(ep.provider_id, 1)                   AS orderer,           -- fallback: user_id=1
  s.encounter_id,
  CAST(NULL AS TEXT)                            AS instructions,
  s.obs_datetime                                AS date_activated,  -- already shifted in stg_obs; pass through
  CAST(NULL AS DATETIME)                        AS auto_expire_date,
  CAST(NULL AS DATETIME)                        AS date_stopped,
  CAST(NULL AS INT)                             AS order_reason,
  CAST(NULL AS VARCHAR)                         AS order_reason_non_coded,
  s.creator,
  s.date_created                                AS date_created,    -- already shifted in stg_obs; pass through
  0                                             AS voided,
  CAST(NULL AS INT)                             AS voided_by,
  CAST(NULL AS DATETIME)                        AS date_voided,
  CAST(NULL AS VARCHAR)                         AS void_reason,
  s.person_id                                   AS patient_id,
  CAST(NULL AS VARCHAR)                         AS accession_number,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:drug:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 21, 12)
  ))                                            AS uuid,
  'ROUTINE'                                     AS urgency,
  CONCAT('ORD-', s.obs_id)                      AS order_number,
  CAST(NULL AS INT)                             AS previous_order_id,
  'NEW'                                         AS order_action,
  CAST(NULL AS VARCHAR)                         AS comment_to_fulfiller,
  1                                             AS care_setting,      -- 1 = Outpatient
  CAST(NULL AS DATETIME)                        AS scheduled_date,
  CAST(NULL AS INT)                             AS order_group_id,
  CAST(NULL AS DOUBLE)                          AS sort_weight,
  CAST(NULL AS VARCHAR)                         AS fulfiller_comment,
  CAST(NULL AS VARCHAR)                         AS fulfiller_status,
  CAST(NULL AS VARCHAR)                         AS form_namespace_and_path
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.source_value_coded        -- source ID (pre-rebind) for correct legacy classification
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.source_value_coded
LEFT JOIN (
  SELECT encounter_id, MIN(provider_id) AS provider_id
  FROM refapp_28_demo.stg_encounter_provider
  GROUP BY encounter_id
) ep ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Drug'

UNION ALL

SELECT
  s.obs_id                                      AS order_id,
  3                                             AS order_type_id,    -- 3 = Test Order
  ct.target_concept_id                          AS concept_id,       -- UUID-resolved local FK; no source-integer fallback
  COALESCE(ep.provider_id, 1)                   AS orderer,
  s.encounter_id,
  CAST(NULL AS TEXT)                            AS instructions,
  s.obs_datetime                                AS date_activated,  -- already shifted in stg_obs; pass through
  CAST(NULL AS DATETIME)                        AS auto_expire_date,
  CAST(NULL AS DATETIME)                        AS date_stopped,
  CAST(NULL AS INT)                             AS order_reason,
  CAST(NULL AS VARCHAR)                         AS order_reason_non_coded,
  s.creator,
  s.date_created                                AS date_created,    -- already shifted in stg_obs; pass through
  0                                             AS voided,
  CAST(NULL AS INT)                             AS voided_by,
  CAST(NULL AS DATETIME)                        AS date_voided,
  CAST(NULL AS VARCHAR)                         AS void_reason,
  s.person_id                                   AS patient_id,
  CAST(NULL AS VARCHAR)                         AS accession_number,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:orders:test:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 21, 12)
  ))                                            AS uuid,
  'ROUTINE'                                     AS urgency,
  CONCAT('ORD-', s.obs_id)                      AS order_number,
  CAST(NULL AS INT)                             AS previous_order_id,
  'NEW'                                         AS order_action,
  CAST(NULL AS VARCHAR)                         AS comment_to_fulfiller,
  1                                             AS care_setting,
  CAST(NULL AS DATETIME)                        AS scheduled_date,
  CAST(NULL AS INT)                             AS order_group_id,
  CAST(NULL AS DOUBLE)                          AS sort_weight,
  CAST(NULL AS VARCHAR)                         AS fulfiller_comment,
  CAST(NULL AS VARCHAR)                         AS fulfiller_status,
  CAST(NULL AS VARCHAR)                         AS form_namespace_and_path
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.source_concept_id         -- source ID (pre-rebind) for correct legacy classification
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd
  ON cd.concept_datatype_id = c.datatype_id
JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.source_concept_id
LEFT JOIN (
  SELECT encounter_id, MIN(provider_id) AS provider_id
  FROM refapp_28_demo.stg_encounter_provider
  GROUP BY encounter_id
) ep ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Test'
  AND cd.name = 'Coded'
  -- Drug_order wins when an obs has a Test-class question AND a Drug-class
  -- answer. Prevents the same obs_id from producing two orders rows.
  AND NOT EXISTS (
    SELECT 1
    FROM legacy_27_raw.concept dc
    JOIN legacy_27_raw.concept_class dcc ON dcc.concept_class_id = dc.class_id
    WHERE dc.concept_id = s.source_value_coded AND dcc.name = 'Drug'  -- source ID
  )
;
