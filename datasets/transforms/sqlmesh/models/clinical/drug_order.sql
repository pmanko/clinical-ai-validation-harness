MODEL (
  name refapp_28_demo.clinical.drug_order,
  kind FULL,
  description 'P1 — obs whose value_coded is a Drug-class concept, promoted to drug_order with concept_id rebound via the bridge rule. Expected row count against the current corpus: ~43,412. Field mapping per data-model.md §R-promotion-rules.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid))
  )
);

SELECT
  -- order_id is auto-generated in the loadback; emit a row per obs.
  NULL AS order_id,
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
FROM refapp_28_demo.staging.stg__legacy_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.value_coded
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
LEFT JOIN refapp_28_demo.seeds.concept_translation ct
  ON ct.source_concept_id = s.value_coded
LEFT JOIN refapp_28_demo.staging.stg__legacy_encounter_provider ep
  ON ep.encounter_id = s.encounter_id
WHERE cc.name = 'Drug'
;
