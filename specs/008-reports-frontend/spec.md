# Feature Specification: Validation Run Reporting Platform

**Feature Branch**: `008-reports-frontend`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "it would be good to make an official spec" — for a clean, simple, extensible application that replaces the current three hand-generated HTML surfaces (the run catalog/index, the per-run report, the live dashboard) and the full-HTML republish/whole-directory-sync model with one data-backed platform: a queryable store of runs / run artifacts / run data and a single, shared, template-driven presentation. This spec is the UNIFIED application and absorbs two in-flight efforts — editable catalog/homepage curation and human review/adjudication — into one product.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a run's report from stored data (Priority: P1)

A researcher opens the public reports catalog, sees the list of published validation runs (each with its title, the models/arms compared, the question count, the date, and the headline scores), and clicks into one to read the full per-run report — the per-arm quality scores, the per-question answers with citations, the reasoning trace for team arms, and the In-Depth scoring. Everything is rendered from the run's stored data through a single shared presentation, not from a pre-baked standalone HTML file.

**Why this priority**: This is the core reader value and the MVP. It proves the data→presentation path: a run's results, scores, and trace are read from a queryable store and rendered once, so the report is consistent and free of the per-run full-HTML duplication that exists today. If only this ships, the project already delivers a clean, maintainable reporting surface.

**Independent Test**: Ingest one completed, judged run into the store, open the catalog, confirm the run appears with correct headline scores, drill into its report, and confirm the scores, answers, citations, and (for a team arm) the reasoning trace all render correctly — with no per-run HTML artifact involved.

**Acceptance Scenarios**:

1. **Given** a completed run in the store, **When** a reader opens the catalog, **Then** the run appears with its curated title, the arms compared, the question count, the date, and the headline benchmark/safety scores pulled from that run's data.
2. **Given** a run's report is open, **When** the reader views a team arm's answer, **Then** the per-question answer, citations, the reasoning-trace steps (orchestrator → retrieval → validator → writer), and the confidence treatment all render from the stored trace + judge data.
3. **Given** the same arm or score concept appears in both the catalog and the report, **When** its presentation is changed, **Then** the change is made in one shared definition and reflected in both surfaces.

---

### User Story 2 - Publish, curate, and edit the catalog through the app (Priority: P2)

An operator finishes a run and its judging, then publishes it by recording it in the store and supplying curated prose (a title, a one-paragraph summary, a takeaway) — all through the application, not by hand-editing a manifest file. The new run appears in the catalog immediately; no other run's report is regenerated and nothing re-uploads a whole directory of HTML. The operator can later edit a run's prose, reorder the catalog, and feature or hide runs, all in the app.

**Why this priority**: This removes the dominant operational pain — today every publish re-renders a 1–2 MB self-contained HTML per report, rebuilds the entire index from scratch, and syncs the whole reports directory, and curation means editing a JSON manifest by hand. Publishing and curating must become in-app, per-run operations. (Absorbs the in-flight editable catalog/homepage effort.)

**Independent Test**: Publish a second run through the app; confirm it appears in the catalog, the first run's report and rendering are untouched, and no full re-render of unrelated runs occurred. Edit the second run's takeaway, reorder it above the first, and hide a third — all in the UI — and confirm each change persists with no file editing and scores stay data-derived.

**Acceptance Scenarios**:

1. **Given** a completed, judged run, **When** the operator publishes it through the app with curated prose, **Then** it appears in the catalog and no other published run's rendered output changes.
2. **Given** a published run, **When** the operator edits its title/summary/takeaway in the app, **Then** only that run's prose updates and its scores remain derived from data.
3. **Given** a catalog of runs, **When** the operator reorders, features, or hides runs in the app, **Then** the catalog reflects the change and it persists across sessions.
4. **Given** the scoring/aggregation logic, **When** a report renders, **Then** the headline numbers are the ones computed once by the producing pipeline, so prose and numbers cannot drift.

---

### User Story 3 - Adjudicate a run with human review (Priority: P3)

A reviewer (owner, domain expert, or clinician) opens a run's report and adjudicates individual cells — scoring an answer's accuracy/completeness/relevance against the patient chart, flagging harm, and recording the rationale. Their human scores are captured per reviewer and tier, displayed alongside the LLM-judge scores (which stay clearly marked advisory), and, once a reviewed subset exists, used to present a calibrated headline with its uncertainty — distinct from the raw LLM-judge headline.

**Why this priority**: Human adjudication is the evidence-calibration backbone. The automated LLM judge is advisory; a physician-scored subset is what lets the platform make calibrated clinical-correctness claims rather than directional ones. The capability is actively in flight, so folding it into one app keeps a single coherent product. (Absorbs the in-flight human review/adjudication effort.)

**Independent Test**: A reviewer scores a handful of cells in a run through the app; confirm the human scores persist with the reviewer's identity and tier, display next to the LLM-judge scores, and that a calibrated headline (with uncertainty) appears for the reviewed subset, distinct from the LLM-judge headline.

**Acceptance Scenarios**:

1. **Given** a run's report, **When** a reviewer scores a cell (per-axis scores, harm flag, rationale note), **Then** the adjudication persists attributed to the reviewer and their tier.
2. **Given** a cell with both an LLM-judge score and a human adjudication, **When** a reader views it, **Then** both are shown distinctly, with the LLM judge marked advisory and the human review the calibration reference.
3. **Given** a human-reviewed subset of a run, **When** the headline is presented, **Then** a calibrated estimate with its uncertainty is shown, distinct from the raw LLM-judge headline.

---

### User Story 4 - Watch a run in progress (Priority: P4)

While a run is executing, an operator opens its live view and watches scenarios fill in per arm — the progress grid, per-cell status/latency, the resident models, the recent feed, and (on drill-in) the answer + reasoning trace as each cell completes — from the same store and the same shared presentation as the published report.

**Why this priority**: Live monitoring is valuable but secondary to the published catalog/report and the review flow, and it has a different runtime (a live feed over an active run rather than a settled, ingested one). Shipping it after the static and review paths lets the data model and presentation prove out first.

**Independent Test**: Start a run, open its live view, and confirm cells appear as they complete with correct status/latency and a drill-in trace — sharing the report's components rather than a separate implementation.

**Acceptance Scenarios**:

1. **Given** an executing run, **When** the operator opens the live view, **Then** completed cells appear with status/latency and update as more complete.
2. **Given** a live cell drill-in, **When** a team arm's cell has completed, **Then** its answer + reasoning trace render using the same components as the published report.

---

### User Story 5 - Query and consume run data (Priority: P5)

A researcher (or an automated agent) filters the catalog — by model/arm, comparison set, date, or score — to find relevant runs, and can retrieve a run's structured data (arms, per-arm scores, per-cell answers/traces, human adjudications) in a machine-readable form without scraping rendered HTML.

**Why this priority**: This is the extensibility payoff — a queryable store unlocks cross-run analysis, agent consumption, and future surfaces — but it builds on the data model proven by the earlier stories.

**Independent Test**: With several runs in the store, filter by a model and by a date range and confirm the correct subset returns; fetch one run's scores in a structured form and confirm it matches the rendered report.

**Acceptance Scenarios**:

1. **Given** multiple runs in the store, **When** a user filters by model/arm or comparison set or date, **Then** only matching runs are listed.
2. **Given** a run, **When** an agent requests its data in a structured form, **Then** it receives the arms, scores, per-cell answers/traces, and any human adjudications without parsing presentation HTML.

---

### Edge Cases

- A run published while its judging is incomplete (no scores yet) MUST render as "answer-only / not yet scored," not a broken or empty score table.
- A **judged sibling** — a scoring pass that reused another run's results and only added scores — MUST attribute results and scores to the right lineage without double-counting or losing the link to the underlying results.
- A cell's reasoning trace is recorded under the arm's **served model identity**, which can differ from the catalog's arm identifier; the platform MUST still correlate each cell to its trace (the divergence that currently breaks trace display).
- A scenario or arm present in a run's results but absent from its judging MUST render answers without scores rather than dropping the cell.
- An abstention, a fabricated citation, an unsupported claim, or a missing record MUST be represented faithfully in both the score view and the answer view, carried from the judge / citation-resolution data rather than inferred by the presentation.
- A cell adjudicated by more than one reviewer (different tiers) MUST show each review distinctly without silently overwriting, and the calibrated headline MUST make clear which reviewed subset it reflects.
- Human review covering only a subset of a run's cells MUST still yield a calibrated estimate scoped to (and labeled as) the reviewed subset.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST maintain a queryable store of validation runs and their artifacts — runs, the arms/models compared, scenarios, per-cell results (answers, citations, latency, status), reasoning traces, judge scores (per-axis and aggregated), human adjudications, and per-run provenance — as the read source for all surfaces, replacing reliance on scattered per-run files.
- **FR-002**: The platform MUST render the run catalog from the store: each entry shows the curated title, the arms compared, the question count, the date, and the headline scores derived from that run's data.
- **FR-003**: The platform MUST render a per-run report from the store: per-arm quality scores, per-question answers with citations, the reasoning trace for team arms, In-Depth/background scoring, and the per-section confidence treatment.
- **FR-004**: The platform MUST render every shared concept (arm makeup, confidence treatment, reasoning trace, answer/citations, score tables) from a SINGLE presentation definition reused across the catalog, the report, the live view, and the review view — eliminating the current per-surface duplication.
- **FR-005**: The platform MUST publish a run as a discrete record-and-curate operation that does NOT regenerate or re-upload any other run's rendered output; adding or editing one run MUST NOT re-render unrelated runs.
- **FR-006**: An operator MUST be able to attach and later edit curated prose (title, summary, takeaway) per run, kept separate from the data-derived scores so the two cannot drift.
- **FR-007**: The platform MUST serve score aggregations (the headline benchmark, per-arm summaries, safety counts) as values computed ONCE by the producing pipeline — the presentation MUST NOT re-derive or re-implement the scoring logic.
- **FR-008**: The platform MUST correlate each cell to its reasoning trace by the arm's served model identity (not the catalog arm identifier), so traces display for arms whose identifier differs from their model.
- **FR-009**: The platform MUST model run lineage as first-class and queryable — the comparison set a run belongs to, and the judged-sibling relationship — so reports attribute results and scores correctly.
- **FR-010**: The platform MUST render a run that is answered-but-not-yet-scored (or partially scored) without error, clearly indicating the missing scores rather than dropping cells.
- **FR-011**: Users MUST be able to filter the catalog by model/arm, comparison set, and date (at minimum) to locate runs.
- **FR-012**: The platform MUST expose each run's structured data (arms, scores, per-cell answers/traces, human adjudications) in a machine-readable form so agents/LLMs can consume it without scraping rendered HTML.
- **FR-013**: The platform MUST support a live view of an in-progress run that shows cells as they complete, sharing the report's presentation and reading from the same data path.
- **FR-014**: The store MUST be populated from the artifacts the existing validation harness already produces, so the harness's run-production responsibilities are unchanged by this feature.
- **FR-015**: The platform MUST faithfully carry evidence-bearing judge signals — abstention outcomes, citation resolution (supported/partly/unsupported), harm flags, and temporal-claim judgments — into both the score and answer views, without the presentation inventing or hiding them.
- **FR-016**: Operators MUST be able to curate the catalog/homepage through the application — edit per-run prose, reorder runs, and feature or hide runs — without hand-editing files; curation changes MUST persist.
- **FR-017**: Reviewers MUST be able to adjudicate a run's cells through the application — recording per-axis scores, a harm flag, and a rationale note — attributed to the reviewer and their tier (owner / domain expert / clinical).
- **FR-018**: The platform MUST display human adjudications alongside the LLM-judge scores, keeping the LLM judge clearly marked advisory and the human review the calibration reference, and never silently overwriting one reviewer's adjudication with another's.
- **FR-019**: When a human-reviewed subset of a run exists, the platform MUST present a calibrated headline estimate with its uncertainty, distinct from the raw LLM-judge headline and labeled with the reviewed subset it reflects.

### Key Entities *(include if feature involves data)*

- **Run**: A single validation execution (or a judging pass over one). Identity, the comparison set, the reference/simulated "now," timing, provenance (git sha, dataset version), and a lineage link to a parent run for judged siblings.
- **Comparison Set**: The named plan of which scenarios × arms a run covers.
- **Arm / Backend**: A configuration under test — a single model or a multi-model team — with its makeup (roles → models), endpoint/serving identity, and kind (single vs team).
- **Model**: A served model with family, size, and quantization metadata.
- **Scenario**: A patient-grounded question (or multi-turn conversation) with expectations (should-cite, should-abstain).
- **Cell / Result**: One arm's answer to one scenario (per turn) — the answer, citations, blocks, latency, status, and the nested In-Depth artifact.
- **Trace**: The reasoning record for a cell (orchestrator/retrieval/validator/writer steps + per-section confidence), correlated to a cell by served-model identity and time window.
- **Judge Row / Score**: The per-cell automated judged scores — accuracy/completeness/relevance, abstention outcome, citation groundedness, harm, temporal axes, citation resolution, and the In-Depth/background block — plus the derived per-arm aggregates. Advisory.
- **Reviewer**: A human adjudicator with an identity and a tier (owner / domain expert / clinical).
- **Adjudication / Review**: A human review of a cell — per-axis scores, a harm flag, a rationale note, the reviewer and tier, and the timestamp. The calibration reference.
- **Published Report**: A run surfaced in the public catalog — its slug, the run it points to (which may be a judged sibling), the curated title/summary/takeaway, its catalog ordering/featured/hidden state, and whether a live view is available.
- **Patient / Chart**: The closed-context ground truth a run's answers are scored against (referenced, not re-stored by this feature).

### Evidence, Provenance & Data Boundaries *(mandatory when clinical data, models, retrieval, mappings, or validation artifacts are involved)*

- **Clinical evidence records**: The per-cell answers and their citations reference patient chart records; both the automated and human scores are anchored to closed-context chart fixtures. This feature READS and DISPLAYS those; it does not produce or alter clinical evidence.
- **Decision rationale**: Each automated score carries the judge's note and each human adjudication carries the reviewer's rationale; the platform MUST display the rationale alongside the score so a reader can trace why a score was given.
- **Operating metadata**: Run manifests, the run-event log, per-arm frozen configuration, reasoning traces, automated judge outputs, human adjudications, and the curated report prose — captured in the store for query and display; the originating artifacts remain the producer's outputs.
- **Accepted deterministic inputs**: The comparison sets, the arm/backend registry, the scenarios, and the chart fixtures are reviewed inputs the platform reads but does not author.
- **Advisory inputs**: The automated LLM-judge scores and the curated per-run prose are advisory/editorial — clearly separated from the human-review calibration reference, and never overriding it.
- **PCCP/change record needs**: A change to the automated scoring/aggregation logic (which lives with the producing pipeline, not this platform) remains the producer's review surface; this platform displays computed values and human adjudications, so a scoring change is reflected by re-ingesting, not by re-implementing logic here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Publishing or re-curating a run regenerates/re-uploads only that run's entry — zero other published runs are re-rendered or re-uploaded (today: every publish rebuilds the whole index and re-uploads the reports directory).
- **SC-002**: Each shared rendered concept (arm card, confidence treatment, reasoning trace, score table) has exactly ONE presentation definition — verified by the absence of a second implementation of the same concept across surfaces (today: each is implemented twice, in two languages).
- **SC-003**: Every headline automated score shown is produced by a single computation in the producing pipeline — zero re-implementation of scoring/aggregation logic in the presentation layer, so prose and numbers cannot diverge.
- **SC-004**: A reader can locate a run by model/arm, comparison set, or date and open its report in under 30 seconds, without scanning files or knowing run identifiers.
- **SC-005**: Reasoning traces display for 100% of team-arm cells that recorded a trace (today: traces silently fail to correlate when the arm identifier differs from the served model).
- **SC-006**: A run's structured data (arms, scores, per-cell answers/traces, human adjudications) is retrievable in a machine-readable form for every published run, without parsing rendered HTML.
- **SC-007**: The published per-report payload is materially smaller than today's 1–2 MB self-contained HTML, because data and presentation are no longer inlined per run.
- **SC-008**: A run that is answered but not yet scored renders without error and is clearly labeled as unscored.
- **SC-009**: An operator can publish, edit prose, reorder, feature, and hide runs entirely through the application UI, with zero hand-editing of files.
- **SC-010**: A reviewer's adjudication of a cell is captured and displayed alongside the automated score, attributed to the reviewer and tier, with no silent overwrite when multiple reviewers score the same cell.
- **SC-011**: When a human-reviewed subset of a run exists, a calibrated headline with its uncertainty is shown distinct from the automated-judge headline and labeled with the reviewed subset.

## Assumptions

- The existing validation harness continues to PRODUCE its run artifacts (results, automated judge outputs, traces, manifests, and human-adjudication records) as it does today or with minimal additions; this feature consumes/ingests those — the producer contract is essentially unchanged (FR-014).
- Automated score aggregation logic stays with the producing pipeline; the platform displays computed values rather than re-deriving them (FR-007). This boundary is what prevents re-creating today's duplication in a new layer.
- The human-review calibration approach (per-cell adjudication + a calibrated estimate with uncertainty over a reviewed subset) reuses the harness's existing review/calibration model (the human-adjudication capability that exists but is currently unused).
- This spec is the UNIFIED application: it absorbs the in-flight `feat/editable-reports-homepage` (catalog/homepage curation → US2 / FR-016) and `feat/report-human-feedback` (human adjudication → US3 / FR-017–019). Those worktrees fold into this workstream rather than remaining separate efforts, and their work should be reconciled/migrated into this app rather than double-built.
- v1 prioritizes the published catalog + per-run report (US1/US2) and the review flow (US3); the live in-progress view (US4) and cross-run query/agent consumption (US5) are in scope but sequenced after the data model and shared presentation prove out.
- The platform serves run data through an application (data-backed rendering) rather than the current static-file-per-report + whole-directory-sync model; a machine-readable export covers the LLM/agent-readable need that static HTML twins serve today.
- The closed-context chart fixtures and the patient/scenario/arm registries are read as existing reviewed inputs; this feature does not author them.
- The public docs site is a SEPARATE surface (different stack and domain) and is not absorbed by this feature; this platform is the runs/reports surface.
