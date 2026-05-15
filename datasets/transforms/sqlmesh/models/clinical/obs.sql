MODEL (
  name refapp_28_demo.clin__obs,
  kind FULL,
  description 'Rebound obs that stays in obs — the ~89.9% of legacy obs not promoted to clin__drug_order, clin__conditions, clin__allergy, or clin__test_order. Source: refapp_28_demo.stg_obs with concept-FKs already rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (obs_id),
  audits (
    unique_values(columns := (obs_id))
  )
);

SELECT s.*
FROM refapp_28_demo.stg_obs s
WHERE NOT EXISTS (
  SELECT 1
  FROM legacy_27_raw.concept c
  JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
  WHERE c.concept_id = s.value_coded AND cc.name = 'Drug'
)
AND s.concept_id <> 6042
AND NOT (s.concept_id IN (6011, 6012, 1083) AND s.value_coded = 1065)
AND NOT EXISTS (
  SELECT 1
  FROM legacy_27_raw.concept c
  JOIN legacy_27_raw.concept_class    cc ON cc.concept_class_id = c.class_id
  JOIN legacy_27_raw.concept_datatype cd ON cd.concept_datatype_id = c.datatype_id
  WHERE c.concept_id = s.concept_id AND cc.name = 'Test' AND cd.name = 'Coded'
)
;
