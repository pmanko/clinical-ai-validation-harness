AUDIT (
  name audit_conditions_row_count_min,
  dialect mysql
);

-- P2 promotion mart. Measured 4,451; floor at 4,000.

SELECT
  'clin__conditions' AS table_name,
  COUNT(*)           AS actual_rows,
  4000               AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 4000
;
