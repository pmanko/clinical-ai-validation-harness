# Feature 006: Modular Validation Runner and Human Review

**Created**: 2026-05-28
**Direction**: independently installable experiment execution, capture, evaluation,
review and offline reporting. Existing clinical comparison and Catalyst execution
paths are being aligned with this boundary; documentation does not establish
isolation, deployed acceptance or publication. [Plan](plan.md) owns implementation
and verification obligations. [Spec 001](../001-harness-control-plane-foundation/spec.md)
owns common readiness/configuration/evidence requirements; the
[metadata guide](../artifacts/planning/metadata-schema.md) owns shared meanings.

## Goal and boundaries

Run authored scenarios against configured targets, compare captured outcomes and
retain evidence and reviewer rationale. Clinical comparisons exercise ChartSearchAI's
real chat interface with the selected supported provider/profile. Bundled inference
and configured Med Agent Hub workflows remain distinct product capabilities;
Hub is not a universal harness prerequisite. Direct Hub/model arms are explicitly
labeled experiments, not proof of ChartSearchAI behavior.

Catalyst experiments exercise an already-prepared Gateway using a selected suite,
source/schema context and model-team settings. Catalyst owns SQL workflow and API
behavior; the harness captures execution evidence and separately attributed reader
rationale. Product contracts, not this feature, define transport, authorization,
provider selection, cancellation, persistence or safety behavior. References:
[ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai),
[Med Agent Hub](https://github.com/pmanko/med-agent-hub),
[QueryStore API](https://github.com/pmanko/openmrs-module-querystore/blob/harness-integration/docs/rest-api.md),
[Catalyst specification](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md).

The caller prepares services and supplies connection settings, scenarios/fixtures,
evaluation settings, provenance and an output location. No Git, submodule,
product pin, source checkout or umbrella installation is needed by the runner.
The harness does not start/stop model routers, scan product sources for model or
prompt identity, or perform checkout, build, deployment or release management.
OpenClinAI setup and publication belong to the
[umbrella](https://github.com/pmanko/openclinai.org).

## User scenarios and independent tests

### US1 — Collect a configured experiment (P1)

Supply reviewed inputs and an available target. Configuration checks explain
unsupported transports or missing inputs; execution calls the selected interface
without preparing it. A clinical multi-turn cell uses one persisted session per
scenario/backend. Catalyst records exact SQL, typed parameters, execution result
or error, and complete case context. Fixture/double runs are labeled accordingly.

**Independent test**: Run clinical and Catalyst collection with doubles in an
installed environment without Git or product sources; then verify each claimed
product path separately against its real interface. Unknown revision/model
metadata stays explicit and does not trigger checkout or source discovery.

### US2 — Evaluate and inspect captured evidence (P2)

Deterministic clinical checks precede optional model judgments. Catalyst's
reader-led protocol preserves complete cases without inventing an automatic
winner or factual-equivalence verdict. Review-only drafts remain separate from
final Answer/In-Depth evidence. Every judgment identifies its actor and input.

**Independent test**: Use diverse captured cases with missing evidence, unsupported
claims, abstention, flagged output, trace mismatch and API/SQL failure. Check that
missing evidence cannot become a passing claim or be silently replaced.

### US3 — Review and regenerate a portable report (P3)

A reviewer reads complete cases and records identity, rubric, decision and rationale.
A copied run directory contains the inputs, evidence and review records needed to
regenerate its report without live targets, evaluators or original dataset paths.

**Independent test**: Copy a packet, remove authored inputs and service access, and
regenerate the report. Preserve flagged final output and separately labeled drafts.
Report agreement only where the selected protocol calls for it.

## Success criteria

Retained identifiers refer to current validation responsibilities.

- **SC-006.1**: Clinical scenarios and comparison sets validate against documented
  schemas; scenario identity, patient reference, turns, tags and expectations are retained.
- **SC-006.2**: `harness-cli validate run <comparison-set>` writes one result per
  scenario/backend/turn with a manifest and events. Clinical product cells use the
  configured ChartSearchAI interface; direct Hub arms remain labeled experiments.
- **SC-006.3**: Results include deterministic latency, JSON validity, citation and
  abstention findings, preserving response confidence, validation, In-Depth,
  references, blocks and safety metadata where provided. Unavailable tokens,
  finish reasons and model identity stay nullable/missing, not source-inferred.
- **SC-006.4**: A standalone HTML report renders the comparison and record-level
  evidence with review controls; it is generated from captured run artifacts.
- **SC-006.5**: Clinical feedback retains Scout accuracy/completeness/relevance
  scores, abstention and groundedness categories, harm finding, decision,
  reviewer identity/time and free-text rationale.
- **SC-006.6**: File-first persistence exposes consistent save/find behavior for
  scenario, comparison, result and feedback records; external databases are not prerequisites.
- **SC-006.7**: A reviewed clinical comparison includes justified comparison arms
  and 2–3 abstention probes; low-level arms are explicitly separate experiments.
- **SC-006.8**: Flagged final Answer/In-Depth output remains visible with caveats;
  changed/rejected drafts retain separate evidence and do not enter final judge input.
- **SC-006.9**: Report consumers reuse one confidence/validation semantic definition.
  Where a public dashboard consumes it, parity is tested by its website owner
  using the same flagged fixture; website delivery is not runner work.

## Clinical smoke and context/evaluation protocols

### Real ChartSearchAI medication-history smoke

- **SC-004.4**: Against a reviewed populated medication-history fixture, asking
  “What medications is this patient on?” through the real ChartSearchAI interface
  returns a non-empty streamed answer and at least one resolvable numbered chart citation.
  The product browser check additionally confirms that the References panel and
  citation navigation render correctly. This is connectivity/evidence smoke,
  not proof of clinical answer completeness or accuracy.

The included corpus anchor is patient UUID
`dd75c020-1691-11df-97a5-7038c432aabf` (Zabella Halambe). Verify the selected
fixture's medication records before using it; old counts and previous runtime
observations do not establish the contents of a newly configured target.

Record the question, selected provider/profile, supplied or observed target
identity, fixture identity, response, citation IDs and resolved evidence. Unknown
revision/model metadata stays explicit. Do not assert exact drug wording or a
fixed latency from this wiring check. Run each provider being claimed separately;
a fixture or test-double result does not establish product acceptance. The caller
prepares OpenMRS, QueryStore and the selected provider. Browser presentation is
verified by the [frontend owner](https://github.com/pmanko/openmrs-esm-chartsearchai),
not simulated by a harness command plan.

### Clinical context and deterministic evaluation

The following identifiers retain the namespace `MAH-CONSOLIDATION-2026-07-09-v1`;
they are not the same-numbered gates in the dual-provider parity roadmap.
Product behavior follows the contracts linked above, including the
[ChartSearchAI contract](https://github.com/pmanko/openmrs-module-chartsearchai/blob/harness-integration/docs/adr.md).

- **MAH-CONSOLIDATION-2026-07-09-v1:G09 — Context quality**: Required-source recall
  is 100% on the reviewed context development set. Temporal and safety records
  are not lost; each included or excluded record has an inspectable trace reason.
  Exercise under-budget, exact-boundary, oversized, mandatory-overflow,
  old-but-relevant and source-failure cases against the selected product contract.
  Record fixture identity and record-level misses, not only totals.
- **MAH-CONSOLIDATION-2026-07-09-v1:G21 — Evaluation**: `date-format-dev` and
  `temporal-core-dev` have zero enforce-arm deterministic blockers. The 12-scenario
  candidate has no new harm/temporal failures and no unexplained per-cell
  regression over 10 points. Apply these criteria only to the reviewed suite,
  rubric and comparable baseline; they are not universal product thresholds or
  a substitute for clinical review.

The caller supplies prepared targets, explicit provider/profile arms, reference
date, reviewed fixtures and baseline evidence. Run deterministic date/temporal
and context checks before the candidate comparison. Optional independent judges
run afterward; retain each actor's input, judgment and rationale separately from
combined or human-adjudicated reporting. Missing evidence is not a pass.

Capture required inputs, target responses, included/excluded IDs, trace reasons,
findings and supplied/observed provenance with the run. Report regeneration is
offline over that packet. Test doubles demonstrate runner mechanics only;
product acceptance requires real interfaces. Build, checkout, model-router
lifecycle, exact-head release gates and publication remain outside the harness.

## Functional requirements

- **FR-006.1**: Product runs MUST use the configured real ChartSearchAI chat path
  and supported provider/profile, replaying turns in one persisted session.
  Direct Hub/model calls MUST be identified as experiments, not product behavior.
- **FR-006.2**: Clinical scenarios MUST support ordered multi-turn replay per
  backend; single-turn is a one-element sequence.
- **FR-006.3**: Results MUST reference the versioned manifest/event spine and run
  identity rather than redefine common provenance. Emit canonical
  `gen_ai.provider.name`, not `gen_ai.system`. Capture supplied/observed target
  provenance with nullable `git_sha` and explicit missing metadata, never pin gates.
- **FR-006.4**: Deterministic metrics MUST require no model call. Optional judges
  run as separately attributed actors and cannot override deterministic safety findings.
- **FR-006.5**: Clinical feedback MUST retain Scout's native 0–10 axes,
  abstention (`correct`, `over-abstained`, `failed-to-abstain`, `n-a`), answer-level
  groundedness (`supported`, `partly`, `unsupported`, `n-a`) and harm hard-fail.
  Catalyst reader rationale uses its experiment's rubric, not synthetic clinical scores.
- **FR-006.6**: File-first records MUST use a consistent repository interface
  (`save(collection, doc)` / `find(collection, query)`). Authored scenarios and
  comparisons are inputs; results and feedback live under the selected run output.
- **FR-006.7**: Reports MUST be standalone offline HTML over captured artifacts,
  without ESM renderer imports, live services or original authored input directories.
- **FR-006.8**: Clinical review MUST support multiple reviewers and report raw
  agreement (and Cohen's kappa for exactly two reviewers) without blocking collection.
  Reader-led Catalyst perspectives remain separate rationales, not averaged verdicts.
- **FR-006.9**: Harness evaluator feedback MUST remain distinct from ChartSearchAI
  end-user thumbs feedback.
- **FR-006.10**: Confidence MUST NOT redact final output. Flagged output remains
  visible for manual review with clear caveats.
- **FR-006.11**: Original/changed/rejected Answer and In-Depth drafts MUST survive
  evidence capture as review-only artifacts, separately rendered and excluded from
  canonical final evidence and model-judge content. Product reload semantics are product-owned.
- **FR-006.12**: Trace correlation MUST prefer per-turn request identity and reject
  explicit request/session/question mismatches. A bounded exact-question/time match
  is allowed only for traces lacking those keys; never borrow an adjacent turn's trace.

## Inputs, evidence and provenance

Clinical inputs remain authored JSON under a selected data root: scenario files,
comparison sets and backend settings. The included `demo` set anchors medication
and abstention probes on reviewed patient fixtures. Experiments may choose other
corpora; no hard-coded product topology or local model source is authoritative.
Catalyst inputs are the selected suite, source/dialect/schema context and model-team
configuration. [Feature 008](../008-catalyst-query-workbench/spec.md) owns the Catalyst experiment protocol.

Freeze required input bytes and digests, configuration without secrets, bounded
clinical fixtures, requests/responses, traces, deterministic evaluations, optional
model judgments and human rationale into the run packet. Resume records identify
ancestry and reused cells; new collection cannot silently inherit changed inputs.
Record supplied target claims separately from observed runtime identity; missing
facts and conflicts remain visible. A repository URL alone is not evidence that
its revision is running. Feature emitters own wire-format schemas and versions.

Reports may be regenerated with no service access. Evaluation/review that calls a
model is a separate operation with provider costs and disclosure implications.
Credentials and private reasoning are excluded. Captured clinical evidence is
bounded, not automatically safe to publish: deliberate review/redaction is required.

## Out of scope

Workspace catalogs, component pins/checkouts, product builds/tests as delivery
orchestration, service lifecycle, deployments, releases and website publication
are owned outside the runner. Clinician RCT design, NASA-TLX, non-inferiority,
randomized crossover and additional inter-rater statistics are not MVP acceptance.
No extra database backend or compatibility layout is required.

## Verification

Use the [implementation and isolation plan](plan.md). Verify supported CLI shapes,
positive/blocked configuration, clinical and Catalyst collection, supplied/observed/
missing/conflicting provenance, diverse evidence and trace failures, reviewer
records and portable offline reports. Product acceptance requires real interfaces;
unit doubles do not establish it. Website parity/publication and deployed release
acceptance are separate owner decisions, not inferred from harness tests.
