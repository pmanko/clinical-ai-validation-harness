"""run_load orchestration (harness/load/pipeline.py) + the `python -m harness.load`
entry (harness/load/__main__.py).

run_load wires resolve_snapshots -> load_all -> repair_scaffolding_accounts and assembles
the run report (which resources loaded vs which views were unresolved). All three are
external/DB-touching boundaries, so they're stubbed; the REAL logic under test is the
resources_loaded / resources_skipped split (derived from which LOAD_RESOURCES views the
resolver returned) and the report assembly. The __main__ test drives the argv -> run_load
dispatch with run_load itself stubbed.
"""

from __future__ import annotations

import json

from harness.load import pipeline
from harness.load import __main__ as load_main


def test_run_load_splits_loaded_vs_skipped_and_assembles_report(monkeypatch, capsys):
    # Resolve only a SUBSET of the manifest views -> the rest must land in resources_skipped.
    all_views = [spec.sqlmesh_view for spec in pipeline.LOAD_RESOURCES]
    resolved_views = set(all_views[:3])  # pretend only the first 3 views resolved

    class _Snap:
        physical_schema = "snap_schema"
        physical_table = "snap_tbl"

    monkeypatch.setattr(pipeline, "resolve_snapshots",
                        lambda cfg: {v: _Snap() for v in resolved_views})

    captured_args = {}

    def fake_load_all(target_schema, resources, snapshots):
        captured_args["target_schema"] = target_schema
        captured_args["snapshot_views"] = set(snapshots)
        return {"ok": True, "results": [], "failures": []}

    monkeypatch.setattr(pipeline, "load_all", fake_load_all)
    monkeypatch.setattr(pipeline, "repair_scaffolding_accounts",
                        lambda schema: {"deleted": {}, "total": 0})
    # DBConfig.from_env touches env only; force a deterministic value
    monkeypatch.setattr(pipeline.DBConfig, "from_env",
                        classmethod(lambda cls, database: type("C", (), {"database": database})()))

    report = pipeline.run_load(target_schema="build_schema")

    assert report["target_schema"] == "build_schema"
    # the resolver's subset == what load_all was handed AND what's reported loaded
    assert captured_args["target_schema"] == "build_schema"
    assert captured_args["snapshot_views"] == resolved_views
    loaded_views = {spec.sqlmesh_view for spec in pipeline.LOAD_RESOURCES
                    if spec.target_table in report["resources_loaded"]}
    assert loaded_views == resolved_views
    # every manifest view not resolved is reported skipped; the two sets partition the manifest
    assert set(report["resources_skipped"]) == set(all_views) - resolved_views
    assert len(report["resources_loaded"]) + len(report["resources_skipped"]) == len(all_views)
    assert report["load"]["ok"] is True
    assert report["repair"]["total"] == 0


def test_main_run_dispatches_to_run_load_and_prints_json(monkeypatch, capsys):
    seen = {}

    def fake_run_load(target_schema="openmrs_test"):
        seen["target_schema"] = target_schema
        return {"target_schema": target_schema, "ok": True}

    monkeypatch.setattr(load_main, "run_load", fake_run_load)
    rc = load_main.main(["run", "--target", "my_schema"])
    assert rc == 0
    assert seen["target_schema"] == "my_schema"
    # the report is printed as JSON
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["target_schema"] == "my_schema"


def test_main_default_target_is_openmrs_test(monkeypatch, capsys):
    monkeypatch.setattr(load_main, "run_load",
                        lambda target_schema="openmrs_test": {"target_schema": target_schema})
    load_main.main(["run"])
    assert json.loads(capsys.readouterr().out)["target_schema"] == "openmrs_test"


def test_main_requires_a_subcommand(monkeypatch):
    # argparse `required=True` on the subparser -> SystemExit when no command is given
    import pytest
    with pytest.raises(SystemExit):
        load_main.main([])
