AUDIT (
  name audit_test_order_row_count_min,
  dialect mysql
);

-- P4 promotion mart. Measured 1,120; floor at 1,000.

SELECT
  'clin__test_order' AS table_name,
  COUNT(*)           AS actual_rows,
  1000               AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 1000
;
