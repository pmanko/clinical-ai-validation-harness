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
-- appears in clin__obs; zero rows on pass.

SELECT 'drug_order' AS promotion_table, d.source_obs_id
FROM refapp_28_demo.clin__drug_order d
WHERE EXISTS (
  SELECT 1 FROM refapp_28_demo.clin__obs o
  WHERE o.obs_id = d.source_obs_id
)

UNION ALL

SELECT 'conditions', c.source_obs_id
FROM refapp_28_demo.clin__conditions c
WHERE EXISTS (
  SELECT 1 FROM refapp_28_demo.clin__obs o
  WHERE o.obs_id = c.source_obs_id
)

UNION ALL

SELECT 'allergy', a.source_obs_id
FROM refapp_28_demo.clin__allergy a
WHERE EXISTS (
  SELECT 1 FROM refapp_28_demo.clin__obs o
  WHERE o.obs_id = a.source_obs_id
)
;
