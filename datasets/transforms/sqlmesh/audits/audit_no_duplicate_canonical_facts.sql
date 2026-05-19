AUDIT (
  name audit_no_duplicate_canonical_facts,
  dialect mysql
);

-- Canonical clinical facts promoted to typed tables (P1 drug_order, P2 conditions,
-- P3 allergy) MUST NOT also appear as residual obs rows.
-- The only exception is P4 test-order result obs which are linked via obs.order_id
-- and represent a semantically distinct result, not a copy of the order fact.
--
-- Emits (promotion_table, source_obs_id) for any promoted obs_id that still
-- appears in this clin__obs evaluation table; zero rows on pass. Re-deriving
-- promoted source IDs keeps the audit valid during a clean SQLMesh build before
-- the sibling promoted-table virtual views are swapped in.

WITH promoted_sources AS (
  SELECT 'drug_order' AS promotion_table, s.obs_id AS source_obs_id
  FROM refapp_28_demo.stg_obs s
  JOIN legacy_27_raw.concept c
    ON c.concept_id = s.source_value_coded
  JOIN legacy_27_raw.concept_class cc
    ON cc.concept_class_id = c.class_id
  WHERE cc.name = 'Drug'

  UNION ALL

  SELECT 'conditions', s.obs_id
  FROM refapp_28_demo.stg_obs s
  WHERE s.source_concept_id = 6042
    AND s.source_value_coded IS NOT NULL

  UNION ALL

  SELECT 'allergy', s.obs_id
  FROM refapp_28_demo.stg_obs s
  WHERE s.source_concept_id IN (6011, 6012, 1083)
    AND s.source_value_coded = 1065
)
SELECT ps.promotion_table, ps.source_obs_id
FROM promoted_sources ps
JOIN @this_model o
  ON o.obs_id = ps.source_obs_id
;
