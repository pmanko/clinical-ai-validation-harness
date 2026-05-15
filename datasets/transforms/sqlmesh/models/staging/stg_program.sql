MODEL (
  name refapp_28_demo.stg_program,
  kind FULL,
  description 'Staging copy of legacy_27_raw.program with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (program_id),
  audits (unique_values(columns := (program_id)))
);

SELECT
  src.program_id,
  COALESCE(ct_0.target_concept_id, src.concept_id) AS concept_id,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.retired,
  src.name,
  src.description,
  src.uuid,
  src.outcomes_concept_id
FROM legacy_27_raw.program src
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
;
