MODEL (
  name refapp_28_demo.stg_concept_name_carryforward,
  kind FULL,
  description 'concept_name rows for the carried-forward local program concepts (stg_concept_carryforward), so the names (GROUP 17, ANTIRETROVIRAL TREATMENT GROUP, etc.) are preserved in the target dictionary.',
  tags (policy_bucket:carry_forward),
  grain (concept_name_id),
  audits (unique_values(columns := (concept_name_id)))
);

SELECT
  src.concept_name_id,
  src.concept_id,
  src.name,
  src.locale,
  src.locale_preferred,
  src.creator,
  src.date_created,
  src.concept_name_type,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.uuid,
  src.date_changed,
  src.changed_by
FROM legacy_27_raw.concept_name src
WHERE src.concept_id IN (
  SELECT concept_id FROM legacy_27_raw.program
  UNION SELECT concept_id FROM legacy_27_raw.program_workflow
  UNION SELECT concept_id FROM legacy_27_raw.program_workflow_state
)
AND src.concept_id NOT IN (
  SELECT source_concept_id FROM refapp_28_demo.seed__concept_translation
)
;
