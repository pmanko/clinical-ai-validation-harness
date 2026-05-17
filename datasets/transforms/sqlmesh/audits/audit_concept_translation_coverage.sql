AUDIT (
  name audit_concept_translation_coverage,
  dialect mysql
);

-- Every distinct legacy concept_id that ≥1 obs row references MUST have
-- an entry in concept_translation. Emit failing concept_ids (zero rows
-- on pass). This is the FR-008(a) determinism gate.

WITH obs_concepts AS (
  SELECT DISTINCT concept_id FROM legacy_27_raw.obs WHERE concept_id IS NOT NULL
  UNION
  SELECT DISTINCT value_coded FROM legacy_27_raw.obs WHERE value_coded IS NOT NULL
)
SELECT
  oc.concept_id AS missing_concept_id
FROM obs_concepts oc
LEFT JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = oc.concept_id
WHERE ct.source_concept_id IS NULL
;
