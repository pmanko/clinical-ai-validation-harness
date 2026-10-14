-- April 2026 CSiM virtual-dataset SQL, preserved as the reproduction baseline.
-- Source: https://docs.google.com/document/d/1wBSzLHmfFndduEL8sTDivOvd4uJK43Ews-Ptcx7AZiU/edit
CREATE OR REPLACE VIEW public.csim_baseline AS
WITH raw_data AS (
    SELECT
        hosp_name, location, sign_symp, month, year,
        ucx_positive, urinalysis, tx___1, duration
    FROM "v1"."UTI Individual Current"
    WHERE hosp_name IS NOT NULL
      AND qi_asb_complete = 2
      AND month IS NOT NULL
      AND year IS NOT NULL

    UNION ALL

    SELECT
        hosp_name, location, sign_symp, month, year,
        ucx_positive, urinalysis, tx___1, duration
    FROM "v1"."UTI Individual Historical"
    WHERE hosp_name IS NOT NULL
      AND month IS NOT NULL
      AND year IS NOT NULL
),

hospital_agg AS (
    SELECT
        i.hosp_name AS hosp_num,
        LPAD(i.hosp_name::TEXT, 2, '0') AS hosp_code,
        TRIM(h.state) AS state,
        CASE i.location
            WHEN 1 THEN 'Ambulatory care clinic'
            WHEN 2 THEN 'Emergency Department'
            WHEN 3 THEN 'Inpatient'
            WHEN 4 THEN 'Rehab or long-term care'
            WHEN 5 THEN 'Urgent or quick care'
            WHEN 6 THEN 'Other'
        END AS location_name,

        i.location AS location_code,
        TO_DATE(i.year::TEXT || '-' || LPAD(i.month::TEXT, 2, '0') || '-01', 'YYYY-MM-DD') AS month_date,
        COUNT(*) AS ucsub,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS txpos,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS asbtreated,
        SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS aspn_treated,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 THEN 1 ELSE 0 END) AS asbcase,
        SUM(CASE WHEN i.urinalysis = 1 THEN 1 ELSE 0 END) AS pos_ua,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN i.duration ELSE 0 END) AS dur_sum,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN 1 ELSE 0 END) AS dur_count,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration <= 3 THEN 1 ELSE 0 END) AS dur_cat_1,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 3 AND i.duration <= 5 THEN 1 ELSE 0 END) AS dur_cat_2,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 5 AND i.duration <= 7 THEN 1 ELSE 0 END) AS dur_cat_3,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 7 THEN 1 ELSE 0 END) AS dur_cat_4,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END), 0) AS inappdx,
        (SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) +
         SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END))::FLOAT /
            NULLIF(SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END) +
                   SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END), 0) AS inappdx_aspn,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS prev,
        SUM(CASE WHEN i.tx___1 = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS txrate,
        SUM(CASE WHEN i.urinalysis = 1 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS pos_ua_rate,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN i.duration ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN 1 ELSE 0 END), 0) AS medabxdur
    FROM raw_data i
    LEFT JOIN "v1"."CSiM Hospitals and States" h
        ON i.hosp_name = h.hosp_code
    WHERE h.hosp_code IS NOT NULL
    GROUP BY i.hosp_name, TRIM(h.state), i.location, i.month, i.year
),

-- All locations combined per hospital per month
hospital_allloc AS (
    SELECT
        i.hosp_name AS hosp_num,
        LPAD(i.hosp_name::TEXT, 2, '0') AS hosp_code,
        TRIM(h.state) AS state,
        'All locations' AS location_name,
        0 AS location_code,
        TO_DATE(i.year::TEXT || '-' || LPAD(i.month::TEXT, 2, '0') || '-01', 'YYYY-MM-DD') AS month_date,
        COUNT(*) AS ucsub,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS txpos,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS asbtreated,
        SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) AS aspn_treated,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 THEN 1 ELSE 0 END) AS asbcase,
        SUM(CASE WHEN i.urinalysis = 1 THEN 1 ELSE 0 END) AS pos_ua,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN i.duration ELSE 0 END) AS dur_sum,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN 1 ELSE 0 END) AS dur_count,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration <= 3 THEN 1 ELSE 0 END) AS dur_cat_1,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 3 AND i.duration <= 5 THEN 1 ELSE 0 END) AS dur_cat_2,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 5 AND i.duration <= 7 THEN 1 ELSE 0 END) AS dur_cat_3,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL AND i.duration > 7 THEN 1 ELSE 0 END) AS dur_cat_4,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END), 0) AS inappdx,
        (SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END) +
         SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END))::FLOAT /
            NULLIF(SUM(CASE WHEN i.ucx_positive = 1 AND i.tx___1 = 0 THEN 1 ELSE 0 END) +
                   SUM(CASE WHEN i.ucx_positive = 0 AND i.urinalysis = 1 AND i.sign_symp = 0 AND i.tx___1 = 0 THEN 1 ELSE 0 END), 0) AS inappdx_aspn,
        SUM(CASE WHEN i.ucx_positive = 1 AND i.sign_symp = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS prev,
        SUM(CASE WHEN i.tx___1 = 0 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS txrate,
        SUM(CASE WHEN i.urinalysis = 1 THEN 1 ELSE 0 END)::FLOAT /
            NULLIF(COUNT(*), 0) AS pos_ua_rate,
        SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN i.duration ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN i.tx___1 = 0 AND i.duration IS NOT NULL THEN 1 ELSE 0 END), 0) AS medabxdur
    FROM raw_data i
    LEFT JOIN "v1"."CSiM Hospitals and States" h
        ON i.hosp_name = h.hosp_code
    WHERE h.hosp_code IS NOT NULL
    GROUP BY i.hosp_name, TRIM(h.state), i.month, i.year
    -- Note: no location in GROUP BY
),

combined AS (
    SELECT * FROM hospital_agg
    UNION ALL
    SELECT * FROM hospital_allloc
)

-- Hospital rows (location-specific + all locations)
SELECT
    hosp_num, hosp_code, state,
    location_name, location_code, month_date,
    ucsub, txpos, asbtreated, aspn_treated, asbcase,
    pos_ua, dur_sum, dur_count,
    dur_cat_1, dur_cat_2, dur_cat_3, dur_cat_4,
    inappdx, inappdx_aspn, prev, txrate, pos_ua_rate, medabxdur
FROM combined

UNION ALL

-- State rows (ucsub-weighted)
SELECT
    NULL AS hosp_num,
    state AS hosp_code,
    state,
    location_name, location_code, month_date,
    SUM(ucsub), SUM(txpos), SUM(asbtreated), SUM(aspn_treated), SUM(asbcase),
    SUM(pos_ua), SUM(dur_sum), SUM(dur_count),
    SUM(dur_cat_1), SUM(dur_cat_2), SUM(dur_cat_3), SUM(dur_cat_4),
    SUM(inappdx * ucsub) / NULLIF(SUM(CASE WHEN inappdx IS NOT NULL THEN ucsub ELSE 0 END), 0),
    SUM(inappdx_aspn * ucsub) / NULLIF(SUM(CASE WHEN inappdx_aspn IS NOT NULL THEN ucsub ELSE 0 END), 0),
    SUM(prev * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(txrate * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(pos_ua_rate * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(CASE WHEN medabxdur IS NOT NULL THEN medabxdur * ucsub ELSE 0 END) /
        NULLIF(SUM(CASE WHEN medabxdur IS NOT NULL THEN ucsub ELSE 0 END), 0)
FROM combined
GROUP BY state, location_name, location_code, month_date

UNION ALL

-- Cohort rows (ucsub-weighted)
SELECT
    NULL AS hosp_num,
    'Cohort' AS hosp_code,
    'ALL' AS state,
    location_name, location_code, month_date,
    SUM(ucsub), SUM(txpos), SUM(asbtreated), SUM(aspn_treated), SUM(asbcase),
    SUM(pos_ua), SUM(dur_sum), SUM(dur_count),
    SUM(dur_cat_1), SUM(dur_cat_2), SUM(dur_cat_3), SUM(dur_cat_4),
    SUM(inappdx * ucsub) / NULLIF(SUM(CASE WHEN inappdx IS NOT NULL THEN ucsub ELSE 0 END), 0),
    SUM(inappdx_aspn * ucsub) / NULLIF(SUM(CASE WHEN inappdx_aspn IS NOT NULL THEN ucsub ELSE 0 END), 0),
    SUM(prev * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(txrate * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(pos_ua_rate * ucsub) / NULLIF(SUM(ucsub), 0),
    SUM(CASE WHEN medabxdur IS NOT NULL THEN medabxdur * ucsub ELSE 0 END) /
        NULLIF(SUM(CASE WHEN medabxdur IS NOT NULL THEN ucsub ELSE 0 END), 0)
FROM combined
GROUP BY location_name, location_code, month_date

ORDER BY month_date, hosp_code, location_code;
