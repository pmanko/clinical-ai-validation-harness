AUDIT (
  name audit_clinical_fk_integrity,
  dialect mysql
);

-- Every concept_id FK referenced by a promoted clinical row MUST:
--   (a) exist in the target concept table, AND
--   (b) match the UUID recorded in seed__concept_translation.
-- Emits failing (source_table, concept_id, target_uuid, concept_uuid) on fail;
-- zero rows on pass.
--
-- This catches the legacy "794 → Hip pain" class of bug where a source integer
-- existed in the concept table but was the wrong concept (UUID mismatch).

WITH promoted_concept_refs AS (
  SELECT 'orders (drug)'    AS source_table, o.concept_id, ct.target_uuid
  FROM refapp_28_demo.clin__orders o
  JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = o.concept_id
  WHERE o.order_type_id = 2

  UNION ALL

  SELECT 'orders (test)',               o.concept_id, ct.target_uuid
  FROM refapp_28_demo.clin__orders o
  JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = o.concept_id
  WHERE o.order_type_id = 3

  UNION ALL

  SELECT 'conditions',                  condition_coded, ct.target_uuid
  FROM refapp_28_demo.clin__conditions cond
  JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = cond.condition_coded
)
SELECT
  pcr.source_table,
  pcr.concept_id          AS promoted_concept_id,
  pcr.target_uuid         AS expected_uuid,
  c.uuid                  AS actual_uuid
FROM promoted_concept_refs pcr
LEFT JOIN openmrs.concept c ON c.concept_id = pcr.concept_id
WHERE c.concept_id IS NULL          -- concept does not exist
   OR c.uuid <> pcr.target_uuid     -- concept exists but UUID does not match
;
