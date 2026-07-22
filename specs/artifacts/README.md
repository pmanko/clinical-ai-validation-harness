# Spec Artifact Index

Durable planning and research artifacts that support the feature roadmap:

- `planning/openmrs-dual-provider-parity-roadmap.md`
  - Approved canonical roadmap for preserving bundled ChartSearchAI and med-agent-hub behind one
    capability-driven OpenMRS interface. It supersedes the hub-only architecture roadmap.
- `planning/openmrs-dual-provider-parity-roadmap-status.md`
  - Mutable execution record for the dual-provider roadmap: baseline heads, gate evidence,
    signoffs, upstream dispositions, and approved deviations.
- `planning/openmrs-dual-provider-upstream-inventory.md`
  - Refreshed repository baseline plus the required keep/port/replace disposition for upstream
    and companion-branch changes before the ChartSearchAI and ESM rebuilds.
- `planning/openmrs-dual-provider-conformance-contract.md`
  - Provider-neutral lifecycle, context, QueryStore freshness, temporal, and safety contract that
    maps the versioned fixtures to their Java, Python, TypeScript, and harness test owners.
- `planning/engine-parity-instrument.md`
  - Approved goal spec for engine-level bundled-vs-hub parity: shared-engine design decisions,
    verbatim request capture/replay, the `engine-parity.v1` contract diff, and acceptance
    criteria AC-1..AC-6 for the scored parity run.
- `planning/hub-consolidation-roadmap.md`
  - Historical superseded roadmap for the prior hub-only clinical answer architecture. Completed
    evidence and still-valid decisions are preserved by reference from the dual-provider roadmap.
- `planning/hub-consolidation-roadmap-status.md`
  - Historical execution record for the superseded hub-only roadmap.
- `planning/chart-context-cache-research-plan-2026-07-15.md`
  - Tracked post-release research and implementation plan for model residency, prompt-prefix reuse,
    source-neutral patient-ledger caching, deterministic selection efficiency, freshness, and
    authorization safeguards.
- `canvases/validation-research.canvas.tsx`
  - Validation roadmap, architecture, validation flow, and demo-data remap plan.
- `canvases/cross-project-comparison.canvas.tsx`
  - Comparative synthesis across chartsearchai, openmrs_chatbot, and Catalyst.
- `canvases/sqlmesh-transformation-flow.canvas.tsx`
  - Concise process map for how feature 002 uses SQLMesh to materialize the OpenMRS 2.7-to-2.8 transform.
- `canvases/scout-comparative-analysis.canvas.tsx`
  - Deep-dive analysis of Duke DIHI Scout and implications for chartsearchai, openmrs_chatbot, and Catalyst.
- `canvases/chartsearchai-and-querystore.canvas.tsx`
  - Historical pre-relay chartsearchai + querystore architecture snapshot; superseded by the hub
    consolidation roadmap for current ownership and integration behavior.
- `canvases/demo-data-profile.canvas.tsx`
  - Profile of the loaded OpenMRS 2.8 demo corpus (5,284 patients): landscape metrics, richness/completeness assessment, content-verified phenotype cohorts, and curated data-rich validation patients. Measured live against schema `openmrs`.
- `canvases/clinical-ai-research-guidance.canvas.tsx`
  - Research grounding, maturity framing, and evolution guidance.
- `planning/data-remap-2.8.md`
  - Demo-data remap plan for OpenMRS 2.8-compatible import work.
- `planning/metadata-schema.md`
  - Manifest and event schema notes for emitted validation metadata.
- `planning/pccp-change-record-template.md`
  - Governance/change-control template for material validation changes.
- `planning/otel-collector-config.yaml`
  - Supporting OpenTelemetry collector config for harness services.
- `planning/catalyst-fhir-sidecar-brief.md`
  - Source brief that feeds `/speckit-specify` for feature 011 (Catalyst FHIR sidecar POC, M10).
- `planning/chartsearchai-model-gateway-brief.md`
  - Source brief that feeds `/speckit-specify` for feature 008 (chartsearchai model gateway, F008). New FastAPI service routing chartsearchai's LLM calls to classes of connections (local-runtime / cloud-api / agentic).
- `planning/clinical-kb-research.md`
  - Methodology survey + host evaluation matrix + recommendation for feature 009 (clinical knowledge base, F009). 15 cited sources covering MedRAG, MedAbstain, CUICurate, MedGraphRAG and related; DB-curated contextualization methodology sketch with sample prompt + YAML schema.
- `planning/clinical-kb-brief.md`
  - Source brief that feeds `/speckit-specify` for feature 009. Dedicated host-agnostic clinical-kb Python service (REST + MCP) with separable curation worker; orthogonal to chartsearchai's per-patient retrieval.
- `planning/lm-studio-api-reference.md`
  - Historical provider research on LM Studio's API surfaces. Superseded for ChartSearchAI by the med-agent-hub profile relay.
- `handoffs/session-handoff-2026-05-12.md`
  - Historical project setup and planning handoff snapshot.

These files are intentionally checked in as spec artifacts so research context travels with this repository without making `docs/` a planning archive.
