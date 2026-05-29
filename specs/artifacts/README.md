# Spec Artifact Index

Durable planning and research artifacts that support the feature roadmap:

- `canvases/validation-research.canvas.tsx`
  - Validation roadmap, architecture, validation flow, and demo-data remap plan.
- `canvases/cross-project-comparison.canvas.tsx`
  - Comparative synthesis across chartsearchai, openmrs_chatbot, and Catalyst.
- `canvases/sqlmesh-transformation-flow.canvas.tsx`
  - Concise process map for how feature 002 uses SQLMesh to materialize the OpenMRS 2.7-to-2.8 transform.
- `canvases/scout-comparative-analysis.canvas.tsx`
  - Deep-dive analysis of Duke DIHI Scout and implications for chartsearchai, openmrs_chatbot, and Catalyst.
- `canvases/chartsearchai-and-querystore.canvas.tsx`
  - chartsearchai + querystore architecture (today's standalone vs tomorrow's querystore-backed), port map, upstream status, and harness M3 + M8 integration points.
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
- `handoffs/session-handoff-2026-05-12.md`
  - Historical project setup and planning handoff snapshot.

These files are intentionally checked in as spec artifacts so research context travels with this repository without making `docs/` a planning archive.
