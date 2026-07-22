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
COMMENT ON COLUMN analytics.pipeline_run_v1.source_watermark IS
    'Greatest source resource timestamp fully represented by a completed run.';
COMMENT ON COLUMN analytics.pipeline_run_v1.observed_at IS
    'Time at which run metadata was observed and recorded in the analytics store.';

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

COMMENT ON VIEW analytics.pipeline_freshness_v1 IS
    'Structured source watermark, run state, and observed lag; never a single ambiguous timestamp.';

-- Known demo-data artifact: a handful of OpenMRS observations carry
-- clearly-wrong effective dates (as early as 1919, as late as 5025). Both
-- fact views exclude effective/period dates outside this window so ordinary
-- date-range questions are not skewed by a few garbage rows.
CREATE OR REPLACE VIEW analytics.hiv_observation_fact_v1 AS
SELECT
    observation.id AS observation_id,
    observation.patient_id,
    observation.encounter_id,
    patient.gender AS patient_gender,
    patient.birth_date AS patient_birth_date,
    observation.obs_status,
    observation.observed_at,
    observation.concept_system,
    observation.concept_code,
    observation.concept_name,
    observation.value_numeric,
    observation.value_unit,
    observation.value_coded_code,
    observation.value_coded_name,
    observation.value_text
FROM public.observation_flat_v1 AS observation
JOIN public.patient_flat_v1 AS patient
    ON patient.id = observation.patient_id
WHERE observation.observed_at >= '2020-01-01'
    AND observation.observed_at < '2027-01-01';

COMMENT ON VIEW analytics.hiv_observation_fact_v1 IS
    'Demo-only HIV care observation fact at exactly one row per FHIR Observation. Concept code/system are the CIEL-system coding when present (OpenMRS lists an internal-UUID coding first); a single row may carry a numeric value, a coded value, or free text depending on the concept, never more than one populated.';

-- One row per visit (Encounter), with the immediately preceding visit for the
-- same patient exposed directly so visit-cadence questions ("average days
-- between visits") do not require the caller to write the window function.
CREATE OR REPLACE VIEW analytics.hiv_visit_fact_v1 AS
SELECT
    encounter.id AS encounter_id,
    encounter.patient_id,
    patient.gender AS patient_gender,
    patient.birth_date AS patient_birth_date,
    encounter.encounter_status,
    encounter.encounter_type,
    encounter.started_at,
    encounter.ended_at,
    LAG(encounter.started_at) OVER (
        PARTITION BY encounter.patient_id ORDER BY encounter.started_at
    ) AS prior_visit_started_at,
    (
        EXTRACT(EPOCH FROM (
            encounter.started_at
            - LAG(encounter.started_at) OVER (
                PARTITION BY encounter.patient_id ORDER BY encounter.started_at
            )
        )) / 86400.0
    )::numeric AS days_since_prior_visit
FROM public.encounter_flat_v1 AS encounter
JOIN public.patient_flat_v1 AS patient
    ON patient.id = encounter.patient_id
WHERE encounter.started_at >= '2020-01-01'
    AND encounter.started_at < '2027-01-01';

COMMENT ON VIEW analytics.hiv_visit_fact_v1 IS
    'Demo-only HIV care visit fact at exactly one row per FHIR Encounter. days_since_prior_visit is computed across this view''s own 2020-2027 window (after the outlier-date exclusion, before any caller filter), so a query that further narrows started_at still sees the real gap rather than one truncated by its own filter; it is null only for a patient''s first encounter inside the 2020-2027 window.';

GRANT USAGE ON SCHEMA analytics TO catalyst_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO catalyst_readonly;

COMMIT;
