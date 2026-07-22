-- HIV analytics layer over the fhir-data-pipes DEFAULT flat tables.
--
-- Layering rule (deliberate): the ingestion layer uses the upstream default
-- ViewDefinitions essentially verbatim (lossless, one row per resource per
-- coding via forEachOrNull), and ALL curation happens here in SQL, where a
-- mistake costs a CREATE OR REPLACE VIEW instead of a full FHIR re-fetch.
-- Do not add hand-written ingestion projections; extend these views instead.
--
-- Base tables (grain = resource x coding cross products):
--   public.observation_flat        id x code.coding x value.coding
--   public.patient_flat            id x generalPractitioner x name(x given) x identifier
--   public.encounter_flat          id x type.coding x participant x location
--   public.condition_flat          id x code/category/clinicalStatus/verificationStatus codings
--   public.medication_request_flat id x medication codings x statusReason codings
--   public.medication_flat         id x code.coding

BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.pipeline_run_v1 (
    pipeline_run_id text PRIMARY KEY,
    contract_version text NOT NULL DEFAULT 'catalyst.analytics.pipeline-run.v1'
        CHECK (contract_version = 'catalyst.analytics.pipeline-run.v1'),
    completion_state text NOT NULL
        CHECK (completion_state IN ('running', 'succeeded', 'failed')),
    source_watermark timestamptz,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    data_pipes_commit text NOT NULL,
    resource_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    CHECK (
        (completion_state = 'running' AND completed_at IS NULL)
        OR
        (completion_state IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    ),
    CHECK (
        completion_state <> 'succeeded'
        OR source_watermark IS NOT NULL
    )
);

COMMENT ON TABLE analytics.pipeline_run_v1 IS
    'One row per Data Pipes run; the authoritative Catalyst freshness/run contract.';

CREATE OR REPLACE VIEW analytics.pipeline_freshness_v1 AS
SELECT
    pipeline_run_id,
    contract_version,
    completion_state,
    source_watermark,
    started_at,
    completed_at,
    observed_at,
    data_pipes_commit,
    resource_counts,
    error_message,
    CASE
        WHEN source_watermark IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (observed_at - source_watermark))::bigint
    END AS observed_lag_seconds
FROM analytics.pipeline_run_v1;

-- Drop the previous generation (curated ingestion projections and the fact
-- views built on them); superseded by the default-table layering above.
DROP VIEW IF EXISTS analytics.hiv_observation_fact_v1;
DROP VIEW IF EXISTS analytics.hiv_visit_fact_v1;
DROP VIEW IF EXISTS analytics.hiv_patient_dim_v1;
DROP VIEW IF EXISTS analytics.hiv_concept_mapping_v1;
DROP TABLE IF EXISTS public.observation_flat_v1;
DROP TABLE IF EXISTS public.patient_flat_v1;
DROP TABLE IF EXISTS public.encounter_flat_v1;
DROP TABLE IF EXISTS public.medication_request_flat_v1;
DROP TABLE IF EXISTS public.condition_flat_v1;

-- One row per patient (collapses the name/identifier/practitioner cross
-- product; gender and birth_date are constant per resource id).
CREATE VIEW analytics.hiv_patient_dim_v1 AS
SELECT DISTINCT
    id AS patient_id,
    gender,
    birth_date
FROM public.patient_flat;

COMMENT ON VIEW analytics.hiv_patient_dim_v1 IS
    'Demo-only patient dimension at exactly one row per FHIR Patient.';

-- Known demo-data artifact: a handful of OpenMRS observations carry
-- clearly-wrong effective dates (as early as 1919, as late as 5025). The fact
-- views exclude effective/period dates outside 2020-01-01..2035-01-01 so
-- ordinary date-range questions are not skewed by a few garbage rows.
CREATE VIEW analytics.hiv_observation_fact_v1 AS
WITH per_observation AS (
    SELECT
        o.id AS observation_id,
        MAX(o.patient_id) AS patient_id,
        MAX(o.encounter_id) AS encounter_id,
        MAX(o.status) AS obs_status,
        MAX(o.obs_date) AS observed_at,
        COALESCE(
            MAX(o.code_display) FILTER (WHERE o.code_sys IS NULL),
            MAX(o.code_display)
        ) AS concept_name,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'https://cielterminology.org'
        ) AS concept_code_ciel,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'http://snomed.info/sct/'
        ) AS concept_code_snomed,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'http://fhir.org/guides/who/anc-cds/CodeSystem/anc-custom-codes'
        ) AS concept_code_who_anc,
        MAX(o.val_quantity) AS value_numeric,
        MAX(o.val_quantity_unit) AS value_unit,
        COALESCE(
            MAX(o.value_display) FILTER (WHERE o.value_sys IS NULL),
            MAX(o.value_display)
        ) AS value_coded_name,
        MAX(o.value_code) FILTER (
            WHERE o.value_sys = 'https://cielterminology.org'
        ) AS value_coded_code_ciel,
        MAX(o.value_code) FILTER (
            WHERE o.value_sys = 'http://snomed.info/sct/'
        ) AS value_coded_code_snomed,
        MAX(o.val_string) AS value_text,
        bool_or(o.val_boolean) AS value_boolean,
        MAX(o.val_datetime) AS value_datetime
    FROM public.observation_flat AS o
    GROUP BY o.id
)
SELECT
    f.observation_id,
    f.patient_id,
    f.encounter_id,
    p.gender AS patient_gender,
    p.birth_date AS patient_birth_date,
    f.obs_status,
    f.observed_at,
    f.concept_name,
    f.concept_code_ciel,
    f.concept_code_snomed,
    f.concept_code_who_anc,
    f.value_numeric,
    f.value_unit,
    f.value_coded_name,
    f.value_coded_code_ciel,
    f.value_coded_code_snomed,
    f.value_text,
    f.value_boolean,
    f.value_datetime
FROM per_observation AS f
JOIN analytics.hiv_patient_dim_v1 AS p
    ON p.patient_id = f.patient_id
WHERE f.observed_at >= '2020-01-01'
    AND f.observed_at < '2035-01-01';

COMMENT ON VIEW analytics.hiv_observation_fact_v1 IS
    'Demo-only HIV care observation fact at exactly one row per FHIR Observation, pivoting each coding system (CIEL / SNOMED / WHO-ANC) into its own column from the lossless observation_flat base. concept_name comes from the OpenMRS-native coding''s display. A row carries a numeric, coded, text, boolean, or datetime value depending on the concept. Only observations whose subject resolves to an ingested Patient appear (subject-less rows are excluded by the patient join). Dataset notes: HIV viral load has only 3 recorded results in this instance (CD4 count and CD4% are the well-populated quantitative markers), and HIV status is not recorded as a Condition — questions about patients with HIV or on treatment must use the Antiretroviral plan/use or Current WHO HIV stage concepts.';

CREATE VIEW analytics.hiv_visit_fact_v1 AS
WITH per_encounter AS (
    SELECT
        e.id AS encounter_id,
        MAX(e.patient_id) AS patient_id,
        MAX(e.status) AS encounter_status,
        MAX(e.type_display) AS encounter_type,
        -- The upstream default view leaves period.start/end untyped, so the
        -- sink stores them as text; typing is curation, so cast here.
        MAX(e.period_start::timestamptz) AS started_at,
        MAX(e.period_end::timestamptz) AS ended_at
    FROM public.encounter_flat AS e
    GROUP BY e.id
)
SELECT
    f.encounter_id,
    f.patient_id,
    p.gender AS patient_gender,
    p.birth_date AS patient_birth_date,
    f.encounter_status,
    f.encounter_type,
    f.started_at,
    f.ended_at,
    LAG(f.started_at) OVER (
        PARTITION BY f.patient_id ORDER BY f.started_at
    ) AS prior_visit_started_at,
    (
        EXTRACT(EPOCH FROM (
            f.started_at
            - LAG(f.started_at) OVER (
                PARTITION BY f.patient_id ORDER BY f.started_at
            )
        )) / 86400.0
    )::numeric AS days_since_prior_visit
FROM per_encounter AS f
JOIN analytics.hiv_patient_dim_v1 AS p
    ON p.patient_id = f.patient_id
WHERE f.started_at >= '2020-01-01'
    AND f.started_at < '2035-01-01';

COMMENT ON VIEW analytics.hiv_visit_fact_v1 IS
    'Demo-only HIV care visit fact at exactly one row per FHIR Encounter (collapsing the type/participant/location coding cross product; encounters without a resolvable Patient subject are excluded by the patient join). days_since_prior_visit is computed across this view''s own 2020-2035 window, so a query that further narrows started_at still sees the real gap; it is null only for a patient''s first encounter inside the window.';

-- Terminology-mapping coverage: one row per distinct concept mapping
-- combination observed in the data, with usage counts. Directly answers
-- questions like "which concepts have no CIEL mapping", "which SNOMED codes
-- co-occur with a given CIEL code", or "what share of observations carry a
-- WHO-ANC mapping".
CREATE VIEW analytics.hiv_concept_mapping_v1 AS
WITH per_observation AS (
    SELECT
        o.id,
        MAX(o.obs_date) AS observed_at,
        COALESCE(
            MAX(o.code_display) FILTER (WHERE o.code_sys IS NULL),
            MAX(o.code_display)
        ) AS concept_name,
        MAX(o.code_code) FILTER (WHERE o.code_sys IS NULL)
            AS openmrs_concept_code,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'https://cielterminology.org'
        ) AS ciel_code,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'http://snomed.info/sct/'
        ) AS snomed_code,
        MAX(o.code_code) FILTER (
            WHERE o.code_sys = 'http://fhir.org/guides/who/anc-cds/CodeSystem/anc-custom-codes'
        ) AS who_anc_code
    FROM public.observation_flat AS o
    GROUP BY o.id
)
SELECT
    concept_name,
    openmrs_concept_code,
    ciel_code,
    snomed_code,
    who_anc_code,
    COUNT(*) AS observation_count
FROM per_observation
-- Same sanity window as the fact views so observation_count reconciles
-- with COUNT(*) on hiv_observation_fact_v1.
WHERE observed_at >= '2020-01-01'
    AND observed_at < '2035-01-01'
GROUP BY 1, 2, 3, 4, 5;

COMMENT ON VIEW analytics.hiv_concept_mapping_v1 IS
    'Terminology-mapping coverage observed in the data: one row per distinct (concept, OpenMRS/CIEL/SNOMED/WHO-ANC code) combination with the number of observations carrying it. Null in a code column means that observation batch carried no coding from that system.';

GRANT USAGE ON SCHEMA analytics TO catalyst_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO catalyst_readonly;

COMMIT;
