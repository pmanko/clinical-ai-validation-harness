# Spec Artifact Index

The [project evidence inventory](project-status/README.md) joins dated effort,
pull-request, artifact and publication observations. Current coordination belongs
to the umbrella and application requirements to their product owners.

Current planning and research artifacts that support the feature roadmap.
- [OpenMRS delivery](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#5-track-a-openmrs-contribution-delivery)
  - Umbrella-owned release criteria and signoffs. Product contracts own behavior.
- [Dual-provider conformance protocol](planning/openmrs-dual-provider-conformance-contract.md)
  - Shared fixture coverage, owning product tests and hash-bound runtime evidence.
- [Provider interface](https://github.com/pmanko/openclinai.org/blob/main/docs/openmrs-provider-interface.md)
  - Umbrella integration reference; native module API behavior remains product-owned.
- [QueryStore selection](https://github.com/pmanko/openmrs-module-querystore/blob/main/docs/adr.md#decision-17-context-slice-read--tiered-record-selection)
  - Product-owned selection and opt-in interpretation; the completed consolidation
    procedure is no longer a maintained harness plan.
- `planning/openmrs-dual-provider-upstream-inventory.md`
  - Dated baseline and upstream dispositions for the July rebuild, not current PR state.
- `planning/engine-parity-instrument.md`
  - Engine-ingress experiment and its recorded acceptance evidence.
- [Feature 006 clinical protocols](../006-validation-harness-mvp/spec.md#clinical-smoke-and-contextevaluation-protocols)
  - Real ChartSearchAI smoke (`SC-004.4`) and reviewed context/evaluation criteria
    (`MAH-CONSOLIDATION-2026-07-09-v1:G09/G21`), with record-level evidence and claim limits.
- `planning/hub-consolidation-roadmap-status.md`
  - Historical execution record for the superseded hub-only roadmap.
- `planning/chart-context-cache-research-plan-2026-07-15.md`
  - Measurement protocol for source/preparation/prefix/residency costs; product contracts and umbrella scheduling own implementation.
- [OpenClinAI documentation and visuals](https://github.com/pmanko/openclinai.org/tree/main/specs)
  - Website-facing diagrams and demonstration pages are umbrella-owned. The harness
    does not maintain a second canvas catalog.
- `planning/data-remap-2.8.md`
  - Demo-data remap plan for OpenMRS 2.8-compatible import work.
- `planning/metadata-schema.md`
  - Manifest and event schema notes for emitted validation metadata.
- `planning/pccp-change-record-template.md`
  - Governance/change-control template for material validation changes.
- `planning/otel-collector-config.yaml`
  - Supporting OpenTelemetry collector config for harness services.
- `planning/clinical-kb-research.md`
  - Dated literature and service research; Hub owns current knowledge-source behavior.
- `planning/lm-studio-api-reference.md`
  - Dated provider API research; bundled and Hub configuration are product-owned.
- `handoffs/session-handoff-2026-05-12.md`
  - Historical project setup and planning handoff snapshot.

These files are intentionally checked in as spec artifacts so research context travels with this repository without making `docs/` a planning archive.

Current model execution and knowledge-source behavior belong to [Med Agent Hub](https://github.com/pmanko/med-agent-hub/blob/main/README.md). Historical gateway/knowledge-service proposals are retained in Git history, not as active source briefs.
