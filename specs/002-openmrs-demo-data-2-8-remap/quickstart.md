# Quickstart: OpenMRS Demo Data Remap (002)

**Feature**: `002-openmrs-demo-data-2-8-remap` | **Updated**: 2026-05-13

Operator walkthrough from a clean checkout to a passing import-smoke + binding + sampler run, plus the parallel OpenELIS feasibility analysis. All commands assume CWD is the harness repo root.

## 0. Prerequisites

- Docker + Docker Compose (Docker Desktop or rootless Docker on Linux)
- Java 21+ (satisfies both the HL7 FHIR Validator CLI and the chartsearchai `mvn -pl api test` validation surface)
- `uv` (managed Python; see M0 quickstart)
- `mvn` (Maven; for chartsearchai tests)
- GitHub access to the four target submodules

## 1. Initialize submodules

```bash
git submodule update --init --recursive
```

Verify:

```bash
git submodule status
# expect 4 entries: targets/chartsearchai, targets/querystore, targets/openmrs_chatbot, targets/catalyst
```

## 2. Set up the Python environment

```bash
uv sync --extra dev
source .venv/bin/activate   # or use `uv run` for each command
```

## 3. Pin OCL snapshots (out-of-band; once per accepted-mapping cycle)

```bash
# Refresh pinned CIEL + LOINC snapshots into datasets/sources/ocl/<collection>/<version>/
harness-cli ocl refresh --collection CIEL --collection LOINC
```

This is a deliberate action: it produces a new `provenance.json` checksum under each `datasets/sources/ocl/<collection>/<version>/` directory and triggers a PCCP-style change record. Subsequent transform/run/smoke/sampler stages read this pinned snapshot offline — no live OCL calls happen during the transform.

## 4. Confirm the harness target registry is healthy

```bash
harness-cli targets status
```

Expect every target to show `evidence_status`, `target_actual_sha`, and whether it's at the reviewed pin. `catalyst` should show as `scaffolding` (umbrella reference, no command yet); `chartsearchai` and `querystore` should be `development`.

## 5. Profile the source corpus + compute schema diff + estimate Liquibase cost (M2-A)

```bash
harness-cli profile --source data/large-demo-data-2-7-0.sql
```

Outputs under `artifacts/<run-id>/`:

- `profile/inventory.json` — populated tables, reference sources, locales, modules
- `schema-diff/diff.json` — diff vs the CIEL-loaded `openmrs` DB (the clean baseline; constructed by `make ciel-baseline`)
- `profile/liquibase-cost-estimate.json` — per-changeset cost estimate for the 2.7→2.8 upgrade-in-place path; flags any changeset that should be pre-staged in SQLMesh to keep SC-001's <60min budget

**Review gate (M2-A)**: an engineering reviewer confirms inventory completeness, reference-source enumeration, locale coverage, and reviews the Liquibase cost estimates to decide which changesets need pre-staging in M2-D.

## 6. Review and accept the terminology mapping (M2-C)

Two ways to land an accepted `datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json`:

1. **Start from OCL candidate-mining.** `harness-cli conceptmap candidates --profile artifacts/<run>/profile/inventory.json` writes a candidate proposal to `artifacts/<run>/conceptmap-candidates.json` using the pinned CIEL snapshot (offline). A clinically informed reviewer edits and promotes it.
2. **Hand-author.** Reviewer drafts the ConceptMap directly conforming to `contracts/conceptmap.profile.md` (FHIR R4 ConceptMap + harness extensions for `policy-bucket`, `source-record-examples`, optional `seed-augment-class` + `seed-augment-reference-term`).

Validate:

```bash
harness-cli conceptmap validate datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json
```

Behind the scenes this runs the HL7 FHIR Validator CLI on the file (FR-028 / SC-011), then runs the harness profile-only cross-element checks. Companion review document `datasets/mappings/openmrs-2.7-to-2.8.conceptmap.review.md` must exist and carry the reviewer signoff.

## 7. Author and review the SQLMesh project (M2-D)

Edit models under `datasets/transforms/sqlmesh/models/` per `contracts/sqlmesh_project.profile.md`. Every model needs `description`, a `policy_bucket` tag, audits, and a grain. Emit the seed from the accepted ConceptMap:

```bash
harness-cli conceptmap seed-emit \
  --in datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json \
  --out datasets/transforms/sqlmesh/seeds/concept_translation.csv
```

Conformance check:

```bash
sqlmesh -p datasets/transforms/sqlmesh/ parse
sqlmesh -p datasets/transforms/sqlmesh/ plan --no-prompts
sqlmesh -p datasets/transforms/sqlmesh/ run --dry-run
sqlmesh -p datasets/transforms/sqlmesh/ audit
```

All four must succeed before M2-E.

## 8. Bring up the O3 RefApp (M0 shared compose) and run the transform (M2-E)

```bash
make up                                                        # full compose stack
make ciel-baseline CIEL_VERSION=v2026-04-28                    # one-time CIEL load into openmrs
sqlmesh -p datasets/transforms/sqlmesh plan prod --no-prompts --auto-apply
sqlmesh -p datasets/transforms/sqlmesh audit                   # acceptance gate
```

Result: SQLMesh materializes the 64+ models into `refapp_28_demo` (views over physical snapshots in `sqlmesh__refapp_28_demo`). Audits enforce row-count floors, concept-translation coverage, FK closure, and policy-bucket coverage.

## 9. Load via dlt + promote (Phase 5D — M2-F entry)

The transform output lives in `refapp_28_demo` as SQLMesh views over physical snapshot tables. The dlt loader picks up from there and writes into `openmrs_test` via a two-schema architecture (`openmrs_test_dlt` is the dlt staging schema; the promote step copies clean rows to `openmrs_test`). See `contracts/dlt_pipeline.profile.md` + research.md §R-load-pattern.

```bash
make loadtest-up            # clones openmrs (CIEL canvas) → openmrs_test; creates openmrs_test_dlt
make load-test              # dlt reads sqlmesh__refapp_28_demo snapshots → openmrs_test_dlt → promote → openmrs_test
```

Then point the live RefApp backend at the loaded schema and verify:

```bash
OMRS_DB_NAME=openmrs_test docker compose -f compose/openmrs-2.8-refapp.yml up -d backend
# Wait for backend to come up (~30-60s after a recreate); Liquibase no-ops because the schema is already 2.8.

make orphan-fk-check        # FR-013 — emits artifacts/<run>/transform/orphan-fk-report.json
make import-smoke           # REST + FHIR readback against a sample of legacy patients
```

`make import-smoke` reads `openmrs_test.patient`, picks N legacy patients, and asserts each resolves via `/ws/rest/v1/patient/<uuid>` + `/ws/fhir2/R4/Patient/<uuid>` with the right demographic shape. Report at `artifacts/<run>/import-smoke/report.json` per FR-016 record-level evidence.

### 9a. Produce a portable SQL dump (for sharing)

```bash
make dump-loaded            # → artifacts/<run>/transform/refapp_28_demo.sql.gz (~39 MB)
```

Same shape as the original `data/large-demo-data-2-7-0.sql.zip` distribution. Load anywhere via `zcat refapp_28_demo.sql.gz | mariadb -u root -p` into a fresh empty MariaDB.

## 10. Translation-coverage sampler (M2-G)

```bash
harness-cli sample --seed 42 --records-per-bucket 5
```

For each policy bucket declared in the accepted ConceptMap, samples N records from the imported demo and verifies each round-trips via REST/FHIR with translated concept identity, units, value, date, linkages, and equivalence label preserved. Output: `artifacts/<run>/coverage/sample-42.json`.

## 11. OpenELIS feasibility analysis (M2-H, runs in parallel with M2-D..G)

```bash
harness-cli openelis analyze \
  --openelis-source ${OPENELIS_ROOT:-../OpenELIS-Global-2} \
  --openelis-target-version 3.2.1
```

Reads the OpenELIS Global schema directly from the sibling checkout (NOT a submodule of this harness; per user direction). Produces:

- `artifacts/<run>/openelis/feasibility.json` (per `contracts/openelis_feasibility.schema.yaml`)
- `artifacts/<run>/openelis/feasibility.md` (human-readable)
- `datasets/mappings/openmrs-2.7-to-openelis.skeleton.conceptmap.json`
- `datasets/mappings/openmrs-2.7-to-openelis.skeleton.yaml`

No OpenELIS bringup happens. Catalyst submodule (`targets/catalyst`) is referenced as the documented umbrella entry point for a future loader feature but no Catalyst code is invoked.

## 12. Finalize the run manifest (M2-Z)

```bash
harness-cli manifest finalize
```

Writes `artifacts/<run>/run_manifest.json` via `harness.metadata.RunManifest` with all M0-required fields plus the 002 extensions (per `contracts/run_manifest_002_extensions.schema.yaml`). Closes `events.jsonl` with a `run_complete` event. Validates against both the M0 schema and the 002 extensions before marking the run as ready for review.

## 13. Cleanup

```bash
harness-cli compose down --profile local
```

Artifact directory under `artifacts/<run-id>/` persists; raw clinical content stays under MariaDB volumes (gitignored).

### 13a. Reset the SQLMesh transform state (when needed)

The SQLMesh metadata schema (`sqlmesh`) and snapshot-data schema (`sqlmesh__refapp_28_demo`) can decouple — most commonly after a MariaDB container restart that reinitializes the metadata schema while leaving snapshot tables in place. The symptom is orphaned views in `refapp_28_demo.*` pointing at snapshot tables SQLMesh no longer tracks. Row counts can silently be wrong.

To recover:

```bash
make reset-transform           # drops 3 schemas, recreates the target (prompts before drop)
make reset-transform FORCE=1   # skip the interactive prompt
make reset-transform PLAN=1    # also chain `sqlmesh plan` after reset
```

After reset, re-materialize:

```bash
uv run sqlmesh -p datasets/transforms/sqlmesh plan prod --no-prompts --auto-apply
```

The `legacy_27_raw` and `openmrs` schemas are NOT touched by reset-transform — only the transform-side state.

---

## Common failure modes and where they surface

| Symptom | Where it shows | Likely cause |
|---|---|---|
| `harness-cli conceptmap validate` fails on FHIR conformance | Validator CLI output (red) | Missing required `target.equivalence` or unknown extension URL |
| `sqlmesh plan` fails on dependency closure | SQLMesh CLI output | A model references a translation entry that the ConceptMap doesn't declare |
| O3 backend never reaches healthy | Compose logs (`harness-cli compose logs backend`) | Liquibase upgrade timing out — check `liquibase-cost-estimate.json`; pre-stage the offending changeset in SQLMesh |
| Sampler reports `bucket: equivalent, records: []` | `coverage/sample-<seed>.json` | ConceptMap declares `equivalent` entries but the demo records that should round-trip aren't in the imported DB; check `orphan-fk-report.json` |
| chartsearchai tests fail | `chartsearchai-tests/results.xml` | Translated concepts don't bind to chartsearchai's expectations; check binding report first |
