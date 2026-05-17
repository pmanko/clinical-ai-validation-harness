MODEL (
  name refapp_28_demo.clin__drug_order,
  kind FULL,
  description 'P1 — obs whose value_coded is a Drug-class concept, promoted to drug_order with concept_id rebound via the bridge rule. Expected row count against the current corpus: ~43,412. Field mapping per data-model.md §R-promotion-rules.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid)),
    audit_drug_order_row_count_min
  )
);

SELECT
  -- order_id = source obs_id. Matches the parent clin__orders row.
  -- Deterministic, clinically traceable. No clinical relevance —
  -- clinical identity is in uuid. See research.md §R-load-pattern.
  s.obs_id AS order_id,
  s.person_id AS patient_id,
  s.encounter_id,
  COALESCE(ct.target_concept_id, s.value_coded) AS concept_id,
  s.obs_datetime AS start_date,
  CAST(NULL AS DATETIME) AS auto_expire_date,
  ep.provider_id AS orderer,
  'NEW' AS order_action,
  'ROUTINE' AS urgency,
  s.creator,
  s.date_created,
  0 AS voided,
  CAST(NULL AS INT) AS voided_by,
  CAST(NULL AS DATETIME) AS date_voided,
  CAST(NULL AS VARCHAR) AS void_reason,
  UUID() AS uuid,
  s.obs_id AS source_obs_id
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.value_coded
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.value_coded
LEFT JOIN (
  -- One provider per encounter (encounter_provider can have multiple roles per encounter).
  SELECT encounter_id, MIN(provider_id) AS provider_id
  FROM refapp_28_demo.stg_encounter_provider
  GROUP BY encounter_id
) ep ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Drug'
;
