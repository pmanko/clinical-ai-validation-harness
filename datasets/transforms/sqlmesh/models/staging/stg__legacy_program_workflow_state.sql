MODEL (
  name refapp_28_demo.staging.stg__legacy_program_workflow_state,
  kind FULL,
  description 'Staging copy of legacy_27_raw.program_workflow_state with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (program_workflow_state_id),
  audits (unique_values(columns := (program_workflow_state_id)))
);

SELECT
  src.program_workflow_state_id,
  src.program_workflow_id,
  COALESCE(ct_0.target_concept_id, src.concept_id) AS concept_id,
  src.initial,
  src.terminal,
  src.creator,
  src.date_created,
  src.retired,
  src.changed_by,
  src.date_changed,
  src.uuid
FROM legacy_27_raw.program_workflow_state src
  LEFT JOIN refapp_28_demo.seeds.concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
;
