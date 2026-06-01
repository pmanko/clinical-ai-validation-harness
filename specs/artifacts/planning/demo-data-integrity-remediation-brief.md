# Demo-Data Integrity Remediation — Kickoff Brief / Prompt

> **Use this as the context/prompt to start the fix on a fresh feature branch.** It is
> self-contained: diagnosis, root cause, scope, fix determination, acceptance, and
> references with file:line. Everything below is grounded in the live DB + the repo's
> own artifacts (no speculation).

## Mandate

The 2.7→2.8 demo dataset the harness produces is **referentially invalid** and must be
fixed at the mapper so re-loads are clean and the fail-closed integrity gate is actually
enforced. This is a blocker: it 500s real chartsearchai/FHIR flows for any patient that
carries the affected stock rows.

## Verdict — the dataset is invalid

A full orphan-FK audit of the **live importable `openmrs` DB** (the harness's own tool,
`harness/transform/orphan_fk.py`):

```
868 FK constraints checked · 12 FKs with orphans · 1,965 orphan rows
  encounter_diagnosis.encounter_id → encounter.encounter_id   562
  encounter_diagnosis.patient_id   → patient.patient_id       530
  obs_reference_range.obs_id       → obs.obs_id                451
  visit.patient_id                 → patient.patient_id        174
  patient_appointment.patient_id   → patient.patient_id        100
  + 7 smaller FKs
```
Report: `artifacts/dev-20260601-145612/transform/orphan-fk-report.json`. This is exactly
the 1,967 figure recorded as a *known, deferred* follow-up in
`datasets/load/openmrs-loadback.review.md:46-55`.

**FR-013** ("the system MUST detect … and either repair deterministically or fail the run
**before any database is offered as importable**") is violated. By the project's own rule,
this importable DB should never have shipped.

## Root cause (grounded mechanism)

The load **replaces `person`/`patient`/`encounter` (and the remapped clinical facts) with
the legacy 2.7 corpus**, giving those tables legacy's id-space — but several **2.8/CIEL
baseline "stock" tables are never wiped**, so their rows still reference the *old* baseline
id-space that no longer exists:

- `harness/load/pipeline.py:70-113` — `LOAD_RESOURCES`. `person`/`patient`/`encounter` are
  `"replace"` (lines 92-97). **`encounter_diagnosis` is absent**, as are `obs_reference_range`,
  `visit`, `patient_appointment`. There is **no `encounter_diagnosis` sqlmesh model**
  (`datasets/transforms/sqlmesh/models/clinical/` has only obs/conditions/drug_order/orders/
  test_order/allergy).
- Load runs with `FOREIGN_KEY_CHECKS=0` (`pipeline.py:214`, `promote.py:49`), so orphans
  insert silently.
- Legacy 2.7 `encounter_diagnosis` row_count = **0** (`artifacts/legacy-27-raw-baseline/
  profile/inventory.json:1475`). So the *intended* `"replace"` would have **emptied** the
  table → zero orphans. **The bug is a missing load step, not bad source data.**

This was **specified**, then **not implemented**:
- `specs/002-openmrs-demo-data-2-8-remap/tasks.md` **T051** (still `[ ]`) calls for a clinical
  model per `obs, conditions, diagnosis, allergy, drug_order, encounter_diagnosis`.
- `contracts/dlt_pipeline.profile.md:36` lists `encounter_diagnosis` among the `"replace"`
  clinical fact tables.
- `openmrs-loadback.review.md:13` marks `encounter_diagnosis → replace` ("child of encounter").

## Why it shipped (how it wasn't caught)

It *was* caught — `make orphan-fk-check` / T057 found all 1,967 — but **deferred** with the
rationale (`openmrs-loadback.review.md:55`): *"current orphans don't block the demo for the
marquee patient/obs/drug_order flow."* That held only for the signoff patient
(`dd553355`, an obs/drug_order flow); it missed that **any diagnosis-bearing patient** 500s.
And the gate is an **optional `make` target with `--allow-orphans`** (`Makefile:92-93`),
**not wired into the load**, defaulting to `openmrs_test` — so FR-013 never blocked the ship.

## Observed impact (symptoms traced to this root)

- `GET /ws/fhir2/R4/Condition?patient=…` → **500** (`fhir2` hydrates a patient's
  `encounter_diagnosis` rows → Hibernate `@ManyToOne` to a missing `Encounter` →
  `FetchNotFoundException`). Breaks the ESM patient-summary "Conditions" widget.
- chartsearchai **chat 500** for the same patients — the querystore chart build pulls the
  diagnoses, hits the same exception (confirmed: the error body contains
  `FetchNotFoundException` + "querystore").
- **48 patients** carry orphaned diagnosis rows (e.g. Aloice Beiywa Mukangu, person_id 39,
  uuid `dd5558ed-1691-11df-97a5-7038c432aabf`). Patients with no such rows work — that's why
  it looked intermittent ("worked before" = a different patient).

## Fix determination

Follow the project's own documented path (`openmrs-loadback.review.md:55`), completed and
enforced:

1. **Wipe the stock residue in the mapper.** For each of the 12 FK-affected tables
   (`encounter_diagnosis`, `obs_reference_range`, `visit`, `patient_appointment`, + the 8
   smaller ones, + the Lucene `PersonAttribute→Person` residue at line 56), **per-table**:
   - If **legacy 2.7 has rows** for it → add a staging model + `LOAD_RESOURCES` entry as
     `"replace"` (legacy ids are consistent with the replaced person/encounter id-space).
   - If **legacy has 0 rows** (stock-only residue, e.g. `encounter_diagnosis`) → either a
     0-row `"replace"` (empties it) **or** a post-clone `TRUNCATE` of stock clinical-detail
     tables in `loadtest-up.sh` **before** dlt runs. The `TRUNCATE` route is simplest for
     pure-stock tables and needs no new sqlmesh models.
   - First step of the effort: **query legacy_27_raw row counts** for all 12 tables to
     choose per-table.
   - Note: real diagnoses for demo patients already come through the **remapped `conditions`
     table** (4,451 rows) — emptying stock `encounter_diagnosis` loses nothing legitimate.
2. **Enforce FR-013 as a blocking gate.** Wire `orphan_fk.detect_orphans` into the load so an
   importable DB with any orphan **fails the run** (drop `--allow-orphans` for importable
   output; target the real `openmrs` schema, not just `openmrs_test`). Replace the
   "doesn't block the marquee flow" deferral with "must be 0 before importable."
3. **Re-audit to 0** and smoke-test the previously-broken flows.

## Acceptance / verification

- `make orphan-fk-check TARGET=openmrs` (and `openmrs_test`) → **0 orphan rows**, gate passes
  without `--allow-orphans`.
- `GET /ws/fhir2/R4/Condition?patient=dd5558ed-1691-11df-97a5-7038c432aabf` → **200**.
- chartsearchai chat for Aloice (`dd5558ed`) → **200** (no HTML 500).
- A spot-check across the 48 affected patients + a Visit/appointment FHIR read → no 500s.
- The fix is **reproducible**: a fresh `transform → load` produces a 0-orphan DB; the gate
  would have failed the old run.

## Non-goals / constraints

- Do **not** synthesize fake diagnoses or restore baseline encounters (their ids now belong
  to legacy data). Do **not** patch `fhir2`/openmrs-core mappings. Do **not** weaken the
  audit. This is the demo harness — exercise the real load pipeline (sqlmesh + dlt), no
  shortcuts.
- Branch hygiene: cut the feature branch from an up-to-date `main`.

## Related (separate workstream, in the chartsearchai fork)

The chat returns a **blank HTML 500** (not a clean error) because in
`ChartSearchAiRestController.chatStream` (`omod/.../web/rest/ChartSearchAiRestController.java:901-1014`)
`resolveOrOpenSession`/chart-build (line 902) sits in a `try` with **no catch** → an exception
there propagates uncaught to Tomcat's HTML error page, bypassing the SSE error handler. The
sync `/chat` has the same gap (wraps `chatService.chat` but not `resolveOrOpenSession`).
**Fix red-first**: wrap session/chart resolution so a build failure returns a clean SSE/JSON
error. This is independent of the data fix (the data fix removes *this* 500; the wrap makes
future integrity gaps surface as real messages, not blank 500s).

## Key references

| Area | Location |
|---|---|
| Orphan audit tool (FR-013) | `harness/transform/orphan_fk.py` |
| Load manifest (missing tables) | `harness/load/pipeline.py:70-113`, FK-checks `:214`, `promote.py:49` |
| Documented issue + fix path | `datasets/load/openmrs-loadback.review.md:13, 46-56` |
| Spec scope (intended, undone) | `specs/002-…/tasks.md` T051 `[ ]`, T057; `contracts/dlt_pipeline.profile.md:36` |
| Legacy source = 0 diagnosis rows | `artifacts/legacy-27-raw-baseline/profile/inventory.json:1475` |
| Gate is optional/not wired | `Makefile:92-93` |
| Live audit (current) | `artifacts/dev-20260601-145612/transform/orphan-fk-report.json` (1,965 / 12 FKs) |
| chartsearchai blank-500 | `…/web/rest/ChartSearchAiRestController.java:901-1014` (sync `chat`: 1022-1106) |
