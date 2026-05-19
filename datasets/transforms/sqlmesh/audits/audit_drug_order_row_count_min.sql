AUDIT (
  name audit_drug_order_row_count_min,
  dialect mysql
);

-- P1 promotion mart. Measured 43,412; floor at 40,000.

SELECT
  'clin__drug_order' AS table_name,
  COUNT(*)           AS actual_rows,
  40000              AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 40000
;
