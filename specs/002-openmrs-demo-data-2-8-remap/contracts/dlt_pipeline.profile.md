# dlt Pipeline Profile (harness-local)

**Standard**: [dlt](https://dlthub.com/) (data load tool), Python-native ETL framework
**Engine**: dlt `>=1.0` with the `sqlalchemy` destination (Apache-2.0)
**Driver**: SQLAlchemy + PyMySQL (already pinned by the harness; consistent with SQLMesh's MySQL adapter)
**Validated by**: `dlt pipeline info`, `dlt pipeline show`, integrated row-count + content-hash checks against the SQLMesh side
**Root**: `harness/load/`

This profile mirrors `contracts/sqlmesh_project.profile.md` for the **load layer** (the second half of the SQLMesh+dlt handover; see `research.md` §R-load-pattern).

## Pipeline identity

- **Name**: `openmrs_loadback__<target_schema>` — parameterized by target so iteration runs (`openmrs_test`) and promotion runs (`openmrs`) don't share dlt state.
- **Source pattern**: read from `sqlmesh__refapp_28_demo.<resolved_snapshot_table>` via `dlt.sources.sql_database`. The `harness/load/snapshot_resolver.py` module resolves each user-facing view in `refapp_28_demo` to its underlying physical snapshot table in `sqlmesh__refapp_28_demo`.
- **Destination pattern**: `sqlalchemy` destination configured via env-injected DSN `mysql+pymysql://<user>:<pass>@<host>:<port>/<staging_schema>`. The `staging_schema` is **always** `<target_schema>_dlt` (e.g., `openmrs_test_dlt` for the `openmrs_test` target).
- **Working directory**: `~/.dlt/pipelines/openmrs_loadback__<target>/` (pipeline state, logs); gitignored.

## Two-schema architecture (mandatory)

dlt's `_dlt_load_id` and `_dlt_id` columns are not suppressible (see [dlt-hub#1317](https://github.com/dlt-hub/dlt/issues/1317) — open feature request, not a release). Writing dlt directly into OpenMRS tables would destructively mutate the Hibernate-defined schema (`_dlt_*` columns appended as NOT NULL).

The deterministic resolution:

```
sqlmesh__refapp_28_demo → [dlt] → openmrs_test_dlt → [promote] → openmrs_test
                                    (with _dlt_*)               (clean OpenMRS schema)
```

The **promote step** (`harness/load/promote.py`) reads from `<target>_dlt.<table>` and INSERTs into `<target>.<table>` using only the OpenMRS-defined column set (intersection of staging + destination, `_dlt_*` excluded). Replace-disposition tables get TRUNCATE+INSERT; merge-disposition tables get INSERT IGNORE.

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

## Performance / parallelism

- SQLAlchemy engine: `pool_size=20, max_overflow=40, pool_pre_ping=True, pool_recycle=300`. dlt parallelizes resource extraction; a smaller pool exhausts with our 32-resource load.
- Session init: `SET sql_mode='ALLOW_INVALID_DATES', time_zone='+00:00', FOREIGN_KEY_CHECKS=0;` — needed because (a) dlt sends TZ-aware datetimes that MariaDB's DATETIME can't accept with strict mode; (b) we replay clinical tables in non-FK-order (orphans then resolved on full load); orphan-FK audit (Phase 5D.4 / FR-013) catches anything that should still error.

## Conformance commands

```bash
# Discovery + schema integrity
dlt pipeline openmrs_loadback__openmrs_test info
dlt pipeline openmrs_loadback__openmrs_test show         # browse loaded data

# Cross-tool consistency: row counts post-load match SQLMesh-side audit floors
docker exec harness-openmrs-db mariadb -uroot -popenmrs -e "
  SELECT 'obs' k, COUNT(*) v FROM openmrs_test.obs
  UNION ALL SELECT 'drug_order', COUNT(*) FROM openmrs_test.drug_order
  UNION ALL SELECT 'conditions', COUNT(*) FROM openmrs_test.conditions
  UNION ALL SELECT 'allergy', COUNT(*) FROM openmrs_test.allergy
  UNION ALL SELECT 'test_order', COUNT(*) FROM openmrs_test.test_order;
"
# Expect counts ≥ the audit_<mart>_row_count_min.sql floors on the SQLMesh side.

# Idempotency (slow): re-running yields no row deltas
uv run pytest evals/load/test_pipeline_idempotency.py -m slow

# FK integrity (FR-013): no orphans across declared FKs
make orphan-fk-check

# Patient-level REST/FHIR readback
make import-smoke

# Portable SQL dump for sharing
make dump-loaded                            # → artifacts/<run>/transform/refapp_28_demo.sql.gz
```

Any failure here disqualifies the load run from acceptance.

## Schema modification policy (NONE on target)

The promote step is the architectural enforcement: **no _dlt_* columns ever appear in the OpenMRS schema**. Two cross-checks:

```bash
docker exec harness-openmrs-db mariadb -uroot -popenmrs \
  -e "SHOW CREATE TABLE openmrs_test.patient\G" | grep _dlt
# Expect: (empty output)
```

If `_dlt_*` columns appear in the target, the promote step has been bypassed and the load is unsafe to use.

## Companion review document

`datasets/load/openmrs-loadback.review.md` — required alongside the pipeline code. Captures per-resource reviewer rationale (why `replace` vs `merge` for each table), FK-reconciliation decisions made during iteration (e.g., legacy-verbatim user IDs vs renumbering), known FK-orphan or schema-mismatch follow-ups, and signoff section.

## Relationship to other contracts

- **`contracts/sqlmesh_project.profile.md`** governs the transform spec (the upstream half). This file governs the load spec (the downstream half).
- **`contracts/run_manifest_002_extensions.schema.yaml`** defines the manifest fields this pipeline stamps.
- **`contracts/coverage_sample.schema.yaml`** governs the per-record sampling that runs post-load against the live RefApp; the dlt pipeline produces the substrate that sampler consumes.
