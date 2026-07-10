"""Direct loader for the SQLMesh → OpenMRS handover.

This package implements the load layer of the transform pipeline: it copies the
SQLMesh transform output straight into the OpenMRS build schema, with no dlt and
no staging schema.

  legacy_27_raw  →[SQLMesh]→  refapp_28_demo (snapshots)  →[direct loader]→  openmrs[_test]

SQLMesh terminates at the transform spec; this package reads the physical
snapshot tables in ``sqlmesh__refapp_28_demo.*`` and ``INSERT … SELECT``s them
into the live OpenMRS DB using only the OpenMRS-defined column set.

Modules:

  - ``snapshot_resolver`` — map ``refapp_28_demo.<view>`` to its underlying
    ``sqlmesh__refapp_28_demo.<snapshot_table>``.
  - ``pipeline`` — the FK-ordered load manifest + the ``run_load`` entry point.
  - ``loader`` — the per-table direct ``INSERT … SELECT`` copy.
"""

from harness.load.pipeline import LoadResource, LOAD_RESOURCES, run_load
from harness.load.snapshot_resolver import ResolvedSnapshot, resolve_snapshots

__all__ = [
    "LoadResource",
    "LOAD_RESOURCES",
    "ResolvedSnapshot",
    "resolve_snapshots",
    "run_load",
]
