"""SQLMesh transform orchestrator for feature 002 (T037+).

The transform engine itself is SQLMesh (`research.md` §R2). This package
contains the *thin* Python orchestrator that:

  - reads the accepted ConceptMap + seed CSVs (`harness.conceptmap`),
  - invokes `sqlmesh plan` / `sqlmesh run` / `sqlmesh audit` against the
    project at `datasets/transforms/sqlmesh/`,
  - dumps the materialized `refapp_28_demo` schema to a deterministic
    `.sql` artifact under `artifacts/<run>/transform/`,
  - stamps the run manifest with project + seed checksums via
    `harness.metadata.RunManifest002Extensions`.

The SQLMesh project structure is defined by
`specs/002-openmrs-demo-data-2-8-remap/contracts/sqlmesh_project.profile.md`.
This package does NOT reimplement transform logic — that lives in the
SQLMesh project's SQL models.
"""
