MODEL (
  name refapp_28_demo.stg_concept_carryforward,
  kind FULL,
  description 'Local (site-specific) legacy concepts referenced by the program model that have no CIEL equivalent — chiefly the AMPATH treatment-cohort GROUP labels (GROUP 1..42, GROUP PEDI/TB/PMTCT/PRISON), the two cohort workflow concepts, and a few clinical state variants. Carried into the target dictionary as local concepts so every program/workflow/state FK resolves and NO enrollment data is dropped. Legacy concept_id does not collide with any CIEL concept_id (verified); concept_class rebound legacy->target (State 18->20, Question 7->7).',
  tags (policy_bucket:carry_forward),
  grain (concept_id),
  audits (unique_values(columns := (concept_id)))
);

SELECT
  src.concept_id,
  src.retired,
  src.short_name,
  src.description,
  src.form_text,
  src.datatype_id,
  CASE WHEN src.class_id = 18 THEN 20 ELSE src.class_id END AS class_id,
  src.is_set,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.version,
  src.changed_by,
  @shift_date(src.date_changed) AS date_changed,
  src.retired_by,
  @shift_date(src.date_retired) AS date_retired,
  src.retire_reason,
  src.uuid
FROM legacy_27_raw.concept src
WHERE src.concept_id IN (
  SELECT concept_id FROM legacy_27_raw.program
  UNION SELECT concept_id FROM legacy_27_raw.program_workflow
  UNION SELECT concept_id FROM legacy_27_raw.program_workflow_state
)
AND src.concept_id NOT IN (
  SELECT source_concept_id FROM refapp_28_demo.seed__concept_translation
)
;
