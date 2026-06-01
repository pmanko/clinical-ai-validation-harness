# SYNC Assessment + Remediation Plan — KB / roadmap-specs / recent-dev

**Date**: 2026-05-31
**Branch**: `004-chartsearchai-adapter`
**Inputs**: three SYNC recons (Clinical KB specs-vs-code; roadmap/specs-vs-as-built; recent-development burst)
**Method**: each recon claim re-verified against current file state at HEAD (recons predate the doc-sync commit `5d8d1d6` and the per-request-override commits `6e5390e`/`a9878dd`; all line numbers below are re-checked, not inherited).

---

## 1. State of sync

The repo is in good shape after the fast recent burst. The biggest items the recons flagged are **already fixed** — and one fix opened a **new, smaller drift** that the recons could not have seen because they predate it.

**Already synced (verified at HEAD; do not re-remediate):**
- **spec-006 `/endpoint` route.** The recon's top high-severity item ("spec-006 names non-existent `POST /backend {endpointId, model}`") is STALE. Commit `5d8d1d6` ("docs: sync roadmap/README/spec-006 to as-built") fixed it. spec-006 SC-006.2 (line 17) and FR-006.1 (line 26) now correctly say `POST /endpoint {endpointUrl, modelName}`, matching `ChartSearchAiRestController.java:485`.
- **roadmap.canvas.tsx F005 node.** The recon's "pre-reconciliation honcho + A2A + LLM-classifier router" claim is STALE. Canvas lines 303-322 now describe an in-process ReAct loop over typed tools (`medical_expert + kb_search`, `MAX_TOOL_ITERATIONS=3`), single uvicorn, "no honcho/Procfile". `grep honcho|classifier|A2A` over the canvas returns only the negative "no honcho/Procfile" assertion at line 314.
- **README milestone table.** 002 = "Complete" (line 54), F005 = "Shipped (model-switch + Carbon picker + model warmup + Tier-1 KB)" (line 57), 004 = "In progress" (line 56). The recon's "002 In progress / F005 In progress" claims are STALE.

**Live drift (real, grounded, must fix):**
1. **spec-006 FR-006.1 + SC-006.2 now describe the OLD global-switch mechanism, not the as-built per-request override.** This is the one item the doc-sync commit could not catch — `5d8d1d6` predates the per-request-override commits `6e5390e` ("harness drives backends per-request — no global mutation") and chartsearchai `a9878dd`. As-built sends `{endpointUrl, modelName}` in the `POST /chat` body (per-request); the spec still says "select the backend (`POST /endpoint`), then chat — No special per-request override." High severity (it is the core integration mechanism).
2. **`med-agent-team-poc-roadmap.md:14` says "6-snippet" — the corpus is 18.** The only surviving false count about as-built anywhere in the docs.
3. **`specs/005-med-agent-hub-bridge/spec.md` does not exist on this branch**, yet spec-006 (line 6, line 8, SC-006.7) depends on "feature 005." All feature-005 code shipped on branch `004`. Governance decision required, not a mechanical edit.
4. **spec-006 header says "Status: planned"** while its core (runner, client, report, scenarios, backends.json) is shipped and live-run (`c04c2fd` … `f89645d`).
5. **`clinical-kb-brief.md` has no Tier-1-precursor pointer.** The brief is the future F009 spec input; a one-line note that a Tier-1 demo precursor already ships in med-agent-hub (and which FR/SCs it intentionally does NOT meet yet) would stop a reader mistaking POC-vs-future-spec gaps for drift. Low severity.

**Important framing — KB "drift" is mostly NOT drift.** The first recon lists ~9 high-severity KB items (no RRF, no cross-encoder reranker, no `/v1/kb` REST, no MCP tools, no `citation_anchor`, no contextualization worker). These compare as-built against `clinical-kb-brief.md`, which is explicitly **"Source brief — feeds `/speckit-specify` for feature 009"** (brief line 3) — a *future* spec, not a contract the current code claims to satisfy. The roadmap (`med-agent-team-poc-roadmap.md` §3, lines 57-61) and `kb_data/README.md` (lines 40-43) already document the shipped KB as a "Tier-1 demo-grade precursor to F009" with rerank / hybrid / contextualization / REST / MCP explicitly deferred. **Future-spec-vs-current-POC is not drift.** Real drift is a doc asserting something false about as-built — and of the KB items, only the "6-snippet" count qualifies. The KB-vs-F009 items are down-ranked to informational below.

**Recent burst — code is GREEN, mostly undocumented but correctly so.** Per-request override, degraded-envelope detection, Scout-rubric feedback form, d4T regimen-currency scenario, KB→18 snippets, model consolidation to `google/gemma-4-e4b`, rate-limit-aware client: all shipped and tested. None require doc changes *except* where they invalidate an existing doc claim (item 1 above) or a stale count (item 2). Feature 007 (file-based LLM config overrides) is specified + planned but unimplemented and **correctly** marked "planned" — no drift.

---

## 2. Drift register (live items, grounded)

| # | Surface | Claim (doc) | Reality (as-built) | Evidence | Severity |
|---|---------|-------------|--------------------|----------|----------|
| D1 | spec-006 FR-006.1 (line 26) + SC-006.2 (line 17) | "select the backend (`POST /endpoint`), then chat (`POST /chat`)… No special per-request override" | Backend is selected per `/chat` request: `{endpointUrl, modelName}` are sent in the `POST /chat` body, no separate `POST /endpoint` switch | `harness/validate/runner.py:102` ("backend is selected per /chat request (a per-request override)"), `runner.py:111-123`; `harness/validate/client.py:125-126` (puts `endpointUrl`/`modelName` in `/chat` body); commit `6e5390e` "no global mutation"; chartsearchai `a9878dd` + `RequestLlmOverride.java:31` (ThreadLocal), set at `ChartSearchAiRestController.java:1050` inside `/chat` try, cleared in finally; task #144 DONE | high |
| D2 | `med-agent-team-poc-roadmap.md:14` (§0 status table) | "`kb_search` typed tool over a **6-snippet** openly-licensed WHO seed" | Corpus has 18 snippets across 5 domain groups | `wc -l corpus.jsonl` = 18; ids: imci-danger-signs, pneumonia-fast-breathing, ors-zinc-diarrhoea, metformin-first-line-t2dm, amoxicillin-child-pneumonia, htn-diagnosis-threshold, hiv-* (8), ciel-dictionary, ocl-context, openmrs-data-model, openmrs-concept-dictionary; commit `49c707a` "KB expanded … (18 snippets)" | high |
| D3 | spec-006 line 6 / line 8 / SC-006.7 | "Depends on feature 005 (med-agent-hub bridge + endpoint-registry picker)" | No `specs/005-med-agent-hub-bridge/spec.md` exists on branch 004; all feature-005 code shipped under 004 (`2e493b1` … `cfaf2be`); stale `005-med-agent-hub-bridge` branch is 58 commits behind, scaffold only | `ls specs/005-med-agent-hub-bridge/` → absent; landscape-and-sync-2026-05-30.md §2 + "Open governance"; task #133 "specs/005 dir" pending | high |
| D4 | spec-006 header (line 5) | "**Status**: planned" | Core shipped + live-run: runner/client/models/repository/report wired in `cli.py`; scenarios + comparison_sets populated; first live run done | commits `c04c2fd` (core), `0065bf4` (first live run), `7c3add3`, `79eae92`, `f89645d`; spec-006 body itemizes shipped SCs | medium |
| D5 | client.py:2-3 docstring | "select the backend with POST /endpoint, then replay turns with POST /chat … (spec 006 FR-006.1)" | Override is sent in the `/chat` body per request; no `POST /endpoint` switch in the chat loop | `client.py:103-131` (chat body carries `endpointUrl`/`modelName`); same drift as D1 but in code-doc | medium |
| D6 | `clinical-kb-brief.md` (F009 source brief) | (no pointer) — reader cannot tell a Tier-1 precursor already ships | A Tier-1 KB ships in med-agent-hub (FTS5 BM25, 18 snippets, abstains, inline-attributed) deliberately not meeting F009 FRs (RRF, rerank, REST, MCP, citation_anchor, contextualization) | `targets/med-agent-hub/server/kb.py`; `kb_data/README.md:40-43`; roadmap §3 lines 57-61 | low |

**Informational (NOT drift — future-spec-vs-POC, already documented as deferred):**
- F009 FR-009.3 hybrid BM25+dense+RRF vs as-built FTS5 BM25 + keyword fallback (`kb.py:71-101`). Deferred per roadmap §3 line 57, `kb_data/README.md:40`.
- F009 FR-009.4 cross-encoder reranker — absent. Deferred (same sources).
- F009 FR-009.1/.2 `/v1/kb/lookup` REST + MCP tools — KB is an in-process typed `kb_search` tool, not a service. Deferred; roadmap §3 line 66.
- F009 FR-009.5 `citation_anchor` triple — corpus carries `source+version+url`, no anchor. Acknowledged `kb_data/README.md:26`.
- F009 SC-009.3 response schema (`content`/`source_url`/`source_version`/`type`) vs as-built (`text`/`url`/`version`, no `type`) — `kb.py:100`. POC typed-tool shape, not the F009 REST contract.
- OpenMRS contextualization (curation worker, YAML artifact, PHI check) — none. Deferred per roadmap §3 line 61.
- K default = 3 (`kb.py:26`) **matches** F009 FR-009.4. No action.

---

## 3. Remediation plan (ordered)

### R1 — spec-006 FR-006.1 + SC-006.2: reconcile to per-request override (fixes D1)
**File**: `specs/006-validation-harness-mvp/spec.md`
- **FR-006.1 (line 26)**: replace "select the backend (`POST /endpoint {endpointUrl, modelName}`, one atomic call …), then chat (`POST /chat`) … No special per-request override; no bypassing chartsearchai to call endpoints directly." with the as-built mechanism: the runner sends `endpointUrl` + `modelName` **in the `POST /chat` body** as a per-request backend override (chartsearchai uses that backend for that request only, via `RequestLlmOverride` thread-local), replaying the scenario's turns in one session. Keep "no bypassing chartsearchai."
- **SC-006.2 (line 17)**: replace "selecting endpoint+model via the same `POST /endpoint {endpointUrl, modelName}` the picker uses (one atomic call; no separate `/model` call needed), then `POST /chat`" with "passing `{endpointUrl, modelName}` in each `POST /chat` request (per-request override), replaying turns in one session."
- **JSON example (line 61)**: the comment "each backend_id resolves to a concrete {endpointUrl, modelName} … for the POST /endpoint call" → "… included in each POST /chat request body."

### R2 — poc-roadmap status table: 6 → 18 snippets (fixes D2)
**File**: `specs/artifacts/planning/med-agent-team-poc-roadmap.md`
- **Line 14**: "a 6-snippet openly-licensed WHO seed" → "an 18-snippet openly-licensed seed (WHO general-clinical + HIV/ART, plus OCL/CIEL and OpenMRS data-model meta)". (Body §3 line 59 "a few dozen … snippets" is approximate and fine; only the status-table count is false.)

### R3 — spec-006 status + 005 dependency (fixes D4; surfaces D3)
**File**: `specs/006-validation-harness-mvp/spec.md`
- **Line 5**: "Status: planned" → "Status: in progress (core runner/client/report shipped; live-run validated)".
- **Lines 6, 8, SC-006.7**: the "feature 005" reference resolves only after the D3 decision below. Pending that, change "feature 005" to a concrete pointer ("the med-agent-hub bridge + endpoint-registry picker shipped on branch 004; see `specs/artifacts/planning/med-agent-team-poc-roadmap.md`") so the dependency is not dangling regardless of the naming outcome.

### R3-DECISION — DECISION REQUIRED: 004-vs-005 spec number (resolves D3)
**Not a mechanical edit — needs the maintainer's call (StructuredOutput cannot ask).** Two options from `landscape-and-sync-2026-05-30.md` §"Open governance":
- **(a)** Retro-create `specs/005-med-agent-hub-bridge/spec.md` from the poc-roadmap + `med-agent-hub-bridge-delta.md`, keep spec-006's "feature 005" reference, retitle PR #15 to cover both, and delete the stale `005-med-agent-hub-bridge` branch (its code is redundant).
- **(b)** Fold feature-005 scope into feature 004, drop the "feature 005" references in spec-006 (replace with "feature 004"), and delete the stale 005 branch.
Either way: **delete/abandon the stale `005-med-agent-hub-bridge` branch** (58 commits behind, scaffold only). Tracked by task #133.

### R4 — client.py docstring (fixes D5)
**File**: `harness/validate/client.py`
- **Lines 2-3**: update the module docstring from "select the backend with POST /endpoint, then replay turns with POST /chat" to the per-request-override description matching `chat()` at line 103-131 (override carried in the `/chat` body). Keeps code-doc honest with the FR-006.1 rewrite in R1.

### R5 — clinical-kb-brief: add Tier-1-precursor pointer (fixes D6)
**File**: `specs/artifacts/planning/clinical-kb-brief.md`
- Add a short note under §2 ("Relationship to other specs") or §1: "A **Tier-1 demo-grade precursor** already ships in `targets/med-agent-hub/server/kb.py` (FTS5 BM25 + keyword fallback over an 18-snippet openly-licensed seed, K=3, abstains, inline-attributed). It deliberately does NOT yet implement F009 FR-009.1/.2 (REST + MCP), FR-009.3/.4 (hybrid+RRF+reranker), FR-009.5 (`citation_anchor`), or the contextualization worker — those are this brief's scope. See `med-agent-team-poc-roadmap.md` §3 and `kb_data/README.md`."

### R6 — (no edit) confirm clean items
- `roadmap.canvas.tsx` F005 node — already synced (in-process ReAct, no honcho). No edit.
- README milestone table — already synced (002 Complete, F005 Shipped, 004 In progress). No edit.
- `kb_data/README.md` — already honest (license `confirm terms`, no page-anchor, F009 deferral, inline attribution). No edit.
- Feature 007 status "planned" — correct. No edit.

---

## 4. Confidence / grounding

Every D-item and R-item is tied to a file:line or commit verified at HEAD this session. The recons' three top items (spec-006 `/backend`, canvas honcho/A2A, README 002/F005 status) were re-checked and found ALREADY FIXED by `5d8d1d6`; they are excluded from remediation to avoid re-editing synced docs. The one item the doc-sync could not catch — FR-006.1's per-request override (D1) — was found by following the commit timeline (`5d8d1d6` predates `6e5390e`/`a9878dd`) and confirmed in `runner.py`/`client.py`.
