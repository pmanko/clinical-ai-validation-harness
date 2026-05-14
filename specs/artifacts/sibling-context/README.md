# Sibling Project Context Snapshots

This directory holds **read-only durable snapshots** of context documents copied from sibling target repositories into the harness's artifact tree. Their purpose is to give harness reviewers and downstream features (eval suites, validation runs, planning sessions) a stable, version-controlled reference to the dev-context that exists in the target repos as untracked or in-flight notes.

These are **snapshots, not source-of-truth**. The authoritative copy lives in the originating repository. When the upstream changes, the snapshot here can be refreshed by a deliberate copy step that records the upstream commit / file checksum in the run manifest.

## Inventory

| File | Source repository | Source path | Snapshot date | Purpose |
|---|---|---|---|---|
| `chartsearchai-local-dev-validation-runbook.md` | `openmrs-module-chartsearchai` | `docs/local-dev-validation-runbook.md` | 2026-05-13 | Verified local-dev setup + validation ladder for chartsearchai (Java, Maven, ONNX model paths, SDK setup, `EnrichedRetrievalEvalTest`). Load-bearing for the harness-thin-layer at M2-F of feature 002. |
| `chartsearchai-openmrs-ai-dev-context.md` | `openmrs-module-chartsearchai` | `docs/openmrs-ai-dev-context.md` | 2026-05-13 | Dev-session context dump (2026-05-12) covering chartsearchai + querystore architecture, per-type indices (`openmrs_obs`, `openmrs_condition`, ...), document shape (`text` + `embedding` + `patient_uuid` + `date` + `resource_type` + `resource_uuid`), serializer classes. Load-bearing for understanding what M4 retrieval evaluation will consume from the remapped demo data. |

## Why snapshots, not symlinks or refs

- Source files are currently untracked in `openmrs-module-chartsearchai` (no committed origin URL yet).
- Harness reviewers should be able to read the context as-of a frozen date when reviewing this feature's spec/plan/tasks, even if upstream evolves.
- Provenance (origin path + snapshot date) is recorded here; downstream runs that depend on these notes should reference both the snapshot file and the originating repo path in their run manifest.

## Refresh policy

Refreshing a snapshot is a deliberate action: copy the upstream file again, update the inventory date, and record the change in a PCCP-style record under the consuming feature's `pccp/` directory if the change materially affects evaluation behavior.
