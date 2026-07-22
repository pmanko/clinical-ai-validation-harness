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
"""

SEED_ROWS = f"""
INSERT INTO public.patient_flat (id, gender, birth_date)
VALUES ('p1', 'female', '1990-01-01'), ('p2', 'male', '1985-06-15');

-- obs-1: three coding systems on the same observation (OpenMRS-native +
-- CIEL + SNOMED); a numeric CD4 result.
INSERT INTO public.observation_flat
    (id, patient_id, status, obs_date, val_quantity, val_quantity_unit,
     code_code, code_sys, code_display)
VALUES
    ('obs-1', 'p1', 'final', '2026-06-01T10:00:00Z', 450, 'cells/uL',
     '5497', NULL, 'CD4 count'),
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
     '5088', NULL, 'Temperature (local)');
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


def _connect(dsn, **kwargs):
    import psycopg

    return psycopg.connect(dsn, **kwargs)


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
        # obs-1's 3 coding rows collapse to one.
        self.assertEqual(
            [row["observation_id"] for row in rows], ["obs-1", "obs-2"]
        )

        obs1, obs2 = rows
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

    def test_concept_mapping_view_flags_the_unmapped_concept(self):
        rows = self._rows(
            "SELECT * FROM analytics.hiv_concept_mapping_v1 "
            "WHERE concept_name = 'Temperature (local)'"
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row["ciel_code"])
        self.assertIsNone(row["snomed_code"])
        self.assertEqual(row["observation_count"], 1)

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
