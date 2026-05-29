# Clinical Knowledge Base Service — Source Brief

**Status**: Source brief — feeds `/speckit-specify` for feature 009.
**Roadmap entry**: F009 — `009-clinical-knowledge-base` (lane: foundation).
**Recommended spec number**: 009 (sibling of F008 gateway; reconciles with the roadmap canvas and README milestone table).
**Last updated**: 2026-05-26.
**Paired research**: [`clinical-kb-research.md`](./clinical-kb-research.md).

This document is the authoritative architectural brief for the clinical knowledge base service. It is the **input** to Spec Kit commands (`/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`). Spec Kit–generated artifacts will live under `specs/009-clinical-knowledge-base/` after Phase 2. Do not edit the generated artifacts; update this brief instead.

---

## 1. Goal

Stand up `clinical-kb`, a dedicated host-agnostic clinical knowledge service that consumers (chartsearchai, the model gateway, openmrs_chatbot, Catalyst sidecar, med-agent-hub subagents) can call to retrieve grounded, citable, short clinical snippets optimized for low-power local models (4-8B parameter range).

The service has two layers:
- **General KB**: a curated corpus of openly licensed clinical reference content (WHO IMCI/EML/ANC, MSF Clinical Guidelines, RxNorm essentials, immunization schedules, pediatric dosing). Hybrid sparse+dense retrieval with RRF; small-cross-encoder reranking; section-aware chunking; explicit abstention.
- **Contextualized KB**: a deployment-tailored subset of the general KB produced by an offline curation worker that analyzes the deployment's OpenMRS DB (concept frequency, diagnosis distribution, drug formulary, encounter mix) and proposes the relevant subset for human review. PHI never leaves the deployment.

The service is *orthogonal* to chartsearchai's per-patient chart retrieval; the two stack at the LLM call site (KB context above patient records, both below the system prompt).

**Operating cost, stated plainly**: this is a new service to build, deploy, version, monitor, and document. The host evaluation matrix (see [`clinical-kb-research.md`](./clinical-kb-research.md) §B) chose the dedicated-service shape (26/30) over the gateway-embedded alternative (22/30) on the assumption that ≥3 downstream consumers (chartsearchai, gateway, openmrs_chatbot or Catalyst) actually integrate. If only one consumer materializes within the next year, the gateway-embedded alternative is cheaper — revisit at the v1 retrospective.

---

## 2. Relationship to other specs

| Spec | Relationship |
|------|--------------|
| **004-real-adapter-entrypoints** | KB is a new target with its own adapter. No code change to 004; KB is an additive target. |
| **005-med-agent-hub-bridge** | Future consumer. Subagents can call KB as an MCP tool when ready; not required in 005 scope. |
| **006-deferred / 007-deferred** | KB MCP tooling becomes a natural building block for these "frontend agent affordance" and "MCP tooling expansion" deferred features. |
| **011-catalyst-fhir-sidecar-poc** | Catalyst MCP can register `kb_lookup` as an additional MCP tool alongside the FHIR tools in §8 of the catalyst-fhir-sidecar-brief. |
| **Parallel gateway spec (sister item)** | The gateway is a natural first consumer because Python-to-Python is fastest to demo. KB is sequenceable independently — the gateway becomes one consumer of many when it lands. |
| **002-openmrs-demo-data-2-8-remap** | The curation worker reads the demo dataset (large-demo-data-2-7-0.sql remapped to 2.8) for its first end-to-end smoke. |

**Sequencing**: KB is **architecturally** independent of F008 — `LlmProvider.search` is a direct injection point, no gateway required. But the cost of the first integration differs significantly by consumer:

- **Gateway-first (cheapest)** — if F008 ships before F009 implementation, the gateway can inject KB context into the messages array before forwarding to the model. Pure Python-to-Python, no chartsearchai code change, no `.omod` rebuild. Iteration cycles measured in minutes.
- **chartsearchai-direct** — works without F008, but requires a Java change to `LlmProvider.search` (one new optional `kbContext` parameter) plus the chartsearchai maintainer's sign-off, plus an `.omod` rebuild for each iteration. Slower feedback loop.
- **openmrs_chatbot** — fastest *technical* path (Python), but lowest leverage (smaller deployment surface than chartsearchai).

The recommendation: **let F008 sequencing drive first-consumer choice**. If F008 finishes before F009 implementation, gateway-first. If F009 finishes first, accept the chartsearchai Java integration cost and use that path. Either is workable; the choice is calendar, not architecture.

---

## 3. Success criteria

- **SC-009.1** `make clinical-kb-build` produces `clinical-kb:dev` Docker image from `targets/clinical-kb/` submodule (or in-repo source, decision per `/speckit-clarify`).
- **SC-009.2** `make clinical-kb-up` starts the service; `/health` reports green; `/manifest` reports loaded corpus version, embedding model identity, dense+sparse index sizes.
- **SC-009.3** `POST /v1/kb/lookup` with `{query, k, intent_hint?, deployment_id?}` returns ≤5 ranked snippets, each with `{id, title, content, source_url, source_version, citation_anchor, score, type}` in <500 ms on a 16 GB MacBook (excluding cold start). Cited sources resolve to a real local document fragment, not a hallucination.
- **SC-009.4** `POST /v1/kb/lookup` returns `{snippets: [], abstain: true, reason: "no_relevant_kb_match"}` when no snippet exceeds the relevance floor, demonstrating MedAbstain-aligned discipline. An eval suite asserts this on a held-out negative set.
- **SC-009.5** `make clinical-kb-curate DEPLOYMENT=<demo>` runs the curation worker against the harness's OpenMRS 2.8 demo DB, emits a `curation_<deployment>_<timestamp>.yaml` artifact with included/excluded/flagged entries plus deployment-profile hash. No PHI appears in the artifact (asserted by an automated check). **Note**: the auto-curation pattern is application-novel (see [`clinical-kb-research.md`](./clinical-kb-research.md) §A.4 — "Honest assessment"). v1 ship-criterion is **a reviewable artifact**, not a reviewer-approved subset. First deployment's artifact may require 2–3 iteration cycles before clinical sign-off; subsequent deployments reuse reviewed decisions where the profile overlaps.
- **SC-009.6** After human review and `clinical-kb load-curation <artifact>`, calling `/v1/kb/lookup` with `deployment_id=<demo>` returns the contextualized subset. Same query against general layer returns a (potentially) different result set; both behaviors are eval-asserted. SC-009.6 measures that contextualization **works mechanically** — quality of the chosen subset is gated by SC-009.5's review process, not by this SC.
- **SC-009.7** Citation/grounding eval: on a held-out medical-QA subset (subset of MIRAGE-style cases, harness-curated), KB-augmented small-model answers achieve ≥10 pp accuracy lift over no-KB baseline at unchanged refusal-on-unanswerable rate.
- **SC-009.8** One real consumer integration demonstrably calls the KB end-to-end. Recommended primary demo: chartsearchai's `LlmProvider.search` prepends a KB context block to numbered records for a clinical-question patient case; the AI answer cites both KB sources (`[KB-1]`) and patient records (`[1]`) distinctly.

---

## 4. Functional requirements

- **FR-009.1** Service MUST expose HTTP REST at `POST /v1/kb/lookup` and `POST /v1/kb/lookup_contextualized` returning `{snippets, abstain, reason, model_provenance, retrieval_provenance}`. Schema is JSON-versioned in `contracts/kb_response.schema.json`.
- **FR-009.2** Service MUST expose an MCP server interface registering at least `kb_lookup`, `kb_lookup_contextualized`, `kb_list_sources`, `kb_get_source_metadata` tools. Both REST and MCP wrap the same retrieval core.
- **FR-009.3** Retrieval MUST be hybrid BM25 + dense, fused with RRF (k=60) per MedRAG/chartsearchai precedent. Dense encoder defaults to all-MiniLM-L6-v2; alternative encoders (MedCPT, bge-small) are pluggable.
- **FR-009.4** A small cross-encoder reranker (MS-MARCO MiniLM tier) MUST score the fused top-N and select the final top-K. Default K=3 for ≤8B-parameter consumers; configurable.
- **FR-009.5** Snippets MUST be section-aware atomic units (one drug monograph section, one guideline recommendation, one immunization schedule entry). Each snippet MUST carry a stable `source_url + source_version + citation_anchor` triple.
- **FR-009.6** When no snippet scores above the relevance floor (configurable; default cosine 0.5 + z-score gate analogous to chartsearchai's absent-data detection), the response MUST be `{snippets: [], abstain: true, reason: "no_relevant_kb_match"}`. The consumer prompt template MUST surface "no KB context available" plainly so the LLM can abstain rather than fabricate.
- **FR-009.7** The general KB corpus MUST be openly licensed (WHO, MSF, RxNorm, CDC public-domain sources, public guideline portals). Any non-open-licensed source MUST be excluded from the v1 ship; placeholder hooks MAY exist for deployments to substitute licensed content locally.
- **FR-009.8** A separable `clinical-kb-curate` worker MUST accept a deployment DB connection string (read-only) and emit a YAML curation artifact. The worker MUST NOT write to the OpenMRS DB. The artifact MUST contain only concept IDs, vocabulary codes, and aggregate counts — never patient IDs, observation IDs, free-text observations, or any PHI. An automated check MUST assert the no-PHI property.
- **FR-009.9** Curation activation MUST require a human review gate by default, recorded in the artifact (`review_status`, `human_reviewer`). Auto-merge is opt-in per deployment via explicit configuration. (Constitution principle II.)
- **FR-009.10** The curation worker MAY call a cloud LLM with the deployment profile (aggregate counts + general-KB titles). Such calls MUST be captured in the curation artifact with model/provider/prompt provenance per constitution principle IV.
- **FR-009.11** All `/v1/kb/lookup` responses MUST emit metadata to harness-conformant trace events (OTel GenAI-aligned where applicable) and persist to the harness's `events.jsonl` when invoked under a run.
- **FR-009.12** The KB content store MUST hot-reload on a watched directory change without service restart, to support the user's iteration-velocity requirement.
- **FR-009.13** The service MUST support a "type-aware" hint analogous to chartsearchai's type detection: queries mentioning drug names route extra-weight to drug-monograph sources; queries mentioning guideline/protocol terms route extra-weight to guideline sources. The hint MAY be passed by the consumer or detected internally.
- **FR-009.14** Service MUST provide an eval CLI (`clinical-kb eval <suite>`) that runs the held-out test sets and emits a CSV report (KB recall, citation correctness, abstention rate, contextualization regression). Pattern follows chartsearchai's eval framework.
- **FR-009.15** A consumer integration adapter MUST land for at least one consumer (recommended: chartsearchai's `LlmProvider.search` is updated to prepend KB context block via a single optional parameter; rollback path is "set KB endpoint URL global property to empty").

---

## 5. Open design questions for `/speckit-clarify`

(See research Section E for full rationale.)

1. **General-KB content scope at v1** — seed corpus vs. full WHO/MSF/RxNorm coverage?
2. **Curation auto-merge policy** — mandatory human review (default) vs. eval-gated auto-merge?
3. **PHI boundary for curation worker** — cloud LLM with aggregates allowed, or local-LLM only?
4. **First consumer integration** — chartsearchai (Java) or gateway (Python) first?
5. **Knowledge source licensing** — which open-licensed sources are in scope for v1?
6. **Per-deployment subset vs. per-deployment full KB** — filter only, or filter-plus-augment for custom protocols?
7. **In-repo source vs. submodule** — does `clinical-kb` follow the chartsearchai/med-agent-hub submodule pattern or live as in-repo Python alongside the harness control plane?

---

## 6. Out of scope (POC)

- **Licensed content (UpToDate, ClinicalKey, BNF)** — placeholder hooks only; substitution is a deployment operator responsibility.
- **Full GraphRAG / Neo4j integration** — start with hybrid sparse+dense; defer GraphRAG until evidence shows it's needed.
- **Multimodal retrieval (images, ECGs, etc.)** — text only for v1.
- **Patient-axis retrieval** — that is chartsearchai's job; KB is orthogonal.
- **Fine-tuned curation model** — v1 uses prompted off-the-shelf cloud LLMs; fine-tuning deferred.
- **Real-time KB updates from new published guidelines** — manual content refresh by maintainer; auto-fetch deferred.
- **Cross-deployment knowledge sharing** — every deployment has its own contextualized layer; sharing aggregate signals across deployments is deferred (privacy review required).
- **Frontend "Sources used" UI surface** — consumer-side concern; KB returns the citation data, consumers render it. UI work happens in the consumer specs.

---

## 7. Demo path that proves success

### 7.1 Local single-consumer demo

**Pick ONE based on F008 status** (see §2 sequencing). The demos are interchangeable — same KB, different injection points.

**Path A — Gateway-first** (preferred if F008 has shipped):
1. `make clinical-kb-build && make clinical-kb-up` — service healthy on `:8090`.
2. `curl POST /v1/kb/lookup` with query "metformin contraindications" returns 3 snippets, each with WHO/RxNorm source URL.
3. `curl POST /v1/kb/lookup` with query "asdf jkl bananarama" returns `abstain: true`.
4. Run `clinical-kb eval recall` — KB recall on held-out eval >0.80.
5. Register the gateway with a `kb-augmented` provider class that prepends `kb_lookup` results to the messages array before forwarding to the chosen model.
6. Open the demo patient in chartsearchai (gateway routes the call), ask "What is the standard dose of metformin and is the patient on it?" — answer cites both `[KB-1]` (RxNorm dosing) and `[3]` (patient's metformin order). No chartsearchai code change.

**Path B — chartsearchai-direct** (use if F008 hasn't shipped yet):
1. Steps 1–4 identical to Path A.
2. Patch chartsearchai's `LlmProvider.search` (one new optional parameter `kbContext`) with a feature-flagged call that fetches KB context for the user's question. **Requires chartsearchai-maintainer sign-off and `.omod` rebuild.**
3. Open the demo patient, ask the same question — same citation behavior, but the integration cost lives in chartsearchai.

### 7.2 Local curation demo
1. `make clinical-kb-curate DEPLOYMENT=demo-008` against the harness OpenMRS 2.8 demo DB.
2. Inspect `curation_demo-008_<ts>.yaml` — verify included/excluded/flagged entries match the demo dataset's concept profile (e.g. HIV demo data should include ART monographs and exclude warfarin).
3. Verify the no-PHI assertion passes.
4. Run `clinical-kb load-curation <artifact>` after marking it reviewed.
5. `POST /v1/kb/lookup_contextualized` with `deployment_id=demo-008` returns a measurably narrower set than the same query against the general layer.

### 7.3 Smoke against second consumer (gateway when available)
1. Once the parallel model-gateway spec lands, gateway prepends `kb_lookup` results to the messages array.
2. Same chartsearchai 3-turn referential smoke from spec 005, but with KB context — verify the answer cites both KB and patient sources.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| **Auto-curation produces unsafe subset (excludes critical KB)** | Mandatory human review by default; held-out eval blocks promotion; constitution III evidence requirements force record-level audit. |
| **KB content licensing dispute** | Limit v1 ship to verifiably open-licensed sources; document licenses per source; placeholder hooks for licensed substitutions. |
| **KB context degrades small-model performance ("lost in the middle")** | Default K=3; top-of-context placement; eval suite includes a long-context stress test; abstain when no snippet clears the floor (better to omit KB than dilute). |
| **Scope creep — KB grows into a full clinical decision-support engine** | Spec out: KB returns snippets, period. Decision-support is consumer-side (e.g. drug-interaction checks). |
| **Cloud-LLM use during curation leaks PHI** | Worker reads only aggregates; no patient-level data ever passed to cloud; automated PHI-detection check on the prompt body before send; comprehensive audit log. |
| **Embedding model choice locks in retrieval quality** | A/B framework supports swapping encoders; eval suite quantifies impact; "generalist beats biomedical" 2024 evidence cited to keep choice open. |
| **Reviewer fatigue on curation artifacts** | Artifacts are diff-able YAML; "flagged for review" subset is small; second deployment's artifact reuses first deployment's reviewed decisions where the profile overlaps. |
| **Auto-curation is application-novel — no published end-to-end pattern** | Build incrementally; ship general layer first, contextualization second; treat contextualization v1 as evidence-gathering, not as a guaranteed quality win. |
| **Service becomes a single point of failure for consumers** | Consumers fall back to "no KB context" path; chartsearchai already works without KB; no consumer's primary function depends on KB up-ness. |

---

## 9. References

**Research artifact**: [`clinical-kb-research.md`](./clinical-kb-research.md) — methodology survey, host evaluation matrix, recommendation rationale, sources.

**In-repo signals**:
- `targets/openmrs_chatbot/KNOWLEDGE_BASE_INTEGRATION_METHODS.md` — dominant existing thinking; 7-method approach (intent classification, SQL agent, drug KB, ChromaDB, response gating, validation agent, specialized handlers); reused as the openmrs_chatbot library/service reference pattern.
- `targets/chartsearchai/README.md` — hybrid retrieval (RRF), MedCPT support, embedding/lucene/hybrid/elasticsearch pipelines, type-aware expansion, absent-data detection (z-score gate), eval framework — all directly transferable.
- `targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/LlmProvider.java` — integration point at `search` (line 120); system-prompt design with JSON-schema enforcement and citation requirements.
- `specs/005-med-agent-hub-bridge/spec.md` — future consumer.
- `specs/artifacts/planning/catalyst-fhir-sidecar-brief.md` — sibling brief structure followed here; §8 MCP tool sketch is the pattern for KB MCP exposure.

**External sources** (top 12 from research Section A.5; full list in research doc):
- MedRAG/MIRAGE — https://arxiv.org/abs/2402.13178
- i-MedRAG — https://arxiv.org/abs/2408.00727
- Self-BioRAG — https://arxiv.org/abs/2401.15269
- MedGraphRAG — https://arxiv.org/abs/2408.04187
- CUICurate — https://arxiv.org/pdf/2602.17949
- MedAbstain — https://arxiv.org/abs/2601.12471
- Lost in the Middle — https://aclanthology.org/2024.tacl-1.9/
- MedCPT — https://huggingface.co/ncbi/MedCPT-Query-Encoder
- HalluGuard — https://arxiv.org/abs/2510.00880
- Generalist beats biomedical embeddings — https://arxiv.org/abs/2401.01943
- NICE-guideline iatroX — https://arxiv.org/abs/2510.02967
- Toward Safer RAG in Healthcare — https://arxiv.org/pdf/2511.06668
