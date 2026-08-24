-- Reviewed descriptions for the Phase 1 relation surface beyond the curated
-- HIV fact views.
--
-- Catalog v6 gives the writer, the editor, the validator, and the executor the
-- same 13 relations. Nine of them are described here: the operating records
-- and the raw fhir-data-pipes flat tables, which are the fallback when a
-- curated view cannot answer an expert question.
--
-- Every flat table repeats a resource once per coding, name, identifier, or
-- participant. That one-to-many fan-out is the single most dangerous thing
-- about them, so each table comment states its grain, names its preferred
-- curated alternative, and each join key says what it repeats against.
-- Descriptions are the model's only schema context; the catalog generator
-- fails when one is missing.

-- ---------------------------------------------------------------- operating
COMMENT ON TABLE analytics.pipeline_run_v1 IS
    'One row per fhir-data-pipes ingestion run: how this data got here and whether the run finished. Operating record, not clinical data -- do not join it to patients or count it as care.';
COMMENT ON COLUMN analytics.pipeline_run_v1.pipeline_run_id IS
    'Ingestion run identifier and stable row identity.';
COMMENT ON COLUMN analytics.pipeline_run_v1.contract_version IS
    'Contract version this run record was written against.';
COMMENT ON COLUMN analytics.pipeline_run_v1.completion_state IS
    'Whether the run completed, failed, or is still going. Only a completed run''s data is trustworthy.';
COMMENT ON COLUMN analytics.pipeline_run_v1.source_watermark IS
    'The point in the source timeline this run had consumed up to.';
COMMENT ON COLUMN analytics.pipeline_run_v1.started_at IS
    'When the ingestion run began.';
COMMENT ON COLUMN analytics.pipeline_run_v1.completed_at IS
    'When the ingestion run finished; null while it is still running or if it failed before finishing.';
COMMENT ON COLUMN analytics.pipeline_run_v1.observed_at IS
    'When this run record was observed and written.';
COMMENT ON COLUMN analytics.pipeline_run_v1.data_pipes_commit IS
    'fhir-data-pipes commit that produced the run, for reproducing it.';
COMMENT ON COLUMN analytics.pipeline_run_v1.resource_counts IS
    'JSON object of resource type to row count for the run. Read a member rather than aggregating the object.';
COMMENT ON COLUMN analytics.pipeline_run_v1.error_message IS
    'Failure text when the run did not complete; null on success.';

COMMENT ON VIEW analytics.pipeline_freshness_v1 IS
    'The most recent ingestion run with its lag, for answering how current the data is. Operating record, not clinical data.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.pipeline_run_id IS
    'Ingestion run identifier; joins to analytics.pipeline_run_v1.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.contract_version IS
    'Contract version this run record was written against.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.completion_state IS
    'Whether the run completed, failed, or is still going.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.source_watermark IS
    'The point in the source timeline this run had consumed up to.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.started_at IS
    'When the ingestion run began.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.completed_at IS
    'When the ingestion run finished; null if it has not.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.observed_at IS
    'When freshness was observed; the reference point for observed_lag_seconds.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.data_pipes_commit IS
    'fhir-data-pipes commit that produced the run.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.resource_counts IS
    'JSON object of resource type to row count for the run.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.error_message IS
    'Failure text when the run did not complete; null on success.';
COMMENT ON COLUMN analytics.pipeline_freshness_v1.observed_lag_seconds IS
    'Seconds between the source watermark and observed_at: how stale the data is. Unit is seconds, not milliseconds.';

-- ------------------------------------------------------------ raw fallbacks
COMMENT ON TABLE public.patient_flat IS
    'Raw FHIR Patient, one row per patient x name x given x identifier x general practitioner. A patient repeats: never count rows here as patients. Prefer analytics.hiv_patient_dim_v1, which is exactly one row per patient and carries family_name and given_name; use this table only when you need an identifier, an organization, or a practitioner the dimension does not expose. Contains identifying information.';
COMMENT ON COLUMN public.patient_flat.id IS
    'FHIR Patient resource identifier. Repeats across rows; joins to patient_id on every other relation.';
COMMENT ON COLUMN public.patient_flat.active IS
    'FHIR Patient.active. Null when the source did not state it, which is not the same as inactive.';
COMMENT ON COLUMN public.patient_flat.gender IS
    'FHIR Patient.gender, constant per patient.';
COMMENT ON COLUMN public.patient_flat.birth_date IS
    'FHIR Patient.birthDate, constant per patient. Compute age as (reference date - birth_date).';
COMMENT ON COLUMN public.patient_flat.is_deceased IS
    'Whether the record marks the patient deceased. Null when the source did not state it.';
COMMENT ON COLUMN public.patient_flat.deceased_time IS
    'Recorded time of death; null when absent or not applicable.';
COMMENT ON COLUMN public.patient_flat.organization_id IS
    'Managing organization reference; repeats the patient when several apply.';
COMMENT ON COLUMN public.patient_flat.practitioner_id IS
    'General practitioner reference; repeats the patient once per practitioner.';
COMMENT ON COLUMN public.patient_flat.family IS
    'FHIR Patient.name.family -- the surname. Repeats per name record, and a patient with two name records has two values here, so selecting one at random invents a person. Prefer analytics.hiv_patient_dim_v1.family_name, which is null unless the patient has exactly one. Identifying information.';
COMMENT ON COLUMN public.patient_flat.given IS
    'FHIR Patient.name.given -- the first name, with the same repetition risk as family. Prefer analytics.hiv_patient_dim_v1.given_name. Identifying information.';
COMMENT ON COLUMN public.patient_flat.identifier_value IS
    'Medical record or other identifier value; repeats the patient once per identifier. Identifying information.';
COMMENT ON COLUMN public.patient_flat.identifier_sys IS
    'Naming system the identifier_value belongs to; compare both together, never the value alone.';

COMMENT ON TABLE public.encounter_flat IS
    'Raw FHIR Encounter, one row per encounter x type coding x participant x location. An encounter repeats: never count rows here as visits. Prefer analytics.hiv_visit_fact_v1, which is one row per encounter and computes days_since_prior_visit.';
COMMENT ON COLUMN public.encounter_flat.id IS
    'FHIR Encounter resource identifier. Repeats across rows.';
COMMENT ON COLUMN public.encounter_flat.status IS
    'FHIR Encounter.status, such as finished or planned.';
COMMENT ON COLUMN public.encounter_flat.patient_id IS
    'FHIR Patient reference; joins to analytics.hiv_patient_dim_v1.patient_id.';
COMMENT ON COLUMN public.encounter_flat.service_org_id IS
    'Service-providing organization reference.';
COMMENT ON COLUMN public.encounter_flat.period_start IS
    'Encounter start, stored as text in the sink -- cast before comparing with a date, and prefer hiv_visit_fact_v1.started_at, which is already typed.';
COMMENT ON COLUMN public.encounter_flat.period_end IS
    'Encounter end, stored as text in the sink; same casting caveat as period_start.';
COMMENT ON COLUMN public.encounter_flat.episodeofcareid IS
    'Episode of care reference; null when the encounter belongs to none.';
COMMENT ON COLUMN public.encounter_flat.type_sys IS
    'Terminology system of the encounter type coding. The OpenMRS-native arm is an empty string or null, not a URL.';
COMMENT ON COLUMN public.encounter_flat.type_code IS
    'Encounter type code within type_sys; read the pair, never the code alone.';
COMMENT ON COLUMN public.encounter_flat.type_display IS
    'Human-readable encounter type for the coding on this row.';
COMMENT ON COLUMN public.encounter_flat.practitioner_id IS
    'Participating practitioner reference; repeats the encounter once per participant.';
COMMENT ON COLUMN public.encounter_flat.location_id IS
    'Location reference; repeats the encounter once per location.';

COMMENT ON TABLE public.medication_flat IS
    'Raw FHIR Medication (the drug catalogue, not a prescription), one row per medication x code coding. A drug repeats once per coding, so never count rows here as drugs. Join from medication_request_flat.med_id. For prescriptions use analytics.hiv_medication_request_fact_v1.';
COMMENT ON COLUMN public.medication_flat.id IS
    'FHIR Medication resource identifier; referenced by medication_request_flat.med_id.';
COMMENT ON COLUMN public.medication_flat.status IS
    'FHIR Medication.status.';
COMMENT ON COLUMN public.medication_flat.code_text IS
    'Free-text drug name when the source gave one; often the most readable name.';
COMMENT ON COLUMN public.medication_flat.code_code IS
    'Drug code within code_sys; read the pair together.';
COMMENT ON COLUMN public.medication_flat.code_sys IS
    'Terminology system of the drug coding. The OpenMRS-native arm is an empty string or null.';
COMMENT ON COLUMN public.medication_flat.code_display IS
    'Human-readable drug name for the coding on this row.';

COMMENT ON TABLE public.condition_flat IS
    'Raw FHIR Condition (diagnoses and problems), one row per condition x code coding. A condition repeats across codings; there is no curated condition view in this source, so this is the surface for diagnosis questions.';
COMMENT ON COLUMN public.condition_flat.id IS
    'FHIR Condition resource identifier. Repeats across codings.';
COMMENT ON COLUMN public.condition_flat.patient_id IS
    'FHIR Patient reference; joins to analytics.hiv_patient_dim_v1.patient_id.';
COMMENT ON COLUMN public.condition_flat.encounter_id IS
    'Encounter the condition was recorded in; null when unlinked.';
COMMENT ON COLUMN public.condition_flat.onset_datetime IS
    'When the condition began, as recorded. Null is common and does not mean recently.';
COMMENT ON COLUMN public.condition_flat.code_code IS
    'Condition code within code_sys; read the pair together.';
COMMENT ON COLUMN public.condition_flat.code_sys IS
    'Terminology system of the condition coding. The OpenMRS-native arm is an empty string or null.';
COMMENT ON COLUMN public.condition_flat.code_display IS
    'Human-readable condition name for the coding on this row; the reliable way to select a diagnosis by name.';
COMMENT ON COLUMN public.condition_flat.category IS
    'Condition category, such as problem-list-item or encounter-diagnosis.';
COMMENT ON COLUMN public.condition_flat.clinical_status IS
    'Clinical status such as active or resolved. Filter on this before counting current problems.';
COMMENT ON COLUMN public.condition_flat.verification_status IS
    'Verification status such as confirmed or provisional.';

COMMENT ON TABLE public.observation_flat IS
    'Raw FHIR Observation, one row per observation x code coding x value coding. An observation repeats: never count rows here as results, and never aggregate val_quantity across unlike concepts. Prefer analytics.hiv_observation_fact_v1, which is one row per observation, pivots CIEL/SNOMED/WHO-ANC into their own columns, and excludes subject-less rows and impossible dates.';
COMMENT ON COLUMN public.observation_flat.id IS
    'FHIR Observation resource identifier. Repeats across codings.';
COMMENT ON COLUMN public.observation_flat.patient_id IS
    'FHIR Patient reference. Null on some source rows; the curated fact view drops those.';
COMMENT ON COLUMN public.observation_flat.encounter_id IS
    'Encounter the observation was recorded in; null when unlinked.';
COMMENT ON COLUMN public.observation_flat.status IS
    'FHIR Observation.status, such as final or preliminary. Filter to final before reporting results.';
COMMENT ON COLUMN public.observation_flat.obs_date IS
    'Effective date-time of the observation. This data contains impossible dates (as early as 1919, as late as 5025); the curated fact view restricts to 2020-01-01..2035-01-01, and a query over this table should do the same.';
COMMENT ON COLUMN public.observation_flat.val_quantity IS
    'Numeric result value. Meaningless without its concept and unit: never sum or average across different concepts.';
COMMENT ON COLUMN public.observation_flat.val_quantity_unit IS
    'Unit of val_quantity as recorded, such as cells/uL or copies/mL. Do not convert between units.';
COMMENT ON COLUMN public.observation_flat.val_quantity_system IS
    'Terminology system for the coded unit, when the source coded it.';
COMMENT ON COLUMN public.observation_flat.val_quantity_code IS
    'Coded unit within val_quantity_system.';
COMMENT ON COLUMN public.observation_flat.val_string IS
    'Free-text result, for observations whose value is not numeric.';
COMMENT ON COLUMN public.observation_flat.val_boolean IS
    'Boolean result, for yes/no observations.';
COMMENT ON COLUMN public.observation_flat.val_datetime IS
    'Date-time result, for observations whose value is a time.';
COMMENT ON COLUMN public.observation_flat.code_code IS
    'Concept code within code_sys; read the pair together.';
COMMENT ON COLUMN public.observation_flat.code_sys IS
    'Terminology system of the concept coding. The OpenMRS-native arm is an empty string or null, not a URL -- treat both the same when selecting native codes.';
COMMENT ON COLUMN public.observation_flat.code_display IS
    'Human-readable concept name for the coding on this row; the reliable way to select a concept by name.';
COMMENT ON COLUMN public.observation_flat.value_code IS
    'Coded answer, for observations whose value is itself a concept.';
COMMENT ON COLUMN public.observation_flat.value_sys IS
    'Terminology system of the coded answer; same empty-string native arm as code_sys.';
COMMENT ON COLUMN public.observation_flat.value_display IS
    'Human-readable coded answer for the row, such as an adherence category.';

COMMENT ON TABLE public.medication_request_flat IS
    'Raw FHIR MedicationRequest (prescriptions), one row per request x medication coding x status-reason coding. A request repeats: never count rows here as prescriptions. Prefer analytics.hiv_medication_request_fact_v1, which is one row per request and resolves the drug name across the reference and direct-coding arms.';
COMMENT ON COLUMN public.medication_request_flat.id IS
    'FHIR MedicationRequest resource identifier. Repeats across codings.';
COMMENT ON COLUMN public.medication_request_flat.patient_id IS
    'FHIR Patient reference; joins to analytics.hiv_patient_dim_v1.patient_id.';
COMMENT ON COLUMN public.medication_request_flat.encounter_id IS
    'Encounter the request was written in; null when unlinked.';
COMMENT ON COLUMN public.medication_request_flat.status IS
    'Request status such as active, completed, or stopped.';
COMMENT ON COLUMN public.medication_request_flat.intent IS
    'Request intent such as order or plan.';
COMMENT ON COLUMN public.medication_request_flat.donotperform IS
    'True when the request records that the medication should NOT be taken. Exclude these when counting prescriptions; the curated view exposes the same flag as do_not_perform.';
COMMENT ON COLUMN public.medication_request_flat.req_practitioner_id IS
    'Requesting practitioner reference. A reference only: this source carries no practitioner name.';
COMMENT ON COLUMN public.medication_request_flat.perf_practitioner_id IS
    'Intended performer practitioner reference; null when unspecified.';
COMMENT ON COLUMN public.medication_request_flat.med_id IS
    'Referenced Medication resource; joins to public.medication_flat.id. Null when the request carries its drug as a direct coding instead.';
COMMENT ON COLUMN public.medication_request_flat.med_display IS
    'Display text carried on the medication reference itself; first choice for the drug name.';
COMMENT ON COLUMN public.medication_request_flat.medication_system IS
    'Terminology system of the request''s own direct drug coding. The OpenMRS-native arm is an empty string or null.';
COMMENT ON COLUMN public.medication_request_flat.medication_code IS
    'Drug code within medication_system, when the request codes the drug directly.';
COMMENT ON COLUMN public.medication_request_flat.medication_display IS
    'Human-readable drug name for the request''s own direct coding.';
COMMENT ON COLUMN public.medication_request_flat.statusreason_sys IS
    'Terminology system of the status-reason coding; repeats the request once per reason.';
COMMENT ON COLUMN public.medication_request_flat.statusreason_code IS
    'Status-reason code within statusreason_sys.';
COMMENT ON COLUMN public.medication_request_flat.statusreason_display IS
    'Human-readable reason the request holds its status, such as why it was stopped.';
