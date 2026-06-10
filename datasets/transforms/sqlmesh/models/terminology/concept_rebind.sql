MODEL (
  name refapp_28_demo.terminology__concept_rebind,
  kind VIEW,
  description 'Concept-rebind layer per contracts/sqlmesh_project.profile.md §Project layout. Exposes legacy obs rows with concept_id + value_coded rebound via the bridge rule (see research.md §R-bridge-rule). Source: refapp_28_demo.stg_obs. Joins refapp_28_demo.seed__concept_translation (the materialized bridge rule, ~2,528 distinct legacy concept_ids → CIEL UUIDs). Emits one row per legacy obs with rebound_concept_id and rebound_value_coded columns alongside the original ids, so downstream clinical models can choose which to use.',
  tags (policy_bucket:remap),
  grain (obs_id)
);

SELECT
  s.obs_id,
  s.person_id,
  s.source_concept_id,
  s.concept_id                       AS rebound_concept_id,
  s.source_value_coded,
  s.value_coded                      AS rebound_value_coded,
  ct_q.equivalence                   AS question_equivalence,
  ct_v.equivalence                   AS value_equivalence,
  s.encounter_id,
  s.obs_datetime AS obs_datetime,            -- already shifted in stg_obs; pass through
  s.value_numeric,
  s.value_text,
  s.value_datetime AS value_datetime,        -- already shifted in stg_obs; pass through
  s.value_drug,
  s.uuid                             AS source_uuid,
  s.voided
FROM refapp_28_demo.stg_obs s
LEFT JOIN refapp_28_demo.seed__concept_translation ct_q
  ON ct_q.source_concept_id = s.source_concept_id
LEFT JOIN refapp_28_demo.seed__concept_translation ct_v
  ON ct_v.source_concept_id = s.source_value_coded
WHERE s.voided = 0
;
