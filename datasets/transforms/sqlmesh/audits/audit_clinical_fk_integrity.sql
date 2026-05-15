AUDIT (
  name audit_clinical_fk_integrity,
  dialect mysql
);

-- Every concept_id referenced by a promoted clinical row MUST resolve to
-- an actual concept in the seeded CIEL dictionary (the live openmrs DB).
-- Emits failing (source_table, concept_id) pairs on fail; zero rows on pass.

WITH promoted_concept_refs AS (
  SELECT 'drug_order' AS source_table, concept_id FROM refapp_28_demo.clin__drug_order
  UNION ALL
  SELECT 'conditions',                  condition_coded FROM refapp_28_demo.clin__conditions
  UNION ALL
  SELECT 'test_order',                  concept_id FROM refapp_28_demo.clin__test_order
)
SELECT
  pcr.source_table,
  pcr.concept_id AS missing_concept_id
FROM promoted_concept_refs pcr
LEFT JOIN openmrs.concept c
  ON c.concept_id = pcr.concept_id
WHERE c.concept_id IS NULL
;
