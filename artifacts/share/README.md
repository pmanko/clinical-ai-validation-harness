# OpenMRS 2.8 RefApp Demo Data (5,284 patients)

Drop-in demo data for **OpenMRS Platform 2.8 / Reference Application 3.6.0**. This is the 2.8/RefApp-compatible refresh of the well-known `large-demo-data-2-7-0.sql.zip` distributed via the [OpenMRS Demo Data wiki page](https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data). The source is **de-identified real AMPATH HIV/TB clinical data**.

## Current artifact

**`openmrs-2.8-refapp-demo-5284-patients-2026-06-15.sql.gz`** (40.9 MB, sha256 `da136fcef0d37a16c7616bc396fdd8b16fced6016debc13e205eb402851bc5c3`)

This build **supersedes** `2026-06-06` / `2026-06-04`. It adds two corrections on top of that lineage; clinical facts (obs/orders/conditions) are otherwise unchanged.

### What's new in this build

1. **Visits reconstructed.** The upstream demo (and every prior build) had **0 visit rows** — every encounter was unlinked (`visit_id` NULL). The source itself never had visits, and modern OpenMRS auto-creates a visit for every encounter (`EmrApiVisitAssignmentHandler`). This build rebuilds that layer: **14,248 visits, one per patient per calendar day**, with every one of the 14,316 encounters now linked. This unblocks OMOP `visit_occurrence` and the O3 visit-centric chart.
2. **Demographics reconciled (age + sex).** The de-identification scrambled **birthdate and sex independently of the clinical content**, producing impossible combinations (e.g. a 67 kg "3-year-old") and pediatric staging on adult-aged patients. Because the clinical data is authoritative (weights are 99.6% self-consistent per patient), age and sex are **re-derived from the clinical evidence**: age from **sex-neutral WHO weight-for-age** (pregnancy = adult floor), and sex set to **female for the 171 patients with a positive pregnancy signal**. **1,200 patients** were corrected (1,058 birthdates, 171 gender) — only those whose recorded values contradicted the evidence; the rest are untouched. Result: **0** patients with an impossible age/weight combination, **0** pregnant patients coded male, child population (<18) now **731**.

- Loads into a database literally named **`openmrs`** (the dump embeds `CREATE DATABASE openmrs; USE openmrs;` — self-contained).
- 232 tables, ~1.71M rows. Referentially clean: the orphan-FK gate checked **868 FK constraints, 0 orphans** (including the new `encounter.visit_id → visit` and `visit.*` constraints).

## How the original maps to visits

The source has flat encounters and no visit boundaries, so the visit grouping is a reviewed mapping rule (the same convention OpenMRS uses when retrofitting visits onto orphan encounters):

- **Grouping:** one visit per `(patient_id, calendar day)`. 99.1% of patient-days already hold exactly one encounter, so visits are ~1:1 with encounters (14,248 visits vs 14,316 encounters); the few multi-encounter days collapse into a single visit (matching `allowOverlappingVisits=false`). The wrapped `encounter_id`s of a visit are recoverable by `(patient_id, DATE(date_started))`.
- **visit_type** is derived from encounter type: *Adult Visit → OPD Visit (3)*; everything else → *Facility Visit (1)*. Result: 13,310 OPD + 938 Facility.
- **date_started / date_stopped** = first / last encounter of that day (closed visits, so OMOP gets a visit end date). `location`/`creator` carried from the encounters.
- **visit_id / uuid** are deterministic (row-number over the unique key; UUIDv5 over `feature-002:visit:<patient>:<day>`), so re-runs are byte-identical.

## Conditions, drugs, procedures (representation notes)

- **Conditions** are in the **`conditions` table** (4,451 rows, 171 distinct diagnoses), promoted 1:1 from the legacy `PROBLEM ADDED` obs. This is the correct O3 representation (the Conditions widget reads this table); diagnoses are intentionally **not** left as obs.
- **Drugs** are in `drug_order` (43,412), synthesized from the ARV/TB treatment obs; the questionnaire obs are retained alongside.
- **Procedures / radiology / surgical history are absent** (the source had none — only Drug + Test order types exist). Adding them is net-new synthetic content, out of scope for this build.

## Data-fidelity note (important for ETL consumers)

This is **de-identified real data**. Investigation established what is trustworthy:

- **Authoritative (clinical content):** observations (weight/vitals, pregnancy/obstetric, diagnoses), medications, and their per-patient grouping are real and internally coherent.
- **Reconstructed (de-identified demographics):** the de-identification scrambled **birthdate and sex** independently of the clinical content. They are now re-derived from clinical evidence — so **pediatric ages are physiologically grounded** (weight-for-age), **adult ages are plausible but synthetic** (assigned from the real adult-age distribution, since weight cannot pin an adult's exact age), and **sex is corrected only where clinically provable** (pregnancy → female; there are no male-specific signals, so most `gender` values are left as recorded and should be treated with caution). Patient **names are fake** (de-identified).

All corrections are deterministic SQLMesh ETL stages — a fresh `transform → load → dump` reproduces this byte-for-byte.

## Contents

| Table | Row count |
|---|---|
| `patient` (non-voided) | 5,284 |
| &nbsp;&nbsp;of which < 18 yrs | 731 |
| `visit` | 14,248 — every patient has ≥1 |
| `encounter` | 14,316 — all linked to a visit |
| `obs` | 428,013 |
| `orders` / `drug_order` / `test_order` | 44,507 / 43,412 / 1,095 |
| `conditions` (non-voided) | 4,451 |
| **Total tables** | **232** |

**Excluded** (consumer-side module tables, recreated empty on install): `chartsearchai_*`, `querystore_*`.

## Load

```bash
gunzip -c openmrs-2.8-refapp-demo-5284-patients-2026-06-15.sql.gz | mariadb -u root -p
```

The dump self-creates the `openmrs` database and toggles `FOREIGN_KEY_CHECKS=0` for the load. Verified loading clean into an empty `mariadb:10.11.7` container (~6 s).

## Source & reproducibility

Produced by the [clinical-ai-validation-harness](https://github.com/pmanko/clinical-ai-validation-harness) feature 002 pipeline (SQLMesh + dlt) from `large-demo-data-2-7-0.sql.zip`:

1. Concept identity bridge: legacy concept IDs → CIEL UUIDs → target local concept IDs.
2. 2.7 → 2.8 schema diff; typed-table promotion (obs → drug_order / test_order / conditions / allergy).
3. Uniform date transplant to a recent window; preferred-address normalization.
4. **Visit reconstruction** (`clin__visit` / `clin__encounter`) + **pediatric DOB correction** (`stg_peds_dob_correction`).

Dump via `scripts/dump-loaded.sh` with deterministic flags; see `*.provenance.json` for the exact sha256, row/table counts, and load command. See the [feature 002 spec](https://github.com/pmanko/clinical-ai-validation-harness/tree/main/specs/002-openmrs-demo-data-2-8-remap).
