MODEL (
  name refapp_28_demo.stg_demographics_reconcile,
  kind FULL,
  description 'Demographic reconciliation. The de-identification scrambled birthdate AND sex independently of clinical content (verified: weight is 99.6% self-consistent per patient, but 24% of pregnant patients are labelled male and the age bands are full of adult weights). Clinical content is the authoritative signal. This model re-derives age from WEIGHT (sex-neutral WHO weight-for-age) and corrects sex from pregnancy, touching ONLY patients whose recorded DOB/sex contradicts the clinical evidence. Deterministic (no random) → byte-identical re-runs (SC-004). Feeds stg_person via COALESCE. Not loaded directly.',
  tags (policy_bucket:seed_augment),
  grain (person_id)
);

-- Reference date = the date-transplant target (config end_date, 2026-06-01). Ages
-- are expressed relative to it. Anchored on already-shifted stg_obs dates, so
-- output birthdates are in the transplanted timeline.
--
-- Authoritative evidence per patient:
--   max_wt      : MAX(Weight kg, concept 4168) — robust (weights are 99.6% self-
--                 consistent; using MAX avoids a low-outlier reading aging a real
--                 adult down, the v1 earliest-weight bug).
--   is_pregnant : a POSITIVE pregnancy signal (weeks-pregnant 37155 / ARV-in-preg
--                 52123 / gravida 11400 / parity 55898, or pregnancy-status=Yes
--                 3373=771). Unambiguous adult-female. (3373 alone is asked of all.)
--   has_peds    : pediatric-specific staging (45111/46439/45406/46550) — used ONLY
--                 as a no-weight child fallback.
WITH wt AS (
  SELECT person_id, MAX(value_numeric) AS max_wt, MIN(obs_datetime) AS wt_date
  FROM refapp_28_demo.stg_obs
  WHERE concept_id = 4168 AND value_numeric > 0
  GROUP BY person_id
),
preg AS (
  SELECT DISTINCT person_id FROM refapp_28_demo.stg_obs
  WHERE concept_id IN (37155, 52123, 11400, 55898)
     OR (concept_id = 3373 AND value_coded = 771)
),
peds AS (
  SELECT DISTINCT person_id FROM refapp_28_demo.stg_obs
  WHERE concept_id IN (45111, 46439, 45406, 46550)
),
base AS (
  SELECT
    pr.person_id,
    TIMESTAMPDIFF(YEAR, @shift_date(pr.birthdate), DATE('2026-06-01')) AS dob_age,
    wt.max_wt,
    wt.wt_date,
    (preg.person_id IS NOT NULL) AS is_pregnant,
    (peds.person_id IS NOT NULL) AS has_peds
  FROM legacy_27_raw.person pr
  LEFT JOIN wt   ON wt.person_id   = pr.person_id
  LEFT JOIN preg ON preg.person_id = pr.person_id
  LEFT JOIN peds ON peds.person_id = pr.person_id
),
-- Empirical adult age pool = patients already consistent (adult weight + adult DOB).
-- Re-aged adults draw a plausible age from this real distribution, deterministically.
adult_pool AS (
  SELECT dob_age AS age, ROW_NUMBER() OVER (ORDER BY dob_age, person_id) AS rn
  FROM base WHERE max_wt >= 45 AND dob_age >= 18
),
pool_n AS (SELECT COUNT(*) AS n FROM base WHERE max_wt >= 45 AND dob_age >= 18)
SELECT
  b.person_id,
  CASE
    -- (1) child weight but adult DOB -> lower to sex-neutral WHO weight-for-age
    WHEN b.max_wt < 25 AND b.dob_age >= 15 THEN
      CAST(DATE_SUB(b.wt_date, INTERVAL (
        CASE
          WHEN b.max_wt < 4  THEN 1   WHEN b.max_wt < 5  THEN 2   WHEN b.max_wt < 6  THEN 3
          WHEN b.max_wt < 7  THEN 5   WHEN b.max_wt < 8  THEN 7   WHEN b.max_wt < 9  THEN 9
          WHEN b.max_wt < 10 THEN 12  WHEN b.max_wt < 11 THEN 15  WHEN b.max_wt < 12 THEN 18
          WHEN b.max_wt < 13 THEN 24  WHEN b.max_wt < 14 THEN 30  WHEN b.max_wt < 15 THEN 36
          WHEN b.max_wt < 17 THEN 48  WHEN b.max_wt < 19 THEN 60  WHEN b.max_wt < 21 THEN 72
          WHEN b.max_wt < 23 THEN 84  ELSE 96
        END) MONTH) AS DATE)
    -- (2) adult weight or pregnant but child DOB -> raise to a sampled real adult age
    WHEN (b.max_wt >= 45 AND b.dob_age < 13) OR (b.is_pregnant AND b.dob_age < 15) THEN
      CAST(DATE_SUB(DATE('2026-06-01'), INTERVAL ap.age YEAR) AS DATE)
    -- (3) no weight + pediatric staging but adult DOB -> child default (~5y)
    WHEN b.max_wt IS NULL AND b.has_peds AND b.dob_age >= 15 THEN
      CAST(DATE_SUB(DATE('2026-06-01'), INTERVAL 5 YEAR) AS DATE)
    ELSE NULL
  END AS corrected_birthdate,
  CASE WHEN b.is_pregnant THEN 'F' ELSE NULL END AS corrected_gender
FROM base b
CROSS JOIN pool_n
LEFT JOIN adult_pool ap
  ON ap.rn = (CONV(SUBSTR(SHA1(CONCAT('feature-002:age:', CAST(b.person_id AS CHAR))), 1, 8), 16, 10) % pool_n.n) + 1
WHERE (b.max_wt < 25 AND b.dob_age >= 15)
   OR ((b.max_wt >= 45 AND b.dob_age < 13) OR (b.is_pregnant AND b.dob_age < 15))
   OR (b.max_wt IS NULL AND b.has_peds AND b.dob_age >= 15)
   OR b.is_pregnant
;
