# Catalyst program roadmap — authoritative plan

**Status:** The Phase 1 product foundation is substantially implemented. The
remaining work is to repair the comparison evidence, exercise the session
context behavior through the real Catalyst path, and publish the planned
three-team comparison for review. Phase 1 is exploratory validation: it does
not require a winning team, production approval, or a deployment choice.

This file is the single source of truth for Catalyst product scope, current
decisions, comparison intent, and program order. The execution sequence lives
in `specs/catalyst-phase1-qualification-remediation-roadmap.md`; its filename is
retained to avoid link churn, but its current purpose is comparison repair.
Supporting briefs and HTML artifacts preserve research context and rejected
alternatives. They do not override either active roadmap.

Exact revisions, pull-request state, test totals, and deployment details belong
in Git, the relevant pull requests, continuous integration, and the generated
evidence. They are not copied into this roadmap.

## Program order

| Phase | Product outcome | Completion rule |
| --- | --- | --- |
| **P1 — Session context** | The writer uses the same readable data surface as the human editor and can use the current instruction, prior user instructions, relevant failure information, and verified examples. Separate session guidance remains an experiment, not a required interface. | The session-context behavior works through the real Catalyst path, and the planned three-team comparison is completed and published with complete evidence and rubric-based review. A preference is optional and does not gate Phase 1 or Phase 2. |
| **P2 — Conversation mode** | A turn may answer, ask, or explain without producing SQL, using the same session state created in P1. | Scope and acceptance are set at the P2 start; P1 does not invent the complete conversation product. |
| **P3 — Dashboard workflow** | Question → queries → datasets → widgets → dashboard → Superset. | The existing Feature 008 D1e/M4 contract and browser-visible acceptance remain binding. |

WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is
scheduled as P3. P3 retains exactly these 15 active gates: T166, T147, T168,
T169, T170, T171, T148, T172, T173, T180, T181, T182, T155, T156, and T157.
P1 and P2 may prepare better queries and session state; neither may reduce or
close a P3 gate.

## Phase 1 decisions

| Area | Current direction |
| --- | --- |
| Data surface | Model and human tools can use every relation the configured read-only database role can read. Relation counts are environment observations, and metadata cannot hide a readable relation. |
| Startup and catalog changes | A database-access change refreshes the catalog; it does not by itself stop ordinary startup. A comparison records the catalog it used. |
| SQL execution | Validation is advisory. The exact user-selected SQL reaches PostgreSQL, bounded by the configured read-only account, read-only transaction, time limit, and result limit. PostgreSQL returns the result or diagnostic. |
| Experimental observations | A wrong query, database diagnostic, wrong answer, clarification, or unsupported response remains part of the experiment when its evidence is complete. |
| Environments | Local and demonstration catalog identities are recorded separately and do not have to match. |
| Interpretation | The roadmap defines no pass percentage, automatic disqualifier, ranking formula, tie-break, or required winner. Automated checks establish facts; the reader interprets the full evidence against the rubric. |
| Collection interruptions | Machine and service interruptions are recorded separately from model behavior. There is no fixed allowance and no model-quality implication. Harness code and tests own collection recovery. |
| Context | Every prior user instruction in the session is the current default. Whether separate session guidance adds useful behavior is an open research question. The first implementation supplies every eligible context item and records the actual per-model request. If that complete request does not fit, it records the capacity rejection rather than silently trimming or ranking context. |
| Independent visit check | The visit answer must answer the independent visit question without irrelevant carryover; sharing a relation or SQL form with an earlier query is not itself a failure. |
| Real database proof | Real PostgreSQL proof is required before the live comparison, not on every ordinary pull request. |
| Repository administration | Branch settings, image publishing, and similar repository operations are not Phase 1 product blockers. |

### 1. One shared readable data surface

Generation, manual editing, completion suggestions, validation, and execution
use every relation the configured read-only database role can read. A catalog
refresh reflects changes to that access without turning an observed relation
count into a product rule.

Reviewed metadata improves descriptions and warnings for known relations but
does not decide whether a readable relation is available. Published catalog v6
remains unchanged as historical evidence. The repaired experiment records the
catalog identity and readable surface it actually used.

Manual validation remains advisory. A person may run the exact SQL and receive
the database's result or diagnostic. The read-only database user, read-only
transaction, time limit, and returned-row limit are the execution boundary.
Result rows never enter model context.

The patient-name scenario must be answerable from the role-readable data.
Phase 1 does not require a particular view or schema change to provide it.

### 2. Honest terminal outcomes

The writer may return exactly three outcomes:

- `ready`: contains a query candidate;
- `needs_clarification`: contains one question and no SQL;
- `unsupported`: explains that the available data cannot answer the request
  and contains no SQL.

`rejected` remains owned by the Gateway for contract or orchestration failure;
it is not a fourth writer choice. Clarification and unsupported turns do not
execute SQL, preserve the prior selected query, and retain what the writer
returned.

### 3. Session context and the open guidance question

The writer can receive the current instruction, every prior user instruction,
relevant failure information, and verified examples from the same session.
This is what this roadmap means by retained conversation history. Raw model
replies are not replayed as trusted text; query versions, verified examples,
and failure records carry the relevant model-side state. Earlier material
cannot silently replace the current instruction.
Verified examples come only from earlier kept queries in the same session that
have an advisory-validation record and executed successfully against the same
source. Validator findings remain attached to the example but do not veto it.
The current target can never receive its own answer as an example.

The existing guidance storage or application programming interface may remain
available as an experimental seam, but Phase 1 does not require a composer
control, a Pin control, or any other user interface for it. We do not yet know
whether separate guidance is more useful than ordinary retained conversation
history.

Research on that question is separate from the core three-team comparison. It
should use nearby scenarios to compare:

1. retained user-instruction history alone;
2. explicit session guidance; and
3. durable catalog metadata or verified examples for reusable knowledge.

The experiment should decide whether explicit guidance has enough utility to
justify a product interface. General rules that should apply across sessions
are better candidates for catalog metadata or verified examples than for a
temporary session control, but that remains a hypothesis to test.

For every model call, evidence records what the model actually received and
identifies omitted material with its reason. The roadmap does not fix an item
count, request ordering, or selection algorithm. It forbids silent summary,
truncation, or substitution. Missing or inconsistent context evidence means
that case cannot support the comparison; it does not take unrelated product
features offline.

The first implementation sends all eligible context. If the Hub proves that
the exact assembled request does not fit the selected model, it records that
capacity rejection. It does not automatically remove context and retry; such a
policy can be considered later if real evidence shows that it is needed.

### 4. Complete-system comparison

The live comparison evaluates the complete Phase 1 system and the three full
model setups. It does not remove individual context features or claim that one
feature caused an observed difference.

The larger comparison runs locally on the owner's GPU. A demonstration setup
may be chosen deliberately for browser proof, but that choice is recorded as a
demo configuration and is not evidence that the setup won. Local and demo
observations are not pooled or presented as equivalent measurements.

### 5. Three model teams

| Team | Profile | Writer | Checker |
| --- | --- | --- | --- |
| Writer only | `catalyst-query-gemma-4-12b` | `gemma-4-12b-q4` | none |
| Same-family check | `catalyst-query-gemma-4-12b-q4-checked` | `gemma-4-12b-q4` | `gemma-4-12b-q4` |
| Cross-family check | `catalyst-query-gemma-4-12b-qwen2.5-14b-checked` | `gemma-4-12b` | `qwen2.5-14b` |

The exact resolved aliases and profile definitions are frozen before live
collection; substitution or switching during the comparison is not allowed.
The third team changes both the checker family and the Gemma build, so this is
a product-setup comparison rather than proof of the checker's isolated effect.

### 6. Frozen scenario set

Comparison suite v2 contains 12 scenarios and 21 evaluated user turns. Published
suite v1 remains readable and byte-identical but is not mixed into the repaired
comparison:

| ID | Turns and expected behavior |
| --- | --- |
| A1 | One ready query: CD4 count results since 2026-02-01 with patient, value, unit, and observed date. |
| A2 | One ready query: count HIV visits by encounter type since 2025-01-01, highest count first. |
| A3 | One ready query: count medication requests for female patients by medication name, excluding `do_not_perform`, highest count first. |
| A4 | One ready query: list each OpenMRS-native concept with no CIEL mapping, its name, and total observation count, highest count first. |
| M1 | The recorded `c973eeba…` medication → refinement → patient-name conversation. All three ready answers are checked, including the historically flawed opening answer. Only harmless ordering and surrounding spacing inside the unique comma-separated medication list are normalized. |
| M2 | Count medication requests by name; state “exclude `do_not_perform`”; regroup by gender; then return the ten highest medication-and-gender groups. Both later turns must honor the earlier instruction without the person restating it. The evidence records how that earlier instruction reached the model. |
| M3 | Verified CD4-count query; near-neighbor CD4-percentage query; unrelated visit-count query. The near neighbor may use the example. The visit answer must match its independent database answer without irrelevant CD4-specific assumptions. |
| B1 | “Show recent HIV results” must ask what date window and which result types; the frozen answer uses the 90 days preceding 2026-08-24 and requests CD4 count, CD4 percentage, and viral load, then the next turn must be ready and correct. |
| B2 | “Show patients with poor adherence” must ask for the definition; the frozen answer defines it as the latest antiretroviral-adherence result other than “All,” then the next turn must be ready and correct. |
| B3 | “Show patients overdue for follow-up” must ask for the date and overdue rule; the frozen answer uses 2026-03-01 and a recorded return date with no later visit, then the next turn must be ready and correct. |
| U1 | “Show each patient's home address” must return unsupported. |
| U2 | “Show the prescribing clinician's name for every medication request” must return unsupported. |

Every ready result is compared with an independent PostgreSQL answer, not SQL
text alone. Each scenario freezes the source, catalog, dataset, profile,
prompt, model, repository state, expected outcome, and answer check needed to
understand its result.

For a `ready` answer, the comparison records the validator's findings and
submits the exact query through the bounded read-only database path. It records
either the result or the database diagnostic. A bad query fails its factual
answer check but remains an observed model result when the evidence is
complete.

Each scenario retains its internal conversation. Every team receives the same
frozen suite and configuration. The suite definition and harness tests own the
collection shape; this roadmap adds no separate collection-count policy.
Collection interruptions remain separate from model observations. If the
environment prevents a complete collection, report that state plainly and let
the operator decide the next collection step.

## Phase 1 comparison and reader review

The roadmap imposes no universal percentages, automatic disqualifiers,
ranking formula, tie-break, or winner selection. For every scenario, the
report presents the complete stored conversation and model context, outputs,
selected SQL, PostgreSQL result or diagnostic, expected behavior, factual
checks, rubric observations, timings, model calls, tokens, and relevant
provenance. Automated checks establish factual observations; they do not
select a team.

The reader evaluates the complete result set against the rubric. The report
may express a preference or explain that the evidence does not support one,
but no label is required and the interpretation does not determine Phase 1
completion.

After collection, the operator may use the existing ChartSearchAI re-judging
path to apply the frozen rubric to the complete stored result set with one
chosen frontier model. One manual judge pass is the default. If another
perspective is useful, use a different model or agent and preserve its
rationale separately. Every reviewer receives the same complete stored case
evidence and the same rubric. There is no separate comparative judge with
reduced context, and judge commentary is not converted into an automatic
score, consensus, ranking, or winner.

Choosing a model setup for a demonstration is a separate practical decision.
It records what was chosen and why without claiming that the comparison proved
it superior or production-ready.

## Delivery gates

### G0 — one current planning record

The two active roadmaps agree with the decisions above. Supporting briefs and
HTML artifacts are clearly historical when they describe discarded options.
Documentation checks protect stable product boundaries. Normal owner review
and the repository's required checks apply.

### G1 — repair issue #58 — complete

The HIV concept mapping correction is merged and verified locally and on the
demo host. Its implementation, tests, and pull-request history are the detailed
record; this roadmap does not mirror them.

### G2 — trustworthy collection and evidence

Extend the existing harness path rather than creating a second runner. Each
turn has its own expected outcome, exact database execution evidence when SQL
is produced, independent answer check, context evidence, token and timing
evidence, and clear separation between model behavior and collection
interruptions. Preserve historical suite evidence under its original identity.
Recovery details live in harness code and tests rather than in product policy.

### G3 — shared data and outcome contracts

Preserve catalog v6 under its historical identity and use one role-readable
surface with patient names, advisory validation, and the three writer outcomes.
Catalog metadata may guide use but may not hide readable relations. Preserve
older request and turn readers.

### G4 — honest context and guidance research

Deliver retained user-instruction history, relevant failure information, and
verified examples with honest inclusion and omission evidence and session
isolation. Existing explicit-guidance support may remain available for
experiments, but no Pin interface is a Phase 1 gate. Compare history, explicit
guidance, and durable knowledge in separate research before choosing a
user-facing design.

### G5 — reproducible local comparison

Pass the relevant component, contract, catalog, PostgreSQL, browser, and
evidence checks on the exact code used for collection. Freeze the suite,
rubric, models, data, and environment; run the three-team comparison; publish
the complete evidence; and perform the reader review described above. Do not
publish per-change causal claims or an automatic team decision.

### G6 — real-product proof and closeout

Use an explicitly recorded demonstration setup and exercise three browser
journeys through the real Catalyst path:

1. patient-name request → ready → validate → execute → database-matching table;
2. “recent HIV results” → clarification → the frozen 2026-08-24 answer → ready,
   then refresh restores the complete timeline and selected version;
3. state “exclude `do_not_perform`” → later regroup still honors the earlier
   instruction after reload, then request patient addresses → unsupported with
   no SQL and the previous selected version preserved.

These are product-flow checks, not additional model scores or evidence of team
superiority. Phase 1 closes when the session-context behavior works through
this real path and the comparison report is published for review. Phase 2 may
proceed regardless of whether the reader expresses a team preference.

## Explicitly outside Phase 1

- production model approval or an automatic winner-selection system;
- a required composer or Pin interface before the guidance research supports
  one;
- cross-session or cross-user memory;
- an automatic system that writes or rewrites guidance;
- a vector database or new retrieval service;
- result rows in model context;
- causal claims that the integrated comparison isolates one context practice;
- branch-protection, image-publication, or similar repository administration
  as a product gate;
- any reduction or closure of the 15 Phase 3 Dashboard Builder gates.

## Earlier development comparison

The comparison published on 2026-08-25 remains useful diagnostic evidence:
<https://reports.openclinai.org/catalyst-phase1-comparison/>. It exercised 36
conversations, but later audit found that one follow-up answer check was also
applied to an earlier turn, several ready turns lacked complete independent
answer checks, and the report applied provisional percentage logic that is not
part of the current direction. Its raw results therefore do not establish a
winner or the relative strength of the three teams.

It was prudent not to deploy from that evidence. The evidence remains published
under its original suite and catalog identities and is not mixed into the
repaired comparison. The next comparison exists to complete the planned
experiment and publish a defensible result set, not to force a selection.
