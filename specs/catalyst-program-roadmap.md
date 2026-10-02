# Catalyst comparison and context-research protocol

The Phase 1 comparison remains separately scheduled. This document owns its
experimental design, scenarios, collection and reader interpretation. The
[OpenClinAI roadmap](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md)
owns scheduling and [Catalyst delivery](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#6-catalyst-delivery) owns shared deployment
acceptance. Application behavior and future conversation scope are defined by
[the Catalyst specification](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md).
The harness consumes configured targets and supplied/observed provenance; it does
not select component pins, assemble environments or redefine product contracts.

## Experiment boundaries

- Use a prepared generic SQL-connected Catalyst target. Included reference
  sources use the selected FHIR Data Pipes → Parquet → Spark path; source setup
  and live source acceptance belong to the umbrella and product owners.
- Record each environment's actual source and readable-schema identity; local
  and demonstration environments need not match.
- Observe the product's `ready`, `needs_clarification` and `unsupported` responses.
  Contract/orchestration errors remain failures. Wrong SQL, database errors,
  wrong answers, clarification and unsupported outcomes are valid observations
  when their evidence is complete. Set availability expectations from the
  accepted readable schema at scenario-design time.
- Author, execute through Catalyst and review each ready-turn reference once at
  design time or when deliberately changed. Review non-SQL expected responses.
  The comparison does not rerun references or independently query a database.
- Automated checks establish collection/contract facts. A reader interprets the
  complete packet against one shared rubric. No numerical threshold, automatic
  disqualifier, ranking, tie-break or winner is required.
- Record service/machine interruptions separately from model behavior. Report
  unfinished collection as unfinished; no fixed allowance or invalidation rule.
- Use retained demonstration data without sensitive records. Repository settings
  and image publication are not experiment or product acceptance gates.
- One Dataset-to-Superset regression smoke supports the comparison's real path;
  it does not establish final Dashboard Builder acceptance.

## Session context and guidance research

Observe the product-owned context contract: current instruction, relevant
same-session history/failures and verified examples. Capture the actual request
and any omitted item with its reason, including explicit capacity failures.

Optional research may compare retained user-instruction history, explicit session
guidance, and durable source descriptions or verified examples. It asks whether
separate guidance has enough utility to justify a product interface; it is outside
the three-team comparison. It does not authorize cross-session/user memory,
automatic guidance writing, a vector database or another retrieval service.

## Model teams

| Team | Profile | Writer | Checker |
| --- | --- | --- | --- |
| Writer only | `catalyst-query-gemma-4-12b` | `gemma-4-12b-q4` | none |
| Same-family check | `catalyst-query-gemma-4-12b-q4-checked` | `gemma-4-12b-q4` | `gemma-4-12b-q4` |
| Cross-family check | `catalyst-query-gemma-4-12b-qwen2.5-14b-checked` | `gemma-4-12b` | `qwen2.5-14b` |

The resolved profiles and aliases are held constant during one comparison batch
and recorded. The third team changes both checker family and Gemma build, so the
comparison describes complete product setups rather than isolating one checker's
causal effect.

## Scenario set

The comparison contains 12 scenarios and 21 evaluated user turns:

| ID | Question or conversation |
| --- | --- |
| A1 | CD4 count results since 2026-02-01 with patient, value, unit, and observed date. |
| A2 | Count HIV visits by encounter type since 2025-01-01, highest count first. |
| A3 | Count medication requests for female patients by medication name, excluding `do_not_perform`, highest count first. |
| A4 | List each OpenMRS-native concept with no CIEL mapping, its name, and total observation count, highest count first. |
| M1 | Medication request -> refinement -> patient-name conversation. Review all three answers. |
| M2 | Count medication requests by name; state “exclude `do_not_perform`”; regroup by gender; then return the ten highest medication-and-gender groups. Later turns must honor the earlier instruction without repetition. |
| M3 | Verified CD4-count query; nearby CD4-percentage query; unrelated visit-count query. The visit answer must not carry irrelevant CD4 conditions. |
| B1 | “Show recent HIV results” asks for date window and result types; the supplied answer uses the 90 days preceding 2026-08-24 and requests CD4 count, CD4 percentage, and viral load. |
| B2 | “Show patients with poor adherence” asks for a definition; the supplied answer defines it as the latest antiretroviral-adherence result other than “All.” |
| B3 | “Show patients overdue for follow-up” asks for the date and overdue rule; the supplied answer uses 2026-03-01 and a recorded return date with no later visit. |
| U1 | Ask for each patient's home address. Determine the expected response from the accepted readable schema. |
| U2 | Ask for the prescribing clinician's name for every medication request. Determine the expected response from the accepted readable schema. |

After the Spark-readable source is accepted, each scenario stores only its
question or conversation, source and readable-schema reference, expected facts
or response, and shared rubric. Each run stores its actual profile, models,
prompts, repository versions, model context, selected SQL, rows or error, and
timings.

For a ready answer, the comparison records advisory findings and submits exact
selected SQL through Catalyst once. A bad query remains an observed result. The
reader compares the stored case with the static reference and rubric; the
harness does not compute factual equivalence.

Every team receives the same suite and configuration during one batch. If the
environment prevents a complete collection, report that state and let the owner
choose the next step.

## Reader review

The report presents the complete conversation, actual model context, outputs,
selected SQL, rows or database error, static reference or expected response,
rubric, timings, model calls, tokens, and recorded configuration for every case.

One deliberately initiated full-context reader pass is the default. It may be a
human or a selected frontier model using the existing ChartSearchAI re-review
capability. If another perspective is useful, run another reader with the same
case evidence and rubric and retain its separate rationale. Do not average,
score, or force consensus.

When the reader is a frontier model, the published report states that the
interpretation comes from one model-reader pass and is not independent human
review.

Choosing a model setup for a demonstration is a separate practical decision. It
records what was chosen and why without claiming the comparison proved it
superior or production-ready.

## Phase 1 completion

Phase 1 completes when:

- the generic connection and every reference source included in the comparison
  work through the real Catalyst path;
- every selected team has one complete suite;
- the reader report and linked evidence are published; and
- the owner reviews the product path and report.

A team preference is optional and does not gate Phase 1 completion or the start
of Phase 2.

## Outside Phase 1

- final Phase 2 conversation scope;
- final Phase 3 Dashboard Builder acceptance beyond the required regression
  smoke;
- production model approval or automatic winner selection;
- production authentication, authorization, row-level access, or sensitive-data
  controls;
- a connector framework, SQL translation, application relation allowlist, or
  curated warehouse;
- per-run reference execution, direct-database replay, result hashing, or
  automatic factual equivalence;
- a required Pin interface before guidance research supports one;
- cross-session or cross-user memory;
- an automatic system that writes guidance;
- a vector database or new retrieval service;
- result rows in model context;
- causal claims that the complete-system comparison isolates one context
  practice; and
- repository administration as a product gate.
