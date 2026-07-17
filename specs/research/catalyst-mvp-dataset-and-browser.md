# Catalyst MVP dataset and browser research

**Research date:** 2026-07-16
**Depth:** standard
**Audience:** technical product and validation reviewers
**Decision scope:** local synthetic data for the OpenELIS → FHIR → analytics → Catalyst → med-agent-hub path

## Executive summary

The Catalyst MVP should use a deterministic OpenELIS-native synthetic cohort,
not a direct copy of a public clinical corpus. The cohort should preserve the
shape of the local OpenMRS demo labs, use standard laboratory identifiers and
units where the installed OpenELIS catalog supports them, and deliberately
include longitudinal HIV viral-load trajectories that exercise clinically
meaningful thresholds. Every row must travel through the real OpenELIS FHIR
backfill and OHS FHIR Data Pipes path.

The UI should lead with a compact dataset overview, then a searchable and
filterable row browser. It should show what kinds of records exist, their date
range, analyte distribution, units, and a few longitudinal patterns before a
user asks a question. The browser is an orientation and evidence surface; it is
not a second analytics dashboard.

## Evidence reviewed

### Candidate data sources

- [Synthea](https://synthetichealth.github.io/synthea/) provides unrestricted
  synthetic longitudinal records and exports FHIR R4 and CSV. It is useful for
  general patient-history breadth and reproducible generation, but its output
  still needs a deterministic adapter into the exact installed OpenELIS test
  catalog.
- The [OpenMRS demo-data documentation](https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo%20Data)
  describes an anonymized corpus of roughly 5,000 patients and 500,000
  observations and warns that dataset and platform versions must match. The
  running local copy is valuable for concept-frequency and result-shape
  research, but it contains implausible dates and numeric outliers and only
  three HIV viral-load observations. It is therefore an input to fixture design,
  not a fixture to copy wholesale.
- MIMIC-IV is a rich hospital/ICU research corpus, but its credentialing and
  data-use restrictions, inpatient bias, and redistribution constraints make it
  a poor default for a self-contained local MVP. It may be useful later for a
  separately governed stress-test adapter.

### Viral-load semantics

- WHO distinguishes undetectable viral load from suppressed and unsuppressed
  viral load. Its policy brief defines unsuppressed as greater than 1,000
  copies/mL and suppressed as detected but no more than 1,000 copies/mL;
  undetectable depends on the assay used. See [WHO's viral-suppression policy brief](https://www.who.int/publications/i/item/9789240055179).
- WHO's HIV SMART Guidelines define virological failure using repeat values
  above 1,000 copies/mL around three months apart with adherence support after
  the first result. See the [WHO HIV data dictionary](https://smart.who.int/hiv/dictionary.html).
- [LOINC 20447-9](https://loinc.org/20447-9/) represents quantitative HIV-1 RNA
  viral load in serum or plasma. The installed OpenELIS demo catalog exposes a
  stable Viral Load test in `copies/ml`; the fixture records that local catalog
  identity while documenting the LOINC concept as terminology guidance rather
  than claiming an unverified direct mapping.

These sources support trajectory archetypes for suppression, persistent
unsuppressed results, rebound, low-level viraemia, and incomplete follow-up.
They do not justify clinical decision support; the MVP remains a synthetic query
validation environment.

### Browser and visualization guidance

- The [W3C WAI tables tutorial](https://www.w3.org/WAI/tutorials/tables/) calls
  for programmatic relationships between headers and cells. Its
  [caption and summary guidance](https://www.w3.org/WAI/tutorials/tables/caption-summary/)
  recommends concise captions that help users find and understand a table.
- [USWDS data-visualization guidance](https://designsystem.digital.gov/components/data-visualizations/)
  treats usability and accessibility as complementary: a visualization needs
  a plain-language takeaway and access to the underlying data.

## Local source inventory

The inspected OpenMRS demo database contains 5,284 patients and 427,874
non-voided observations. Its strongest numeric laboratory concepts include CD4
absolute count, CD4 percentage, CD8 absolute count, haemoglobin, white blood
cell count, platelets, MCV, ALT, lymphocyte count, and creatinine. Exact HIV
viral-load inventory is only three observations across three patients:

| Pseudonymous source person | Date | Value |
| --- | --- | ---: |
| 13 | 2026-01-05 | 400 |
| 4160 | 2025-10-15 | 400 |
| 6078 | 2025-09-17 | 825 |

The broader source contains dates as late as year 5025 and implausible extreme
values. Any source-derived distribution must therefore publish inclusion bounds
and rejected-row counts. No names or direct identifiers are ported.

## Recommended MVP cohort

Use a fixed seed and a versioned manifest to create:

- 96 synthetic patients;
- four longitudinal viral-load results per patient (384 results) over a
  ten-month window;
- one result per patient for eight complementary analytes supported by the
  installed OpenELIS catalog: CD4 absolute count, CD4 percentage, haemoglobin,
  platelets, WBC, creatinine, ALT, and glucose (768 results);
- 1,152 total observations, each with deterministic accession numbers, FHIR
  UUIDs, specimen receipt, completion/release timestamps, units, and a scenario
  tag in the fixture manifest;
- four balanced viral-load trajectory archetypes: sustained suppression,
  improving toward suppression, persistent unsuppressed, and rebound;
- deterministic operational edge cases such as longer turnaround, boundary
  values at 50 and 1,000 copies/mL, and deliberately absent follow-up for a
  small documented subset.

The cohort must be idempotent, schema-guarded, and loaded through OpenELIS before
FHIR backfill. Counts in the analytics mart and manifest must match exactly.

## Browser recommendation

The first screen should expose:

1. patient count, result count, date range, and number of test types;
2. analyte cards or a compact distribution table with count, patients, unit,
   minimum, median, and maximum;
3. filters for test type, date range, and pseudonymous patient identifier;
4. a paginated accessible table with patient, test, value, unit, observed date,
   issued date, and turnaround;
5. a short list of example questions derived from the visible catalog;
6. a separate profile selector and a safe reasoning trace that shows profile,
   generator/reviewer model roles, stage progression, validation checks, and
   trace identifiers without exposing hidden chain-of-thought.

## Risks and controls

- **Synthetic realism:** Values are scenario fixtures, not epidemiologic
  prevalence estimates. The manifest identifies formulas and archetypes.
- **Terminology mismatch:** OpenELIS stable GUIDs are authoritative for loading;
  external codes are documented only where verified.
- **Prompt overfitting:** Validation includes diverse questions, unsafe SQL,
  ambiguous requests, missing dates, multiple analytes, and result-shape checks.
- **False provenance:** Every run records dataset version, seed, catalog version,
  profile, model roles, prompts, code revisions, SQL candidate/review/final
  outcome, and executed row evidence.
- **Clinical interpretation:** Threshold-oriented scenarios validate data query
  behavior only and are labelled non-clinical synthetic demonstrations.

## Decision

Proceed with the deterministic 96-patient, 1,152-result OpenELIS-native cohort
and overview-first browser. Use Synthea and OpenMRS as research inputs for
breadth, not runtime dependencies. Defer MIMIC-IV integration and epidemiologic
calibration to separately governed experiments.
