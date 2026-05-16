# dlt Pipeline Profile (harness-local)

**Standard**: [dlt](https://dlthub.com/) (data load tool), Python-native ETL framework
**Engine**: dlt `>=1.0` with the `sqlalchemy` destination (Apache-2.0)
**Driver**: SQLAlchemy + PyMySQL (already pinned by the harness; consistent with SQLMesh's MySQL adapter)
**Validated by**: `dlt pipeline info`, `dlt pipeline show`, integrated row-count + content-hash checks against the SQLMesh side
**Root**: `harness/load/`

This profile mirrors `contracts/sqlmesh_project.profile.md` for the **load layer** (the second half of the SQLMesh+dlt handover; see `research.md` §R-load-pattern).

## Pipeline identity

- **Name**: `openmrs_loadback`
- **Source pattern**: read from `sqlmesh__refapp_28_demo.<resolved_snapshot_table>` via `dlt.sources.sql_database`. The `harness/load/snapshot_resolver.py` module resolves each user-facing view in `refapp_28_demo` to its underlying physical snapshot table in `sqlmesh__refapp_28_demo`.
- **Destination pattern**: `sqlalchemy` destination configured via env-injected DSN `mysql+pymysql://<user>:<pass>@<host>:<port>/<OMRS_DB_NAME>`. Default `OMRS_DB_NAME=openmrs_test` (iteration target); promotion target is `OMRS_DB_NAME=openmrs`.
- **Working directory**: `.dlt/openmrs_loadback/` (pipeline state, logs); gitignored.

## Resource conventions

- **One dlt `@resource` per logical target table**. Resource name === destination table name (e.g., resource `obs` writes to `<OMRS_DB_NAME>.obs`).
- **Primary key declaration**: every resource MUST declare `primary_key=[...]` matching the destination table's PK. Used by `write_disposition='merge'` for idempotent re-runs.
- **Write disposition policy**:
  - `'replace'` for **clinical fact tables**: `obs`, `drug_order`, `conditions`, `allergy`, `test_order`, `encounter`, `encounter_provider`, `encounter_diagnosis`. Wipe-and-reload each iteration; FKs from these always come from the same legacy corpus.
  - `'merge'` (with PK) for **lookup tables that may coexist with CIEL-baseline rows**: `concept_*` (when not skipped entirely — see below), `location`, `encounter_type`, `provider`, `role`, `privilege`, `visit_type`.
  - **`concept_*` tables are SKIPPED by default** — CIEL has already populated them via the openconceptlab module in the loadtest-up step; rewriting them risks UUID-pattern collisions per `research.md` §R-bridge-rule.
- **Resource ordering**: resources MUST be enumerated in FK-dependency order — parent tables before children (e.g., `person` before `patient` before `encounter` before `obs` before `drug_order`). dlt does not auto-resolve FK order; this is a harness responsibility.
- **Column projection**: where the 2.7-source-shape and 2.8-target-shape differ (per `artifacts/<run>/schema-diff/diff.json`), the resource MUST explicitly project columns to match the 2.8 destination schema. Default `SELECT *` is acceptable only when source/target columns match exactly (most tables, per the measured diff).

## Pipeline configuration

- **`pipelines_dir`**: `.dlt/` (gitignored).
- **`pipeline_name`**: `openmrs_loadback`.
- **`dataset_name`**: same as destination schema (`openmrs_test` or `openmrs`).
- **`progress`**: `log` for CI, `tqdm` for interactive.
- **Credentials**: read from environment variables; no secrets in code or YAML.

## Required run-manifest stamping

Every load run MUST stamp into `artifacts/<run>/run_manifest.json` (via `harness.metadata.RunManifest002Extensions`):

| Field | Source | Description |
|---|---|---|
| `dlt_pipeline_run_id` | `pipeline.last_trace.run_id` | UUID dlt assigns to the load run |
| `dlt_state_hash` | SHA-256 of `.dlt/openmrs_loadback/state.json` after run | Determinism witness across replays |
| `materialized_outputs[]` (extended) | per-resource row count + content checksum | Stamped per loaded table, mirroring the SQLMesh-side stamp |

## Conformance commands

```bash
# Discovery + schema integrity
dlt pipeline openmrs_loadback info
dlt pipeline openmrs_loadback show          # browse loaded data

# Idempotency: re-running yields no row deltas
make load-test                              # first run
make load-test                              # second run (must produce identical materialized_outputs[])

# Cross-tool consistency: row counts post-load match SQLMesh-side audit floors
docker exec harness-openmrs-db mariadb -uroot -popenmrs -e "
  SELECT 'obs' k, COUNT(*) v FROM openmrs_test.obs
  UNION ALL SELECT 'drug_order', COUNT(*) FROM openmrs_test.drug_order
  UNION ALL SELECT 'conditions', COUNT(*) FROM openmrs_test.conditions
  UNION ALL SELECT 'allergy', COUNT(*) FROM openmrs_test.allergy
  UNION ALL SELECT 'test_order', COUNT(*) FROM openmrs_test.test_order;
"
# Expect counts ≥ the audit_<mart>_row_count_min.sql floors on the SQLMesh side.
```

Any failure here disqualifies the load run from acceptance.

## Companion review document

`datasets/load/openmrs-loadback.review.md` — required alongside the pipeline code. Captures per-resource reviewer rationale (why `replace` vs `merge` for each table), FK-reconciliation decisions made during iteration (e.g., legacy-verbatim user IDs vs renumbering), known FK-orphan or schema-mismatch follow-ups, and signoff section.

## Relationship to other contracts

- **`contracts/sqlmesh_project.profile.md`** governs the transform spec (the upstream half). This file governs the load spec (the downstream half).
- **`contracts/run_manifest_002_extensions.schema.yaml`** defines the manifest fields this pipeline stamps.
- **`contracts/coverage_sample.schema.yaml`** governs the per-record sampling that runs post-load against the live RefApp; the dlt pipeline produces the substrate that sampler consumes.
