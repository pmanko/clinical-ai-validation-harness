# OpenMRS 2.8 RefApp Demo Data (5,284 patients)

Drop-in demo data for **OpenMRS Platform 2.8 / Reference Application 3.6.0**. This is the 2.8/RefApp-compatible refresh of the well-known `large-demo-data-2-7-0.sql.zip` distributed via the [OpenMRS Demo Data wiki page](https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data).

## Current artifact

**`openmrs-2.8-refapp-demo-5284-patients-2026-06-03.sql.gz`** (40.3 MB, sha256 `2f95ec36…`)

This is the regenerated corpus (referentially clean, fully preserved, promotable) and **supersedes** the `2026-05-19` publish.

- Loads into a database literally named **`openmrs`** (the dump embeds `CREATE DATABASE openmrs; USE openmrs;` so it is self-contained — no schema choice on the consumer side).
- 232 tables, ~1.70M rows.
- **Referentially clean**: the `harness.transform.orphan_fk --target openmrs` gate checked **868 FK constraints, 0 orphans** against this build.
- Mapping remediation in this build:
  - Concept FK resolution: drug-order parent concepts resolve through CIEL UUIDs to the correct concept instead of accidentally landing on unrelated target concepts. Verified on a known patient (Zabella Talai Halambe, `2428TU-4`): her drug-order concepts resolve to CIEL **Efavirenz** (`633…`), **Nevirapine** (`631…`), **Lamivudine** (`628…`), and **Stavudine** (`625…`).
  - `drug_order.drug_inventory_id` is non-null for **all 43,412** promoted drug-order rows, backed by a deterministic synthetic concept-level drug catalog (`drug_id = 300000 + CIEL concept numeric`).
  - Typed-table promotion writes only canonical promoted rows; no duplicate residual obs for P1/P2/P3 facts.
  - Synthetic UUIDs on promoted rows are deterministic (UUIDv5-style, name-based), so byte-identical dumps are reproducible from identical source state.

## Contents

| Table | Row count |
|---|---|
| `patient` (non-voided) | 5,284 |
| `encounter` (non-voided) | 14,316 |
| `obs` (total) | 428,013 |
| `orders` (parent table) | 44,507 |
| `drug_order` (child) | 43,412 — all with `drug_inventory_id` |
| `test_order` (child) | 1,095 |
| `conditions` (non-voided) | 4,451 |
| `allergy` (non-voided) | 2 |
| **Total tables** | **232** (full OpenMRS Platform 2.8 schema; standard module tables included) |

**Excluded** (consumer-side module tables — the consuming module recreates them empty on install):
- `chartsearchai_audit_log`, `chartsearchai_chat_message`, `chartsearchai_chat_session`, `chartsearchai_embedding`
- `querystore_bootstrap_progress`

## Load

```bash
# The dump self-creates the openmrs database, so the receiving instance just
# needs an empty MariaDB / MySQL with a privileged user. No CREATE DATABASE
# step on the consumer side.

gunzip -c openmrs-2.8-refapp-demo-5284-patients-2026-06-03.sql.gz | mariadb -u root -p
```

Takes ~20 seconds against an empty `mariadb:10.11.7` container (verified — see `verified_load` in the provenance).

The dump toggles `FOREIGN_KEY_CHECKS=0` + `UNIQUE_CHECKS=0` for the duration of the load so the order of `CREATE TABLE` within a single transaction is safe.

## Reproducibility

Dump produced via [`scripts/dump-loaded.sh`](../../scripts/dump-loaded.sh) with deterministic flags (byte-identical for identical source state):

```
--single-transaction --quick
--skip-comments --skip-dump-date --skip-tz-utc
--skip-add-locks --skip-disable-keys
--extended-insert --hex-blob
--default-character-set=utf8mb4
--databases openmrs
--ignore-pattern 'chartsearchai_%'   # consumer-side chartsearchai module tables
--ignore-pattern 'querystore_%'      # consumer-side querystore bootstrap marker
```

See `openmrs-2.8-refapp-demo-5284-patients-2026-06-03.sql.gz.provenance.json` for the exact `sha256`, row counts, remediation evidence (the orphan-FK gate result, drug-catalog coverage, and the known-patient CIEL concept resolution — each re-derived from this build), the pipeline provenance (regen commit), and the ephemeral clean-container load verification.

## Source

Produced by the [clinical-ai-validation-harness](https://github.com/pmanko/clinical-ai-validation-harness) feature 002 transformation pipeline (SQLMesh + dlt), which takes the original `large-demo-data-2-7-0.sql.zip` and applies:

1. Concept identity bridge: legacy concept IDs → CIEL UUIDs → target local concept IDs.
2. 2.7 → 2.8 schema diff (Liquibase changesets pre-staged in SQLMesh).
3. Typed-table promotion rules (obs → drug_order / test_order / conditions / allergy with parent/child shape preserved).
4. Drug catalog augmentation (concept-level deterministic synthetic drug rows for promoted medication orders).
5. FK closure + orphan reconciliation; no duplicate canonical facts.

Result is a deterministic, clinically-faithful 2.8/RefApp-compatible corpus suitable for development, testing, and demos. See the [feature 002 spec](https://github.com/pmanko/clinical-ai-validation-harness/tree/main/specs/002-openmrs-demo-data-2-8-remap) for details on the transformation.
