AUDIT (
  name audit_allergy_row_count_min,
  dialect mysql
);

-- P3 promotion mart. Measured 2 (selector predicate matches very few
-- legacy rows — drug-allergy boolean questions). Floor at 1 just to
-- catch zero — anything else would be lossy.

SELECT
  'clin__allergy' AS table_name,
  COUNT(*)        AS actual_rows,
  1               AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 1
;
