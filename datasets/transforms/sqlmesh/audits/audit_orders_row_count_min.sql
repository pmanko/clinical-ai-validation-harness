AUDIT (
  name audit_orders_row_count_min,
  dialect mysql
);

-- clin__orders is the parent of drug_order + test_order. Floor = ~44,000
-- (measured 43,412 drug_order + 1,120 test_order = 44,532). Drops below
-- this catch a silent failure in either of the two UNION branches.

SELECT
  'clin__orders'                                  AS table_name,
  COUNT(*)                                        AS actual_rows,
  44000                                           AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 44000
;
