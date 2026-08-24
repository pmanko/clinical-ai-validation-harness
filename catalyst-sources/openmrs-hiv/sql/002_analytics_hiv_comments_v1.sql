-- Column documentation for the HIV analytics views. These comments are the
-- single source of truth for catalog column descriptions: the catalog
-- generator introspects them (pg_description) and emits the catalog JSON.
-- Edit here, regenerate the catalog; never edit the catalog by hand.

COMMENT ON COLUMN analytics.hiv_observation_fact_v1.observation_id IS
    'FHIR Observation resource identifier and stable row identity.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.patient_id IS
    'FHIR Patient resource identifier referenced by the observation.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.encounter_id IS
    'FHIR Encounter resource identifier the observation was recorded within.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.patient_gender IS
    'FHIR Patient.gender.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.patient_birth_date IS
    'FHIR Patient.birthDate. Compute age at observation as (observed_at - patient_birth_date) rather than assuming a stored age column.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.obs_status IS
    'FHIR Observation.status.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.observed_at IS
    'FHIR Observation effective dateTime.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.concept_name IS
    'Human-readable concept display name from the OpenMRS-native coding; populated on every row regardless of which terminology mappings exist. This is the reliable way to select a concept: a question naming a marker must constrain this field.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.concept_code_ciel IS
    'CIEL numeric code for the observed concept (e.g. 5497 for CD4 count). Coverage verified against the complete dataset: 99.9% of observations carry a CIEL coding; a small residue does not, so concept_name (which is populated on every row and carries the semantic aliases) remains the primary way to select a concept, with this column for terminology filtering and cross-reference.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.concept_code_snomed IS
    'SNOMED CT code for the observed concept when the source carries a SNOMED coding. Cross-reference/terminology column; coverage is partial, as with CIEL.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.concept_code_who_anc IS
    'WHO ANC custom code (http://fhir.org/guides/who/anc-cds) for the observed concept when present. Cross-reference/terminology column; sparse.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_numeric IS
    'Populated only for numeric-valued concepts (e.g. CD4 count, CD4%, CD8 count). Null for coded, text, boolean, or datetime observations; do not aggregate across unlike concepts or units.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_unit IS
    'Unit for value_numeric, when the source Observation carries one.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_coded_name IS
    'Human-readable label for a coded answer (e.g. Yes/No/Unknown for antiretroviral use, a WHO stage, an adherence category), from the OpenMRS-native coding; populated for every coded-valued observation.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_coded_code_ciel IS
    'CIEL numeric code for the coded answer when the source carries one; near-complete coverage, same residue caveat as concept_code_ciel. value_coded_name is populated on every coded row.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_coded_code_snomed IS
    'SNOMED CT code for the coded answer when the source carries one; cross-reference column.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_text IS
    'Free-text value, for the small number of concepts recorded as plain text.';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_boolean IS
    'Boolean value, for yes/no concepts recorded as FHIR valueBoolean (e.g. screening flags).';
COMMENT ON COLUMN analytics.hiv_observation_fact_v1.value_datetime IS
    'Datetime value, for concepts recorded as FHIR valueDateTime (e.g. return-visit or event dates).';

COMMENT ON COLUMN analytics.hiv_visit_fact_v1.encounter_id IS
    'FHIR Encounter resource identifier and stable row identity.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.patient_id IS
    'FHIR Patient resource identifier referenced by the encounter.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.patient_gender IS
    'FHIR Patient.gender.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.patient_birth_date IS
    'FHIR Patient.birthDate.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.encounter_status IS
    'FHIR Encounter.status.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.encounter_type IS
    'FHIR Encounter type display name; almost all encounters in this demo instance are OPD Visit.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.started_at IS
    'FHIR Encounter.period.start.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.ended_at IS
    'FHIR Encounter.period.end.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.prior_visit_started_at IS
    'started_at of this patient''s immediately preceding visit in this view; null for a patient''s first visit in the 2020-2035 window.';
COMMENT ON COLUMN analytics.hiv_visit_fact_v1.days_since_prior_visit IS
    'Days between this visit and the patient''s immediately preceding visit. Real, patient-specific spacing (some patients visit monthly with gaps, some have single-day visit pairs); it is not a fixed or uniform interval. Null for a patient''s first visit.';

COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.concept_name IS
    'Human-readable concept display name from the OpenMRS-native coding.';
COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.openmrs_concept_code IS
    'OpenMRS-native concept code (UUID-form, no system URI in the source).';
COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.ciel_code IS
    'CIEL numeric code mapped to this concept, when the observations carried one; null means those observations had no CIEL mapping.';
COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.snomed_code IS
    'SNOMED CT code mapped to this concept, when present.';
COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.who_anc_code IS
    'WHO ANC custom code mapped to this concept, when present.';
COMMENT ON COLUMN analytics.hiv_concept_mapping_v1.observation_count IS
    'Number of observations carrying exactly this mapping combination.';

COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_request_id IS
    'FHIR MedicationRequest resource identifier and stable row identity.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.patient_id IS
    'FHIR Patient resource identifier the medication was requested for.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.patient_gender IS
    'FHIR Patient.gender of the requested-for patient.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.patient_birth_date IS
    'FHIR Patient.birthDate. MedicationRequest carries no date here, so age at request cannot be derived from this view alone.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.encounter_id IS
    'FHIR Encounter the request was recorded within. Join hiv_visit_fact_v1 on this to get a date.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.request_status IS
    'FHIR MedicationRequest.status, for example active, completed or stopped.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.request_intent IS
    'FHIR MedicationRequest.intent, for example order or plan.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.do_not_perform IS
    'True when the request records that the medication should NOT be taken. Exclude these when counting prescriptions.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_name IS
    'Drug name, by precedence: the request''s own reference display, its direct coding display, the referenced Medication''s text, then the referenced Medication''s coding display. Null when none of those is populated -- verified nonempty in the current data, but not guaranteed by the source.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_code_openmrs IS
    'OpenMRS-native drug code (no external coding system), from the request''s own coding when present, otherwise the referenced Medication''s.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_code_ciel IS
    'CIEL numeric drug code, from the request''s own coding when present, otherwise the referenced Medication''s. Null when neither carries a CIEL mapping.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_code_snomed IS
    'SNOMED CT drug code, from the request''s own coding when present, otherwise the referenced Medication''s. Null when neither carries a SNOMED mapping.';
COMMENT ON COLUMN analytics.hiv_medication_request_fact_v1.medication_code_who_anc IS
    'WHO ANC custom drug code, from the request''s own coding when present, otherwise the referenced Medication''s. Null when neither carries a WHO ANC mapping; sparse in this data (at most one drug carries it).';
