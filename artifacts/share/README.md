# OpenMRS 2.8 RefApp Demo Data (5,284 patients)

Drop-in demo data for **OpenMRS Platform 2.8 / Reference Application 3.6.0**. This is the 2.8/RefApp-compatible refresh of the well-known `large-demo-data-2-7-0.sql.zip` distributed via the [OpenMRS Demo Data wiki page](https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data).

## Current artifact

**`openmrs-2.8-refapp-demo-5284-patients-2026-05-19.sql.gz`** (40.3 MB, sha256 `91c66bf4…`)

- Loads into a database literally named **`openmrs`** (the dump embeds `CREATE DATABASE openmrs; USE openmrs;` so it is self-contained — no schema choice on the consumer side).
- 232 tables, ~1.65M rows.
- Includes the mapping remediation that fixes:
  - Concept FK resolution: drug-order parent concepts now resolve through CIEL UUIDs (e.g. legacy `794` → CIEL `6689 Lopinavir / ritonavir`) instead of accidentally landing on unrelated target concepts (`794` was historically being read as the local `Hip pain` concept).
  - `drug_order.drug_inventory_id` is non-null for **all 43,412** promoted drug-order rows, backed by a deterministic synthetic concept-level drug catalog (`drug_id = 300000 + source_concept_id`).
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

**Excluded** (consumer-side modules will create their own tables on install):
- `chartsearchai_audit_log`, `chartsearchai_chat_message`, `chartsearchai_chat_session`, `chartsearchai_embedding`

## Load

```bash
# The dump self-creates the openmrs database, so the receiving instance just
# needs an empty MariaDB / MySQL with a privileged user. No CREATE DATABASE
# step on the consumer side.

gunzip -c openmrs-2.8-refapp-demo-5284-patients-2026-05-19.sql.gz | mariadb -u root -p
```

Takes ~22 seconds against an empty `mariadb:10.11.7` container.

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
--ignore-pattern 'chartsearchai_%'   # excludes consumer-side module tables
```

See `openmrs-2.8-refapp-demo-5284-patients-2026-05-19.sql.gz.provenance.json` for `sha256`, exact row counts, the remediation evidence (resolved CIEL concept IDs on a known patient + 0-failure SQLMesh audits + passing pytest evals), and ephemeral-load verification metadata.

## Source

Produced by the [clinical-ai-validation-harness](https://github.com/pmanko/clinical-ai-validation-harness) feature 002 transformation pipeline (SQLMesh + dlt), which takes the original `large-demo-data-2-7-0.sql.zip` and applies:

1. Concept identity bridge: legacy concept IDs → CIEL UUIDs → target local concept IDs (validated by `audit_concept_uuid_agreement`).
2. 2.7 → 2.8 schema diff (Liquibase changesets pre-staged in SQLMesh).
3. Typed-table promotion rules (obs → drug_order / test_order / conditions / allergy with parent/child shape preserved).
4. Drug catalog augmentation (concept-level deterministic synthetic drug rows for promoted medication orders).
5. FK closure + orphan reconciliation; no duplicate canonical facts.

Result is a deterministic, clinically-faithful 2.8/RefApp-compatible corpus suitable for development, testing, and demos. See the [feature 002 spec](https://github.com/pmanko/clinical-ai-validation-harness/tree/main/specs/002-openmrs-demo-data-2-8-remap) for details on the transformation.

