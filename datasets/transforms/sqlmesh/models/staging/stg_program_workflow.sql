MODEL (
  name refapp_28_demo.stg_program_workflow,
  kind FULL,
  description 'All legacy program workflows, concept rebound to CIEL where a mapping exists (clinical TREATMENT STATUS), else keeping the legacy concept_id which stg_concept_carryforward loads into the dictionary (the AMPATH cohort TREATMENT GROUP workflows). No workflow is dropped.',
  tags (policy_bucket:passthrough),
  grain (program_workflow_id),
  audits (unique_values(columns := (program_workflow_id)))
);

SELECT
  src.program_workflow_id,
  src.program_id,
  COALESCE(ct_0.target_concept_id, src.concept_id) AS concept_id,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.retired,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.uuid
FROM legacy_27_raw.program_workflow src
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
;
