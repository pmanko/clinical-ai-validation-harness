"""dlt loader for the SQLMesh → OpenMRS handover.

Per ``contracts/dlt_pipeline.profile.md`` + research.md §R-load-pattern,
this package implements the OLTP load layer of the transform pipeline:

  legacy_27_raw  →[SQLMesh]→  refapp_28_demo (snapshots)  →[dlt]→  openmrs[_test]

SQLMesh terminates at the transform spec; dlt picks up the physical
snapshot tables in ``sqlmesh__refapp_28_demo.*`` and writes them to
the live OpenMRS DB with PK-based idempotency.

Modules:

  - ``snapshot_resolver`` — map ``refapp_28_demo.<view>`` to its
    underlying ``sqlmesh__refapp_28_demo.<snapshot_table>``.
  - ``pipeline`` — the dlt pipeline definition + run entry point.
"""

from harness.load.pipeline import LoadResource, LOAD_RESOURCES, build_pipeline, run_pipeline
from harness.load.snapshot_resolver import ResolvedSnapshot, resolve_snapshots

__all__ = [
    "LoadResource",
    "LOAD_RESOURCES",
    "ResolvedSnapshot",
    "build_pipeline",
    "resolve_snapshots",
    "run_pipeline",
]
