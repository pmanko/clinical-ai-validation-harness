# Load Profile (harness-local) — direct loader

> **Updated (dlt retired).** This file originally specified a SQLMesh→**dlt**→staging→promote
> handover. dlt has been removed: its differentiated features (schema inference/evolution,
> nested-JSON normalization, incremental/state loads, PK-merge) were never exercised here — the
> input is flat relational SQLMesh output and the destination is a fixed Hibernate schema we
> full-replace — while its one non-suppressible side-effect (the `_dlt_id`/`_dlt_load_id` columns)
> forced an entire parallel staging schema + a manual column-stripping copy. The load is now a
> **direct `INSERT … SELECT`** from each resolved SQLMesh snapshot into the build schema, and
> instances are **provisioned from a portable dump**, never mutated in place. Filename kept for
> reference continuity; the substance below is the current contract.

**Engine**: stdlib + PyMySQL (no ETL framework). **Root**: `harness/load/`.
**Validated by**: row-count + content-hash checks against the SQLMesh side; FR-013 orphan-FK +
completeness gates; idempotent re-run test.

This profile mirrors `contracts/sqlmesh_project.profile.md` for the **load layer** (the second half
of the transform; see `research.md` §R-load-pattern).

## Data flow

```
legacy_27_raw → [SQLMesh] → refapp_28_demo (views over sqlmesh__refapp_28_demo snapshots)
                                   │
                                   ▼  [direct loader: INSERT … SELECT]
                              openmrs_test  (build schema; CIEL baseline cloned by loadtest-up.sh)
                                   │
                                   ▼  [dump-loaded.sh — portable, module-clean, target-neutral]
                          refapp_28_demo.sql.gz   ← the deliverable
                                   │
                                   ▼  [seed-local.sh / cloud-seed.sh — restore into a fresh DB]
                              openmrs        (a fresh instance; backend boots, Liquibase reconciles)
```

There is **no staging schema and no dlt**. SQLMesh's snapshot tables are already clean relational
tables, so the loader reads each one and `INSERT … SELECT`s it (cross-schema, same MariaDB instance)
into the build schema using only the OpenMRS-defined column set.

## Loader (`harness/load/`)

- **Manifest** (`pipeline.py` → `LOAD_RESOURCES`): one `LoadResource(sqlmesh_view, target_table,
  primary_key, write_disposition)` per logical target table, enumerated in **FK-dependency order**
  (parents before children: person → patient → encounter → obs; `clin__orders` before its
  `drug_order`/`test_order` children). FK order is a harness responsibility — nothing auto-resolves it.
- **Snapshot resolution** (`snapshot_resolver.py`): each `refapp_28_demo.<view>` resolves to its
  underlying physical `sqlmesh__refapp_28_demo.<snapshot_table>`; the loader reads the snapshot
  directly (the snapshot name differs from the OpenMRS target table name).
- **Copy** (`loader.py` → `load_one`/`load_all`, pure SQL builder `_build_load_sql`):
  - **Column projection**: intersect the destination's columns with the source snapshot's. Columns
    added in 2.8 but absent in the 2.7-derived source are left to the DB default and **reported**
    (`dropped_columns`); a stray `_dlt_*` is filtered defensively.
  - **Write disposition**: `replace` → `TRUNCATE` + `INSERT` (clinical fact tables — legacy is the
    canonical history); `merge` → `INSERT IGNORE` (lookup tables that coexist with CIEL-baseline
    stock — legacy IDs that collide are skipped); `append` → plain `INSERT`.
  - `concept_*` tables are **not loaded** — CIEL already populated them in the build schema via
    `loadtest-up.sh` cloning the CIEL-loaded `openmrs` canvas (rewriting risks UUID-pattern
    collisions per `research.md` §R-bridge-rule).
  - Session: `SET sql_mode='ALLOW_INVALID_DATES', time_zone='+00:00', FOREIGN_KEY_CHECKS=0` — clinical
    tables are replayed in non-strict FK order; the FR-013 orphan-FK audit catches anything that
    should still error.

## Liquibase / module ownership (one rule)

The **OpenMRS app owns Liquibase and all module schema**. The loader and the deliverable dump are
**clinical + core data only**: `dump-loaded.sh` strips the chartsearchai module's tables AND its
`liquibasechangelog` rows, so a freshly-provisioned instance has none of that state and the module's
own Liquibase **installs it fresh on boot** — no "table already exists" race. (This is exactly the
failure the retired in-place promote produced by clobbering a running backend's schema.)

## Provisioning (never mutate in place)

- **Build**: `make loadtest-up && make load-test` → `openmrs_test`; gate with `make orphan-fk-check`
  + `make completeness-check`; package with `make dump-loaded SOURCE=openmrs_test`.
- **Serve local**: `make seed` (`seed-local.sh`) — stop backend → DROP/CREATE `openmrs` → restore the
  dump → start backend → reindex. Serves both reset-provision (`make reset && make up && make seed`)
  and reseed-in-place. `make seed FROM_SCHEMA=openmrs_test` dumps-then-seeds in one step.
- **Serve cloud**: `make cloud-seed` (`cloud-seed.sh`) — same module-clean dump, restored into a
  fresh VM-side `openmrs`.

## Conformance commands

```bash
# Run the direct loader into the build schema
make load-test                              # → openmrs_test (default)

# Row counts post-load match the SQLMesh-side audit floors
docker exec harness-openmrs-db mariadb -uroot -popenmrs -e "
  SELECT 'obs' k, COUNT(*) v FROM openmrs_test.obs
  UNION ALL SELECT 'drug_order', COUNT(*) FROM openmrs_test.drug_order
  UNION ALL SELECT 'conditions', COUNT(*) FROM openmrs_test.conditions
  UNION ALL SELECT 'allergy', COUNT(*) FROM openmrs_test.allergy
  UNION ALL SELECT 'test_order', COUNT(*) FROM openmrs_test.test_order;"

# Idempotency (slow): re-running yields no row/content deltas
uv run pytest evals/load/test_pipeline_idempotency.py -m slow

# FK integrity (FR-013): no orphans across declared FKs
make orphan-fk-check

# Patient-level REST/FHIR readback
make import-smoke

# Portable, module-clean, target-neutral demo-data dump
make dump-loaded SOURCE=openmrs_test        # → artifacts/<run>/transform/refapp_28_demo.sql.gz
```

Any failure here disqualifies the load run from acceptance.

## Schema modification policy (NONE on target)

The loader copies **rows**, never DDL: it `TRUNCATE`/`INSERT`s into the existing OpenMRS-defined
tables and never alters their shape, never touches `liquibasechangelog`/`liquibasechangeloglock`, and
never carries module tables. No `_dlt_*` column can appear in the target (there is no dlt). A schema
change to the target is exclusively the OpenMRS app's Liquibase, run at boot.

## Determinism (SC-004)

Re-running the loader on identical SQLMesh snapshots yields identical row counts and content
(`replace` = TRUNCATE+INSERT; promoted-row UUIDs are deterministic name-based UUIDs). The portable
dump is byte-stable via `dump-loaded.sh`'s deterministic mariadb-dump flags. Determinism now rests
directly on SQLMesh's fingerprinted snapshots + a deterministic copy, with no dlt pipeline state in
between.

## Relationship to other contracts

- **`contracts/sqlmesh_project.profile.md`** governs the transform spec (upstream). This file governs
  the load + provisioning (downstream).
- **`contracts/run_manifest_002_extensions.schema.yaml`** — the run-manifest fields the load stamps
  (now loader row counts / dropped-columns rather than dlt run-id / state-hash).
- **`contracts/coverage_sample.schema.yaml`** — the per-record sampling that runs post-load against
  the live RefApp; the loader produces the substrate sampler consumes.
