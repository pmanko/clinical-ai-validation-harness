MODEL (
  name refapp_28_demo.clin__orders,
  kind FULL,
  description 'Parent orders rows for promoted drug_order + test_order (Hibernate joined-table inheritance: openmrs.orders is the parent of drug_order/test_order; child rows require a matching parent with the same order_id). One row per promoted obs. order_id = source obs_id (deterministic, traceable; no clinical relevance — clinical identity lives in uuid).',
  tags (policy_bucket:seed_augment),
  grain (order_id),
  audits (
    unique_values(columns := (order_id)),
    audit_orders_row_count_min
  )
);

-- The two promotion selectors are disjoint (drug_order = value_coded.class=Drug;
-- test_order = concept.class=Test+datatype=Coded) so an obs_id appears in at most one branch.
SELECT
  s.obs_id                                      AS order_id,
  2                                             AS order_type_id,    -- 2 = Drug Order (openmrs.order_type)
  COALESCE(ct.target_concept_id, s.value_coded) AS concept_id,
  COALESCE(ep.provider_id, 1)                   AS orderer,           -- fallback: user_id=1
  s.encounter_id,
  CAST(NULL AS TEXT)                            AS instructions,
  s.obs_datetime                                AS date_activated,
  CAST(NULL AS DATETIME)                        AS auto_expire_date,
  CAST(NULL AS DATETIME)                        AS date_stopped,
  CAST(NULL AS INT)                             AS order_reason,
  CAST(NULL AS VARCHAR)                         AS order_reason_non_coded,
  s.creator,
  s.date_created,
  0                                             AS voided,
  CAST(NULL AS INT)                             AS voided_by,
  CAST(NULL AS DATETIME)                        AS date_voided,
  CAST(NULL AS VARCHAR)                         AS void_reason,
  s.person_id                                   AS patient_id,
  CAST(NULL AS VARCHAR)                         AS accession_number,
  CONCAT('ORD-DRG-', s.obs_id)                  AS uuid,              -- placeholder; opportunistic uniqueness; sufficient until §R-typed-promotion Q2 UUIDv5 lands
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
  ON c.concept_id = s.value_coded
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.value_coded
LEFT JOIN (
  -- An encounter can have multiple providers (one per role). For the
  -- orderer fallback we just need one — pick the lowest provider_id
  -- deterministically.
  SELECT encounter_id, MIN(provider_id) AS provider_id
  FROM refapp_28_demo.stg_encounter_provider
  GROUP BY encounter_id
) ep ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Drug'

UNION ALL

SELECT
  s.obs_id                                      AS order_id,
  3                                             AS order_type_id,    -- 3 = Test Order
  COALESCE(ct.target_concept_id, s.concept_id)  AS concept_id,
  COALESCE(ep.provider_id, 1)                   AS orderer,
  s.encounter_id,
  CAST(NULL AS TEXT)                            AS instructions,
  s.obs_datetime                                AS date_activated,
  CAST(NULL AS DATETIME)                        AS auto_expire_date,
  CAST(NULL AS DATETIME)                        AS date_stopped,
  CAST(NULL AS INT)                             AS order_reason,
  CAST(NULL AS VARCHAR)                         AS order_reason_non_coded,
  s.creator,
  s.date_created,
  0                                             AS voided,
  CAST(NULL AS INT)                             AS voided_by,
  CAST(NULL AS DATETIME)                        AS date_voided,
  CAST(NULL AS VARCHAR)                         AS void_reason,
  s.person_id                                   AS patient_id,
  CAST(NULL AS VARCHAR)                         AS accession_number,
  CONCAT('ORD-TST-', s.obs_id)                  AS uuid,
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
  ON c.concept_id = s.concept_id
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd
  ON cd.concept_datatype_id = c.datatype_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.concept_id
LEFT JOIN (
  SELECT encounter_id, MIN(provider_id) AS provider_id
  FROM refapp_28_demo.stg_encounter_provider
  GROUP BY encounter_id
) ep ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Test'
  AND cd.name = 'Coded'
  -- An obs can have a Test-class question AND a Drug-class answer
  -- (e.g., "what drug did the patient take?"). Drug_order wins the
  -- promotion in that case; this clause prevents the same obs from
  -- producing two orders rows.
  AND NOT EXISTS (
    SELECT 1
    FROM legacy_27_raw.concept dc
    JOIN legacy_27_raw.concept_class dcc ON dcc.concept_class_id = dc.class_id
    WHERE dc.concept_id = s.value_coded AND dcc.name = 'Drug'
  )
;
