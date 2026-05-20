AUDIT (
  name audit_clinical_fk_integrity,
  dialect mysql
);

-- Every concept_id FK referenced by a promoted orders row MUST:
--   (a) exist in the target concept table, AND
--   (b) match the UUID recorded in seed__concept_translation.
-- Emits failing (source_table, concept_id, target_uuid, concept_uuid) on fail;
-- zero rows on pass.
--
-- This catches the legacy "794 → Hip pain" class of bug where a source integer
-- existed in the concept table but was the wrong concept (UUID mismatch).

SELECT
  CONCAT('orders (', CASE WHEN o.order_type_id = 2 THEN 'drug' ELSE 'test' END, ')') AS source_table,
  o.concept_id          AS promoted_concept_id,
  ct.target_uuid        AS expected_uuid,
  c.uuid                AS actual_uuid
FROM @this_model o
  JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = o.concept_id
LEFT JOIN openmrs.concept c ON c.concept_id = o.concept_id
WHERE c.concept_id IS NULL          -- concept does not exist
   OR c.uuid <> ct.target_uuid      -- concept exists but UUID does not match
;
