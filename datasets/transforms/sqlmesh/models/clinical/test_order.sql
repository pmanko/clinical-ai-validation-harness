MODEL (
  name refapp_28_demo.clin__test_order,
  kind FULL,
  description 'P4 — obs whose question concept is Test-class with Coded datatype, promoted to test_order. The TEST concept (obs.concept_id, not value_coded) populates test_order.concept_id. The source obs is preserved as the result, linked back via obs.order_id. Expected ~1,120 rows.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid)),
    audit_test_order_row_count_min
  )
);

SELECT
  -- order_id = source obs_id. Matches the parent clin__orders row.
  s.obs_id AS order_id,
  s.person_id AS patient_id,
  COALESCE(ct.target_concept_id, s.concept_id) AS concept_id,
  s.encounter_id,
  s.obs_datetime AS date_activated,
  'NEW' AS order_action,
  'ROUTINE' AS urgency,
  CAST(NULL AS DATETIME) AS auto_expire_date,
  CAST(NULL AS INT) AS orderer,
  s.creator,
  s.obs_datetime AS date_created,
  0 AS voided,
  CAST(NULL AS INT) AS voided_by,
  CAST(NULL AS DATETIME) AS date_voided,
  CAST(NULL AS VARCHAR) AS void_reason,
  UUID() AS uuid,
  s.obs_id AS source_obs_id
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.concept_id
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd
  ON cd.concept_datatype_id = c.datatype_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.concept_id
WHERE cc.name = 'Test'
  AND cd.name = 'Coded'
  -- Drug_order wins when an obs has a Test-class question AND a Drug-class
  -- answer (see clin__orders for the same exclusion). Prevents duplicate
  -- orders rows for the same obs_id.
  AND NOT EXISTS (
    SELECT 1
    FROM legacy_27_raw.concept dc
    JOIN legacy_27_raw.concept_class dcc ON dcc.concept_class_id = dc.class_id
    WHERE dc.concept_id = s.value_coded AND dcc.name = 'Drug'
  )
;
