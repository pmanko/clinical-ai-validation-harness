"""Execute the curated OpenMRS HIV SQL against a real PostgreSQL and assert its
semantics: the per-coding cross product collapses to one row per resource, each
terminology system (CIEL/SNOMED/WHO-ANC) pivots into its own column, the
patient-dimension join drops subject-less observations, and days_since_prior_visit
is computed within the view's own date window. This is the twin of
targets/catalyst/tests/analytics/test_fact_view_semantics.py for the second data
source; that repo's contract tests only check the SQL's text shape.

Needs a reachable PostgreSQL (skips otherwise): set
CATALYST_HIV_ANALYTICS_TEST_DSN, or have the catalyst-mvp analytics-db
container up (localhost:15443, catalyst_analytics_hiv). A scratch database is
created and dropped around the run; seed tables mirror the fhir-data-pipes
sink column types exactly.
"""

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACT_SQL = ROOT / "catalyst-sources" / "openmrs-hiv" / "sql" / "001_analytics_hiv_v1.sql"
INGESTION_SCRIPT = (
    ROOT / "catalyst-sources" / "openmrs-hiv" / "run-ingestion.sh"
)

DEFAULT_DSN = (
    "postgresql://catalyst_analytics_writer:demo-only-change-me"
    "@localhost:15443/catalyst_analytics_hiv"
)
SCRATCH_DB = "catalyst_hiv_fact_semantics_test"

CIEL = "https://cielterminology.org"
SNOMED = "http://snomed.info/sct/"

# Mirrors the fhir-data-pipes sink schema for the HIV source (information_schema
# on the live sink).
SEED_DDL = """
CREATE TABLE public.observation_flat (
    id varchar, patient_id varchar, encounter_id varchar, status varchar,
    obs_date timestamptz, val_quantity numeric, val_quantity_unit varchar,
    val_quantity_system varchar, val_quantity_code varchar,
    val_string varchar, val_boolean boolean, val_datetime timestamptz,
    code_code varchar, code_sys varchar, code_display varchar,
    value_code varchar, value_sys varchar, value_display varchar
);
CREATE TABLE public.patient_flat (
    id varchar, active boolean, gender varchar, birth_date date,
    is_deceased boolean, deceased_time timestamptz, organization_id varchar,
    practitioner_id varchar, family varchar, given varchar,
    identifier_value varchar, identifier_sys varchar
);
CREATE TABLE public.encounter_flat (
    id varchar, status varchar, patient_id varchar, service_org_id varchar,
    period_start varchar, period_end varchar, episodeofcareid varchar,
    type_sys varchar, type_code varchar, type_display varchar,
    practitioner_id varchar, location_id varchar
);
CREATE TABLE public.medication_flat (
    id varchar, status varchar, code_text varchar, code_code varchar,
    code_sys varchar, code_display varchar
);
CREATE TABLE public.medication_request_flat (
    id varchar, patient_id varchar, encounter_id varchar, status varchar,
    intent varchar, donotperform boolean, req_practitioner_id varchar,
    perf_practitioner_id varchar, med_id varchar, med_display varchar,
    medication_system varchar, medication_code varchar,
    medication_display varchar, statusreason_sys varchar,
    statusreason_code varchar, statusreason_display varchar
);
"""

SEED_ROWS = f"""
INSERT INTO public.patient_flat (id, gender, birth_date)
VALUES ('p1', 'female', '1990-01-01'), ('p2', 'male', '1985-06-15');

-- obs-1: three coding systems on the same observation (OpenMRS-native +
-- CIEL + SNOMED); a numeric CD4 result. Production represents the native
-- system as an empty string.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, val_quantity, val_quantity_unit,
     code_code, code_sys, code_display)
VALUES
    ('obs-1', 'p1', 'final', '2026-06-01T10:00:00Z', 450, 'cells/uL',
     '5497', '', 'CD4 count'),
    ('obs-1', 'p1', 'final', '2026-06-01T10:00:00Z', 450, 'cells/uL',
     '5497', '{CIEL}', 'CD4 count (CIEL)'),
    ('obs-1', 'p1', 'final', '2026-06-01T10:00:00Z', 450, 'cells/uL',
     '733961000000107', '{SNOMED}', 'CD4 count (SNOMED)');
-- obs-2: OpenMRS-native only (no CIEL/SNOMED mapping) -- the
-- terminology-mapping-gap case.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, val_quantity, val_quantity_unit,
     code_code, code_sys, code_display)
VALUES
    ('obs-2', 'p2', 'final', '2026-06-05T10:00:00Z', 36.5, 'degC',
     '5088', '', 'Temperature (local)');
-- obs-5: production empty-string native code and coded answer alongside an
-- external mapping whose display sorts later. A generic MAX(display) fallback
-- would silently choose the external wording.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, code_code, code_sys, code_display,
     value_code, value_sys, value_display)
VALUES
    ('obs-5', 'p1', 'final', '2026-06-07T10:00:00Z',
     'empty-native-code', '', 'Empty-system concept',
     'empty-native-answer', '', 'Empty-system answer'),
    ('obs-5', 'p1', 'final', '2026-06-07T10:00:00Z',
     'empty-ciel-code', '{CIEL}', 'ZZZ external concept',
     'empty-ciel-answer', '{CIEL}', 'ZZZ external answer');
-- obs-6: compatibility NULL native system, retained so accepting the real
-- empty-string representation does not regress sources that normalize it.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, code_code, code_sys, code_display,
     value_code, value_sys, value_display)
VALUES
    ('obs-6', 'p2', 'final', '2026-06-08T10:00:00Z',
     'null-native-code', NULL, 'Null-system concept',
     'null-native-answer', NULL, 'Null-system answer'),
    ('obs-6', 'p2', 'final', '2026-06-08T10:00:00Z',
     'null-ciel-code', '{CIEL}', 'ZZZ null external concept',
     'null-ciel-answer', '{CIEL}', 'ZZZ null external answer');
-- obs-3: no resolvable patient subject -- must be excluded by the patient join.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, val_quantity, code_code, code_sys, code_display)
VALUES
    ('obs-3', 'does-not-exist', 'final', '2026-06-06T10:00:00Z', 1,
     '5497', NULL, 'CD4 count');
-- obs-4: outside the 2020-2035 sanity window -- must be excluded.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, val_quantity, code_code, code_sys, code_display)
VALUES
    ('obs-4', 'p1', 'final', '1919-06-06T10:00:00Z', 1,
     '5497', NULL, 'CD4 count');

-- p1: two encounters (collapsing the type-coding cross product on enc-2), so
-- days_since_prior_visit has a real gap to compute.
INSERT INTO public.encounter_flat
    (id, patient_id, status, period_start, period_end, type_code, type_sys, type_display)
VALUES
    ('enc-1', 'p1', 'finished', '2026-06-01T09:00:00+00', '2026-06-01T09:30:00+00',
     'a', 'sct', 'Visit type A'),
    ('enc-2', 'p1', 'finished', '2026-06-11T09:00:00+00', '2026-06-11T09:30:00+00',
     'b', 'sct', 'Visit type B'),
    ('enc-2', 'p1', 'finished', '2026-06-11T09:00:00+00', '2026-06-11T09:30:00+00',
     'c', 'local', 'Visit type B (local)');
"""

# The OpenMRS-native coding carries '' for code_sys/medication_system in the
# real sink, not NULL (found by running this fix against the live analytics
# database) -- seeded that way here so a regression back to an IS-NULL-only
# filter fails this suite instead of only failing in production.
MEDICATION_SEED_ROWS = f"""
-- med-multi: three codings on the same Medication (OpenMRS-native + CIEL +
-- SNOMED) -- an independent MAX() per column here previously paired a code
-- from one coding with the system of another.
INSERT INTO public.medication_flat (id, code_text, code_code, code_sys, code_display)
VALUES
    ('med-multi', 'Multi Drug', '1001', '', 'Multi Drug (local)'),
    ('med-multi', NULL, '1001-ciel', '{CIEL}', NULL),
    ('med-multi', NULL, '9001-snomed', '{SNOMED}', NULL);
-- med-text: no display on its coding, but a top-level text.
INSERT INTO public.medication_flat (id, code_text, code_code, code_sys, code_display)
VALUES ('med-text', 'Text Only Drug', '2002', '', NULL);
-- med-display-only: no text, coding display is the only thing available.
INSERT INTO public.medication_flat (id, code_text, code_code, code_sys, code_display)
VALUES ('med-display-only', NULL, '3003', '', 'Display Fallback Drug');
-- med-blank: identity only, no display or text anywhere.
INSERT INTO public.medication_flat (id, code_text, code_code, code_sys, code_display)
VALUES ('med-blank', NULL, '4004', '', '');

-- req-1: reference display wins (tier 1); proves the multi-coded fix.
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform, med_id, med_display)
VALUES ('req-1', 'p1', 'active', 'order', FALSE, 'med-multi', 'Reference Display One');
-- req-2: no reference; its OWN direct medication[x] CodeableConcept fans out
-- across three coding rows (OpenMRS-native + CIEL + SNOMED), and
-- donotperform is NULL on all three -- proves the direct arm gets the same
-- per-system treatment as the referenced Medication, direct display wins
-- (tier 2), and COALESCE(donotperform, FALSE) still holds under BOOL_OR.
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform,
     medication_code, medication_system, medication_display)
VALUES
    ('req-2', 'p1', 'active', 'order', NULL, '5005', '', 'Direct Display Two'),
    ('req-2', 'p1', 'active', 'order', NULL, '5005-ciel', '{CIEL}', NULL),
    ('req-2', 'p1', 'active', 'order', NULL, '9005-snomed', '{SNOMED}', NULL);
-- req-3: no reference or direct display -- falls to the referenced
-- Medication's text (tier 3).
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform, med_id)
VALUES ('req-3', 'p2', 'active', 'order', TRUE, 'med-text');
-- req-4: falls all the way to the referenced Medication's coding display
-- (tier 4, the least preferred).
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform, med_id)
VALUES ('req-4', 'p1', 'active', 'order', FALSE, 'med-display-only');
-- req-5: reference display is '' (present but blank, not NULL) and the
-- referenced Medication has no display or text either -- every tier is
-- blank, so the name is NULL, not ''.
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform, med_id, med_display)
VALUES ('req-5', 'p2', 'active', 'order', FALSE, 'med-blank', '');
-- req-6: subject does not resolve to an ingested Patient -- excluded by the
-- patient join, same as observations.
INSERT INTO public.medication_request_flat
    (id, patient_id, status, intent, donotperform, med_id, med_display)
VALUES ('req-6', 'does-not-exist', 'active', 'order', FALSE, 'med-multi', 'Should Not Appear');
"""


def _connect(dsn, **kwargs):
    import psycopg

    return psycopg.connect(dsn, **kwargs)


class HivIngestionScriptContractTests(unittest.TestCase):
    def test_controller_readiness_retries_transient_http_errors(self):
        script = INGESTION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "curl -fsS --retry-all-errors --retry-connrefused --retry 60",
            script,
        )
        self.assertIn("--retry-delay 3 --retry-max-time 180 --max-time 5", script)
        self.assertIn(
            '"http://localhost:${CONTROLLER_PORT}/actuator/health" | grep -q UP',
            script,
        )

    def test_ingestion_reconciles_native_concept_codes_and_displays(self):
        script = INGESTION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "count(NULLIF(openmrs_concept_code, ''))",
            script,
        )
        self.assertIn("missing_from_view", script)
        self.assertIn("missing_from_raw", script)
        self.assertIn("display_mismatches", script)
        self.assertIn("o.code_sys IS NULL OR o.code_sys = ''", script)
        self.assertIn("o.value_sys IS NULL OR o.value_sys = ''", script)


class HivFactViewSemanticsTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        try:
            import psycopg  # noqa: F401
        except ImportError:  # pragma: no cover - environment-specific
            raise unittest.SkipTest("psycopg is not installed")
        cls.admin_dsn = os.environ.get(
            "CATALYST_HIV_ANALYTICS_TEST_DSN", DEFAULT_DSN
        )
        try:
            admin = _connect(cls.admin_dsn, autocommit=True, connect_timeout=3)
        except Exception as error:  # pragma: no cover - environment-specific
            raise unittest.SkipTest(f"PostgreSQL is not reachable: {error}")
        with admin:
            admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")
            admin.execute(f"CREATE DATABASE {SCRATCH_DB}")
        cls.scratch_dsn = cls.admin_dsn.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"
        cls.conn = _connect(cls.scratch_dsn)
        cls.conn.execute(SEED_DDL)
        cls.conn.execute(SEED_ROWS)
        cls.conn.execute(MEDICATION_SEED_ROWS)
        cls.conn.execute(FACT_SQL.read_text())
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "conn"):
            return
        cls.conn.close()
        with _connect(cls.admin_dsn, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")

    def _rows(self, sql):
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            columns = [d.name for d in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def test_observation_fact_pivots_terminology_and_excludes_bad_rows(self):
        rows = self._rows(
            "SELECT * FROM analytics.hiv_observation_fact_v1 ORDER BY observation_id"
        )
        # obs-3 (no patient) and obs-4 (outside date window) are excluded;
        # each multi-coded observation collapses to one.
        self.assertEqual(
            [row["observation_id"] for row in rows],
            ["obs-1", "obs-2", "obs-5", "obs-6"],
        )

        obs1, obs2, obs5, obs6 = rows
        self.assertEqual(obs1["concept_name"], "CD4 count")
        self.assertEqual(obs1["concept_code_ciel"], "5497")
        self.assertEqual(obs1["concept_code_snomed"], "733961000000107")
        self.assertIsNone(obs1["concept_code_who_anc"])
        self.assertEqual(float(obs1["value_numeric"]), 450.0)
        self.assertEqual(obs1["patient_gender"], "female")

        # obs-2: OpenMRS-native only -- both mapped-code columns are null.
        self.assertEqual(obs2["concept_name"], "Temperature (local)")
        self.assertIsNone(obs2["concept_code_ciel"])
        self.assertIsNone(obs2["concept_code_snomed"])

        self.assertEqual(obs5["concept_name"], "Empty-system concept")
        self.assertEqual(obs5["value_coded_name"], "Empty-system answer")
        self.assertEqual(obs6["concept_name"], "Null-system concept")
        self.assertEqual(obs6["value_coded_name"], "Null-system answer")

    def test_concept_mapping_view_flags_the_unmapped_concept(self):
        rows = self._rows(
            "SELECT * FROM analytics.hiv_concept_mapping_v1 "
            "WHERE concept_name = 'Temperature (local)'"
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["openmrs_concept_code"], "5088")
        self.assertIsNone(row["ciel_code"])
        self.assertIsNone(row["snomed_code"])
        self.assertEqual(row["observation_count"], 1)

    def test_concept_mapping_uses_exact_empty_and_null_native_codings(self):
        rows = self._rows(
            "SELECT concept_name, openmrs_concept_code "
            "FROM analytics.hiv_concept_mapping_v1 "
            "WHERE concept_name IN ('Empty-system concept', 'Null-system concept') "
            "ORDER BY concept_name"
        )
        self.assertEqual(
            rows,
            [
                {
                    "concept_name": "Empty-system concept",
                    "openmrs_concept_code": "empty-native-code",
                },
                {
                    "concept_name": "Null-system concept",
                    "openmrs_concept_code": "null-native-code",
                },
            ],
        )

    def test_every_seeded_concept_mapping_has_a_native_code(self):
        rows = self._rows(
            "SELECT count(*) AS total, "
            "count(NULLIF(openmrs_concept_code, '')) AS with_native_code "
            "FROM analytics.hiv_concept_mapping_v1"
        )
        # obs-3 has no resolvable Patient and is excluded from the patient fact,
        # but the terminology view intentionally covers it; all five in-window
        # observations still carry a native code.
        self.assertEqual(rows, [{"total": 5, "with_native_code": 5}])

    def test_visit_fact_collapses_codings_and_computes_gap_in_own_window(self):
        rows = self._rows(
            "SELECT * FROM analytics.hiv_visit_fact_v1 "
            "WHERE patient_id = 'p1' ORDER BY started_at"
        )
        # enc-2's 2 type-coding rows collapse to one row.
        self.assertEqual([row["encounter_id"] for row in rows], ["enc-1", "enc-2"])
        first, second = rows
        self.assertIsNone(first["days_since_prior_visit"])
        self.assertEqual(float(second["days_since_prior_visit"]), 10.0)

    def _medication_row(self, request_id):
        rows = self._rows(
            "SELECT * FROM analytics.hiv_medication_request_fact_v1 "
            f"WHERE medication_request_id = '{request_id}'"
        )
        self.assertEqual(len(rows), 1, f"expected exactly one row for {request_id}")
        return rows[0]

    def test_medication_fact_holds_one_row_per_request_and_excludes_unresolved_patient(self):
        rows = self._rows(
            "SELECT medication_request_id FROM analytics.hiv_medication_request_fact_v1 "
            "ORDER BY medication_request_id"
        )
        # req-2's own three-coding fan-out collapses to one row; req-6 (no
        # resolvable patient) is excluded by the patient join.
        self.assertEqual(
            [row["medication_request_id"] for row in rows],
            ["req-1", "req-2", "req-3", "req-4", "req-5"],
        )

    def test_multi_coded_referenced_medication_keeps_each_code_with_its_own_system(self):
        row = self._medication_row("req-1")
        self.assertEqual(row["medication_name"], "Reference Display One")
        self.assertEqual(row["medication_code_openmrs"], "1001")
        self.assertEqual(row["medication_code_ciel"], "1001-ciel")
        self.assertEqual(row["medication_code_snomed"], "9001-snomed")
        self.assertIsNone(row["medication_code_who_anc"])
        self.assertFalse(row["do_not_perform"])
        self.assertEqual(row["patient_gender"], "female")

    def test_direct_coding_arm_fans_out_and_pivots_like_the_referenced_medication(self):
        row = self._medication_row("req-2")
        # Direct display wins because there is no reference display (tier 2).
        self.assertEqual(row["medication_name"], "Direct Display Two")
        self.assertEqual(row["medication_code_openmrs"], "5005")
        self.assertEqual(row["medication_code_ciel"], "5005-ciel")
        self.assertEqual(row["medication_code_snomed"], "9005-snomed")
        # donotperform was NULL on every one of the three fanned-out rows.
        self.assertFalse(row["do_not_perform"])

    def test_medication_name_precedence_falls_to_the_referenced_medications_text(self):
        row = self._medication_row("req-3")
        self.assertEqual(row["medication_name"], "Text Only Drug")
        self.assertEqual(row["medication_code_openmrs"], "2002")
        self.assertTrue(row["do_not_perform"])
        self.assertEqual(row["patient_gender"], "male")

    def test_medication_name_precedence_falls_to_the_referenced_codings_display(self):
        row = self._medication_row("req-4")
        self.assertEqual(row["medication_name"], "Display Fallback Drug")
        self.assertEqual(row["medication_code_openmrs"], "3003")

    def test_blank_medication_name_is_null_not_an_empty_string(self):
        row = self._medication_row("req-5")
        # Every arm was blank (reference display '', referenced Medication has
        # neither display nor text) -- the contract permits null; '' is not a
        # name.
        self.assertIsNone(row["medication_name"])
        self.assertEqual(row["medication_code_openmrs"], "4004")
