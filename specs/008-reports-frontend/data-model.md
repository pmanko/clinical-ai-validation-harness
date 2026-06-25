# Phase 1 Data Model: Validation Run Reporting Platform

**Feature**: 008-reports-frontend · **Date**: 2026-06-25

Derived from the spec's Key Entities and the file-based data-model investigation. Entities map ~1:1 to
Prisma models over SQLite (Postgres-ready). **Aggregations (benchmark, per-arm summary) are ingested as
producer-computed values, not derived in the platform** (research Decision 5) — they are stored
columns/rows, never computed views.

## Entities

### Run — the spine
One per validation execution OR judging pass.
- `runId` (PK, uuid), `comparisonSetId` (FK), `runDir` (physical dir; may differ from `runId` for judged siblings — authoritative for locating data), `parentRunId` (FK→Run, nullable — a judging pass that reused another run's results), `gitSha`, `datasetVersion`, `schemaMappingVersion`, `evidenceStatus`, `referenceDate`, `startedAt`, `completedAt`, `generatedAt`.
- Relationships: N:1 ComparisonSet; self-ref `parentRunId`; 1:N Result, JudgeRow, ArmAggregate, Adjudication.

### ComparisonSet — input run plan
- `id` (PK); N:M Scenario (via `ComparisonSetScenario`); N:M Arm (via `ComparisonSetArm`).

### Scenario — input
- `id` (PK), `patientUuid` (FK→Patient), `shouldAbstain` (bool), `shouldCiteResourceTypes` (json), `tags` (json).
- 1:N `ScenarioTurn` (`scenarioId`, `n`, `question`).

### Arm — input registry ("backend")
- `backendId` (PK), `label`, `endpointUrl`, `modelName`, `indepthEndpointUrl?`, `indepthModelName?`, `kind` (`single`|`team`).
- 1:N `ArmRole` (`role`, `modelId`) for team makeup.

### Model — registry
- `modelId` (PK), `family`, `params`, `quant`, `note`.

### Patient — referenced ground truth (minimal)
- `uuid` (PK), `display`, `gender`, `birthdate`. The chart snapshot + `valid_uuids` stay in the harness fixtures; the platform references the patient, **not** the clinical records (data boundary).

### Result — the fact table
- `id` (PK), `runId` (FK), `scenarioId` (FK), `armId` (FK), `turn`, `answer` (text), `disclaimer?`, `responseModel`, `blocks` (json), `error?`, `startedAt`, `endedAt`, `referenceDate`, and metrics (`httpStatus`, `latencyMs`, `jsonValid`, `answerChars`, `citationCount`, `abstained`, `tokensIn`, `tokensOut`).
- UNIQUE (`runId`, `scenarioId`, `armId`, `turn`).
- 1:N `ResultReference` (`idx`, `resourceType`, `resourceUuid`, `date`).
- 1:1 `IndepthResult` (`answer`, `modelName`, `latencyMs`, `httpStatus`, `error?`) — the first-turn two-call artifact.

### Trace
- `id` (PK), `resultId` (FK), `levelId`, `steps` (json: orchestrator/retrieval/validator/writer), `answerConfidenceLevel/Note`, `indepthConfidenceLevel/Note`, `inDepthClaims` (json), `referenceDate`.
- **Correlation rule (the current defect, fixed at ingest)**: resolve `resultId` by `levelId == arm.modelName` AND `ts ∈ [startedAt, endedAt] ± 5s` — NOT by `backendId`.

### JudgeRow — advisory automated score
- `id` (PK), `runId` (FK), `scenarioId` (FK), `armId` (FK), `accuracy`, `completeness`, `relevance`, `abstentionOutcome`, `citationGroundedness`, `harm` (bool), `temporalDateAccuracy?`, `temporalWindow?`, `temporalTrend?`, `citationResolution` (json), `note`.
- UNIQUE (`runId`, `scenarioId`, `armId`).
- 1:1 `JudgeBackground` (`support`, `addedValue`, `noNewHarm`, `conciseness`, `nClaims`, `note`) — team In-Depth only.

### ArmAggregate — producer-computed, INGESTED (research Decision 5)
- `runId` (FK), `armId` (FK), `benchmark`, `answerMeans` (json), `inDepthMeans?` (json), `harmCount`, `confabCount`. PK (`runId`, `armId`).
- **Rule**: the platform NEVER recomputes these; the headline shown anywhere == this ingested row.

### Reviewer
- `id` (PK), `identity`, `tier` (`owner`|`domain`|`clinical`).

### Adjudication — human review, the calibration reference
- `id` (PK), `runId` (FK), `scenarioId` (FK), `armId` (FK), `reviewerId` (FK), `axes` (json), `harm` (bool), `note`, `judgedAt`.
- **Rule**: multiple reviewers per cell allowed, no overwrite (FR-018); the calibrated headline is scoped to the reviewed subset (FR-019).

### PublishedReport — catalog entry
- `slug` (PK), `runId` (FK — `meta.run_dir`, may be a judged sibling), `comparisonSetId`, `title`, `summary`, `takeaway`, `sortOrder`, `featured` (bool), `hidden` (bool), `hasLive` (bool).
- **Rule**: prose is editable and kept separate from data-derived scores; `sortOrder`/`featured`/`hidden` are in-app curation state (FR-016).

### CatalogMeta — singleton
- `intro`, `scoringNote` — the catalog header prose.

## Key relationships

- Run —N:1— ComparisonSet; Run —self— parentRun (judged sibling).
- Run —1:N— Result —1:N— ResultReference; Result —1:1— IndepthResult; Result —1:1?— Trace.
- Run —1:N— JudgeRow —1:1?— JudgeBackground; Run —1:N— ArmAggregate (one per arm).
- Run —1:N— Adjudication —N:1— Reviewer.
- PublishedReport —N:1— Run.

## Validation rules (from requirements)

- A Result with no matching JudgeRow renders as "answered, not scored" — never dropped (FR-010, edge case).
- A Trace correlates by `modelName`, never `backendId` (FR-008, edge case).
- ArmAggregate values are ingested, never recomputed (FR-007, research Decision 5).
- Adjudications never overwrite each other; the JudgeRow is advisory, the Adjudication is the reference (FR-018).
- A judged-sibling Run attributes Results to the parent and JudgeRows to itself (FR-009).

## State / lifecycle

- **Run**: ingesting → answered (Results present) → scored (JudgeRow + ArmAggregate present) → published (PublishedReport row) → reviewed (Adjudications present; calibrated headline available).
- **Ingest is idempotent**: re-ingesting a run upserts Result / JudgeRow / ArmAggregate / Trace by their unique keys (safe after a re-judge or a scoring-export change).
