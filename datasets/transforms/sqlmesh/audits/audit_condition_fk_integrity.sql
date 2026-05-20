AUDIT (
  name audit_condition_fk_integrity,
  dialect mysql
);

-- Every condition_coded FK referenced by a promoted condition row MUST:
--   (a) exist in the target concept table, AND
--   (b) match the UUID recorded in seed__concept_translation.
-- Emits failing (source_table, concept_id, target_uuid, concept_uuid) on fail;
-- zero rows on pass.

SELECT
  'conditions'          AS source_table,
  cond.condition_coded  AS promoted_concept_id,
  ct.target_uuid        AS expected_uuid,
  c.uuid                AS actual_uuid
FROM @this_model cond
JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.target_concept_id = cond.condition_coded
LEFT JOIN openmrs.concept c
  ON c.concept_id = cond.condition_coded
WHERE c.concept_id IS NULL
   OR c.uuid <> ct.target_uuid
;
