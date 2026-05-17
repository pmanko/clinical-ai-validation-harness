# Feature 003: ChartSearchAI Bring-Up + Playwright Smoke Test

**Status**: in-progress | **Started**: 2026-05-16 | **Predecessor**: 002 (transformed openmrs_test corpus)

## Goal

Bring up the upstream `chartsearchai` OpenMRS module on a 2.8 RefApp stack pointed at the transformed `openmrs_test` corpus (5,284 legacy patients delivered by feature 002), and exercise it end-to-end with a Playwright smoke test that confirms a clinician-style natural-language question against a real demo patient returns a grounded answer with citations.

This is the M2-F.1 milestone (SC-015) that feature 002 deferred at T064a-f.

## Success criteria

- **SC-003.1**: `make chartsearch-up` boots the chartsearch-flavored backend + frontend + gateway alongside a chartsearch-owned MariaDB seeded from feature 002's `refapp_28_demo.sql.gz` dump. Backend health-check passes within 15 min cold (Liquibase delta from 3.6.0→nightly + first-time module install).
- **SC-003.2**: `GET /ws/rest/v1/module` lists `chartsearchai` with `started: true`.
- **SC-003.3**: The frontend renders the **Ask AI about this patient** sparkle button on a patient chart for a user with the `AI Query Patient Data` privilege.
- **SC-003.4**: Playwright smoke test (`evals/playwright/tests/chartsearchai.smoke.spec.ts`) passes against the running stack with the remote LLM engine configured. Test asserts: (a) chat panel renders within 5s of clicking sparkle, (b) response text non-empty within 60s of submit, (c) **References** section contains ≥1 numbered citation backed by a real record in the patient's chart.
- **SC-003.5**: Both LLM engines (`remote` default, `local` as opt-in) are wired into the compose file via env vars. README documents both paths.

## Functional requirements

- **FR-003.1**: Backend MUST be built from a Dockerfile that COPYs `chartsearchai` from `targets/chartsearchai/` (the harness's submodule pin) rather than `git clone --depth 1` from upstream. This honors the M0 target-pinning principle.
- **FR-003.2**: Frontend MUST be built from a Dockerfile that bakes `@openmrs/esm-chartsearchai-app` into the SPA bundle (matching upstream's pattern; this ESM is NOT a submodule, so `git clone --depth 1` is acceptable here).
- **FR-003.3**: Backend MUST point at the `openmrs` database in its OWN MariaDB instance (NOT the harness's existing `harness-openmrs-db`), to avoid Liquibase races between the base-RefApp 3.6.0 backend and the chartsearch-flavored backend.
- **FR-003.4**: That `openmrs` database MUST be seeded on first boot from feature 002's portable dump (`artifacts/<run>/transform/refapp_28_demo.sql.gz` — produced by `make dump-loaded` against `openmrs_test`).
- **FR-003.5**: LLM engine MUST be configurable via env vars (`CHARTSEARCH_LLM_ENGINE`, `CHARTSEARCH_REMOTE_ENDPOINT_URL`, `CHARTSEARCH_REMOTE_MODEL_NAME`, `CHARTSEARCH_REMOTE_API_KEY`). The API key MUST be injected into `openmrs-runtime.properties` at container start (not stored in DB) per chartsearchai's security model.
- **FR-003.6**: Compose stack MUST run on the existing harness Docker network without conflicting with the base RefApp stack (different ports, different DB).
- **FR-003.7**: Playwright workspace MUST be self-contained under `evals/playwright/` with its own `package.json`, browser provisioning, and config. CI-friendly (headless, with junit + html reporters).

## Demo patient (smoke-test anchor)

| Field | Value |
|---|---|
| `patient_id` | 2429 |
| `uuid` | `dd75c020-1691-11df-97a5-7038c432aabf` |
| Given name | Zabella |
| Family name | Halambe |
| Gender | F |
| Birthdate | 1978-10-08 |
| Obs count | 303 |
| Encounter count | 11 |
| Order count | 39 |
| Condition count | 0 |
| Allergy count | 0 |

Selected as the richest chart in `openmrs_test` by obs count. Anchors the smoke test on a known-populated medication history (39 orders) so the AI has substantive material to ground its answer.

**Smoke question**: *"What medications is this patient on?"*

**Assertions**:
1. Answer text non-empty within 60 seconds (covers LLM cold-start + inference).
2. References panel renders with ≥1 numbered citation entry.
3. At least one citation is hyperlinked to a chart tab (Orders or similar).

NOT asserted: specific drug names. Brittle against LLM phrasing variance; the smoke test is about the wiring, not the AI's recall.

## Out of scope

- Local LLM smoke run (Gemma 4 E4B GGUF, ~5GB) — wired into compose but not the default; not part of CI smoke.
- `querystore` module bringup (separate feature, deferred).
- `openmrs_chatbot` module (separate feature).
- chartsearchai eval harness (`EnrichedRetrievalEvalTest`, 485 cases) — out of scope; that's an upstream development concern.
- Production LLM provider selection — endpoint URL + model name are env-driven; harness ships with placeholders and `.env.chartsearch.example`.
- Indexing / embedding-pipeline opt-in (`chartsearchai.embedding.preFilter=true`) — defaults to `false` (full-chart mode) per upstream; saves us the ONNX setup overhead for the first smoke.

## Non-functional notes

- **Apple Silicon (host arch `arm64/Darwin`)**: the chartsearchai backend image is Linux x86_64. Docker Desktop on M-series will run it under `linux/amd64` emulation — backend boot is slower (~3-5 min cold vs ~30s on x86_64); CPU LLM inference under emulation is impractical. This is why remote LLM is the default smoke-test path.
- **First boot cost**: ~3 min image build (with cache miss on `mvn package`), ~3 min container start (Liquibase + module init), ~30s to first chartsearchai response on remote engine. Subsequent boots cached.
- **Disk**: chartsearchai-owned DB volume ~250 MB after seed; backend image ~1.2 GB; frontend image ~150 MB. No 5GB GGUF model unless local engine is opted into.
