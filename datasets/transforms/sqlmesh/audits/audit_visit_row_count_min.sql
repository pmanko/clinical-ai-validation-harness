AUDIT (
  name audit_visit_row_count_min,
  dialect mysql
);

-- Reconstructed visits: one per (patient, day). Measured ~14,248 (vs 14,316
-- encounters). Floor at 14,000 to catch a grouping/source regression that would
-- silently drop visits.

SELECT
  'clin__visit' AS table_name,
  COUNT(*)      AS actual_rows,
  14000         AS required_min_rows
FROM @this_model
HAVING COUNT(*) < 14000
;
