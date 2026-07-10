"""Loader orchestration tests (harness/load/loader.py) over a FAKE DB connection.

The real DB is the only external boundary, so it's stubbed by monkeypatching
`loader._connect` with an in-memory fake whose cursor answers the exact queries the
loader issues (information_schema existence/columns + the INSERT/TRUNCATE/DELETE). That
keeps the REAL control flow under test: the missing-source / no-columns / no-shared-columns
branches, the ok path's rowcount + commit, the error path's rollback, and load_all's
FK-order + stop-on-first-failure + report assembly. _build_load_sql (the pure SQL) is
covered in test_loader.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from harness.load import loader


# --------------------------------------------------------------------------- #
# a minimal fake pymysql connection driven by a scripted information_schema
# --------------------------------------------------------------------------- #
class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append(sql.strip())
        s = " ".join(sql.split())
        if "information_schema.tables" in s:
            schema, table = params
            self._result = [(1,)] if (schema, table) in self.conn.existing_tables else []
        elif "information_schema.columns" in s:
            schema, table = params
            cols = self.conn.columns.get((schema, table), [])
            self._result = [(c,) for c in cols]
        elif s.upper().startswith(("INSERT", "INSERT IGNORE")):
            self.rowcount = self.conn.insert_rows
            if self.conn.raise_on_insert:
                raise RuntimeError("boom: duplicate key")
        elif s.upper().startswith(("TRUNCATE", "DELETE")):
            self.rowcount = self.conn.delete_rows
        self._result = self._result if self._result is not None else []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result or [])


class _FakeConn:
    def __init__(self, *, existing_tables, columns, insert_rows=0, delete_rows=0,
                 raise_on_insert=False):
        self.existing_tables = set(existing_tables)
        self.columns = columns
        self.insert_rows = insert_rows
        self.delete_rows = delete_rows
        self.raise_on_insert = raise_on_insert
        self.executed: list[str] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _patch_connect(monkeypatch, conn):
    monkeypatch.setattr(loader, "_connect", lambda schema: conn)
    return conn


# --------------------------------------------------------------------------- #
# load_one
# --------------------------------------------------------------------------- #
def test_load_one_missing_source_table(monkeypatch):
    conn = _patch_connect(monkeypatch, _FakeConn(existing_tables=set(), columns={}))
    res = loader.load_one("tgt", "src_schema", "src_tbl", "tgt_tbl", "replace")
    assert res.status == "missing_in_source"
    assert "does not exist" in res.error
    assert res.rows_loaded == 0
    # nothing was committed; the connection is always closed
    assert conn.closed and not conn.committed


def test_load_one_target_has_no_columns(monkeypatch):
    conn = _FakeConn(
        existing_tables={("src_schema", "src_tbl")},
        columns={("src_schema", "src_tbl"): ["a"], ("tgt", "tgt_tbl"): []},
    )
    _patch_connect(monkeypatch, conn)
    res = loader.load_one("tgt", "src_schema", "src_tbl", "tgt_tbl", "replace")
    assert res.status == "error"
    assert "no columns" in res.error


def test_load_one_no_shared_columns(monkeypatch):
    conn = _FakeConn(
        existing_tables={("src_schema", "src_tbl")},
        columns={("src_schema", "src_tbl"): ["x", "y"],
                 ("tgt", "tgt_tbl"): ["a", "b"]},
    )
    _patch_connect(monkeypatch, conn)
    res = loader.load_one("tgt", "src_schema", "src_tbl", "tgt_tbl", "replace")
    assert res.status == "error"
    assert "no shared columns" in res.error
    assert res.dropped_columns == ["a", "b"]


def test_load_one_ok_replace_truncates_inserts_and_commits(monkeypatch):
    conn = _FakeConn(
        existing_tables={("src_schema", "src_tbl")},
        columns={("src_schema", "src_tbl"): ["id", "v", "legacy_only"],
                 ("tgt", "tgt_tbl"): ["id", "v", "tgt_only_28"]},
        insert_rows=42, delete_rows=0,
    )
    _patch_connect(monkeypatch, conn)
    res = loader.load_one("tgt", "src_schema", "src_tbl", "tgt_tbl", "replace")
    assert res.status == "ok"
    assert res.rows_loaded == 42                      # the INSERT rowcount, not TRUNCATE's
    assert res.dropped_columns == ["tgt_only_28"]     # 2.8-only dest col reported
    assert conn.committed and conn.closed
    # a TRUNCATE then an INSERT were actually issued
    assert any(s.upper().startswith("TRUNCATE") for s in conn.executed)
    assert any(s.upper().startswith("INSERT") for s in conn.executed)


def test_load_one_error_rolls_back(monkeypatch):
    conn = _FakeConn(
        existing_tables={("src_schema", "src_tbl")},
        columns={("src_schema", "src_tbl"): ["id"], ("tgt", "tgt_tbl"): ["id"]},
        raise_on_insert=True,
    )
    _patch_connect(monkeypatch, conn)
    res = loader.load_one("tgt", "src_schema", "src_tbl", "tgt_tbl", "append")
    assert res.status == "error"
    assert "boom" in res.error
    assert conn.rolled_back and conn.closed and not conn.committed


# --------------------------------------------------------------------------- #
# load_all — FK order, skip-missing-snapshot, stop-on-first-failure, report shape
# --------------------------------------------------------------------------- #
@dataclass
class _Spec:
    sqlmesh_view: str
    target_table: str
    write_disposition: str


@dataclass
class _Snap:
    physical_schema: str
    physical_table: str


def test_load_all_orders_results_and_skips_unresolved_views(monkeypatch):
    # three resources; the middle one has no resolved snapshot -> skipped (continue branch)
    resources = [
        _Spec("v_person", "person", "replace"),
        _Spec("v_missing", "missing", "replace"),
        _Spec("v_obs", "obs", "replace"),
    ]
    snapshots = {
        "v_person": _Snap("snap_schema", "person_snap"),
        "v_obs": _Snap("snap_schema", "obs_snap"),
    }
    calls = []

    def fake_load_one(tgt, src_schema, src_tbl, tgt_tbl, disp):
        calls.append(tgt_tbl)
        return loader.LoadResult(tgt_tbl, 5, 0.01, "ok")

    monkeypatch.setattr(loader, "load_one", fake_load_one)
    report = loader.load_all("openmrs_test", resources, snapshots)
    assert report["ok"] is True
    assert [r["target_table"] for r in report["results"]] == ["person", "obs"]
    assert calls == ["person", "obs"]               # v_missing was skipped, order preserved
    assert report["target_schema"] == "openmrs_test"


def test_load_all_stops_on_first_real_failure(monkeypatch):
    resources = [
        _Spec("v_a", "a", "replace"),
        _Spec("v_b", "b", "replace"),
        _Spec("v_c", "c", "replace"),
    ]
    snapshots = {v: _Snap("s", v + "_snap") for v in ("v_a", "v_b", "v_c")}

    def fake_load_one(tgt, ss, st, tt, disp):
        if tt == "b":
            return loader.LoadResult(tt, 0, 0.01, "error", "FK violation")
        return loader.LoadResult(tt, 3, 0.01, "ok")

    monkeypatch.setattr(loader, "load_one", fake_load_one)
    report = loader.load_all("openmrs_test", resources, snapshots)
    assert report["ok"] is False
    assert report["failures"] == ["b: error — FK violation"]
    # stopped at b -> c never loaded
    assert [r["target_table"] for r in report["results"]] == ["a", "b"]


def test_load_all_missing_in_source_is_not_a_failure(monkeypatch):
    resources = [_Spec("v_a", "a", "replace"), _Spec("v_b", "b", "replace")]
    snapshots = {"v_a": _Snap("s", "a_snap"), "v_b": _Snap("s", "b_snap")}

    def fake_load_one(tgt, ss, st, tt, disp):
        status = "missing_in_source" if tt == "a" else "ok"
        return loader.LoadResult(tt, 0 if tt == "a" else 9, 0.01, status)

    monkeypatch.setattr(loader, "load_one", fake_load_one)
    report = loader.load_all("openmrs_test", resources, snapshots)
    # a missing source does NOT stop the run and does NOT count as a failure
    assert report["ok"] is True
    assert len(report["results"]) == 2


# --------------------------------------------------------------------------- #
# repair_scaffolding_accounts — runs each DELETE, sums rowcounts, commits
# --------------------------------------------------------------------------- #
def test_repair_scaffolding_accounts_runs_all_deletes_and_sums(monkeypatch):
    conn = _FakeConn(existing_tables=set(), columns={}, delete_rows=2)
    _patch_connect(monkeypatch, conn)
    out = loader.repair_scaffolding_accounts("openmrs_test")
    # five DELETE statements (user_role, user_property, users, provider_attribute, provider)
    assert set(out["deleted"]) == {
        "user_role", "user_property", "users", "provider_attribute", "provider"}
    assert out["total"] == 2 * 5
    assert conn.committed and conn.closed
    assert all(s.upper().startswith("DELETE") for s in conn.executed)
