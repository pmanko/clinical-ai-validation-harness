AUDIT (
  name audit_parent_child_integrity,
  dialect mysql
);

-- Every child row in clin__drug_order and clin__test_order MUST have a
-- matching parent row in clin__orders with the same order_id.
-- Emits orphaned (child_table, order_id) pairs on fail; zero rows on pass.

SELECT 'drug_order' AS child_table, d.order_id
FROM refapp_28_demo.clin__drug_order d
WHERE NOT EXISTS (
  SELECT 1 FROM refapp_28_demo.clin__orders o WHERE o.order_id = d.order_id
)

UNION ALL

SELECT 'test_order', t.order_id
FROM refapp_28_demo.clin__test_order t
WHERE NOT EXISTS (
  SELECT 1 FROM refapp_28_demo.clin__orders o WHERE o.order_id = t.order_id
)
;
