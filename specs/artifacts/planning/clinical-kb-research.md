# Clinical Knowledge Base — Research Document
**Audience**: harness maintainers, spec author for the clinical-KB feature
**Date**: 2026-05-19
**Status**: research artifact feeding the spec brief in `clinical-kb-brief.md`
**Scope**: a quick-access clinical knowledge base (KB) for low-power local models, with both a general layer and a deployment-contextualized layer auto-curated from the OpenMRS database.

---

## Section A — Methodology survey

### A.1 RAG patterns for clinical use (2024-2026)

The clinical RAG literature in the last 24 months has consolidated around a few recurring patterns. The harness should treat these as load-bearing, not optional.

**MedRAG / MIRAGE benchmark (Xiong et al., ACL 2024)** is the de-facto baseline. It built MIRAGE (7,663 Qs from 5 medical QA datasets) and tested 41 combinations of corpora, retrievers, and LLMs (GPT-3.5, GPT-4, Mixtral, Llama2, MEDITRON, PMC-Llama). Three findings matter here:

1. Hybrid retrieval (BM25 + a dense biomedical retriever) consistently beats either alone.
2. RAG lifts GPT-3.5 and Mixtral to "GPT-4 level" — up to 18 percentage points over chain-of-thought. The leverage is highest for smaller models. This is exactly the user's situation.
3. The "lost-in-the-middle" effect (Liu et al. 2024) appears in medical RAG: relevant snippets buried in the middle of a long context are under-used. Implies short, ordered, top-of-context snippets. Source: https://arxiv.org/abs/2402.13178

**i-MedRAG (Xiong et al. 2024)** — iterative follow-up RAG. The LLM is allowed to ask follow-up retrieval queries based on prior retrievals; reasoning chains form across iterations. Zero-shot i-MedRAG on GPT-3.5 reached 69.68% on MedQA, beating all prior prompt-engineering approaches. Important: this only helps complex clinical-vignette questions; for simple lookups (drug dose, allergy presence) it's overhead. Source: https://arxiv.org/abs/2408.00727

**Self-BioRAG / Self-MedRAG (2024)** — adds self-reflection. A 7B model trained with critic tokens decides per-step whether to retrieve, whether the retrieved context is sufficient, and whether the answer is supported. Reported to outperform other 7B open foundation models on MedQA/MedMCQA/MMLU-Med. Mechanism is generalizable beyond the fine-tuned model: the harness can implement the same gating pattern via prompts + intent classification (which is exactly what `openmrs_chatbot` already does deterministically). Source: https://arxiv.org/abs/2401.15269

**MedGraphRAG (Wu et al., 2024; ACL 2025)** — GraphRAG specialized for medicine. Builds a three-layer hierarchical graph: user-source documents → trusted reference (e.g. UpToDate, MedlinePlus) → terminology backbone (UMLS / SNOMED-CT / RxNorm). Retrieval traverses upward to ground claims in citations and definitions. Reported state-of-the-art on safety-critical benchmarks with credible source documentation. Source: https://arxiv.org/abs/2408.04187; code: https://github.com/ImprintLab/Medical-Graph-RAG

**CUICurate (2026)** — most relevant to the user's auto-curation idea. Uses GraphRAG over UMLS for automated UMLS concept-set curation: given a target concept (e.g. "type 2 diabetes management"), it retrieves candidate CUIs from a UMLS graph then runs LLM filtering/classification to assemble a vetted concept set. This is the closest published prior art for "use an LLM to curate a deployment-specific concept-anchored KB." Source: https://arxiv.org/pdf/2602.17949

**Hybrid retrieval (BM25 + dense) with Reciprocal Rank Fusion** is the modern default. Already used inside chartsearchai's Elasticsearch/hybrid pipelines (RRF k=60 is standard). The "Sparse vs Dense Retrieval for RAG" surveys are unanimous: BM25 catches exact lexical anchors (drug names, ICD codes) that dense embeddings smear, while dense embeddings catch the "any cancer? → Kaposi sarcoma" semantic case. Sources: https://mljourney.com/sparse-vs-dense-retrieval-for-rag-bm25-embeddings-and-hybrid-search/, https://arxiv.org/abs/2402.13178

### A.2 Hallucination reduction in clinical chatbots

**MedAbstain / "Knowing When to Abstain" (2026)** establishes the benchmark for refusal in medical MCQA. Key finding: even SOTA models (GPT-4, Claude) over-answer when uncertain. Adding an explicit abstention option in the prompt produced larger safety gains than scaling model size or chain-of-thought. Implication for the harness: every KB-grounded answer pathway needs an explicit "no answer in KB → abstain" return value, and the prompt template must offer that route. Source: https://arxiv.org/abs/2601.12471

**AbstentionBench (2026)** — 35,000 unanswerable queries across 20 datasets. Demonstrates that even reasoning-enhanced LLMs fail at abstaining on unanswerable questions. Source: https://arxiv.org/abs/2506.09038

**HalluGuard (2025)** — a small (7B-ish) reasoning model trained as a hallucination judge. Classifies document-claim relationships as grounded or hallucinated and produces justifications citing the source span. Pattern: keep the answering model small and add a separate small-model judge in front of the user. Cheap to run on CPU. Source: https://arxiv.org/abs/2510.00880

**Ontology-grounded KGs for clinical QA (Elsevier 2026)** — reports reducing ChatGPT-4 hallucination from 63% to 1.7% by enforcing ontology-structured semantic grounding during answer generation. Caveat: a single-paper reduction this dramatic is suspicious without the benchmark in hand, but the directional finding (forcing answers to ontology-typed entities reduces fabrication) matches the broader literature. Source: https://www.sciencedirect.com/science/article/abs/pii/S1532046426000171

**"Toward Safer RAG in Healthcare" (Nov 2025)** — meta-review identifying common failure modes: source confusion (citing a retrieved doc that doesn't actually support the claim), partial-grounding (a generic claim true at population level but unsupported for the specific patient), and contradictory-evidence collapse. Recommends span-level citation + a confidence/abstain output channel. Source: https://arxiv.org/pdf/2511.06668

**iatroX / NICE-guideline grounding (Oct 2025)** — production RAG system grounded in UK NICE guidelines. Field report: clinicians accept AI answers more readily when each sentence is mapped back to a named guideline passage with version number. The "named source" matters as much as relevance. Source: https://arxiv.org/abs/2510.02967

### A.3 Optimization for small models (<7B parameters)

This is the user's binding constraint: chartsearchai's default deployment runs Gemma 4 E4B (4.5B effective) on ~6-8 GB RAM, and they ship MedGemma 1.5 4B as an option. Both have 128K context windows but degrade with poorly-organized context.

**The "lost in the middle" finding (Liu et al., TACL 2024)** — U-shaped recall curve. Best performance when relevant info is at the start or end of context, worst in the middle. Replicated for medical RAG by MedRAG/MIRAGE. Mitigations:
- Put the most relevant 1-3 snippets at the *top* of the KB context block, just below the system prompt. Worst case: at the very end, just before the question.
- Re-rank retrieved candidates with a small cross-encoder (e.g. MS-MARCO MiniLM, ~22M params, CPU-cheap) before truncating to top-K.
- Aggressively trim. For a small model, K=3-5 short snippets beats K=10 longer ones.
Sources: https://aclanthology.org/2024.tacl-1.9/, https://arxiv.org/abs/2406.16008

**MedCPT (Jin et al., Bioinformatics 2023; refreshed 2024)** — biomedical contrastive pre-trained transformer trained on 255M PubMed click logs. Two encoders (query + article) and a re-ranker. Already supported by chartsearchai (`chartsearchai.embedding.queryModelFilePath` accepts MedCPT). Reasonable default for the *general* KB layer because the corpus will be reference text (drug monographs, guidelines, WHO IMCI/EML), which is structurally similar to MedCPT's training distribution. Sources: https://huggingface.co/ncbi/MedCPT-Query-Encoder, https://academic.oup.com/bioinformatics/article/39/11/btad651/7335842

**"Generalist embeddings beat specialists for clinical text" (2024 study)** — counter-evidence: BioBERT/ClinicalBERT *underperformed* general-purpose sentence-transformer models by 15-20% on short-context clinical semantic search. Reason: domain pretraining lifts knowledge but not the contrastive signal that retrieval needs. Implication: do NOT assume "biomedical model = best." Test all-MiniLM-L6-v2 (chartsearchai default), MedCPT, and bge-small-en-v1.5 on real harness queries; pick on evidence. Source: https://arxiv.org/abs/2401.01943

**ACC-RAG / REFRAG / SARA (2025)** — adaptive context compression. ACC-RAG combines hierarchical compressed embeddings with a context selector that "halts" once accumulated context is sufficient; reports >4× faster inference than standard RAG with equal or better accuracy on Mistral-7B. REFRAG uses RL to select compressed spans; outperforms baselines on LLaMA-2-7B. Useful only when context is the bottleneck — for 4-5B chartsearchai models with 32K context, simpler aggressive truncation likely suffices. Sources: https://arxiv.org/abs/2507.22931, https://openreview.net/pdf?id=T16WNvb9lj

**ModernBERT + ColBERT (2025)** — biomedical RAG with late-interaction reranker on top of a modernized BERT backbone. Outperforms cross-encoder rerankers at similar latency. Worth tracking but not blocking. Source: https://arxiv.org/abs/2510.04757

**Tiny-Critic RAG (2026)** — uses a parameter-efficient SLM via LoRA as a deterministic gatekeeper for ultra-low-latency binary routing. Same pattern as the openmrs_chatbot two-layer classifier, formalized. Source: https://arxiv.org/pdf/2603.00846

### A.4 Auto-curation of a deployment-specific KB from a clinical DB

This is the most novel part of the user's vision and the area with the least prior art. Components exist; the integration pattern is application-novel.

**CUICurate (2026)** — automated UMLS concept-set curation via GraphRAG + LLM filtering. Directly applicable building block. https://arxiv.org/pdf/2602.17949

**"Structured Extraction of Real World Medical Knowledge using LLMs" (Respond Health, NIH-funded 2024)** — uses LLMs to mine real-world EHR data for knowledge graph construction (frequency-driven). https://arxiv.org/html/2412.15256v1

**EHR-R1 (2025)** — reasoning-enhanced foundational LM tailored for EHR analysis; 300K instruction cases across 42 EHR tasks. Demonstrates that a model can be specialized for EHR introspection (the curation worker's role). https://arxiv.org/pdf/2510.25628

**PrimeKG construction (Harvard 2023, ongoing)** — assembled a 4M-relationship biomedical knowledge graph by harvesting 20 sources. Methodology of LLM-assisted assembly of a KG from heterogeneous biomedical sources is now established. https://medium.com/@amitjainusc/unlocking-biomedical-insights-with-primekg-9a090faf2d86

**Open Concept Lab + OpenMRS CIEL dictionary** — the OpenMRS deployment-side reality. Each deployment subscribes to a subset of CIEL concepts; the active `concept_dictionary` differs by site (a Kenyan HIV clinic uses different concepts than a Ugandan maternal-health program). This is the per-deployment specialization signal: don't load drug monographs for drugs that aren't in the formulary. Sources: https://wiki.openmrs.org/display/docs/Concept+Dictionary+Basics, https://openconceptlab.org/2023/03/13/using-ocl-for-openmrs-concept-dictionary-management/

**Honest assessment**: a published end-to-end system that says "given an OpenMRS DB, here is the curated KB you should ship" does not appear to exist. The building blocks (concept extraction, LLM-driven concept-set assembly, frequency analysis) are well-supported. The combination is application-novel. The brief should call this honestly.

### A.5 Cited sources (URL + 1-line takeaway)

1. **MedRAG / MIRAGE** — https://arxiv.org/abs/2402.13178 — RAG lifts small medical LLMs by up to 18 pp; hybrid retrieval wins; lost-in-the-middle confirmed in medical RAG.
2. **i-MedRAG** — https://arxiv.org/abs/2408.00727 — iterative follow-up RAG (zero-shot) hits 69.68% on MedQA, beats all prior prompt engineering.
3. **Self-BioRAG** — https://arxiv.org/abs/2401.15269 — 7B model with self-reflection critic tokens outperforms peers on MedQA/MedMCQA.
4. **MedGraphRAG** — https://arxiv.org/abs/2408.04187 — three-layer graph (sources → references → terminology) for safe, citable medical answers.
5. **CUICurate** — https://arxiv.org/pdf/2602.17949 — GraphRAG + LLM filter for automated UMLS concept-set curation (closest prior art for auto-curation).
6. **MedAbstain** — https://arxiv.org/abs/2601.12471 — abstention prompts beat model scaling for safety; explicit "I don't know" option is mandatory.
7. **Lost in the Middle** — https://aclanthology.org/2024.tacl-1.9/ — U-shape recall curve; put critical snippets at top or bottom.
8. **MedCPT** — https://huggingface.co/ncbi/MedCPT-Query-Encoder — best-in-class biomedical IR encoder, already supported by chartsearchai.
9. **HalluGuard** — https://arxiv.org/abs/2510.00880 — small evidence-grounded judge model for RAG hallucination detection with span citations.
10. **Generalist beats biomedical embeddings (2024)** — https://arxiv.org/abs/2401.01943 — counter-evidence: don't assume biomedical pretraining is required; test empirically.
11. **NICE-guideline RAG (iatroX, 2025)** — https://arxiv.org/abs/2510.02967 — production lessons; clinicians want named, versioned source citations per sentence.
12. **Toward Safer RAG in Healthcare** — https://arxiv.org/pdf/2511.06668 — failure-mode taxonomy: source confusion, partial grounding, contradictory-evidence collapse.
13. **ACC-RAG context compression** — https://arxiv.org/abs/2507.22931 — adaptive compression delivers >4× faster RAG on 7B models with no quality loss.
14. **GraLC-RAG (chunking)** — https://arxiv.org/pdf/2603.22633 — graph-aware late chunking with UMLS infusion; section-aware chunking beats fixed-window.
15. **ModernBERT + ColBERT** — https://arxiv.org/abs/2510.04757 — late-interaction reranking outperforms cross-encoder at similar latency for biomedical RAG.

---

## Section B — Host service evaluation matrix

Five candidate hosts × six criteria (1=poor, 5=excellent). Scored explicitly so reviewers can challenge any cell.

### Criteria
- **C1 Cohesion**: fits this harness's existing patterns (Python-first, OpenMRS-target-coordination, sibling-checkout).
- **C2 Ops overhead**: services, container count, infra dependencies introduced.
- **C3 Reusability**: serves chartsearchai, openmrs_chatbot, the parallel gateway, future med-agent-hub subagents (spec 005) and Catalyst (spec 011) without re-implementation.
- **C4 Data-flow simplicity**: number of hops; failure modes; debuggability.
- **C5 PHI boundary**: keeps non-PHI knowledge separate from PHI patient data; auto-curation pipeline can run against a deployment without exporting PHI.
- **C6 Iteration velocity**: the user's stated need — short feedback loops for KB content tuning.

### Candidates

#### 1. Inside chartsearchai (Java module extension)
| Crit | Score | Justification |
|------|-------|---------------|
| C1 | 2 | chartsearchai is the canonical retrieval surface today but Java; harness is Python; mismatch. |
| C2 | 4 | No new service; reuses chartsearchai's ONNX/Elasticsearch infra. |
| C3 | 1 | Only chartsearchai benefits; openmrs_chatbot, Catalyst, gateway must re-implement. |
| C4 | 5 | Single in-process call: extend `LlmProvider.search` to prepend KB context before chart records. |
| C5 | 3 | KB sits next to patient indexes; risk of cross-contamination in indexing if not strictly partitioned. |
| C6 | 2 | KB content updates require `.omod` rebuild or runtime properties dance; slow iteration. |
| **Total** | **17** | |

#### 2. Inside the parallel model-gateway (Python FastAPI, sister spec)
| Crit | Score | Justification |
|------|-------|---------------|
| C1 | 5 | Python-native, harness-native, FastAPI matches Catalyst's `catalyst-gateway` pattern. |
| C2 | 3 | Adds substantial KB code surface to a service whose primary job is routing — risk of scope creep. |
| C3 | 4 | Any client that uses the gateway gets the KB free; clients that bypass gateway (e.g. direct LM Studio for debugging) don't. |
| C4 | 4 | One hop, but couples KB lifecycle to gateway lifecycle. |
| C5 | 3 | Gateway sees prompts (sometimes containing PHI); auto-curation worker should be a separate process to avoid mixing PHI access patterns. |
| C6 | 3 | Faster than Java but coupled to gateway release cadence. |
| **Total** | **22** | |

#### 3. Dedicated knowledge service (new Python FastAPI + MCP, KB-only)
| Crit | Score | Justification |
|------|-------|---------------|
| C1 | 5 | Matches the harness's "small-service Python target" pattern (chartsearchai, catalyst-mcp, querystore). |
| C2 | 2 | A new container, a new lifecycle, a new docs surface — the largest infra cost of the five. |
| C3 | 5 | One implementation, four+ consumers (chartsearchai inject, gateway inject, openmrs_chatbot, Catalyst sidecar, med-agent-hub subagents). |
| C4 | 4 | Two hops (consumer → KB service → optional curation worker). Clean failure boundaries. |
| C5 | 5 | KB service holds only non-PHI knowledge; auto-curation worker runs deployment-side with PHI never leaving the host; only frequency aggregates leave. |
| C6 | 5 | Independent release cadence; KB content updates hot-reload without restarting consumers. |
| **Total** | **26** | |

#### 4. Reuse openmrs_chatbot KB infrastructure as a library/service
| Crit | Score | Justification |
|------|-------|---------------|
| C1 | 4 | openmrs_chatbot is Python; KB modules already exist; pattern proven. |
| C2 | 3 | Need to extract the KB layer cleanly from the chatbot orchestration code, which is currently entangled. Refactor cost is non-trivial. |
| C3 | 3 | Risks shipping chatbot-specific assumptions (Flask UI, hardcoded intents) into the shared KB. |
| C4 | 3 | Refactor introduces ambiguity about what's KB vs. what's chatbot. |
| C5 | 4 | Patient data already kept separate in openmrs_chatbot; pattern transfers. |
| C6 | 4 | Python iteration speed; existing JSON/ChromaDB tooling. |
| **Total** | **21** | |

#### 5. Hybrid: curation worker in the gateway, retrieval in chartsearchai
| Crit | Score | Justification |
|------|-------|---------------|
| C1 | 2 | Splits ownership across two languages and two services for one logical capability. |
| C2 | 2 | Worst of both: changes to KB content require coordinated changes in two services. |
| C3 | 2 | Other consumers still re-implement; only the gateway↔chartsearchai pair benefits. |
| C4 | 2 | Three hops, two services, version-skew risk. |
| C5 | 4 | Curation isolation is fine; retrieval is fine. |
| C6 | 2 | Slowest iteration of all five (split ownership). |
| **Total** | **14** | |

### Matrix summary

| Host | Total | Verdict |
|------|-------|---------|
| Dedicated knowledge service | **26** | **Primary recommendation** |
| Gateway-embedded | 22 | Acceptable if dedicated service is deferred; KB scope creep risk. |
| openmrs_chatbot library extract | 21 | Strong second; depends on refactor cost. |
| chartsearchai-embedded | 17 | Best for single-target chartsearchai; fails reusability test. |
| Hybrid split | 14 | Not recommended — pays cost of two services for the leverage of one. |

---

## Section C — Recommended approach

### Primary recommendation

**Build a dedicated, host-agnostic clinical knowledge service** with three deliverables:

1. **`clinical-kb` Python service** exposing both HTTP REST and MCP tool interfaces. Single retrieval surface, single content store, single curation pipeline.
2. **Two retrieval surfaces stacked**:
   - `kb_lookup(query, k, intent_hint=None, deployment_id=None)` — general clinical KB layer.
   - `kb_lookup_contextualized(query, k, deployment_id)` — same query routed through the contextualized subset for that deployment.
3. **A separable curation worker** (`clinical-kb-curate`) that runs offline per deployment, analyzes the local OpenMRS DB, and emits a deployment-specific curated KB subset by reference (not by copying PHI).

### Why this wins

Three reasons drove the dedicated-service decision over the (cheaper-looking) gateway-embedded option.

**Reuse arithmetic.** The harness coordinates *at least four likely consumers*: chartsearchai (Java), openmrs_chatbot (Python), the parallel model-gateway (Python, sister spec), and med-agent-hub subagents (spec 005). A KB inside any one host serves only one. A standalone KB serves all four with one curation pipeline. The user explicitly asked: "design KB to be host-agnostic so the decision can be made on evidence."

**PHI boundary.** The auto-curation worker needs to read the OpenMRS DB to compute concept frequency and drug-order distribution. If the worker runs inside the gateway or chartsearchai, the PHI access path gets entangled with the LLM inference path. A separable worker process can run with read-only DB credentials, emit non-PHI aggregates (concept ID → count), and never touch the inference path. This matches harness constitution principle on data boundaries (clinical evidence data MUST remain separate from operating metadata).

**Iteration velocity.** The user's stated need is "quick-access" and they will iterate on KB content. A Java rebuild for chartsearchai-embedded KB takes minutes. A standalone Python service hot-reloads JSON/ChromaDB content in seconds.

### Stacking, not replacing

Critical to state plainly: this KB is **orthogonal** to chartsearchai's existing per-patient retrieval. They stack:

- chartsearchai retrieves patient-axis records (THIS patient's records about diabetes).
- The KB retrieves knowledge-axis context (general management of T2DM per WHO; metformin contraindications).
- The LlmProvider system prompt becomes: `system + KB_snippets + numbered_patient_records + question`.
- Injection point in chartsearchai is `LlmProvider.search` (line 120 in `LlmProvider.java`). It already separates `numberedRecords` from `question`; a `kbContext` parameter slots in cleanly.

This is not a replacement of chart retrieval. Anyone reading the brief should leave with that clear.

### Methodological choices, evidence-anchored

| Layer | Default choice | Evidence |
|-------|----------------|----------|
| Retrieval | Hybrid (BM25 + dense) with RRF (k=60) | MedRAG, harness chartsearchai already uses RRF |
| Dense encoder | Start with all-MiniLM-L6-v2; A/B against MedCPT and bge-small | "Generalist beats biomedical" 2024 finding |
| Reranker | MS-MARCO MiniLM cross-encoder, then optional ColBERT later | "Lost in middle" + ModernBERT+ColBERT 2025 |
| Chunking | Section-aware, atomic-unit (one drug monograph section = one chunk) | GraLC-RAG; multimodal best-practice guides |
| Context shape | Top-K = 3 default for small models, top of context, ≤300 tokens each | Lost-in-middle (TACL 2024); MedRAG findings for sub-7B models |
| Abstention | Explicit "no KB hit" response + prompt template offering it | MedAbstain |
| Citation | Per-snippet source ID returned in API response; consumer renders inline | Toward Safer RAG; NICE-guideline iatroX field report |
| Intent gating | Two-layer (keyword + embedding) classifier on the *KB* side returning `routing_hint` | openmrs_chatbot pattern (in-repo, proven) |
| Curation orchestration | LLM-guided concept-set selection from CIEL/OCL, frequency-weighted | CUICurate methodology, OpenMRS OCL ecosystem |
| Safety judge | Optional small-model judge in front of consumer (HalluGuard-style) | HalluGuard 2025 — deferred to v2 |

### Branch points (if/then)

- **If the model-gateway spec lands first**, the gateway is the first consumer of the KB (it injects KB context into the messages array before forwarding to the model). No change to the KB.
- **If chartsearchai integration is prioritized over gateway**, chartsearchai's `LlmProvider.search` injects KB context. No change to the KB.
- **If MCP is not yet feasible in chartsearchai**, expose HTTP REST first, add MCP after. Both interfaces serve the same content/retrieval logic.
- **If the deployment has no DB to introspect (cold start)**, the contextualized layer falls back to the general layer until the curation worker has run once.

### Assumptions stated explicitly

- The harness will run on Linux/macOS, Python 3.11+, in compose alongside existing services.
- Knowledge content will start small (drug monographs for active formularies, WHO IMCI essentials, child immunization schedules, pediatric dosing tables). Not all of UpToDate.
- Curation worker has read-only access to the OpenMRS DB (no write).
- "Lower-power model" means 4-8B params, ~6-10 GB RAM, 32K-128K context window, locally hosted.

---

## Section D — DB-curated contextualized KB methodology

This section sketches the curation pipeline concretely.

### D.1 What the worker reads from the OpenMRS DB

The OpenMRS data model centers on `concept` and `obs`. Concrete signals:

| Signal | OpenMRS source | Purpose |
|--------|----------------|---------|
| Active concept dictionary | `concept` joined to `concept_name` (filtered to deployment locale) | Defines vocabulary surface |
| Concept frequency in observations | `obs.concept_id` GROUP BY, last 12 months | Which conditions/measurements actually occur |
| Diagnosis distribution | `obs` filtered to diagnosis-class concept; alternatively `conditions` table | Top-N conditions for this deployment |
| Drug formulary | `drug` table joined to `concept` | Drugs that exist as orderable items |
| Drug-order frequency | `orders` joined to `drug` for last 12 months | Which drugs are actually prescribed |
| Concept mappings | `concept_reference_map` to SNOMED-CT, ICD-10, RxNorm, LOINC | Bridge from OpenMRS local concepts to external KBs |
| Patient demographic profile | `person` aggregates (age distribution, sex) — counts only | Profile (pediatric-heavy, maternal, geriatric) |
| Encounter type frequency | `encounter.encounter_type_id` | Care setting profile (HIV clinic vs ANC vs general) |

**PHI discipline**: the worker emits only aggregate counts and concept identifiers — never patient IDs, never observation IDs, never free-text observations. The aggregate output is non-PHI.

### D.2 Concept set assembly (CUICurate-inspired)

1. Query OpenMRS for `(concept_id, name, frequency)` tuples above a threshold (e.g. top 200 concepts by 12-month frequency).
2. Resolve each to external vocabulary (SNOMED-CT / ICD-10 / RxNorm / LOINC) via `concept_reference_map`. Concepts without mappings are flagged and excluded with rationale stored in the curation artifact.
3. Cluster concepts into therapeutic/diagnostic areas using the SNOMED-CT hierarchy (or simple keyword groups as fallback).
4. For each cluster, the curation LLM is given:
   - The cluster summary (top concepts, frequency-weighted)
   - The full general KB index (titles + first 200 chars of each entry)
   - A prompt asking it to select the subset of general-KB entries most relevant to this deployment's actual case mix.
5. The LLM emits a candidate inclusion list with rationale per entry.
6. The list is stored as the curation artifact (`curation_<deployment_id>_<timestamp>.yaml`), reviewed by a human gate per harness constitution principle II ("LLM-assisted analysis MAY propose ... but accepted behavior MUST live in reviewed configuration"). Auto-merge is NOT default.
7. Once reviewed and accepted, the curated subset is loaded into a per-deployment ChromaDB collection (or filtered view of the general index).

### D.3 Pipeline shape

```
[OpenMRS DB (deployment-local)]
        │  read-only, aggregate-only
        ▼
[clinical-kb-curate worker (per deployment)]
        │
        ├── Concept frequency analysis (SQL)
        ├── External vocab mapping (deterministic)
        ├── Cluster construction (deterministic, SNOMED hierarchy)
        └── LLM-guided KB subset selection (cloud LLM call permitted; no PHI sent)
        │
        ▼
[curation_<deployment>_<timestamp>.yaml]   ← human review gate
        │
        ▼
[clinical-kb service: deployment-scoped collection]
        │
        ▼ (consumed by)
[chartsearchai | gateway | openmrs_chatbot | catalyst | med-agent-hub]
```

### D.4 Sample curation prompt sketch

```
You are auditing the relevance of a clinical knowledge base for a specific deployment.

DEPLOYMENT PROFILE (aggregate counts, no patient data):
- Encounter mix: 62% antenatal care, 18% general adult, 12% pediatric, 8% other.
- Top diagnoses (last 12 months): malaria (3,210), anemia in pregnancy (1,850), HIV stable on ART (1,290), ...
- Top drug orders: iron+folate (5,402), artemether-lumefantrine (3,109), TDF/3TC/DTG (1,210), ...
- Vocabularies present: CIEL, SNOMED-CT, RxNorm (partial).

GENERAL KB INDEX (titles + summaries):
[1] WHO IMCI: Pneumonia management in under-fives — Pediatric, respiratory ...
[2] WHO ANC contact 3: First-trimester anemia screening — Antenatal, hematology ...
[3] BNF: Warfarin dosing in atrial fibrillation — Adult, anticoagulation ...
... (full index)

TASK: Output a YAML list of KB entry IDs to INCLUDE in the deployment-specific subset.
For each, give a one-sentence rationale tied to the deployment profile. Output entries to EXCLUDE separately, with rationale.

CONSTRAINTS:
- Never output PHI.
- If the deployment profile is insufficient to judge an entry, mark it review-required.
- Prefer inclusion when uncertain; the human reviewer will trim.
```

### D.5 Output schema

```yaml
curation_artifact:
  deployment_id: "kenya-hiv-clinic-002"
  curated_at: "2026-05-19T14:00:00Z"
  source_db_snapshot: "openmrs-202605-week-19"
  curator_model: "claude-sonnet-4-7@anthropic"
  human_reviewer: null  # filled when reviewed
  review_status: "pending"
  deployment_profile_hash: "sha256:..."
  included_entries:
    - kb_entry_id: "who-imci-art-pediatric-v2024"
      rationale: "high HIV pediatric volume; ART regimens differ by age cohort"
      review_required: false
    - kb_entry_id: "who-art-adult-first-line-2024"
      rationale: "top-3 drug orders include TDF/3TC/DTG; first-line ART monograph essential"
      review_required: false
  excluded_entries:
    - kb_entry_id: "bnf-warfarin-monitoring"
      rationale: "no warfarin prescriptions in 12 months"
      review_required: false
  flagged_for_review:
    - kb_entry_id: "msf-pediatric-tb-treatment"
      rationale: "no TB diagnoses but ART-treated cohort has TB comorbidity risk; reviewer judgment"
```

This artifact is the durable, reviewable record per constitution III ("Record-Level Evidence").

### D.6 Prior art status

Components are well-supported:
- **CUICurate (2026)** — LLM-driven concept-set curation from UMLS.
- **PrimeKG (2023)** — LLM-assisted assembly of biomedical KG from many sources.
- **Structured Extraction from EHR (Respond Health 2024)** — LLM extraction of knowledge structures from real-world EHR data.
- **EHR-R1 (2025)** — reasoning-tuned LM specialized for EHR analysis.

The end-to-end pattern — "introspect a deployment's OpenMRS DB to curate a deployment-tailored KB subset for a small local model" — is application-novel. The brief should claim this honestly: components are well-supported, the integration pattern is novel.

---

## Section E — Open questions for the spec author (`/speckit-clarify` candidates)

1. **General-KB content scope at v1.** Must the v1 KB ship with full WHO IMCI / WHO EML / WHO ANC / BNF / RxNorm essentials, or is a smaller "seed corpus" (e.g. pediatric pneumonia + maternal anemia + HIV first-line ART + top-20 essential drugs) acceptable for the demo path? Smaller seed = faster to demo; larger = more honest assessment of retrieval quality.

2. **Curation auto-merge vs. mandatory human review.** Constitution principle II requires accepted mappings to "live in reviewed configuration." Does the contextualized KB require human review before activation, or is "LLM-curated + automated gate (e.g. eval pass) + audit log" acceptable for v1? Bias should be toward mandatory review; confirm.

3. **PHI boundary for the curation worker.** Is the auto-curation worker permitted to send aggregate concept frequency data to a cloud LLM (no patient-level data, only counts and concept IDs/external vocab codes)? Or must all curation run on a locally hosted LLM regardless of cost?

4. **First consumer.** Should chartsearchai or the parallel model-gateway be the first KB consumer integration? Recommend gateway-first because Python-to-Python is fastest to demo and chartsearchai's Java integration requires a small `.omod` change that the chartsearchai maintainer must sign off on.

5. **Knowledge source provenance and licensing.** WHO and MSF content is openly licensed. BNF / UpToDate / ClinicalKey are NOT. Which sources are in scope for v1, and is there a process for ingesting open-licensed content only, with placeholders for licensed content the deployment can substitute?

6. **Per-deployment subset vs. per-deployment full KB.** Does the contextualized layer (a) filter the general KB to a relevant subset (lighter), or (b) augment the general KB with deployment-specific content (e.g. a deployment's own custom protocols)? Recommendation: (a) for v1, (b) deferred.

---

## Appendix — How this maps onto existing harness code

| Existing component | Role in proposed architecture |
|---|---|
| `targets/chartsearchai/api/.../LlmProvider.java` (line 120, `search`) | Injects KB context into the `system + records + question` envelope. One small change. |
| `targets/openmrs_chatbot/KNOWLEDGE_BASE_INTEGRATION_METHODS.md` (methods 1, 4, 5, 6) | Source pattern for intent classification, retrieval, response gating, validation. Re-implemented as KB-service-internal logic. |
| `targets/openmrs_chatbot/data/*.json` (drug KBs, immunization schedules, milestones) | Seed content for the general KB. |
| `targets/openmrs_chatbot/vectorstore/chroma.py` | Reference impl for the KB ChromaDB collection. |
| `specs/005-med-agent-hub-bridge/spec.md` | Future consumer; KB lookup is a candidate MCP tool for subagents. |
| `specs/artifacts/planning/catalyst-fhir-sidecar-brief.md` § 8 (MCP tool sketch) | Pattern for how Catalyst could consume KB MCP tools. |
| `compose/` | Adds one `clinical-kb` service; one optional `clinical-kb-curate` job. |
| `harness/targets.yaml` | New `clinical-kb` target entry. |
| `evals/` | New eval suite: KB recall, KB citation correctness, abstention discipline, lost-in-middle stress, contextualization regression. |
