# Catalyst FHIR Sidecar — Source Brief

**Status**: Source brief — feeds `/speckit-specify` for feature 011.
**Roadmap entry**: M10 (Planning) — `011-catalyst-fhir-sidecar-poc`.
**Last updated**: 2026-05-17.
**Paired canvas**: [`specs/artifacts/canvases/catalyst-fhir-sidecar.canvas.tsx`](../canvases/catalyst-fhir-sidecar.canvas.tsx).

This document is the authoritative architectural brief for the Catalyst FHIR sidecar POC. It is the **input** to Spec Kit commands (`/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`). Spec Kit–generated artifacts live under `specs/011-catalyst-fhir-sidecar-poc/` after Phase 2. Do not edit the generated artifacts; update this brief instead.

---

## 1. Problem framing

**Catalyst is the core project.** OpenELIS Global 2 (OE2) is the supported host platform.

Catalyst has been developed as a Python multi-service sidecar (gateway + agents + MCP) alongside OE2. The prior NL-to-SQL framing (allowlist schema RAG → SQL generation → RBAC-gated execution) is still the long-term backend model, but it requires OE2 Java backend integration (M2–M4 in the OGC-070 plan) that has not yet landed.

The FHIR-first sidecar reboot:
- Starts from what OE2 already exposes today: two FHIR surfaces (HAPI sidecar, embedded providers).
- Uses FHIR read operations as the data access method, not direct SQL.
- Defers frontend/Carbon integration.
- Establishes a sidecar report/analytics UI as the interaction model now, not later.
- Pushes OE2 toward FHIR parallelism as a strategic driver — Catalyst is the forcing function.

This is not a change of project identity. Catalyst remains the lab AI sidecar. It is a change of initial integration layer.

---

## 2. Target architecture

```
Lab user / reviewer
       │
       ▼
Catalyst sidecar UI (report portal)
       │
       ▼
catalyst-gateway  (:8000, OpenAI-compat facade)
       │
       ▼
catalyst-agents   (RouterAgent → CatalystAgent)
       │
       ▼
catalyst-mcp      (:9102, FHIR + schema tools)
       │   ╔══════════════════════════╗
       ├──►║  OE2 HAPI FHIR           ║  primary path (fast iteration)
       │   ║  fhir.openelis.org:8443  ║
       │   ╚══════════════════════════╝
       │   ╔══════════════════════════╗
       └──►║  OE2 embedded FHIR       ║  parity probe (production semantics)
           ║  /OpenELIS-Global/fhir/* ║
           ╚══════════════════════════╝

OpenELIS Global 2 (OE2)
  ├── OE Java webapp (clinlims PostgreSQL)
  ├── FHIR Transform / FhirTransformServiceImpl → writes to HAPI
  ├── Embedded FHIR providers (Patient, ServiceRequest, Observation, DiagnosticReport, Practitioner, Organization)
  └── HAPI FHIR sidecar (fhir.openelis.org — separate container, same DB)
```

OE2 is consumed as a **sibling checkout** via `HARNESS_OE2_ROOT` or `OPENELIS_ROOT` env override. It is not vendored or added as a submodule — consistent with M0 convention and existing feature 002 usage.

---

## 3. OE2 FHIR layer facts (as of 2026-05-17)

These are the measured ground-truth facts that Spec Kit clarification and the research.md should refine.

| Fact | Detail |
|------|--------|
| HAPI FHIR sidecar | Container `fhir.openelis.org`; ports `8081:8080` / `8444:8443`; image `itechuw/openelis-global-2-fhir:develop`; config from `volume/properties/hapi_application.yaml` |
| HAPI DB | Shares `clinlims` PostgreSQL with the main app; `FHIR_DATASOURCE_*` env vars point at `db.openelis.org:5432/clinlims` |
| HAPI auth | No application-layer auth in `hapi_application.yaml`; CORS allows `*`; network/TLS boundary is the only protection |
| HAPI CORS | `allow_external_references: true`; `auto_create_placeholder_reference_targets: true`; OpenAPI UI enabled |
| Embedded FHIR | `FhirRestfulServer` servlet mapped at `/fhir/*` on the WAR context (`/OpenELIS-Global/fhir/`); registered as Spring `IResourceProvider` beans |
| Embedded providers present | `Patient`, `Organization`, `Practitioner`, `ServiceRequest`, `Observation`, `DiagnosticReport` |
| Embedded providers absent | `Specimen` (in subscription/transform plumbing; no dedicated embedded provider) |
| FHIR sync path | `FhirTransformServiceImpl` builds FHIR bundles and POSTs to HAPI via HAPI Java client; triggered on OE2 clinical transactions |
| Embedded FHIR auth | Spring Security; `Basic` auth (HTTP `Authorization: Basic …`) or session cookie required; embedded `/fhir/*` is NOT an open page |
| nginx proxy | `nginx-prod.conf` proxies `/api/` only; `/fhir` path is **not** proxied; Catalyst must hit ports 8081/8444 (HAPI) or 8080/8443 (webapp) directly |
| Backfill/sync trigger | `FhirTransformationController` at `/OEToFhir` (manual trigger); `org.openelisglobal.fhir.transformOnStartup=false` by default |
| LOINC in OE2 | Liquibase migrations exist for LOINC (`2.7.x.x/add_loinc_code.xml`, `2.8.x.x/loinc.xml`, `3.1.x.x/dictionary-loinc.xml`, `3.1.x.x/panel_loinc.xml`) |
| compose files | Production: `docker-compose.yml`; dev (with locally built WAR): `dev.docker-compose.yml` |

**Key sources in OE2 repo:**
- `src/main/java/org/openelisglobal/fhir/providers/` — embedded provider classes
- `src/main/java/org/openelisglobal/dataexchange/fhir/service/FhirTransformServiceImpl.java` — domain→FHIR transform
- `src/main/java/org/openelisglobal/security/SecurityConfig.java` — auth chains
- `src/main/java/org/openelisglobal/fhir/transormation/controller/FhirTransformationController.java` — manual backfill endpoints
- `fhir/hapi_application.yaml` — HAPI config
- `docker-compose.yml`, `dev.docker-compose.yml` — service topology

---

## 4. Resource coverage stance

| Resource | OE2 HAPI | OE2 Embedded | Required for POC |
|----------|----------|--------------|-----------------|
| `Patient` | Yes | Yes | Yes |
| `ServiceRequest` | Yes | Yes | Yes |
| `Observation` | Yes | Yes | Yes |
| `DiagnosticReport` | Yes | Yes | Yes |
| `Practitioner` | Yes | Yes | Yes |
| `Organization` | Yes | Yes | Yes |
| `Specimen` | Partial (via subscription/transform) | No dedicated provider | Gap — document if missing |

If `Specimen` is not reliably present at POC time, it is recorded in the OE2 FHIR-layer gap log rather than papered over with SQL.

---

## 5. Surface choice rationale

**HAPI-first for POC.** Catalyst MCP talks to the HAPI sidecar as a clean service boundary. No Spring Security session needed; only network access. Fast iteration.

**Embedded-FHIR parity probe (M10-F).** After the HAPI-grounded answer path is working, replay the same canonical questions through the embedded providers. Divergences are recorded as OE2-side gaps for upstream filing. The parity probe is what makes M10 evidence credible beyond "it works against the permissive HAPI container."

---

## 6. Canonical POC question set

Success criteria measure against **all five questions**. These are the acceptance questions for the POC — not negotiable, not expandable without a spec change.

| # | Question | Primary FHIR resources |
|---|----------|----------------------|
| 1 | "Show recent lab results for patient X." | `Patient`, `Observation` |
| 2 | "What tests were ordered for patient X?" | `Patient`, `ServiceRequest` |
| 3 | "Summarize abnormal results for patient X." | `Patient`, `Observation` |
| 4 | "Which diagnostic reports are available for patient X?" | `Patient`, `DiagnosticReport` |
| 5 | "What results are linked to order Y?" | `ServiceRequest`, `Observation` |

Each answer must cite the FHIR resource IDs it used. IDs must resolve in OE2 (both HAPI and embedded for the parity probe).

---

## 7. Scout-style sidecar UI brief

The sidecar UI is the **first-pass lab report and analytics portal**, not just a chatbox. This framing is intentional: it positions Catalyst alongside how Duke DIHI Scout structures clinical AI output — answer quality grounded by evidence cards, not free-form chat.

The UI presents:

1. **Question input** — free-text question; patient/order context selector.
2. **Answer panel** — LLM-generated answer with inline citation markers `[O/1]`, `[SR/2]`, etc. referencing FHIR resource IDs.
3. **Evidence cards** — grouped by FHIR resource type. Each card: resource type badge, resource ID, display text (e.g. observation name + value + date + flag), link to resolve in OE2 if available.
4. **Lab-result table** — for `Observation` resources: test name, value, units, reference range, abnormal flag, effective date, order reference.
5. **Lab timeline** — time-ordered view of `Observation` and `DiagnosticReport` resources for the patient, with abnormal flags highlighted.
6. **Debug drawer** — on demand: FHIR query plan (which tools were called, what queries were issued), raw resource IDs, raw resource snippet viewer.

The UI is Catalyst-owned and sidecar-deployed. It is **not** integrated into the OE2 React frontend or Carbon design system at this stage. That integration is deferred.

Technology choice (HTMX gateway-served vs separate Vite app) is an open question for `/speckit-clarify`.

---

## 8. MCP tool sketch

These replace / extend the current `get_query_context` / `validate_sql` MCP tools. The agent should call these via the MCP protocol (HTTP/streamable MCP), not the current stub `mcp_client.get_schema()` bypass.

| Tool | Description |
|------|-------------|
| `search_patient` | Search for patients by name/identifier; returns `Patient` bundle |
| `get_patient_context` | Demographic + identifier summary for a patient |
| `get_service_requests` | Lab orders for a patient; optional date range |
| `get_observations` | Lab result `Observation` resources for a patient; optional test code filter |
| `get_diagnostic_reports` | `DiagnosticReport` resources for a patient |
| `get_resource_by_reference` | Resolve a FHIR reference (`ResourceType/id`) |
| `build_patient_lab_timeline` | Chronological merge of `Observation` + `DiagnosticReport` for a patient |

Current MCP state: `get_query_context` returns mock schema; `validate_sql` does regex-based SQL checking. `MCP_DB_ENABLED=false` by default. The FHIR tools are new — `psycopg2-binary` is present in the MCP deps but not used; `httpx` (via gateway) is available.

---

## 9. Sidecar response contract sketch

The gateway response shape that the sidecar UI and harness adapter will consume:

```json
{
  "answer": "string — LLM-generated answer",
  "facts": [
    {
      "text": "string — compact fact extracted from FHIR resource",
      "source_ref": "ResourceType/id"
    }
  ],
  "citations": [
    {
      "index": 1,
      "resourceType": "Observation",
      "id": "string",
      "url": "https://fhir.openelis.org:8444/fhir/Observation/...",
      "display": "string — human-readable label"
    }
  ],
  "uiBlocks": [
    {
      "type": "lab_result_table",
      "rows": [
        {
          "test": "string",
          "value": "string",
          "unit": "string",
          "refRange": "string",
          "flag": "N|L|H|LL|HH|null",
          "date": "ISO-8601",
          "orderRef": "ServiceRequest/id"
        }
      ]
    },
    {
      "type": "lab_timeline",
      "events": [
        {
          "date": "ISO-8601",
          "resourceType": "Observation|DiagnosticReport",
          "id": "string",
          "display": "string",
          "flag": "abnormal|normal|null"
        }
      ]
    }
  ],
  "provenance": {
    "fhir_surface": "hapi|embedded|hybrid",
    "fhir_base_url": "string",
    "tools_called": ["string"],
    "resource_ids": ["ResourceType/id"]
  }
}
```

This contract feeds `contracts/sidecar_response.schema.json` produced by `/speckit-plan`.

---

## 10. Sibling-checkout assumption

OE2 is consumed as a sibling checkout alongside this harness repo:

```
../OpenELIS-Global-2/   (or $HARNESS_OE2_ROOT / $OPENELIS_ROOT)
```

This matches the M0 convention established for `chartsearchai`, `querystore`, and feature 002's `OPENELIS_ROOT` usage. OE2 is **not** added as a submodule of this harness. Catalyst Python code lives in the `targets/catalyst` submodule, pinned to `DIGI-UW/openelis-catalyst` (which OE2's `origin/develop` now mirrors at `projects/catalyst`).

For the harness adapter smoke (M10-E), the compose command will be:

```bash
docker compose -f $HARNESS_OE2_ROOT/dev.docker-compose.yml up -d   # bring up OE2
docker compose -f targets/catalyst/catalyst-dev.docker-compose.yml up -d  # bring up Catalyst sidecar
```

---

## 11. Out of scope (POC)

These items are explicitly deferred. Attempting them in the POC would derail the fast-iteration goal.

- **SQL execution** — `catalyst-mcp.validate_sql` stays available but is not on the POC critical path. Full SQL execution requires OE2 Java backend integration (OGC-070 M2).
- **OE2 frontend / Carbon UI integration** — deferred. Sidecar UI is Catalyst-owned, not OE2 embedded.
- **LocalPHI mode** — patient data in LLM context. Deferred per OGC-070 plan; requires Phase 2 security hardening.
- **Catalyst RBAC / audit Java backend integration** — requires OGC-070 M2 Java work.
- **Full OE2 FHIR sync / backfill engineering** — OE2-side work; referenced as host requirement, not built here.
- **`openelis-catalyst` repo housekeeping** — stale README paths (still say `projects/catalyst/…`), multi-agent default port collision with MCP (9102 used by both), etc. Tracked in the standalone repo, not here.
- **OE2 source-tree changes** — nginx `/fhir` route, HAPI auth hardening, etc. Filed upstream from the M10-F gap log.
- **ChromaDB RAG schema retrieval** — OGC-070 M1 milestone; out of scope for FHIR POC.

---

## 12. Open questions for `/speckit-clarify`

These must be resolved before Phase 2 spec artifacts are authored:

1. **HAPI auth model** — Is the HAPI container intentionally unauthenticated at the app layer for dev, and do we add a basic-auth header or network control for the POC?
2. **Specimen coverage** — If `Specimen` is not reliably present in the HAPI store at POC time, do we document the gap and proceed with the five canonical questions as-is, or adjust the question set?
3. **Lane name** — `openelis` (host-context naming) vs `catalyst` (project-naming) for the new roadmap lane. Current plan uses `openelis`; user may prefer `catalyst`.
4. **Sidecar UI hosting** — Gateway-served (small Flask/FastAPI-served static HTML + HTMX from `catalyst-gateway`) vs separate Vite/React app in the `openelis-catalyst` repo? Gateway-served is simpler for POC.
5. **Evidence-display granularity** — Should evidence cards link back into the OE2 legacy UI (`/OpenELIS-Global/…`) for patient/order drill-down, or only show FHIR resource JSON?

---

## 13. References

**OE2 files (sibling checkout at `$OPENELIS_ROOT`):**
- `docker-compose.yml`, `dev.docker-compose.yml` — service topology
- `fhir/hapi_application.yaml` — HAPI FHIR config
- `src/main/java/org/openelisglobal/fhir/providers/` — embedded FHIR provider classes
- `src/main/java/org/openelisglobal/dataexchange/fhir/service/FhirTransformServiceImpl.java`
- `src/main/java/org/openelisglobal/security/SecurityConfig.java`
- `volume/nginx/nginx-prod.conf` — confirms `/fhir` not proxied
- `specs/OGC-070-catalyst-assistant/plan.md` — Catalyst milestone plan (M0.0–M5)

**Catalyst submodule (`targets/catalyst`):**
- `catalyst-dev.docker-compose.yml` — Catalyst four-service compose (gateway, router, agent, mcp)
- `env.recommended` — env template; `MCP_DB_ENABLED=false` default, `MCP_DB_HOST=db.openelis.org`
- `catalyst-mcp/src/tools/schema_tools.py` — current mock `get_query_context` / `validate_sql`
- `catalyst-mcp/src/config.py` — `load_database_config()` gated by `MCP_DB_ENABLED`
- `catalyst-agents/src/agents/catalyst_executor.py` — calls stub `mcp_client.get_schema()` (bypasses MCP on hot path — must be fixed in M10-C)
- `tests/run_tests.sh` — current smoke test orchestrator

**Harness artifacts:**
- `harness/targets.yaml` — `catalyst` entry (currently `evidence_status: scaffolding`, no shared profiles)
- `adapters/catalyst/README.md` — placeholder (updated in Phase 3)
- Feature 002 M2-H: `specs/002-openmrs-demo-data-2-8-remap/plan.md` — OpenELIS feasibility + LOINC skeleton (terminology input to M10)

**Canvases updated by this brief:**
- [`specs/artifacts/canvases/validation-research.canvas.tsx`](../canvases/validation-research.canvas.tsx)
- [`specs/artifacts/canvases/scout-comparative-analysis.canvas.tsx`](../canvases/scout-comparative-analysis.canvas.tsx)
- [`specs/artifacts/canvases/clinical-ai-research-guidance.canvas.tsx`](../canvases/clinical-ai-research-guidance.canvas.tsx)
