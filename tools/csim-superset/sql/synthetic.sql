-- Entirely invented clinical flags and hospital codes; no source records.
CREATE SCHEMA IF NOT EXISTS v1;
CREATE TABLE IF NOT EXISTS v1."CSiM Hospitals and States" (
  hosp_code integer PRIMARY KEY, state text NOT NULL
);
CREATE TABLE IF NOT EXISTS v1."UTI Individual Current" (
  hosp_name integer, location integer, sign_symp integer, month integer,
  year integer, ucx_positive integer, urinalysis integer, tx___1 integer,
  duration integer, qi_asb_complete integer
);
CREATE TABLE IF NOT EXISTS v1."UTI Individual Historical"
  (LIKE v1."UTI Individual Current");
TRUNCATE v1."UTI Individual Current", v1."UTI Individual Historical",
  v1."CSiM Hospitals and States";
INSERT INTO v1."CSiM Hospitals and States" VALUES (91, 'TEST-A'), (92, 'TEST-B');
WITH scenarios(hospital, location, month_start, numerator, denominator, submissions) AS (
  VALUES
    (91, 3, DATE '2025-11-01', 2, 10, 10),
    (91, 3, DATE '2025-12-01', 9, 90, 90),
    (91, 3, DATE '2026-01-01', 1, 1, 1),
    -- Hospital 91 has no February submissions at either location.
    (91, 3, DATE '2026-03-01', 0, 9, 9),
    -- April has submissions but no qualifying denominator, not a zero rate.
    (91, 3, DATE '2026-04-01', 0, 0, 10),
    (91, 3, DATE '2026-05-01', 2, 8, 8),
    (91, 2, DATE '2026-01-01', 2, 4, 4),
    (91, 2, DATE '2026-03-01', 2, 6, 6),
    (92, 3, DATE '2025-11-01', 4, 20, 20),
    (92, 3, DATE '2025-12-01', 2, 20, 20),
    (92, 3, DATE '2026-01-01', 4, 10, 10),
    (92, 3, DATE '2026-02-01', 1, 10, 10),
    (92, 3, DATE '2026-03-01', 6, 20, 20),
    (92, 3, DATE '2026-04-01', 0, 20, 20),
    (92, 3, DATE '2026-05-01', 5, 20, 20),
    (92, 2, DATE '2026-01-01', 1, 4, 4)
)
INSERT INTO v1."UTI Individual Current"
SELECT hospital, location, CASE WHEN n <= numerator THEN 0 ELSE 1 END,
       EXTRACT(MONTH FROM month_start), EXTRACT(YEAR FROM month_start),
       CASE WHEN n <= denominator THEN 1 ELSE 0 END, 1, 0, 3 + n % 7, 2
FROM scenarios CROSS JOIN LATERAL generate_series(1, submissions) n;
