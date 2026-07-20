# Hub Consolidation Roadmap Status

Execution state for `MAH-CONSOLIDATION-2026-07-09-v1`.

**Status: Historical and superseded by `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`**

> **Supersession note:** This status record remains immutable evidence for completed hub work and
> approved amendments. Current execution status is maintained in
> [`openmrs-dual-provider-parity-roadmap-status.md`](openmrs-dual-provider-parity-roadmap-status.md).

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`hub-consolidation-roadmap.md`](hub-consolidation-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-09 |
| Approved roadmap SHA-256 | `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Current execution boundary | Approved Amendment A4 pre-merge safety remediation on med-agent-hub PR #13; M4 release QA remains open |
| Next protected boundary | Explicit user signoff is required before merging PR #13; User Release Signoff D remains required before release completion |
| Approved amendments | A1: Git-owned temporal-facts provenance, approved 2026-07-11; A2: 12B-first publish candidate, approved 2026-07-13; A3: stable evaluation IDs with Git-owned history, approved 2026-07-13; A4: shared medication knowledge graph and honest safety boundary, approved 2026-07-16 |

The roadmap intentionally preserves the exact approved Plan Mode body, including its
pre-approval status line. This companion file is the authoritative execution-status record.

## Approved Amendment A1: Git-Owned Temporal-Facts Provenance

The temporal facts object is an internal, same-deployment data structure. It is not an independently
deployed public wire contract and the product will not run multiple temporal-facts formats. Git and
the existing run/deployment provenance identify the implementation that produced historical data.

Required implementation:

1. The current hub produces and consumes one object named `temporal_facts`; no runtime schema
   negotiation, converter, compatibility branch, or `temporal_facts.v*` identifier remains.
2. Active prompts, tests, context-dev metadata, trace summaries, and documentation refer to
   `temporal_facts` without enumerating historical versions.
3. Hub traces record `HUB_BUILD_REVISION`; harness runs continue to record their Git SHA and pinned
   hub commit. Historical run artifacts remain immutable and are not rewritten.
4. The deterministic temporal gate consumes the current object directly and never branches on a
   temporal-facts version string.
5. A repository gate fails if active hub/harness code or current documentation reintroduces a
   `temporal_facts.v*` identifier. Explicitly historical archived run artifacts are exempt.
6. This amendment applies only to the internal temporal facts object. Public or persisted contracts
   such as `temporal_gate.v1`, `sources.v1`, and judge/report artifact schemas retain their versions.

The same correction closes the independent review findings discovered during the checkpoint:

- a claimed last-visit date fails deterministic validation when the ledger has no explicit
  Encounter/Visit record; latest clinical activity remains separately labeled;
- automatic scoping of one declared citation is allowed only for one unambiguous prose claim;
- product citation canonicalization runs after every potentially mutating temporal gate; and
- final product-path tests prove these conditions before live proof resumes.

Amendment exit criteria: no active `temporal_facts.v*` identifiers, trace provenance identifies the
hub commit, the full hub and parent suites pass, and an independent re-review reports no blocker.

Amendment result: **Pass** at med-agent-hub `4dee5a3`. The hub emits one unversioned internal
`temporal_facts` object, traces require an exact hub commit, 392 hub tests pass, 34 focused parent
tests pass, the seven-repository drift scan passes, and the independent re-review reports no blocker.

## Approved Amendment A2: 12B-First Publish Candidate

The user approved a 12B-only quality-baseline report before further E4B or medical-team iteration on
2026-07-13. This changes only the pre-final candidate composition: the established 12 scenarios,
fixtures, reference date, deterministic audit, independent judging, and publication requirements are
unchanged. E4B remains the intended fast product candidate and the medical-team profile remains an
experimental comparison, but their known structural-output failures are not hidden inside the 12B
quality-baseline report.

Amendment exit criteria: the 12B run completes all 12 cells on exact committed heads, passes the
deterministic audit with no blocker, receives an independent hash-bound judgment, and is published
with its model/profile scope stated explicitly. This is pre-final report authorization, not release
signoff.

## Approved Amendment A3: Stable Evaluation IDs With Git-Owned History

Current product backend IDs are the authoritative med-agent-hub profile IDs. The harness does not
retain duplicate aliases such as `product-12b-checked`, nor separately named current files such as a
`hub-profile-12b-candidate` copy. The stable `hub-profile-candidate` and
`hub-profile-appointment-smoke` IDs describe their current composition; Git records earlier
compositions.

Historical runs remain reproducible without preserving dead current configuration. Evaluation
evidence resolves a run's comparison-set definition from the exact harness Git SHA in that run's
manifest. Historical run artifacts and backend IDs are not rewritten. Registry definitions with no
current comparison-set consumer are deleted, and an executable test requires the live registry and
live comparison sets to have exactly matching backend-ID sets.

Amendment exit criteria: product backend IDs equal their hub `modelName`; product comparison sets
contain product profiles only; the live registry has no missing or orphaned definition; a test proves
a deleted historical comparison-set name resolves from the recorded run commit; and current config,
runner, evidence, and documentation checks pass.

## Approved Amendment A4: Shared Medication Knowledge Graph and Honest Safety Boundary

**Amendment ID:** `MAH-MEDICATION-KG-2026-07-16-v1`
**Approval:** Explicit user approval on 2026-07-16 after the research and steering session.

The hub will expose one source-neutral medication knowledge and safety capability. In the current
iteration it serves agentic ChartSearchAI knowledge and deterministic product checks. A later CDS
Hooks adapter may project the same evaluator into actual clinical decision support; CDS Hooks is not
the hub's internal data model or execution engine.

Locked decisions:

1. This is a research/noncommercial MVP. Every imported evidence item carries its own source,
   version, retrieval date, content digest, licence identifier/URL, and permitted-use metadata.
2. Initial content covers the current HIV, TB, paediatric, combination-product, and vaccine fixture
   surface plus a reviewed candidate set of common high-priority interactions.
3. Rule review states are `proposed`, `evidence_curated`, `clinically_approved`, and `retired`.
   Only `clinically_approved` rules may produce deterministic warnings or future CDS cards.
   Earlier states may appear only as explicitly labelled informational research knowledge.
4. The canonical representation is a typed property graph. Interaction rules are reified entities
   carrying participants, clinical consequence, seriousness, operational classification,
   recommended action, mechanism, modifying factors, evidence, applicability, and review state.
5. The deployable artifact is a schema-validated, checksum-bound graph package loaded into indexed,
   read-only SQLite tables inside med-agent-hub. There is no separately operated graph service.
6. Medication identity resolution and medication-exposure resolution are separate from graph query
   and rule evaluation. Fixed-dose products decompose into ingredients; vaccines and non-medication
   order concepts retain distinct types; exposure resolves to `active`, `inactive`, or `uncertain`.
7. CIEL/OpenMRS mappings include code system, code, display, map type/direction, source version, and
   local concept/drug UUIDs. Name-only matching is a disclosed low-confidence fallback. Querystore is
   one optional producer of this normalized source contract, not a hub dependency.
8. Evaluation returns `checked`, `limited`, or `unavailable`, plus package identity, coverage,
   identity confidence, issues, findings, and evidence. Missing data, ambiguous identity, uncertain
   exposure, an unavailable package, or an internal failure cannot masquerade as a clean check.

Pre-merge correction required on med-agent-hub PR #13:

- The bundled seed rules are unreviewed. Their current WHO attribution does not substantiate the
  detailed dose, interaction, contraindication, or cross-reactivity claims, and the WHO children's
  essential-medicines list is not public domain. Existing seed rules therefore remain informational
  candidates and cannot trigger product safety warnings.
- ATC remains medication classification and candidate-discovery evidence. Shared ATC hierarchy or
  curated class membership alone cannot activate a deterministic interaction, duplicate-therapy,
  contraindication, or cross-reactivity warning.
- Product envelopes preserve `safetyWarnings` for compatibility and add an explicit safety result.
  Disabled experimental legs may omit it; enabled product paths must report an honest terminal state.
- Dataset load, context construction, and validation failures report `limited` or `unavailable`
  instead of returning an indistinguishable empty-warning success.
- Hub, Java relay/persistence, ESM hydration/rendering, tests, README, environment examples, and the
  root acceptance gate must agree on these semantics.

Successor implementation after explicit PR #13 merge signoff:

1. Add manifest, node, reified-rule, evidence, terminology-mapping, and JSON Schema files plus a
   deterministic package compiler/loader and read-only SQLite query layer.
2. Add medication identity and exposure resolvers, including structured CIEL mappings, ingredient
   expansion, duplicate-order handling, and explicit uncertainty.
3. Add source-neutral `knowledge/search`, `safety/evaluate`, and `safety/manifest` capabilities and
   integrate them into product profiles without coupling the core service to ChartSearchAI.
4. Curate evidence from publication-specific WHO guidance, NIH guidance, and FDA/openFDA material.
   DDInter and the published high-priority list are discovery inputs only; Liverpool content remains
   link-only absent reuse permission; WHO SMART trial/demo artifacts cannot directly activate rules.
5. Add a later, separately approved CDS Hooks `order-select`/`order-sign` adapter over the same
   evaluator. Learned retrieval, a network graph database, and production/commercial licensing are
   out of scope for this amendment.

Executable exit criteria:

| Control | Required proof |
|---|---|
| A4.01 Review boundary | A non-approved rule cannot emit a deterministic warning or CDS finding. |
| A4.02 Honest state | Package, mapping, exposure, and runtime failures produce `limited` or `unavailable`, never an empty checked result. |
| A4.03 ATC boundary | ATC-only same-class and cross-branch examples do not emit deterministic interaction or contraindication warnings. |
| A4.04 Wire lifecycle | Safety result and warning evidence survive stream, final envelope, Java persistence, ESM hydration, and reload. |
| A4.05 Package integrity | Invalid schemas, checksums, duplicate IDs, dangling edges, and unsupported package formats fail clearly. |
| A4.06 Identity | Code-first CIEL mappings are deterministic; ambiguous name-only matches are limited. |
| A4.07 Exposure | Stopped, renewed, duplicate, missing-date, combination, vaccine, and uncertain orders have reviewed outcomes. |
| A4.08 Evidence | Every approved finding includes rule ID, medications, seriousness, action, source, evidence, applicability, and package identity. |
| A4.09 Source independence | Inline and mock alternate sources pass without Querystore running. |
| A4.10 Fixture coverage | Reviewed HIV/TB/paediatric outcomes cover the fixture combinations without treating vaccines as ordinary DDI pairs. |
| A4.11 Documentation | Hub, harness, Querystore, ChartSearchAI, ESM, PR descriptions, and active specifications describe the same boundary. |
| A4.12 Independent QA | Full suites, executable gates, DIGI-UW/code-qa, and an independent clinical-content review have no unresolved blocker. |

PR boundary: PR #13 is the existing 48-commit hub-consolidation integration branch, not a narrow
drug-safety PR. It receives only the bounded pre-merge correction above. The graph package and APIs
begin on one successor hub branch after explicit merge signoff, paired with one harness integration
branch/pin update; they are not folded into PR #13 and do not require one PR per internal milestone.

## Baseline Snapshot

The first table is the pre-fetch snapshot observed when execution began. The second records the
immutable post-fetch baseline used for M0 classification and future reconciliation.

| Repository | Checked-out SHA | Branch | Pull request state at approval |
|---|---|---|---|
| harness | `c5749e6` | `feat/simple-5arm-benchmark` | #33 open, mergeable, CI blocked |
| med-agent-hub | `fb9cdbb` | `feat/hub-context-grounding` | #12 open, clean, CI green |
| chartsearchai | `d315500` | `harness-integration` lineage | #26 draft, conflicting |
| chartsearchai-esm | `58ed478` | `harness-integration` | #12 draft, conflicting; pin not yet remote-reachable |
| querystore | `de2ba8c` | `harness-integration` lineage | #63 open, clean, CI green |
| catalyst | `3c1f1aa` | `main` | unchanged baseline dependency |
| openmrs_chatbot | `2e723f8` | `main` | unchanged baseline dependency |

### Refreshed Baseline

All configured remotes were fetched with pruning on 2026-07-09. No upstream code was merged or
rebased during M0.

| Repository | Local baseline | Integration remote | Upstream baseline | Divergence from upstream |
|---|---|---|---|---|
| harness | `d734df9` | `origin/feat/simple-5arm-benchmark` | `origin/main` at `a6f32b0` | integration branch contains the approved R0 artifact |
| med-agent-hub | `297208c` | `origin/feat/hub-context-grounding` | `origin/main` at `1c5d836` | 33 ahead, 0 behind after M0 goldens |
| chartsearchai | `d315500` | `origin/harness-integration` | `upstream/main` at `0abbd61` | 54 ahead, 13 behind |
| chartsearchai-esm | `58ed478` | `origin/harness-integration` | `upstream/main` at `3003cd2` | 39 ahead, 2 behind; local pin is now remote-reachable |
| querystore | `de2ba8c` | `origin/harness-integration` | `upstream/main` at `a10faa3` | 2 ahead, 9 behind |
| catalyst | `3c1f1aa` | `origin/main` | `origin/main` at `3c1f1aa` | 0 ahead, 0 behind; no incoming delta |
| openmrs_chatbot | `2e723f8` | `origin/main` | `origin/main` at `2e723f8` | 0 ahead, 0 behind; no incoming delta |

### M2 Post-Merge Refresh

The merged M1 parent baseline is `d08c12e`; hub PR #12 is merged on `main` at `7869c62`.
All active OpenMRS remotes were fetched with pruning before M2 edits.

| Repository | M2 local baseline | Refreshed upstream | Divergence and PR state |
|---|---|---|---|
| chartsearchai | `d315500` | `upstream/main` at `5223f92` | 54 ahead, 14 behind; PR #26 open, mergeability indeterminate |
| chartsearchai-esm | `58ed478` | `upstream/main` at `3003cd2` | 39 ahead, 2 behind; PR #12 open and conflicting |
| querystore | `de2ba8c` | `upstream/main` at `a10faa3` | 2 ahead, 9 behind; PR #63 head `fb50dd9` clean before rebase |

### M2 Reconciled Heads

| Repository | Tested head | Reconciliation result |
|---|---|---|
| med-agent-hub | `bbb369c` | PR #13 ports drug-safety follow-through, requires explicit kilogram units, enforces every product envelope, and selects available defaults in the hub |
| chartsearchai | `e6bb4de` | PR #26 is a fixed-endpoint hub relay, persists interrupted In-Depth and safety warnings, and preserves terminal In-Depth across a missing final envelope |
| chartsearchai-esm | `38a8ce3` | PR #12 excludes progressive preview, uses only hub-authoritative defaults, and prevents interrupted In-Depth from hydrating as pending |
| querystore | `3f54b8b` | PR #63 rebased onto upstream `a10faa3` without a feature-tree change |

### M3 Remediation Heads

| Repository | Committed head | Result |
|---|---|---|
| med-agent-hub | `021e305` | All prior temporal, evidence, review, and nested-envelope remediation plus exact stage-local context fitting for Answer review/retry and In-Depth synthesis/review/retry, structured `insufficient_context` outcomes, complete bounded citation-grounding batches, type-confirmed repair or withholding of malformed product tables, canonical mapping-fact grounding, block-scoped table citation usage, and one canonical stage-timing trace schema. Reviewer findings are accepted only when the reported wrong fragment exists in the reviewed draft; mixed localized/unlocalized rewrites cannot ship. Temporal future-event checks bind claims to their date and distinguish historical, negated, and current scheduling language. Exact claim-and-source-set matches may consume deterministic temporal pass evidence; richer claims remain semantically grounded. Grounding failures are grouped by claim/source set, compatibility confidence follows terminal validation state, and duplicate validation issues are removed structurally. Stage durations close before public SSE yields so client backpressure is excluded; 454 tests pass. |
| chartsearchai | `550acd0` | Dead relay services removed; authoritative hub wire, audit identity, interruption state, and no-review grounding persistence covered; 88 tests pass |
| chartsearchai-esm | `b3ad02d` | Validation interruption, feedback retry, no-review preemption, and resolved/unresolved evidence UX corrected; 182 tests plus lint/build pass |
| querystore | `37b64ae` | One shared guard serializes global and type-scoped maintenance generations; overlapping requests return `409`, the helper trusts the server's terminal generation once, and preflight/reindex consume the same drift policy. The full 512-test suite passes with two optional model-eval skips. |

### M4 Release-Simplification Heads

| Repository | Tested implementation head | Result |
|---|---|---|
| harness | `14aa1fd` | Pins the tested companion heads, publishes the judged small-model comparison, records the cache/reasoning follow-up, and classifies the latest Catalyst hub-integration delta without adopting its unsafe floating/default-revision setup. |
| med-agent-hub | `af30dc5` | Current profile/stage engine, temporal enforcement, final grounding, context contracts, exact stage trace, and token-count transport retry. PR #13 is at this head. |
| chartsearchai | `7b91ed1` | Current thin fixed-endpoint hub relay and persistence contract. Upstream PR #26 is at this head. |
| chartsearchai-esm | `3ac24b3` | Current hub-owned profile discovery, staged lifecycle, flagged-output review, and evidence UX. Upstream PR #12 is at this head. |
| querystore | `dd2da77` | Current guarded patient-record source and portable dump/index support. Upstream PR #63 is at this head. |

The companion set is deployed in one reviewed order: med-agent-hub wire/profile release,
ChartSearchAI relay, ESM consumer, then parent pins/configuration. This avoids an indefinite
mixed-version compatibility layer while ensuring each consumer lands after its provider contract.
The harness status-only commit following `14aa1fd` does not change runtime behavior; the generated
relay proof records the exact final harness commit rather than relying on this prose table.

Local validation on these heads, including the release-proof audit remediation: parent 791 passed
with 35 environment-dependent skips and four deselections; ChartSearchAI 76 passed through the
complete Maven reactor; ESM 191 passed plus typecheck, lint, and production build;
med-agent-hub 502 passed; Querystore 512 passed with two optional model-evaluation skips; and the
seven-repository documentation scan passed. Parent PR #35 CI is green at exact head `14aa1fd`.
Hub #13, ChartSearchAI #26, ESM #12, and Querystore #63 are mergeable at the heads above with all
required checks green; branch-policy deploy/release jobs are the only skips.

## Roadmap Validation

Validation was run after the approved body was copied and before implementation work began.

| Check | Result |
|---|---|
| Approved-body integrity | Pass: SHA-256 is `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Required structure | Pass: 10 numbered sections, 24 acceptance gates, and 6 execution milestones |
| Local references | Pass: all 21 checked local links resolve from the roadmap location |
| Wrapper contamination | Pass: no `<proposed_plan>` wrapper tags were copied |
| Artifact index | Pass: roadmap and status are linked from `specs/artifacts/README.md` |
| Supersession | Pass: the June lane roadmap is explicitly marked historical and superseded |
| Remote reachability | Pass: R0 commit `d734df9` and ESM pin `58ed478` are reachable on their integration remotes |

## Upstream Disposition

Disposition status: Complete

`Keep` means replay the upstream change during M2. `Port` means preserve only the durable behavior
or documentation in its new owner and verify it there. `Exclude` means do not replay the change
because it conflicts with the approved architecture. The complete fetched deltas are listed below.

### Classified Upstream Snapshot

The gate binds each disposition inventory to a fixed baseline and classified upstream head. It
fails if any tracked upstream ref advances until the new commits are classified and this snapshot
is explicitly updated.

| Repository | Upstream ref | Baseline | Classified head | Inventory |
|---|---|---|---|---|
| Harness | `origin/main` | `d08c12e` | `d08c12e` | No incoming delta after the merged M1 baseline |
| med-agent-hub | `origin/main` | `7869c62` | `7869c62` | No incoming delta after merged hub PR #12 |
| ChartSearchAI | `upstream/main` | `d315500` | `5223f92` | Disposition table below |
| chartsearchai-esm | `upstream/main` | `58ed478` | `3003cd2` | Disposition table below |
| Querystore | `upstream/main` | `de2ba8c` | `577db52` | Disposition table below |
| Catalyst | `origin/main` | `3c1f1aa` | `27ad2aa` | Disposition table below |
| openmrs_chatbot | `origin/main` | `2e723f8` | `2e723f8` | No incoming delta |

### ChartSearchAI (`d315500..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `e16e93d` | Exclude | Embedded native-inference GPU documentation conflicts with G15/G19. |
| `b0c7abc` | Exclude | Progressive preview adds Java-owned inference orchestration and a provisional UI answer, both explicitly removed by G15/G17. |
| `49bf7a9` | Exclude | Patient-chart KV prewarm and bundled-engine lifecycle conflict with hub-owned readiness and the thin relay. |
| `cc3279a` | Exclude | Its core-event migration only feeds the excluded local index/prewarm path; no relay-owned behavior remains to port. |
| `f72bb89` | Exclude | Comment-only correction applies to services removed with the excluded prewarm/index path. |
| `65a76ce` | Keep | Preserve the Reference Application `3.7.0-rc.2` standalone baseline and verify it independently from the 2.8 data-remap contract. |
| `e9189cf` | Exclude | Documents the excluded Java prewarm global-property family. |
| `c27a41e` | Port | Move durable drug-KB demo guidance to med-agent-hub/harness ownership; do not restore Java KB ownership. |
| `ed5a153` | Port | Preserve the demo-patient naming correction with the ported guide. |
| `1b7c53e` | Port | Preserve the neutral patient identifier with the ported guide. |
| `e4dcf81` | Port | Translate bundled/custom KB wording to the hub's curated JSON and WHO-ATC sources. |
| `5678a36` | Port | Preserve the useful KB entry-schema reference against the hub schema. |
| `0abbd61` | Port | Move the demo override fixture to the hub/harness only if it passes the hub drug-safety contract. |
| `5223f92` | Port | Preserve its current-Core activator-test repair on the Java baseline; port weight-aware dosing, curated cross-branch reactivity groups, prose warnings, and null/fail-safe hardening to med-agent-hub before keeping Java drug ownership deleted. |

### ChartSearchAI ESM (`58ed478..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `dc2d5f7` | Exclude | Progressive provisional-answer rendering conflicts with the committed fast Answer plus explicit checking lifecycle. |
| `3003cd2` | Keep | Replay the corrected O3 contributing link in the rebuilt integration branch. |

### Querystore (`de2ba8c..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `c7e094f` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `cdc722c` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `796ff92` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `0f80220` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `c8a5922` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `0d40fba` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `452f504` | Keep | Review-skill source-verification rule; rebase with no runtime impact. |
| `a5ea7a9` | Keep | Adds an OpenMRS module-review skill only; rebase with no runtime impact. |
| `a10faa3` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `4f7b347` | Keep | Review-skill workflow update only; rebase with no runtime impact. |
| `577db52` | Keep | Review-skill hardening only; rebase with no runtime impact. |

### Catalyst (`3c1f1aa..origin/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `2422cfa` | Keep | Contributor/environment instructions only; no runtime integration behavior. |
| `04a58dd` | Port | Preserve the one-command OpenELIS + Catalyst + med-agent-hub goal, but do not advance the tested pin: the compose build omits the required 40-character `HUB_BUILD_REVISION`, so the current hub fails startup validation. A follow-up must pin the hub source, pass its exact revision as a build argument, and prove profile readiness rather than health alone. |
| `66bc007` | Port | Preserve optional Querystore configuration and a single hub endpoint, but replace the floating `MED_AGENT_HUB_REF=main` checkout and document that the current scripts merely co-locate the service; they do not yet connect Catalyst report requests to a hub profile. |
| `27ad2aa` | Port | Merge commit for the two full-stack changes above. Keep the current Catalyst submodule pin until the provenance/readiness fixes are reviewed and tested in Catalyst rather than importing a known-broken startup path into this release. |

## M0 Verification

| Check | Result |
|---|---|
| Parent local CI | Pass: 561 passed, 37 environment-dependent skips, 3 slow-test deselections; no failures |
| Parent diff coverage | Pass: 93%, above the required 90% threshold; router policy is 97% covered |
| Parent remote CI | Pass: PR #33 `pytest-and-diff-coverage` succeeded at `d658d9b`; branch is mergeable |
| Hub local CI | Pass: 198 tests, including five byte-exact pre-refactor output contracts |
| Hub remote CI | Pass: PR #12 unit/contract and Docker checks succeeded at `297208c`; branch is mergeable |
| Pin reachability | Pass: every root submodule pin is contained by a fetched remote branch |
| Documentation drift | Pass: all seven repositories scanned; 19 historical marked files allowed |
| Red-first gate matrix | Pass: G01-G24 are emitted exactly once and any fail/pending result makes the script nonzero |
| Scope boundary | Pass: M0 changed tests, controls, status, and one reviewed harness bug; no M1 hub architecture implementation began |

The independent M0 review initially found that a remote endpoint carrying a hub-shaped model ID
could manage the local llama router, that tests preserved that behavior, and that G03/test coverage
could report stronger evidence than they actually checked. Commit `d658d9b` remediates those findings:

- router management now depends on an explicitly local endpoint, and a remote endpoint ignores even
  an explicit local-router residency cap;
- G03 validates each incoming SHA inside its repository-specific disposition section across the
  parent and all six submodules;
- the gate test executes the real shell matrix instead of checking source text alone; and
- the documentation-drift verifier explicitly recognizes architecture-verifier scripts as checks,
  not current-architecture claims.

The independent re-review found no remaining M0 blocker. It confirmed that batch/SSE convergence is
M1 G04 work, while M0 G06 correctly freezes the existing raw-leg batch envelopes before refactoring.

## M1 Verification

med-agent-hub PR #12 was squash-merged to `main` as `7869c62`. Its tree is byte-identical to the
tested consolidation/review head `31e6037`. It replaces the
flag-driven runner matrix with compiled profiles and one stream-and-drain stage engine, adds the
provider-neutral evidence ledger and exact context selector, enforces Answer and In-Depth safety,
and deletes the unused A2A/MCP/SDK runtime. The commit removes 8,594 lines and adds 7,992, a net
reduction of 602 lines while adding the required context and safety contracts.

| Check | Result |
|---|---|
| Hub unit/contract/integration suite | Pass: 246 tests; one third-party Starlette/httpx deprecation warning |
| Parent full suite | Pass: 569 passed, 37 environment-dependent skips, 3 slow-test deselections |
| Raw-leg compatibility | Pass: bridge and byte-exact golden suites remain green |
| Context quality | Pass: 12 cells, 48/48 required sources, 100% recall; 4 full and 8 selected contexts |
| Exact token budgets | Pass: measured inputs 16,226-20,478 tokens against a 20,480-token input limit |
| Proof integrity | Pass: artifact validates current comparison-set, hub-code, and router-config hashes |
| Documentation drift | Pass: all seven repositories scanned; 19 marked historical files allowed |
| Hub-scope acceptance gates | Pass: G04-G14 all green; G15 onward remain protected M2-M4 work |
| Remote reachability | Pass: hub merge commit `7869c62` is the head of `origin/main` |

The first independent M1 review reproduced seven blockers that the original checks had missed:
task-local budget loss between streamed events, inherited In-Depth grounding verdicts, a fallback
without temporal metadata, hidden product envelopes without exact budgets, a parallel team KB path,
a stale/weak context proof, and duplicated product/review-leg rewrite logic. All seven were converted
into runtime fixes and regression tests. A fresh independent reviewer reran those repros and found no
remaining blocker; its G04-G14 table is entirely green.

Copilot's merge review then identified four configuration-edge findings. Commit `31e6037` sends
backend bearer authentication during profile discovery, removes invented OpenMRS administrator
credentials, rejects partial Querystore configuration at startup, preserves explicit source
failures, and corrects the stale empty-chart docstring. The paired parent change removes Compose
credential defaults and requires a least-privileged `Get Patients` service account. Local hub and
parent suites pass. Hub unit/contract and Docker checks are green on the tree-identical tested head
`31e6037`; parent GitHub Actions run `29121901758` passed the full harness suite and changed-line
coverage on `59c2df4`. PR #12 was then squash-merged as `7869c62` with no tree delta.

The first refreshed parent PR #33 run after M1 failed because GitHub Actions checked out the parent
without submodules while run metadata now resolves authoritative profile configuration from the
pinned hub. The production behavior and local submodule-backed test passed; the submodule-free CI
copy emitted an empty frozen arm configuration. The follow-up makes checkout recursive while keeping
test execution scoped to the parent with `--ignore=targets`, and adds direct tests for the context
quality proof command. Local CI-equivalent results are 567 passed, 37 skipped, and 3 deselected, with
93% changed-line coverage. GitHub Actions run `29119406818` passed both the full harness suite and
changed-line coverage on commit `a2af5fa`. The run reported a non-blocking deprecation annotation for
Node 20-based action runtimes; GitHub currently forces those actions to Node 24.

## M2 Verification

The OpenMRS integration branches were rebuilt from current upstream rather than merging the old
integration histories. Safety backup tags and separate rebuild branches were pushed before the
existing PR heads were updated with exact force-with-lease checks.

| Check | Result |
|---|---|
| Hub drug-safety follow-through | Pass: 263 tests; weight observations require explicit kilogram units; every product envelope enforces temporal checks; authoritative available-default selection passes |
| ChartSearchAI module | Pass: clean packaged OMOD; 83 current tests with no failures, errors, or skips; pending interruption, terminal EOF, and safety-warning reload are covered |
| Thin relay boundary | Pass: no bundled inference, Java stage decomposition, Java grounding/safety/context pipeline, Querystore dependency, client endpoint switching, or bundled serving weights |
| ESM contracts | Pass: TypeScript and lint clean; 173 tests; production build succeeds with the existing asset-size warning only |
| Profile discovery | Pass: product-only metadata, authoritative labels/default, unavailable-state handling, and profile-only request tests |
| Lifecycle persistence | Pass: fast Answer, validation update, In-Depth, same-message update, hydration, multi-turn, and cancellation unit/contract tests |
| Querystore PR #63 | Pass: rebased onto all nine classified upstream commits; 471 tests with no failures/errors and two optional-model eval skips |
| Documentation drift | Pass: all seven repositories scanned; 19 marked historical files allowed |
| Remote PR CI | Pass at exact heads: parent `f54442a`, hub `bbb369c`, ChartSearchAI `e6bb4de`, ESM `38a8ce3`, and Querystore `3f54b8b`; all required checks are green |
| Stage-refactor matrix | Pass for all M2-owned checks at the reconciled heads; only the live multi-turn/preempt checks reserved for M3 are pending because `RUN_E2E=1` was not set |
| Independent review | Pass after remediation: the targeted re-review found no blocker, reran 11 focused Java tests, and confirmed pending interruption plus `indepth_done`/`indepth_error` EOF semantics; the exact-head fix is `e6bb4de` |

## M3 Verification

| Check | Result |
|---|---|
| Canonical local startup | Pass through `make chartsearchai-local` on implementation head `14aa1fd`, hub `af30dc5`, ChartSearchAI `7b91ed1`, ESM `3ac24b3`, and Querystore `dd2da77`, with every source tree clean. The stable startup verified the router and hub, served exact-provenance Java/ESM artifacts, configured the fixed hub relay, selected `single-e4b-checked`, and completed a real persisted relay/hydration probe. The Answer appeared in 14.1 seconds; its unsupported optional In-Depth draft was correctly withheld as `needs_review`, and final history hydration was byte-identical. The generated relay artifact, refreshed after this status-only update, is authoritative for the exact final harness commit. |
| Local patient source | Pass: the generated `med-agent-hub` OpenMRS user has only the `Get Patients` privilege and returned records through the Querystore adapter |
| Default profile discovery | Pass: `single-e4b-checked` is available, authoritative, human-readable, and marked default; the ESM picker renders hub profile metadata |
| Deterministic local checks | Pass on the committed companion trees: 467 hub tests; 512 Querystore tests with two optional model-dependent skips; 182 ESM tests plus lint/build; 88 ChartSearchAI tests through the complete Maven reactor; and 693 parent tests with 35 expected skips and 4 deselections. The real MariaDB portable-dump round-trip and two Chromium timing-UX tests also pass. Five clean-shell subprocess tests prove operational scripts locate the repository without ambient `PYTHONPATH`. The parent suite required normal macOS process/semaphore permissions for its existing SQLMesh and Playwright tests. |
| Current integration rehearsal | Pass on companion heads hub `af30dc5`, ChartSearchAI `7b91ed1`, ESM `3ac24b3`, and Querystore `dd2da77`: 502 hub tests; the complete ChartSearchAI Maven reactor; 191 ESM tests plus typecheck, lint, and production build; 512 Querystore tests with two optional-model skips; and 788 parent tests with 35 expected skips and four deselections. The restricted parent run failed only where macOS blocked local sockets, semaphores, Chromium, or Maven's user cache; the identical suites passed with normal test permissions. |
| Stage observability | Pass at hub `021e305`: every configured stage records elapsed time plus completed/failed/cancelled outcome in one schema; cancellation and context-source failures reach the normal trace; timings close before SSE delivery; dashboard and report tests render status plus observed/expected coverage. The focused run includes one human-readable `team-med-checked` arm. |
| Reindex ownership | Pass at Querystore `37b64ae`: one shared guard allows only one queued/running global or type-scoped maintenance generation; overlaps receive `409`. The stable helper relies on the server-owned generation and terminal state, then applies the same drift policy as preflight; it has no second local lock or settling heuristic. |
| Product Answer contract | Pass in code at hub `021e305`: product profiles always apply the hub-owned strict `chart_answer` schema, including when a caller supplies a conflicting `response_format`; raw low-level legs remain caller-controlled. Dynamic table keys are checked after generation, with only type-confirmed date/weight flattening repaired and ambiguous blocks withheld. Exact stage accounting now covers Answer plus every In-Depth subcall, and nested table refs remain scoped to their cells. Reviewer findings must localize to reviewed content before they can change status or authorize a rewrite. Grounding failures cannot coexist with green compatibility confidence, and identical lifecycle issues are emitted once. ChartSearchAI `9930139` preserves the full hub wire for synchronous clients. |
| Relay duration boundary | Pass in code at ChartSearchAI `9930139`: live run `6cbae7f4` proved the old 300-second whole-profile request timeout could discard a completed 12B Answer during the slower In-Depth tail and trigger four full-profile retries. Hub relay requests now have no arbitrary total-duration cutoff; hub stage/model controls and disconnect cancellation remain the execution bounds. A Java request contract and G15 deletion check prevent regression. |
| Compiled execution plan | Pass with a simpler implementation: `StagePlan` is the named immutable tuple used by `Profile.stages` and consumed directly by runtime. There is no second wrapper object, accessor, or duplicate execution representation. |
| Product temporal anchor | Pass in code and live product trace: product profiles default to wall-clock today in the configured clinical/site timezone (`2026-07-10` for the Honolulu host while the container was on UTC July 11), a fixed `HUB_ANCHOR=2026-06-20` remains authoritative for evaluation, and low-level experimental legs retain latest-record behavior when no anchor is supplied. The engine resolves this date once and shares the same ISO value with drug safety and temporal facts. |
| Temporal/In-Depth remediation | Pass in code and adversarial review: table rows preserve date/value associations; every selected numeric claim is checked against the full series ledger; ranges, ordinal pairing, mixed measurements, and Unicode clinical-unit typography are covered; malformed citations fail closed; safe grouped citations are canonicalized before review; partially rejected sections preserve accepted claims; only a total rejection permits one traced retry; lifecycle-wide removals, reasons, and audit counts survive the product envelope; uncited or unsafe claims are withheld; and non-substantive Answers deterministically withhold In-Depth. |
| Citation-set grounding | Pass: claims supported by multiple citations are checked against a bounded combined source set; claim/path-level checks are retained; mixed, unchecked, and unsupported In-Depth support cannot report complete; normalized `KnowledgeReference` evidence retains authority/version/URL/license through the final event; raw/batch profiles cannot emit ungrounded KB citations; and positive/negative source-set UI wording does not imply an individual-record verdict |
| Grounding-before-preemption | Pass in code: `answer_validation` is emitted only after final post-review grounding, so the ESM cannot unlock/preempt while Answer references are still `checking`; `indepth_pending` then starts the separately preemptable tail. |
| Atomic In-Depth evidence | Pass in code and live proof: `indepth_done`/`indepth_error` carry the full final envelope with canonical nested `inDepth`; the hub no longer emits colliding flattened `answer`/`status` fields, and Java/ESM require that nested contract. Java persists final references and verdicts with the terminal In-Depth state, and the exact-head terminal envelope matched final `done` and hydrated history. |
| Warm performance observation | Historical M3 observations remain documented but are non-gating. The unused collection/summarization subsystem was removed after G20 was deferred; a later performance workstream must define and approve its measurement contract before adding code. |
| Live multi-turn/preemption | Pass on exact parent `1c43634` and hub `32783bc`. A red-first concurrent-handoff contract reproduced the false negative by letting the replacement request acquire the shared lock before the cancelled request wrote telemetry. The fix retains the shared lock but records acquisitions and releases in request-scoped evidence around each stage-generator step and teardown. The complete hub suite passes 552 tests, including the forced race. The focused live OpenMRS Playwright proofs both pass: the same-session two-turn flow completed in 46.0 seconds, and the preemption flow completed in 1.0 minute. In the latter, the replacement question was accepted and answered, the interrupted turn became terminal, and its trace recorded `acquisitions=4`, `releases=4`, `active=0`, and `router_lock_released=true` while the replacement was free to use the shared slot. |
| Full stage-refactor matrix | Partial on the current exact heads. The consolidation matrix passes G07 and the focused exact-head proof now passes G18. G03, G09, G19, G21, G23, and consequently G24 remain pending; G20 is explicitly deferred. Older all-green stage-refactor results remain historical evidence and do not override this exact-head matrix. |
| Video proof | Pass on parent `c995bd4`, hub `fc62811`, ChartSearchAI `7b91ed1`, and ESM `3ac24b3`. The expanded 1280x720 E4B recording passed its real three-turn, persistence, and positive-preemption assertions in 3.5 minutes. The 210.28-second source is preserved at `artifacts/reports/demos/videos/chartsearchai-e4b-checked-multiturn-preempt-20260715.webm`; the reviewed H.264/yuv420p 2x publication cut is `chartsearchai-e4b-checked-multiturn-preempt-20260715-2x.mp4` (105.2 seconds, 1,800,011 bytes). Sampled frames verify readable narration, edited-original disclosure, visible In-Depth withholding, checking-to-checked transition, and resolved evidence tiles. The exact-question recording warmup reached `answer_done` in 9.63 seconds and was used only as a test control. |
| Exact-head context quality | Pass at hub `becdebe` (behavioral implementation `dad07e6` plus formatter-only follow-up): the stable verifier replayed 12 labeled E4B/12B cases through the real hub context-preparation path and llama.cpp tokenizer with all 48 required sources available. The input limit is a ceiling rather than a packing target: mandatory safety evidence, exact matches, meaningful normalized overlap, and a bounded 32-record clinical core that prioritizes active conditions and recency are eligible; other records are traced as `zero_relevance`. Exact inputs are 13,484-17,569 under the unchanged 20,480 limit, with 35-84 selected records and a 50.7 average. All 3,182 exclusions are `zero_relevance`; no case needs a budget exclusion. Overflow fitting uses one batched model-tokenizer request for rendered record costs plus bounded exact assembled-prompt checks, and it can skip an individually oversized or boundary-underestimated ranked record without blocking later viable evidence. Canonical chart indices are preserved, while temporal facts and drug-safety preparation remain tested against the complete ledger. The final source hash `b0508fded392ae56a9511649284c0caf3c25de225a63ef71dc4cfb4dc9174d4e` passes the exact gate, the changed Python files pass Black 23.12.1 and Black-compatible Flake8 6.1.0, and the full hub suite passes 549 tests. Successive independent reviews found and drove red-first fixes; the final attempted post-fix confirmation worker timed out and is not claimed as a clean independent pass. |
| Eligibility-only product diagnostic | Run `20a08ef1-6829-4bea-843e-ae523ee11b02` completed 14/14 E4B and 12B checked-profile cells against parent `abf0bea` and eligibility-only hub `7bb9371`, with no transport or context-overflow error. Inputs were 17,060-19,107 tokens and selected records averaged 93.4, compared with a 20,470.6-token and 168.1-record packed baseline. E4B end-to-end latency averaged 71.2 seconds versus 98.3; 12B averaged 164.9 versus 172.6. Context preparation still averaged about 9.7 and 10.0 seconds because that deployed revision retained the record-by-record full-prompt recount now removed by `dad07e6`. Model validation outcomes were mixed, as expected for a small-model diagnostic; this run is unjudged, unpublished, and not release proof. |
| Bounded-context product proof | Resumed run `d6c28766-643a-4c23-b56a-7ea90e029864` completed 14/14 multi-turn E4B/12B checked-profile cells at parent `e05e00e` and behavioral hub `dad07e6`, with seven cells per profile, no HTTP/context error, and no input-ceiling violation. Exact inputs were 16,977-19,480 against the 20,480 ceiling; every cell deliberately stopped with 1,000-3,503 tokens unused. The 1,436 included decisions were 988 `meaningful_overlap` plus the deterministic 32-record recent core in each cell; all 3,716 exclusions were `zero_relevance`, with no eligible or mandatory record excluded for budget. Each response retained the 368-record complete ledger while its model view selected 34-126 records, and all 14 Answer and In-Depth gate objects recorded `enforce`. Context-stage time averaged 13.6 seconds for E4B and 14.7 seconds for 12B, so the batched overflow fitter is correct but has not yet demonstrated a context-preparation latency reduction; exact history, assembled-prompt, and fallback token checks remain measurable follow-up work. The original run process survived loss of its terminal session and briefly contended with the supported resume for the single 12B worker; it was terminated by exact PID. Therefore the 12B end-to-end latency from this run is not a valid performance comparison. This proof is unjudged and unpublished because it validates infrastructure behavior, not clinical answer quality. |
| M3 independent review | Pass after iterative remediation. Architecture, clinical-safety, and integration reviewers report no remaining P0-P2 blocker. Their findings drove red-first coverage for date/value edge cases, test isolation, no-review preemption, full-envelope hydration, complete ESM asset provenance, feedback identity/retry, and evidence-title/resolution UX. |
| Release-proof hardening | Pass in code: the 24-cell audit has positive and failure-injection coverage; complete In-Depth now requires substantive text plus an enforce-gate terminal result; independent judge manifests require actor/model/method and source/output hashes; combined scores are deterministically recomputed; per-cell review requires an explicit comparable baseline or a reason it is not comparable; DIGI-UW/code-qa must report zero blockers against exact reviewed SHAs. |
| Source indexing | Pass for the focused run: the fresh Querystore generation completed every resource type, with 427,868 of 427,874 observations indexed and all types within the shared drift policy. The recovery helper now requires `indexingstatus.complete=true` before evaluating drift, after a live run exposed that drift tolerance alone could release a still-running generation. The historical restore predates or bypassed the new corpus-receipt path, so its missing dump receipt remains an explicit provenance caveat rather than reconstructed metadata. |
| Complete patient-chart transport | Superseded after live performance review. Hub `ef403cc` and Querystore `4a081e3` proved strict per-read projection and snapshot transport, but live traces showed that rebuilding/reconciling the source chart during every ordinary read dominated context latency. The retained safety value did not justify a second read policy layered over upstream QueryStore behavior. See the thin-adapter correction below. |
| Thin QueryStore read adapter | Pass in code and live proof at QueryStore `fd8a00c`, hub `32783bc`, and parent `1c43634`: PR #63 is one feature commit over upstream `577db52`, retaining only the authorized `/patientrecord` REST adapter over `getPatientChart`, `searchByPatient`, and `search`. Per-read strict projection, snapshot-envelope versioning, and hub compatibility code for that discarded envelope are removed. Index readiness and repair remain explicit operational workflows (`indexingstatus`, `drift`, `reindex`); the hub retains paging, total-count, stable-identity, duplicate, malformed-record, and truncation checks. The complete QueryStore unit suite, all 33 Elasticsearch integration cases, 552 hub tests, 76 focused hub contracts, 32 local-start tests, 786-test parent suite, and seven-repository drift scan pass. The canonical local launcher deployed the thin QueryStore OMOD, read 365 materialized records twice with stable results, resolved final Answer references from QueryStore, and persisted/hydrated the same final envelope. The hub trace measured `source_fetch_ms=67` and total context preparation at 145 ms, compared with the discarded strict path's 11-21 second source fetch. The exact-parent-head focused relay/preemption proof now passes after the pin update. Local backup branches preserve both pre-squash strict histories. |
| Candidate diagnostics | Run `2ae78e95-bb9b-4db7-b0b4-9b82aa187d49` remains a failed product-path diagnostic. Run `65839998-5fd5-4041-be76-0e626d7b4e96` completed 24/24 transports but is invalid for model-quality comparison: the live Querystore served original 2006 dates while the committed fixtures and rubric described the transplanted 2025-2026 corpus. It is not eligible for judging or publication. |
| Evaluation provenance | Pass in code: preflight compares the complete rendered chart plus ordered mapping ledger for every selected patient; fixture capture fetches all pages before atomic replacement; run manifests hash the comparison set, scenarios, chart fixtures, canonical ledgers, and restored dump receipt. Seed verifies dump identity and rejects module-bearing full backups before touching the database. A real MariaDB dump/restore test proves both module tables and Liquibase rows are excluded. Live exact-ledger proof remains part of the run preflight. |
| Focused profile diagnostic | Run `b63702b3-c9d4-4631-a545-826f2521278b` completed all 18 cells across E4B single, 12B single, and `team-med-checked`; all transports returned HTTP 200 and every expected stage emitted terminal timing. Its deterministic audit failed with 21 checks across 10 cells, including real table/date/context defects and suspected exact-fact grounding false negatives. It remains unjudged and is published only as an explicitly labeled diagnostic at `hub-profile-team-focus-diagnostic-2026-07-13`. |
| Focused diagnostic remediation | Pass in code at hub `021e305`: malformed dynamic tables are repaired only for type-confirmed date/weight rows and otherwise withheld; Answer review and correction recheck each fit the evidence ledger independently; grounding never silently drops a cited source. Reviewer hallucinations are discarded unless their quoted wrong fragment occurs in reviewed content, mixed localized/unlocalized edits cannot ship, and temporal scheduling claims are checked against their specific date without confusing historical follow-up language with a future appointment. A temporal pass can ground a source set only when both the complete normalized claim and exact cited source set match; strict sentence contracts prevent unrelated clauses from inheriting that pass. Conflicting multi-source cells cannot use deterministic exact grounding. The hub suite passes 454 tests and independent review found no remaining P0-P2 issue. |
| First remediated rerun | Run `e914eb8a-79fb-4736-bc94-4b36fc3ae620` completed 18/18 against hub `7fd5bc7` and parent `96cecc3`, with zero transport errors and 11 deterministic blockers. It remains diagnostic and unjudged. |
| Second remediated rerun | Run `e52e56de-048c-42ac-af71-e52bf85d0a6b` completed 18/18 against hub `bc20034` and parent `8e3d637`, with zero transport errors and 10 deterministic blockers. It confirmed the reviewer-localization fix, exposed one missed present-tense scheduling grammar and collective temporal grounding mismatch now fixed in `021e305`, and showed genuine model-output failures in E4B weight structure and team medication/weight citation structure. It remains diagnostic and unjudged. |
| Exact-head appointment smoke | Run `da340047-5b9c-4ebc-b436-a8d6a3a50287` completed 2/2 against hub `021e305` and parent `a2b5d30`, with zero transport errors and zero deterministic blockers. E4B shipped the safe historical-return-date answer as checked with one evidence-type warning and no unsupported references; 12B shipped the collective 11-source no-upcoming claim as checked with zero Answer issues and no unsupported references. The deterministic audit passed. |
| First 12B quality-baseline attempt | Run `942322ec-d297-4ddd-82c6-3e2f9a69b681` completed 12/12 against hub `021e305` and parent `8a479e6`, with zero transport failures. Its deterministic audit failed on exactly two checks in `am-upcoming-appointments`: the single collective claim carried six unscoped top-level citations, so citation scope and final grounding failed. No other cell produced an audit blocker. The run remains diagnostic, unjudged, and unpublished. |
| Collective appointment citation remediation | Pass in code at hub `733214d`: one prose claim may bind a complete top-level source set, but period-separated, semicolon-separated, and all FANBOYS-coordinated multi-claim forms still fail closed. The strict collective no-upcoming grammar now accepts “all scheduled return visits are in the past” only when the entire claim matches; unrelated tails cannot inherit deterministic temporal grounding. Red-first unit, staged-lifecycle, temporal, and grounding tests pass; the complete hub suite is 467 tests, and the final independent review found no P0-P2 issue. |
| Exact-head 12B collective appointment smoke | Run `6b2a776e-ceec-4f9b-aee9-19c4fa1e4d32` completed 1/1 against hub `733214d` and parent `793aa95`, with zero transport failures and zero deterministic blockers. The final Answer is checked; all six appointment references resolve and are verified collectively against the exact deterministic temporal source set. The unsupported In-Depth draft was withheld as `needs_review`, so no unsafe tail shipped. |
| Hub-native In-Depth judge prep | Pass: judge prep now reads current `response.inDepth`, historical separate-call `row.indepth.response`, and embedded legacy sections in that order. It scores background only when content actually shipped, while preserving withheld status/validation and Answer lifecycle metadata separately from semantic Scout fields. The completed diagnostic now prepares 7 cells with In-Depth and 5 without, matching the response envelopes; 24 related tests pass and independent review found no P0-P2 issue. |
| Independent-actor judge finalization | Pass: finalization retains documented temporal rubric fields without requiring the older undocumented `has_temporal_claim` flag, while preserving that flag for workflow compatibility. The stable Make target now carries required actor type, judge model, and method provenance instead of failing actor-mode finalization. Twenty-seven related tests pass and final independent review found no P0-P2 issue. |
| Fresh judged 12B candidate | Run `8e1291c4-6598-4d8d-8979-2e7247fcf0f2` completed 12/12 against parent `a539e9d` and hub `733214d`, with zero transport errors and a passing implemented deterministic audit. All 12 Answers reached `checked`; six In-Depth sections completed and six unsafe/unsupported drafts were withheld as `needs_review`. Independent actor `codex-candidate-2026-07-13` judged the immutable run with the Scout rubric: Benchmark 88.4/100, accuracy 9.17, completeness 8.67, relevance 9.0, zero harm/confabulation/fabricated citations, and all 66 references resolved. The judge nevertheless found two real strict-window failures that the deterministic audit missed: one X-ray six days before the cutoff, and one order table with 10 out-of-window rows plus one omitted qualifying order. |
| Small-model answer-path comparison | Run `60c848c6-bd63-44f3-ad2d-9cb76d024d61` completed all 72 cells across E4B and 12B answer-only, deterministic-check, and fully checked profiles. All requests returned HTTP 200 and the deterministic analyzer found zero malformed dates. Named actor `codex-small-model-2026-07-15` produced and promoted 72 hash-bound Scout rows after a chart-level pass; all 12 byte-identical `single-12b-checked` Answers received the same numeric scores as the earlier independent 12B candidate judge. Answer Benchmarks were E4B answer-only 82.8, E4B deterministic 88.8, E4B checked 91.2, 12B answer-only 88.2, 12B deterministic 86.2, and 12B checked 88.7, with zero judged harm, confabulation, or fabricated citations. The E4B gate correctly replaced a historical appointment presented as upcoming, while the 12B gate removed useful failure-to-thrive context from one child-growth answer; strict six-month windows remained unresolved. The checked arms resolved all 121 references (55 E4B and 66 12B). The curated report and frozen 72-cell dashboard are published at `https://reports.openclinai.org/small-model-answer-paths-2026-07-15/`. This run records end-to-end response latency only because its `08ed6e3` harness revision predates canonical stage-timing capture; per-stage claims continue to use the later 18-cell focused diagnostic. Results remain directional: one automated judge, 12 scenarios, and no physician calibration. |
| Judged report compatibility and publication | Pass at parent commits `a032074` and `bf30fd9`: current hub-native In-Depth is authoritative for judge/report output; withheld content cannot leak into Evidence Used; final hub grounding states reach canonical source tiles but are explicitly labeled as hub grounding rather than whole-answer support; cohort/reviewer caveats are data-derived. The complete parent suite passes 719 tests with 35 expected skips and four deselections, and independent review found no P0-P2 issue. The curated report is published at `https://reports.openclinai.org/hub-profile-12b-checked-candidate-2026-07-13/` with the deterministic/judge disagreement disclosed. |
| Manual-review visibility | Pass in code on hub `269ea24`, ChartSearchAI `8b653ea`, and ESM `f9d3161`: low-confidence final output stays directly visible; changed Answer text, citations, and tables plus rejected In-Depth drafts retain separate review evidence; review-only material is excluded from final evidence and judge content; report/dashboard semantics share one module; and exact request correlation cannot borrow an adjacent turn while mixed-version historical fallback remains available. Hub 490, harness 782, ESM 191 plus type/lint/build, and the Java relay target pass. The deterministic Playwright review/reload story passes in 5.4 seconds and its bundle explicitly identifies intercepted stream/history APIs as SPA rendering/hydration proof rather than Java/hub/database persistence proof. Independent correctness and DIGI-UW/code-qa reviews found no remaining code or test blocker. |
| Strict-window follow-up disposition | Deferred by explicit user approval on 2026-07-13. A red-first experiment confirmed that inferring arbitrary temporal windows and exhaustive category intent from free-text regexes becomes brittle and benchmark-shaped; it was discarded before commit. The durable future direction is a typed temporal-query contract whose proposed interval/category/exhaustiveness is validated before deterministic enforcement. That language-understanding layer is not part of this first consolidation iteration. The two judged strict-window failures remain disclosed known limitations and G21 remains partial rather than being waived. |
| Release-proof audit remediation | Pass in code on the companion heads recorded above: the small-model artifact distinguishes the configured fresh-launch two-slot default from an already-running router with a larger cap, behaviorally executes the real router launcher, invokes E2B then E4B, and requires both to remain loaded. The relay artifact binds the exact Querystore source commit, built OMOD provenance, deployed manifest, mounted OMOD hash, and final Answer evidence from the live `querystore` adapter. Red-first tests failed on both former proof gaps; the focused 80-test set, 791-test parent suite, 76-test Java reactor, and seven-repository drift scan pass after remediation. Exact-head live artifacts remain pending until the parent pin commit is deployed. |
| Remaining proof | Commit and push the parent pin/gate/status update, refresh the canonical local relay and E2B/E4B residency artifacts on that exact head, rerun the full live gate matrix, and finish the exact-head DIGI-UW/code-qa review set. G20 remains deferred and G21 remains partial by explicit scope rather than passing, so G24 cannot pass even if G23 becomes green. Medical-team structural-output remediation, typed temporal-query work, and performance/cache tuning remain separate workstreams. |

## Milestones

| Milestone | Status | Evidence or blocker |
|---|---|---|
| R0 Persist roadmap | Complete | Roadmap/status/index committed and pushed at `d734df9`; post-copy validation is recorded above |
| M0 Stabilize baseline | Complete | All refreshed pins are reachable, upstream deltas are classified, raw-leg goldens are pinned, and the independent re-review has no blocker |
| M1 Consolidate hub | Complete | Hub PR #12 is merged at `7869c62`; 246 hub tests, 569 parent tests, hash-bound context proof, independent re-review, review remediation, and companion CI pass. User Signoff B granted. |
| M2 Reconcile OpenMRS integration | Complete | Five independent-review findings and the terminal EOF follow-up are remediated; exact-head local suites, companion CI, architecture gates, documentation drift, and final independent review pass. User Signoff C granted. |
| M3 Product/local proof | Revalidation in progress | The product proof passed on the prior exact head. The release audit strengthened its router-launch and deployed-Querystore identity requirements; exact-head live artifacts must be refreshed after the remediation commit before this returns to complete. |
| M4 Evaluation and release | In progress | The 12B candidate and six-arm small-model comparison are judged and published. Both preserve the disclosed strict-window gap; the small-model run additionally shows one beneficial E4B temporal patch and one regressive 12B growth patch. General free-text window extraction is deferred to a future typed temporal-query workstream, so G21 remains partial. Final independent QA, release hygiene, and User Release Signoff D remain. |

## Acceptance Gates

| Gate | Status | Current evidence |
|---|---|---|
| G01 Roadmap integrity | Pass | Structure/link validation passed; approved SHA-256 recorded above |
| G02 Baseline integrity | Pass | Root and all six submodule heads are committed, pushed, clean, and reachable from their configured remotes; companion CI and upstream disposition evidence remain green. |
| G03 Upstream reconciliation | Pass | Fixed baseline-to-classified-head ranges cover every disposition, and the gate fails if a tracked upstream ref advances |
| G04 One engine | Pass | Streaming and blocking drain one `StageEngine`; old runners/flag bridge are deleted; cancellation and budget context tests pass |
| G05 Profile correctness | Pass | Profiles compile immutable stage plans, invalid order fails, unknown IDs return `model_not_found`, and metadata is authoritative |
| G06 Raw-leg compatibility | Pass | Five byte-exact pre-refactor envelopes remain green; merged hub `7869c62` is tree-identical to tested head `31e6037`, where the complete 246-test suite passed |
| G07 Source independence | Pass | Inline, optional QueryStore, static KB, and mock alternate adapters share one normalized source contract, and the hub starts without QueryStore. The external adapter mirrors upstream QueryStore read behavior instead of reconciling on each request; hub transport checks reject malformed, duplicated, truncated, or count-inconsistent pages. The live relay proof binds the thin QueryStore runtime, its built and mounted OMOD hash, 365-record stable reads, 67 ms source fetch, and final Answer references from the QueryStore ledger. The final QueryStore head is `fd8a00c`; its only delta from that runtime proof is the corrected non-zero-vector Elasticsearch integration fixture, and all 33 Elasticsearch cases pass. Index readiness and repair remain explicit operational workflows. |
| G08 Context budgeting | Pass | Every product envelope requires exact tokenizer-backed budgeting; the exact rendered model/messages/tools prompt is counted and capped before backend calls, while llama.cpp's output schema remains a zero-input-token generation grammar |
| G09 Context quality | Pass | Hub `becdebe` retains 48/48 required records across 12 cases with exact inputs of 13,484-17,569 against the 20,480 ceiling; date-only metadata cannot mask missing evidence, every selection decision has a trace reason, zero-relevance evidence is not packed, and overflow candidates use batched model-token costs plus exact final-prompt checks. The 14-cell product proof independently shows 1,000-3,503 tokens left unused once eligible evidence is exhausted. |
| G10 Answer temporal safety | Pass | Every `output: product` profile ignores attempts to disable temporal facts or weaken enforce; ChartSearchAI marks product requests and the hub rejects low-level/internal profile ids on that path |
| G11 In-Depth temporal safety | Pass | Every displayed claim is deterministically temporally gated and must cite current-ledger evidence; uncited, rejected, mixed, unchecked, unsupported, reviewer-unavailable, or empty claim sets cannot report complete |
| G12 Review ordering | Pass | Product and review legs share one conservative review implementation; rewrites are re-gated and final Answer refs are re-resolved before grounding |
| G13 Citation integrity | Pass | Prior-turn markers are stripped; Answer and In-Depth citations resolve to the current ledger; claim/path checks and source sets survive the wire and terminal persistence |
| G14 Drug-safety parity | Pass | Hub parity, unit-safe weight, Java assistant-wire persistence, and history rehydration contracts pass |
| G15 Thin OpenMRS relay | Pass | Java has one fixed hub endpoint and one profile request; it no longer supplies prompts or an answer schema, preserves the complete hub wire for sync and staged clients, maps structured `insufficient_context`, and has deleted the dead local chart-size exception plus legacy inference/discovery/grounding/context code |
| G16 Product discovery | Pass | Hub availability plus explicit `selection_priority` produces at most one available default; ESM never invents a list-order fallback |
| G17 Lifecycle UX | Pass | Java and ESM contracts preserve and render visible flagged output, changed original Answers/citations/blocks, rejected In-Depth drafts, separate review references, stream-error settlement, and reload hydration. Static-report and executable-dashboard parity tests are load-bearing, and the deterministic Playwright SPA review/reload proof passes with an explicit mocked-API boundary. |
| G18 Multi-turn and cancellation | Pass | On exact parent `1c43634` with hub `32783bc`, the forced concurrent-handoff contract and both focused live OpenMRS Playwright flows pass. Same-session history works, replacement work preempts trailing In-Depth, and cancellation telemetry proves balanced request-scoped slot ownership (`4` acquisitions, `4` releases, `0` active) even after replacement work begins. |
| G19 Local setup | Pending live refresh | The prior exact-head relay, hydration, and co-residency proof passed. The strengthened artifact now also binds the fresh-launch two-slot default, real router launcher inputs, Querystore commit/OMOD/deployment identity, and live Querystore evidence; it must be regenerated after the remediation commit. |
| G20 Performance | Deferred | Performance tuning and relative measurement are intentionally after UI proof, evaluation, judging, and publication. |
| G21 Evaluation | In progress | Fresh 12B run `8e1291c4-6598-4d8d-8979-2e7247fcf0f2` and six-arm run `60c848c6-bd63-44f3-ad2d-9cb76d024d61` are complete, judged, and published. The latter has zero malformed dates and zero judged harm, and proves that E4B enforcement fixes the historical-appointment error. It still does not pass G21: both judges expose strict six-month-window failures outside the implemented deterministic audit, and one 12B deterministic patch reduces child-growth completeness from 8 to 3 by removing failure-to-thrive context. User-approved scope keeps this gate partial; it is not reclassified as a pass. Robust window remediation requires a future typed temporal-query contract rather than free-text regex tuning. |
| G22 Documentation | Pass | Current READMEs, contributor rules, workflow comments, API docs, and all submodules pass the seven-repository drift scan |
| G23 Independent QA | Pending | Focused independent review of the complete-chart remediation passed with no P0-P2 blocker after two red/fix/re-review rounds. The official DIGI-UW/code-qa checkout is current and the deterministic evidence bundle has been regenerated from the live E4B run. Exact-head meaningful-coverage, simplicity, spec/code, cross-repository companion, and hash-bound results still remain. No green result has been fabricated. |
| G24 Release hygiene | Pending | The previous exact-head CI, live E2E, PR heads, submodule pins, and clean trees passed. The strengthened live artifacts and current CI/PR checks must be refreshed, G23 is incomplete, and G21 remains explicitly partial rather than green. |

## Signoffs

| Signoff | Status | Scope unlocked |
|---|---|---|
| Roadmap approval | Granted 2026-07-09 | R0 and M0 |
| User Signoff A | Granted 2026-07-10 | M1 hub consolidation |
| User Signoff B | Granted 2026-07-10 | M2 OpenMRS integration reconciliation |
| User Signoff C | Granted 2026-07-10 | M3 product/local proof completion and release preparation |
| Pre-final report authorization | Granted 2026-07-10 | Run, judge, and publish one fresh profile-based candidate report after deterministic QA and before final validation; this does not authorize final release, merges, or obsolete-PR closure |
| User Release Signoff D | Pending | Merge, publication, obsolete-PR closure, and release completion |

## Amendments

| Date | Approved change | Reason and replacement evidence |
|---|---|---|
| 2026-07-10 | G20 no longer uses the roadmap's fixed 30-second local Answer threshold as a pass/fail criterion. | User clarified that local-machine performance is variable and the absolute limit is arbitrary. M3 discloses cold/warm state, records host/runtime provenance and warm-run distributions, and separates pre-display pipeline overhead from the underlying answer-stage work. Browser tests require eventual lifecycle completion but do not fail on an absolute latency number. |
| 2026-07-10 | A fresh judged report must be run and published before final validation. | After the known M3 correctness blockers are fixed and deterministic QA is clean, create a new candidate set that exercises the product profiles rather than the obsolete two-call experimental arms. Run `single-e4b-checked` as the default product path and `single-12b-checked` as the quality comparison across the 12 temporal/date scenarios, exclude high-team, preserve independent judgments, publish the report, and inspect per-cell regressions before the final validation/release pass. This is limited publication authorization for that report, not User Release Signoff D. |
| 2026-07-12 | Add one checked medical-team arm to the next focused comparison and expose stage timing. | The next iteration uses six representative scenarios across E4B single, 12B single, and `team-med-checked` (18 cells). This is a focused readiness comparison before any broader candidate; it does not re-admit the quarantined high-team configurations. Dashboard cell details and static reports show per-stage elapsed time and status, while report summaries disclose observed/expected timing coverage. |
| 2026-07-13 | Publish the failed 18-cell run as a diagnostic before remediation continues. | The user explicitly authorized publication before continuing. The public title, summary, and takeaway state that the run is unjudged, failed deterministic QA, and is not a model-quality comparison. This does not satisfy G21, replace the required clean judged candidate, or grant release signoff. |
| 2026-07-13 | Run the 12B-only 12-scenario quality baseline before further E4B/team iteration. | Focused diagnostics and the clean appointment smoke show 12B as the current quality baseline while E4B and the medical-team profile retain separate structural-output failures. Scenario scope, deterministic gates, independent judging, and publication criteria remain unchanged. |
| 2026-07-13 | Defer general strict-window language interpretation from the first consolidation iteration. | The judged candidate exposed two real six-month-window failures. An uncommitted red-first implementation demonstrated that growing a handwritten free-text grammar and automatic table reconstruction would overfit phrasings and could reject or rewrite valid constrained questions. The experiment was discarded in full. Existing proven temporal facts and date/trend/appointment gates remain unchanged; G21 remains partial, and a typed `temporal_query` contract is reserved for a separately designed future iteration. |
| 2026-07-13 | Replace product aliases and manually named candidate copies with stable IDs and Git-owned history. | The user rejected manual in-project version history. Product backend IDs now equal med-agent-hub profile IDs; stable comparison-set IDs carry current composition; unused definitions are removed; and historical evidence loads the comparison definition at the run manifest's Git SHA. |
| 2026-07-15 | Preserve the current efficiency investigation as a measured follow-up workstream. | The local test/demo startup can exercise the default profile through the real demo-patient context path and an explicit question, and the recording helper can warm its exact intended first question. This is only a repeatable warm-state measurement control: it is not a product improvement, does not cache chart retrieval, and does not make an arbitrary future question reusable. A same-scenario full-profile comparison found that E4B exposed Answers in 11.6 and 15.8 seconds, while mixed E2B-writer/E4B-tail took 24.4 and 21.5 seconds and produced lower-quality structured output. The explicit test-only `llama-router-small-model-proof` invokes E2B and E4B sequentially and requires both to report `loaded` afterward, so eviction is measured rather than inferred from `--models-max`; its first live artifact passed. The normal local path still defaults to a two-model residency cap and does not run this proof or a clinical warmup. E4B remains the default based on observed output and latency, not parameter count. On the tested 365-record chart, deterministic context preparation consumed roughly 10 seconds and selected to 20,475 of a 20,480-token input limit. The next performance iteration must first add sub-stage measurements, then evaluate authorization-scoped patient-ledger caching, a near-linear selector with one exact final token check, and conservative 12k/16k/current-context ablations against required-source recall, temporal/citation safety, judged quality, and relative warm latency. Final answers and question-specific selections are never cached. Model residency, prompt-prefix/KV reuse, clinical-evidence reuse, and derived-computation reuse are tracked separately in [`chart-context-cache-research-plan-2026-07-15.md`](chart-context-cache-research-plan-2026-07-15.md). These observations do not reactivate an absolute local latency threshold; G20 remains deferred until its measurement contract is separately approved. |
| 2026-07-15 | Preserve role-specific bounded reasoning as a future measured workstream. | The fast Answer remains the non-reasoning control (`reasoning-budget=0`, deterministic sampling) because its job is low latency and the current E2B/E4B comparison does not show that smaller alone is faster. A later, separately approved experiment may enable bounded reasoning per role for review, In-Depth, grounding, or specialist/team stages, never as a global router default. Each comparison must hold model, prompt, evidence, and output contract constant; vary only the role's reasoning budget; and report first-Answer latency, tail latency, reasoning/output tokens, temporal and citation failures, safe edits/withholds, and judged answer quality. Hidden reasoning is not rendered or persisted as clinical evidence, and deterministic temporal, citation, and substance gates remain authoritative. This experiment is deferred until the current release proof is complete and does not change G20's deferred status. |
| 2026-07-16 | Treat the exact model input limit as a safety ceiling, not a context-fill objective, and remove the sequential recount. | The previous oversized-chart selector ranked every remaining record, including records with zero query relevance, and therefore packed prompts to the limit. Hub `7bb9371` adds deterministic eligibility before exact budget admission, preserves a bounded active-condition/recent clinical core, traces zero-relevance exclusions, stops when eligible evidence is exhausted, and retains complete-ledger temporal and drug-safety checks. Hub `dad07e6` then replaces the record-by-record full-prompt recount with one batched model-tokenizer request and bounded exact assembled checks. Review-driven query matching prevents numeric, decimal, compact-duration, and unlabeled identifier collisions. The labeled exact-token gate remains 48/48, so this is a general context-supply correction rather than a benchmark-specific prompt rule. |
| 2026-07-16 | Restore QueryStore's upstream read semantics and keep the new HTTP surface thin. | Live traces showed 11-21 seconds in source fetch because the strict branch rebuilt/reconciled every patient on every ordinary read. The original requirement was only to expose QueryStore's existing in-JVM read behavior to med-agent-hub. PR #63 is therefore rebuilt from upstream with the additive `/patientrecord` controller and DTO only. Git backup branches preserve the discarded strict implementation; runtime code does not carry its snapshot-envelope version or compatibility path. |
| 2026-07-16 | Reuse exact token counts instead of repeating tokenizer work during one stage. | Hub `1fa17f3` owns one `RouterTokenCounter` for context fitting and dispatch, caches exact assembled-prompt counts within the request, caches router capability discovery across requests, and records source/history/selection/token-counter timing. It retains exact model-tokenizer admission rather than replacing safety counts with estimates. Hub `6068d2d` then aligns the optional QueryStore client with the single thin response contract. The full hub suite passes 551 tests. |
| 2026-07-17 | Measure cancellation cleanup per request rather than by sampling global lock state. | The shared router lock correctly serializes model work, but its instantaneous state can describe a replacement request by the time the cancelled request writes telemetry. Hub `32783bc` adds request-scoped acquisition/release evidence, preserves `try/finally` release, and activates the context-local evidence around each async-generator step so cross-task iteration remains valid. A red-first forced handoff test and the focused live OpenMRS preemption flow prove balanced release without blocking the replacement. |
