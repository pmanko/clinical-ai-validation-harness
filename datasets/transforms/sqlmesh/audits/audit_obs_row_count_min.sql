AUDIT (
  name audit_obs_row_count_min,
  dialect mysql
);

-- clin__obs is the ~89.9% kept-obs mart. Floor is well below the
-- measured 428,013 to absorb minor drift across legacy data refreshes,
-- but far above zero so a silent materialization failure (like the
-- empty-snapshot incident that motivated this audit) fails loud.

SELECT
  'clin__obs' AS table_name,
  COUNT(*)   AS actual_rows,
  400000     AS required_min_rows
FROM refapp_28_demo.clin__obs
HAVING COUNT(*) < 400000
;
