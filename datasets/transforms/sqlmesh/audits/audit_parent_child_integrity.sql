AUDIT (
  name audit_parent_child_integrity,
  dialect mysql
);

-- Every source row promoted to a drug_order or test_order child MUST have a
-- matching parent row in this clin__orders evaluation table with the same
-- order_id and order_type_id. Re-deriving expected children avoids referencing
-- sibling virtual views before a clean SQLMesh plan has promoted them.
-- Emits missing/mistyped (child_table, order_id) pairs on fail; zero rows on pass.

WITH expected_children AS (
  SELECT 'drug_order' AS child_table, s.obs_id AS order_id, 2 AS order_type_id
  FROM refapp_28_demo.stg_obs s
  JOIN legacy_27_raw.concept c
    ON c.concept_id = s.source_value_coded
  JOIN legacy_27_raw.concept_class cc
    ON cc.concept_class_id = c.class_id
  WHERE cc.name = 'Drug'

  UNION ALL

  SELECT 'test_order', s.obs_id, 3
  FROM refapp_28_demo.stg_obs s
  JOIN legacy_27_raw.concept c
    ON c.concept_id = s.source_concept_id
  JOIN legacy_27_raw.concept_class cc
    ON cc.concept_class_id = c.class_id
  JOIN legacy_27_raw.concept_datatype cd
    ON cd.concept_datatype_id = c.datatype_id
  WHERE cc.name = 'Test'
    AND cd.name = 'Coded'
    AND NOT EXISTS (
      SELECT 1
      FROM legacy_27_raw.concept dc
      JOIN legacy_27_raw.concept_class dcc
        ON dcc.concept_class_id = dc.class_id
      WHERE dc.concept_id = s.source_value_coded AND dcc.name = 'Drug'
    )
)
SELECT ec.child_table, ec.order_id
FROM expected_children ec
LEFT JOIN @this_model o
  ON o.order_id = ec.order_id
 AND o.order_type_id = ec.order_type_id
WHERE o.order_id IS NULL
;
