"""Execute scripts/generate-catalyst-source-catalog.py against a real
PostgreSQL to guard its fail-fast contracts: every column must have a
COMMENT ON COLUMN, every view a COMMENT ON VIEW, every SQL type must be in
TYPE_MAP, and every semantic canonical value must match at least one live
row. The generator has no unit-testable seams (a single inline main()), so
this drives it the same way real usage does — against a scratch database,
mirroring tests/analytics/test_fact_view_semantics.py's real-Postgres
pattern rather than stubbing psycopg. Loaded in-process via importlib (not
subprocess) so coverage instrumentation and diff-cover see it exercised.

Needs a reachable PostgreSQL (skips otherwise): set
CATALYST_GENERATOR_TEST_DSN, or have the catalyst-mvp analytics-db
container up (localhost:15443). A scratch database is created and dropped
around the run.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate-catalyst-source-catalog.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_catalyst_source_catalog", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

DEFAULT_DSN = (
    "postgresql://catalyst_analytics_writer:demo-only-change-me"
    "@localhost:15443/catalyst_analytics"
)
SCRATCH_DB = "catalyst_generator_test"

SEED_DDL = """
CREATE SCHEMA IF NOT EXISTS gen_test;

CREATE VIEW gen_test.happy_v1 AS SELECT 1::int AS id, 'Malaria'::text AS name;
COMMENT ON VIEW gen_test.happy_v1 IS 'One row per test fixture.';
COMMENT ON COLUMN gen_test.happy_v1.id IS 'Fixture identifier.';
COMMENT ON COLUMN gen_test.happy_v1.name IS 'Fixture display name.';

CREATE VIEW gen_test.no_view_comment_v1 AS SELECT 1::int AS id;
COMMENT ON COLUMN gen_test.no_view_comment_v1.id IS 'Fixture identifier.';

CREATE VIEW gen_test.no_col_comment_v1 AS SELECT 1::int AS id;
COMMENT ON VIEW gen_test.no_col_comment_v1 IS 'One row per test fixture.';

-- A geometric type: no logical equivalent the catalog can express, and
-- unlike jsonb it is not something an analytics relation would carry.
CREATE VIEW gen_test.bad_type_v1 AS SELECT point(0, 0) AS payload;
COMMENT ON VIEW gen_test.bad_type_v1 IS 'One row per test fixture.';
COMMENT ON COLUMN gen_test.bad_type_v1.payload IS 'Unmapped-type column.';
"""


def _connect(dsn, **kwargs):
    import psycopg

    return psycopg.connect(dsn, **kwargs)


class GenerateSourceCatalogTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        try:
            import psycopg  # noqa: F401
        except ImportError:  # pragma: no cover - environment-specific
            raise unittest.SkipTest("psycopg is not installed")
        cls.admin_dsn = os.environ.get(
            "CATALYST_GENERATOR_TEST_DSN", DEFAULT_DSN
        )
        try:
            admin = _connect(cls.admin_dsn, autocommit=True, connect_timeout=3)
        except Exception as error:  # pragma: no cover - environment-specific
            raise unittest.SkipTest(f"PostgreSQL is not reachable: {error}")
        with admin:
            admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")
            admin.execute(f"CREATE DATABASE {SCRATCH_DB}")
        cls.scratch_dsn = cls.admin_dsn.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"
        with _connect(cls.scratch_dsn) as conn:
            conn.execute(SEED_DDL)
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "admin_dsn"):
            return
        with _connect(cls.admin_dsn, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")

    def _run(self, overlay: dict, out_path: Path, tmp_path: Path):
        overlay_path = tmp_path / "overlay.json"
        overlay_path.write_text(json.dumps(overlay))
        argv = [
            "generate-catalyst-source-catalog.py",
            "--dsn",
            self.scratch_dsn,
            "--overlay",
            str(overlay_path),
            "--out",
            str(out_path),
        ]
        module = _load_module()
        stderr = io.StringIO()
        old_argv = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stderr(stderr):
                try:
                    module.main()
                    returncode = 0
                except SystemExit as exc:
                    returncode = exc.code or 0
        finally:
            sys.argv = old_argv
        return SimpleNamespace(returncode=returncode, stderr=stderr.getvalue())

    def test_generates_catalog_with_types_nullability_and_unit_column(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_path = tmp_path / "catalog.json"
            overlay = {
                "catalogVersion": "gen-test-v1",
                "dataSource": "gen-test-fixture",
                "dialect": "postgresql",
                "schemaVersion": "analytics-v1",
                "approvedViews": [{"name": "gen_test.happy_v1", "version": "1"}],
                "nonNullableColumns": ["gen_test.happy_v1.id"],
                "unitColumns": {"gen_test.happy_v1.id": "name"},
            }
            result = self._run(overlay, out_path, tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            catalog = json.loads(out_path.read_text())
            self.assertEqual(
                set(catalog.keys()),
                {
                    "contractVersion",
                    "catalogVersion",
                    "deploymentMode",
                    "dataSource",
                    "dialect",
                    "schemaVersion",
                    "description",
                    "views",
                },
            )
            self.assertEqual(catalog["catalogVersion"], "gen-test-v1")
            (view,) = catalog["views"]
            self.assertEqual(view["name"], "gen_test.happy_v1")
            self.assertEqual(view["grain"], "One row per test fixture.")
            columns = {c["name"]: c for c in view["columns"]}
            self.assertEqual(columns["id"]["logicalType"], "integer")
            self.assertFalse(columns["id"]["nullable"])
            self.assertEqual(columns["id"]["unitColumn"], "name")
            self.assertEqual(columns["name"]["logicalType"], "string")
            self.assertTrue(columns["name"]["nullable"])
            self.assertEqual(
                columns["name"]["description"], "Fixture display name."
            )

    def test_fails_fast_on_missing_view_comment(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            overlay = {
                "catalogVersion": "gen-test-v1",
                "dataSource": "gen-test-fixture",
                "dialect": "postgresql",
                "schemaVersion": "analytics-v1",
                "approvedViews": [
                    {"name": "gen_test.no_view_comment_v1", "version": "1"}
                ],
            }
            result = self._run(overlay, tmp_path / "catalog.json", tmp_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no COMMENT ON VIEW", result.stderr)

    def test_fails_fast_on_missing_column_comment(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            overlay = {
                "catalogVersion": "gen-test-v1",
                "dataSource": "gen-test-fixture",
                "dialect": "postgresql",
                "schemaVersion": "analytics-v1",
                "approvedViews": [
                    {"name": "gen_test.no_col_comment_v1", "version": "1"}
                ],
            }
            result = self._run(overlay, tmp_path / "catalog.json", tmp_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no COMMENT ON COLUMN", result.stderr)

    def test_fails_fast_on_unmapped_sql_type(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            overlay = {
                "catalogVersion": "gen-test-v1",
                "dataSource": "gen-test-fixture",
                "dialect": "postgresql",
                "schemaVersion": "analytics-v1",
                "approvedViews": [{"name": "gen_test.bad_type_v1", "version": "1"}],
            }
            result = self._run(overlay, tmp_path / "catalog.json", tmp_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unmapped SQL type", result.stderr)
            self.assertIn("point", result.stderr)

    def test_fails_fast_on_canonical_value_matching_zero_rows(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            overlay = {
                "catalogVersion": "gen-test-v1",
                "dataSource": "gen-test-fixture",
                "dialect": "postgresql",
                "schemaVersion": "analytics-v1",
                "approvedViews": [{"name": "gen_test.happy_v1", "version": "1"}],
                "semanticDimensions": {
                    "gen_test.happy_v1": [
                        {
                            "field": "name",
                            "semanticType": "analyte",
                            "values": [
                                {"canonical": "Nonexistent Analyte", "aliases": []}
                            ],
                        }
                    ]
                },
            }
            result = self._run(overlay, tmp_path / "catalog.json", tmp_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("matches zero rows", result.stderr)
            self.assertIn("Nonexistent Analyte", result.stderr)
