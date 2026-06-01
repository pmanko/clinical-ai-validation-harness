# Landscape & Sync — Today (2026-05-30)

Synthesis of a six-surface project recon, driving two goals:
- **GOAL A** — a demoable **006 validation-harness MVP** (simple evaluation workflow) in ~a couple of days.
- **GOAL B** — a **clean PR + GitHub history** across all repos, ready for a reviewer.

Every claim below is grounded in the recon evidence plus spot-verification against the live tree on branch `004-chartsearchai-adapter` (HEAD `ffe35fb`).

---

## 1. Landscape summary

**What the project IS.** `clinical-ai-validation-harness` is a Python orchestration framework (the `harness/` package) for validating clinical-AI pipelines against a remapped OpenMRS demo dataset. Its delivered spine: data import/profiling (002), schema mapping + ConceptMap authoring, SQLMesh transforms, and a `RunManifest` + `events.jsonl` metadata layer. It pins **6 target submodules**, drives a docker-compose stack (Caddy proxy + gateway + MariaDB + OpenMRS + frontend + Elasticsearch + OTEL), and exposes a `harness <subcommand>` CLI (`schema-diff`, `import-smoke`, `conceptmap`, `transform`, `sample`, `ocl`, `manifest`).

**The 6 submodules and their roles:**
- **chartsearchai** (`2a67d3a`, `004-chartsearchai-adapter` work; harness-integration pin) — the primary validation target. AI chart-search over an OpenAI-compatible LLM endpoint: `ModelSwitchService` (endpoint/model discovery + switch), `ChartSearchAiRestController` (REST: `GET/POST /endpoint`, `GET /endpoints`, `POST /model`, `POST /model/load`, `GET /models`, `POST /chat[/stream|/new|/refresh-chart]`, `GET /chat`), `RemoteLlmEngine` (OpenAI-compat wire contract — `response_format` + streaming + temperature/top_k). 50 test files. **ACTIVE.**
- **chartsearchai-esm** (`1955226`) — the OpenMRS ESM front-end. Carbon `MenuButton` sectioned model picker (per-endpoint section headers + radio groups), maximize + New-chat controls. API layer `fetchEndpoints`/`setEndpointModel` → `GET /chartsearchai/endpoints` + `POST /chartsearchai/endpoint`. 12 picker tests green. **ACTIVE.**
- **med-agent-hub** (`a085839`) — the as-built "Med Agent Team" backend. **In-process ReAct loop over typed tools (NOT A2A multi-process).** OpenAI-compat `/v1/chat/completions` (sync + buffer-then-stream SSE) + `/v1/models` (single `med-agent-team` id). `run_team()`: `google/gemma-4-e4b` orchestrator/synthesizer + a typed `medical_expert` tool (medgemma) + a typed `kb_search` tool, `MAX_TOOL_ITERATIONS=3`, envelope bound only on the final constrained synthesis call, guaranteed-valid fallback envelope. **Tier-1 KB** = 6 openly-licensed WHO snippets (FTS5 BM25 + keyword fallback, provenance per snippet). Single-stage Dockerfile, one uvicorn process (no honcho/Procfile). 14 tests (8 bridge + 6 KB). Legacy `sdk_agents/` + `mcp/` + 5 `a2a` test files are **dead code** (unreachable from `main.py → openai_compat.py → team.py`). **ACTIVE.**
- **querystore** (`ba1fa2c`, upstream main) — the runtime search tier (Lucene/MySQL/Elasticsearch CQRS read store off the clinical DB). Deployed omod, wired through compose (Elasticsearch profile), Makefile (`chartsearch-backend` tier-switch, `chartsearch-up`), `.env` overrides. **ACTIVE.**
- **openmrs_chatbot** (`2e723f8`, upstream main) — **PARKED.** `harness/targets.yaml` marks `validation_surface: unavailable`, `evidence_status: scaffolding`. Deferred to M12. No omod, no compose, no Makefile target.
- **catalyst** (`3c1f1aa`, initial import) — **PARKED.** `unavailable`/`scaffolding_only`. Deferred to M10 (Catalyst FHIR sidecar POC). No omod, no compose, no Makefile target.

**As-built med-agent-hub bridge + team + KB** = an in-process ReAct loop (no A2A, no MCP protocol). chartsearchai selects it as one endpoint section ("Med Agent Hub") in the Carbon picker, switches to it via two global-property flips (`POST /chartsearchai/endpoint`), and drives it over the exact `/v1/chat/completions` contract LM Studio uses. The team returns chartsearchai's strict `{answer, references, blocks}` envelope.

**The chartsearchai backend + sectioned picker** are functionally complete and tested: the REST surface, model-switch service, endpoint registry, wire contract, and the Carbon two-level picker all match their as-built designs with no observed code-vs-design drift.

**The `harness/` control plane** delivers: CLI (5 commands, no `validate`), `metadata.py` (`RunManifest` + `append_event`, plus 002 transform extensions — **no Result/Feedback/Scenario/ComparisonSet classes**), adapters (`chartsearchai`/`querystore` — Maven command plans, a 004 abstraction, NOT a REST driver), `targets.py` registry, and the load/transform/profile/conceptmap/ocl modules. The compose stack + OTEL collector are ready.

**Where each numbered feature stands:**
- **001** Harness Control Plane Foundation — *Draft / in progress* (accurate).
- **002** OpenMRS Demo-Data Remap — *Completed* (2026-05-29, accurate; transform shipped, corpus promoted to `openmrs`).
- **004** Real Adapter Entrypoints (chartsearchai PoC) — *in progress* (accurate; multi-turn chat + querystore Elasticsearch tier landed; Zabella smoke green). **This branch also carries all "feature 005" work.**
- **005** med-agent-hub Bridge + Picker — **no `spec.md` exists**, but the functionality is **fully shipped in code** (med-agent-hub submodule + chartsearchai picker + compose service), landed on **branch 004**.
- **006** Validation Harness MVP — *planned*; spec written; **zero implementation**. Greenfield.
- **007** File-based LLM Config Overrides — *planned*; spec written; task CFG.1 pending.

---

## 2. Drift inventory

See the structured `drift[]` for the machine-readable list. Highlights, by severity:

**HIGH**
1. **Spec 006 uses a non-existent REST surface (`POST /backend`).** SC-006.2 and FR-006.1 say the runner switches backend via `POST /backend {endpointId, model}`. The real chartsearchai controller exposes **`POST /endpoint {endpointUrl, modelName}`** (`ChartSearchAiRestController.java:484`) and `POST /model {modelName}` (line 407); there is **no `/backend` route**. The ESM picker itself uses `setEndpointModel → POST /chartsearchai/endpoint`. This would mislead the MVP build at its core integration point. *Evidence: controller `@RequestMapping` list lines 318–1133; `chartsearchai.ts:582`.*
2. **006 → 005 dangling dependency.** Spec 006 line 6 + line 61 + SC-006.7 depend on "feature 005" / "feature 005's endpoint registry," but **no `specs/005-*/spec.md` exists** on any branch reachable from main or 004. The functionality shipped on branch 004.
3. **004-vs-005 feature-number scope drift.** All "feature 005" deliverables (bridge, KB, warmup, picker, cloud refactor) landed on **branch `004-chartsearchai-adapter`** (first bridge commit `2e493b1`, KB `cfaf2be`). The `005-med-agent-hub-bridge` branch exists but is **58 commits behind 004** and holds only a `specs/005` scaffold that never received the implementation. A reviewer sees feature-005 code under a 004 PR with no 005 spec.

**MEDIUM**
4. **roadmap.canvas.tsx F005 node is pre-reconciliation.** Lines 303–322 describe an "LLM-classifier router engaged on every request," "honcho + stdout logs," and an A2A-style message flow. As-built is an **in-process ReAct loop over typed tools, single uvicorn process (no honcho)**, per the poc-roadmap §0 table. The node also lacks any "shipped/as-built" status marker while P1/B4/WARM are done. *Evidence: canvas 303–322 vs `med-agent-hub/Dockerfile` single CMD + poc-roadmap §0.*
5. **README.md milestone table.** Line 57 marks F005 *In progress* — should reflect **P1 + B4 + WARM shipped, P3 Tier-1 shipped** (per poc-roadmap §0). Line 54 marks 002 *In progress* — 002 spec is **Completed** (2026-05-29).
6. **SC-006.3 requires metrics the `/chat` boundary does not surface.** `tokens_in/out`, `finish_reasons`, `gen_ai.response.model` are raw-model/OpenAI-layer fields; chartsearchai consumes them server-side and its `/chat` response is only `{answer, disclaimer, references[], blocks[], session, messageId}` (`ChartSearchAiRestController.java:994–1078`, verified — no `usage`/`token`/`finish`/`gen_ai` put-to-response anywhere). `json_valid` measured at the runner is near-tautological (chartsearchai already parses/validates the model JSON; it'd be false only on HTTP error). This is a spec/reality gap that reshapes the MVP metric set (see §3).

**LOW**
7. **CLEAN.2 / CLEAN.3 / CLEAN.4 tasks (#119/#120/#121) are MOOT.** They target upstream fork PRs (#21, #22, #25 on chartsearchai; #10, #11 on esm) that **do not exist**. The chartsearchai fork has only fork-sync pull PRs (#1–14); the esm fork has one MERGED PR #1 that already bundles the picker work; the activator/model-switch work is already baked into the harness-integration branches.
8. **poc-roadmap §2–§5** still carry the A2A topology text — but the doc is **self-aware** (explicit `SUPERSEDED (2026-05-30)` marker at the top of §2, §0 table is the source of truth). Low-priority history cleanup (the MAH.D1 docs pass).
9. **chartsearchai-and-querystore.canvas.tsx** references "feature 009" where it means "feature 015" (querystore parity). Typo-level.

---

## 3. GOAL A — 006 MVP lift (demoable simple-evaluation workflow)

The MVP loop: **resolve `backend_id` → `{endpointUrl, modelName}` → `POST /endpoint` → replay turns via `POST /chat` in one session per backend → write `results.jsonl` over the existing `RunManifest`/`append_event` spine → minimal standalone TSX report with a per-cell Scout-rubric feedback form → `feedback.jsonl`.**

### What EXISTS today (evidenced)
- **Metadata spine** — `harness/metadata.py`: `RunManifest` (run_id, component, git_sha, dataset_id/version, gen_ai_provider, evidence_status, provenance) + `append_event(path, dict)` JSONL appender. Production-ready; 006 results reference `run_id` without modifying it.
- **chartsearchai REST surface** — fully implemented and tested: `POST /endpoint {endpointUrl, modelName}` (atomic dual-GP switch, validates model ∈ `/v1/models`), `GET /endpoints` (registry + per-endpoint live model list + reachable/current), `POST /chat {patient, session?, question}` → `{answer, disclaimer, references[], blocks[], session, messageId}` (multi-turn in one session). This IS the integration surface the runner drives.
- **The 3 backends to compare** — Gemma + MedGemma (single-model LM Studio endpoints) + `med-agent-team` (med-agent-hub) all reachable through the same `/v1/chat/completions` contract; selectable via the endpoint registry GP.
- **Compose stack** — `openmrs-2.8-refapp.yml` + `services.yml`: chartsearchai reachable via Caddy proxy; OpenMRS + MariaDB + Elasticsearch + OTEL up. Zabella Halambe demo patient (`dd75c020-…`) is loaded and was used as the multi-turn smoke.
- **Demo scenario content** — the 3-turn medication thread already verified as the multi-turn smoke is the spec's first scenario.

### What's MISSING (greenfield, with rough estimates)
- `harness validate run <comparison-set>` CLI subcommand + Makefile target — **~2h**
- **backend_id → {endpointUrl, modelName} resolver** against the endpoint-registry GP (the spec's `backend_ids` are abstract; the API needs concrete url+model) — **~2h**
- chartsearchai HTTP client (`POST /endpoint` switch, then per-turn `POST /chat` in one session) — **~half-day**
- Scenario + ComparisonSet schema + loader/validator; author `meds-zabella` + 2–3 abstention probes + `demo` comparison set JSON — **~half-day**
- Deterministic no-LLM metrics computed **client-side from the `/chat` envelope**: `latency_ms` (timed), `citation_count` = `len(references)`, `abstained` (derive from answer/blocks), `answer_present`, `json_valid` (HTTP/parse success only) — **~2h**
- `results.jsonl` writer as a projection over the run's events (references `run_id`, does not re-declare provenance) — **~2h**
- `save(collection, doc)` / `find(collection, query)` repository interface + JSONL impl (collections: scenarios, comparison_sets, results, feedback); Mongo = documented stub — **~half-day**
- Standalone TSX report: scenarios-down-left, one column per backend, answer + citations (`[index] resourceType — date`) + blocks + metric chips — **~1 day** (long pole)
- Per-cell Scout-rubric feedback form (0–10 accuracy/completeness/relevance + abstention outcome + per-citation groundedness + harm hard-fail + pass/fail + reviewer id + free text) → appends `feedback.jsonl` — **~half-day**

### MISSING but recommend CUTTING for the couple-days demo
- `tokens_in/out`, `finish_reasons`, `gen_ai.response.model` — **not available at the `/chat` boundary**; emit `null` in v1, or correlate from OTel GenAI spans (real work; defer).
- Multi-reviewer % agreement / Cohen's κ (FR-006.8) — defer.
- Mongo impl (already deferred by spec) — keep as stub.
- Report remote deploy (build-deployable, run local-only — already deferred).

### Ordered build plan to a demoable workflow
1. Add `harness validate run <comparison-set>` subcommand to `cli.py` + a `validate-run` Makefile target.
2. Define `Scenario` + `ComparisonSet` schemas; author `scenarios/meds-zabella.json`, 2–3 abstention probes, and `comparison_sets/demo.json`.
3. Build the **backend resolver** (`backend_id` → `{endpointUrl, modelName}` from `GET /endpoints` / registry GP).
4. Build the chartsearchai HTTP client: `POST /endpoint` to switch, then per-turn `POST /chat` in one session; capture `latency_ms` around each call.
5. Compute client-side deterministic metrics from the `/chat` envelope (`citation_count`, `abstained`, `answer_present`, `json_valid`); null the unavailable OTel/token fields.
6. Write `results.jsonl` via a `save("results", …)` repository call referencing the run's `run_id`; write `run_manifest.json` via the existing spine.
7. Wire the repository interface (JSONL impl for all 4 collections; Mongo stub raising "not implemented").
8. Build the minimal standalone TSX report reading `results.jsonl` (grid + metric chips + citation strings).
9. Add the per-cell feedback form → append `feedback.jsonl` via `save("feedback", …)`.
10. Run `harness validate run demo` with the full local stack up; hand-check one cell; demo the grid + a submitted feedback doc.

### Couple-days feasible?
**With-cuts: YES.** The core loop (steps 1–7) is genuinely a day-ish over the existing spine + REST surface; the long pole is the TSX report + feedback form (steps 8–9). Cut Mongo wiring, multi-reviewer agreement, OTel-sourced token/finish metrics, and report polish; a minimal grid + form is demoable.

### Risks
- **`POST /endpoint` switch is a global mutation** (sets active backend for everyone) — fine for single-operator demo; serialize backend runs (the spec already accepts the global switch).
- **Backend warmup / cold-start latency** skews `latency_ms` on the first turn per backend (warmup TTL exists but JIT loads can reclaim RAM); warm before timing or flag first-turn latency.
- **OTel correlation for token/finish metrics is real work** — do not present it as "free"; defer to v2.
- **med-agent-team tool-loop latency** (3 iterations + medgemma + synthesis) is much higher than single-model backends; expected, but document it so the comparison isn't read as a defect.
- **Spec drift (`/backend`) must be fixed first** or the integration will be coded against a non-existent route.

---

## 4. GOAL B — review readiness (PR + GitHub history)

### Current state a reviewer hits today
- **harness repo:** PR #15 (OPEN) on `004-chartsearchai-adapter` is titled for chartsearchai + querystore, but it **also carries all of "feature 005"** (bridge, KB, warmup, picker integration) — 58 commits ahead of main. There is **no `specs/005` directory** on 004, so feature-005 code arrives under a 004 PR with a dangling spec reference (006 depends on "feature 005"). The `005-med-agent-hub-bridge` branch is **stale** (58 commits behind 004; only a spec scaffold).
- **Submodule pins:** all 6 pins **match HEAD exactly, zero drift**; working tree is clean. chartsearchai / chartsearchai-esm / med-agent-hub pin their `harness-integration` branches per `.gitmodules`.
- **med-agent-hub fork:** `harness-integration` branch is pinned but has **no review PR**. PR #2 ("semantic search RAG") is OPEN but stale (last activity 2025-08-14) and unrelated to the bridge work.
- **chartsearchai fork:** only fork-sync pull PRs (#1–14); **no feature/review PR** for the activator + model-switch + endpoint-registry work that's on `harness-integration`.
- **esm fork:** PR #1 is **MERGED** (Carbon picker + maximize + controls) — clean.
- **Cleanup tasks:** CLEAN.2/CLEAN.3/CLEAN.4 (#119/#120/#121) reference **non-existent PRs** → moot. CLEAN.5 (#122) — bump harness pins on main via PR #15 merge — is the real remaining action.

### Ordered cleanup plan (for a human to execute carefully — no history surgery here)
1. **Resolve 004-vs-005 naming** (decision): either (a) retitle/keep PR #15 as the combined "004 chartsearchai adapter + med-agent-hub bridge (feature 005 functionality)" and **retro-create `specs/005-med-agent-hub-bridge/spec.md`** from the poc-roadmap + delta note, OR (b) explicitly fold feature-005 scope into feature 004 and drop the 005 references. Then **delete or abandon the stale `005-med-agent-hub-bridge` branch** (its code is redundant).
2. **med-agent-hub fork:** open one tight review PR from `harness-integration` → fork main (or upstream) covering the in-process ReAct bridge + team + Tier-1 KB; close/relabel the stale PR #2.
3. **chartsearchai fork:** open one tight review PR from `harness-integration` covering activator privilege provisioning + ModelSwitchService endpoint registry + REST endpoints + RemoteLlmEngine wire contract.
4. **esm fork:** already clean (PR #1 merged) — no action beyond confirming the harness pin matches the merged tip.
5. **Close out the moot tasks** CLEAN.2/3/4 (#119/#120/#121) with a note that the referenced PRs never existed and the work is already on `harness-integration`.
6. **harness PR #15:** write a tight body (what + why + bullets + 1 line on tests), ensure it bumps all submodule pins on main, retarget/merge → closes CLEAN.5 (#122).
7. Sync the drifted docs (see §5) so the PR diff includes correct status surfaces.

### Blocking for review
- The **004-vs-005 naming/spec decision** must be made (a reviewer cannot reconcile feature-005 code with a missing 005 spec and a 006 dependency on it).
- The **fork review PRs** (med-agent-hub, chartsearchai) must exist so a reviewer can read the submodule changes as PRs, not just pins.
- The **`/backend` → `/endpoint` spec-006 fix** should land so the spec a reviewer reads matches the REST reality it depends on.
- **Doc status drift** (roadmap canvas F005, README) should be synced so dashboards don't contradict the shipped state.

---

## 5. Remediation (≤1 entry per file — sync status to reality only)

- **`specs/006-validation-harness-mvp/spec.md`** — replace the non-existent `POST /backend {endpointId, model}` with the real `POST /endpoint {endpointUrl, modelName}` (SC-006.2, FR-006.1, and the `backend_ids` resolution comment); note that one `POST /endpoint` sets both endpoint + model atomically (no separate `/model` call needed). Note that `tokens_in/out`, `finish_reasons`, `gen_ai.response.model` are **not surfaced by `/chat`** (null in v1 or OTel-deferred). Optionally soften the "feature 005" dependency to "med-agent-hub bridge (shipped on branch 004)." Do NOT decide the 004-vs-005 naming here.
- **`specs/roadmap.canvas.tsx`** — update the F005 node (303–322): mark P1 + B4 + WARM + Tier-1 KB as shipped; correct "honcho + stdout logs" → single uvicorn image; reword "LLM-classifier router engaged on every request" / A2A message-flow language to the as-built **in-process ReAct loop over typed tools (medical_expert + kb_search)**. Do NOT rewrite dependencies or invent scope.
- **`README.md`** — milestone table: bump F005 (line 57) from *In progress* to reflect **P1+B4+WARM shipped / P3 Tier-1 shipped**; correct 002 (line 54) from *In progress* to *Completed* (matches its `spec.md`).
- **`specs/artifacts/planning/med-agent-team-poc-roadmap.md`** — already self-aware (SUPERSEDED markers + §0 table). Minimal: confirm §0 P4/C3 still pending and drop/annotate the `specs/005-med-agent-hub-bridge/` "does not exist" note once the 004-vs-005 decision lands. No design rewrite.

---

*Written from recon evidence + live-tree spot checks on `004-chartsearchai-adapter` @ `ffe35fb`. All file:line citations were verified against the working tree.*
