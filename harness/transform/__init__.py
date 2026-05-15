"""SQLMesh transform orchestrator.

The transform engine is SQLMesh; the project itself lives at
``datasets/transforms/sqlmesh/``. This package is the thin Python
orchestrator that:

  - reads the accepted ConceptMap + seed CSVs (``harness.conceptmap``),
  - invokes ``sqlmesh plan`` / ``sqlmesh run`` / ``sqlmesh audit``,
  - dumps the materialized ``refapp_28_demo`` schema to a deterministic
    ``.sql`` artifact under ``artifacts/<run>/transform/``,
  - stamps the run manifest with project + seed checksums.

It does NOT reimplement transform logic — that lives in the SQLMesh
project's SQL models.
"""
