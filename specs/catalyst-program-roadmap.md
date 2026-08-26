# Catalyst program roadmap

**Status:** Phase 1 generic-connection implementation and comparison remain open. Phase 2
and Phase 3 follow in that order.

This file is the single authority for Catalyst product scope, Phase meanings,
context behavior, the model-team comparison, and program order. Implementation
sequence and status live only in
`specs/catalyst-implementation-plan.md`.

## Program order

| Phase | Product outcome | Completion |
| --- | --- | --- |
| **Phase 1 — Session context** | Catalyst uses a generic SQL connection. The writer and editor share its complete readable schema and declared dialect. The writer can use the current instruction, prior user instructions, relevant failures, and verified examples. | The generic connection and selected Spark reference sources work through Catalyst, every selected team completes the comparison suite once, the full-context reader report is published, and the owner reviews it. A team preference is optional. |
| **Phase 2 — Conversation mode** | A turn may answer, ask, explain, or produce SQL while using the same session state established in Phase 1. | Scope and acceptance are set after the Phase 1 report is reviewed. |
| **Phase 3 — Dashboard workflow** | Question -> queries -> Datasets -> Widgets -> Dashboard -> Superset. | The live product is compared side by side with the binding Dashboard Builder design and all required visible behavior is accepted by the owner. |

Feature 008 owns its current product requirements and tasks. Phase 1 requires
one Dataset-to-Superset regression smoke during Phase 1 connection implementation; that
smoke does not close or reduce Phase 3.

## Phase 1 decisions

| Area | Decision |
| --- | --- |
| Catalyst boundary | Catalyst owns SQL-connected conversation, notebook, execution, results, and Dashboard Builder behavior. It does not own FHIR ingestion, a clinical warehouse, or a mandatory database engine. |
| Selected reference deployment | Each source included in the selected demo or comparison will use FHIR Data Pipes -> Parquet -> Spark SQL. Catalyst and Superset will connect as SQL clients. This path is not yet implemented or accepted. |
| Data available to the model and editor | Every table, view, column, and type readable through the configured connection. Counts are observations, not product rules. Optional descriptions cannot hide relations. |
| Session source | One source per session. A different source starts a different session. |
| SQL execution | Validation is advisory. Exact selected SQL reaches the configured connection with a time limit and returned-row limit. Catalyst records rows or the database error. |
| Experimental observations | Wrong SQL, a database error, a wrong answer, clarification, and unsupported are all valid observations when their evidence is complete. |
| Environments | Local and demonstration environments record their own connection and readable-schema identities; they do not have to match. |
| Scenario references | A ready turn's reference query is written, run, and reviewed once at design time or when deliberately changed. Clarification and unsupported turns have reviewed expected responses. The live comparison does not rerun references. |
| Interpretation | Automated checks establish collection and contract facts. A reader interprets the complete evidence against one shared rubric. There is no required percentage, automatic disqualifier, ranking formula, tie-break, label, or winner. |
| Collection interruptions | Service or machine interruptions are recorded separately from model behavior. There is no fixed allowance or automatic invalidation rule. An unfinished collection is reported as unfinished. |
| Access control | This stage uses retained demo data without sensitive records. Production identity, authorization, and row-level access are later work. |
| Repository administration | Branch settings, image publishing, and similar repository operations are not product acceptance gates. |

## Writer responses

The writer has three product responses:

- `ready`: contains a query candidate;
- `needs_clarification`: contains one question and no SQL;
- `unsupported`: explains why the readable data cannot answer the request and
  contains no SQL.

Gateway contract or orchestration failure remains a failure rather than a fourth
writer response. Clarification and unsupported turns execute no SQL, preserve
the prior selected query, and retain the returned text.

Set each data-availability expectation from the accepted readable schema when
the scenario is designed.

## Session context and guidance research

The current instruction is authoritative. A writer may receive all prior user
instructions in the session, relevant failure information, and verified examples
from earlier successful queries against the same source. Earlier material cannot
silently replace the current instruction, and the current target cannot receive
its own answer as an example.

For every model call, evidence records what was actually sent and any omitted
item with its reason. Phase 1 fixes no item count, ranking formula, or silent
truncation policy. If the complete request does not fit, record that capacity
error rather than quietly removing context and retrying.

Explicit session guidance is an optional research surface; Phase 1 requires no
Pin or composer interface. Research may compare:

1. retained user-instruction history;
2. explicit session guidance; and
3. durable source descriptions or verified examples.

That research decides whether separate guidance has enough utility to justify a
product interface. It is not part of the three-team comparison.

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
