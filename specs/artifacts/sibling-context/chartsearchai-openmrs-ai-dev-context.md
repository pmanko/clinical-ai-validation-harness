# OpenMRS AI Project — Dev Session Context Dump
*Last updated: 2026-05-12. Drop this whole file into a fresh dev session (Claude Code, Cursor, etc.) before starting work — it's the minimum context to make non-trivial changes safely.*

---

## 0. TL;DR for a fresh agent

You're working on the **OpenMRS AI with Google** project — let clinicians ask natural-language questions about a patient's chart and get answers with source citations. The code lives in **two OpenMRS modules** that are mid-migration:

- **`openmrs-module-chartsearchai`** = LLM inference + reasoning + retrieval + frontend ESM. Live demo: https://chartsearchai.openmrs.org. **Today this owns everything end-to-end.**
- **`openmrs-module-querystore`** = CQRS read-store being extracted from chartsearchai so chartsearchai can keep its LLM + reasoning and delegate index/retrieval. Four open ADR questions block migration.

The user (Piotr) leads **performance / benchmarking evaluation** for this project as of 2026-05-11. Local LLM runtime is **LM Studio** (`http://localhost:1234/v1`).

---

## 1. The two repos

| Repo | URL | Role | Last push |
|------|-----|------|-----------|
| openmrs-module-chartsearchai | https://github.com/openmrs/openmrs-module-chartsearchai | LLM + reasoning + retrieval today; LLM-only after migration | 2026-05-12 00:22 UTC (very active) |
| openmrs-module-querystore | https://github.com/openmrs/openmrs-module-querystore | Pure CQRS read store (MySQL/Lucene/Elasticsearch backends) | 2026-05-11 21:41 UTC |

Both are MPL 2.0 with Healthcare Disclaimer. Both require **OpenMRS Platform 2.8.0+, Java 11+, Webservices REST 2.44.0+**.

---

## 2. Architecture (load-bearing facts)

```
┌──────────────────────────────────────────────────────────────────────┐
│  chartsearchai  (Java OpenMRS module)                                │
│                                                                      │
│  ┌──────────────────────────────┐    ┌────────────────────────────┐  │
│  │ LLM engine                   │    │ Frontend ESM (O3 React)    │  │
│  │   local: embedded llama-server│    │   floating button OR        │  │
│  │   remote: OpenAI-compat API  │    │   workspace dock OR both    │  │
│  │   (LM Studio fits here)      │    └────────────────────────────┘  │
│  └──────────────────────────────┘                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ Retrieval pipelines (choose one via GP)                       │    │
│  │   embedding (ONNX in-process)  ← default                      │    │
│  │   lucene     (BM25 only)                                      │    │
│  │   hybrid     (Lucene + ONNX kNN via RRF)                      │    │
│  │   elasticsearch (8.14+ cluster)                               │    │
│  └──────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────┐   ┌─────────────────────────────────────────┐   │
│  │ AOP indexing    │   │ Embedded llama-server (port 18085)      │   │
│  │ (move to events)│   │ ManagedSubprocess + idle-stop after 30m │   │
│  └─────────────────┘   └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘

After migration:
chartsearchai LLM layer  ──→  querystore.QueryStoreService  ──→  per-type indices
                                                              (openmrs_obs,
                                                               openmrs_condition,
                                                               openmrs_allergy, ...)
```

**Per-type indices (querystore convention):** `openmrs_obs`, `openmrs_condition`, `openmrs_diagnosis`, `openmrs_allergy`, `openmrs_order`, `openmrs_program`, `openmrs_dispense`, `openmrs_patient`, `openmrs_encounter`, `openmrs_visit`. Module-contributed types are `openmrs_<moduleid>_<type>`. Cross-type queries use `openmrs_*`.

**Document shape (querystore Decision 6):** every document has `text` (plain-text, labeled prose — *not* JSON, *not* FHIR), `embedding` (dense vector), `patient_uuid`, `date`, `resource_type`, `resource_uuid`, plus type-specific structured metadata.

**Plain-text serialization example:**
```
Drug order: Metformin 500mg. Dose: 1.0 Tablet(s) Oral twice daily.
Duration: 30 Day(s). Quantity: 60.0 Tablet(s). Action: NEW. Urgency: ROUTINE
```

---

## 3. Module structure

### chartsearchai
```
openmrs-module-chartsearchai/
├── api/                        # core Java module (services, indexers, advice)
│   ├── src/main/java/.../chartsearchai/
│   │   ├── ChartSearchAiConstants.java     # all GP_ keys live here
│   │   ├── api/impl/
│   │   │   ├── LlmInferenceService.java
│   │   │   ├── LlmEngine.java
│   │   │   ├── LlmProvider.java
│   │   │   ├── LlmAnswerExtractor.java
│   │   │   ├── LlmResponseParser.java
│   │   │   ├── RetrievalQuery.java
│   │   │   ├── EmbeddingRankingPipeline.java
│   │   │   ├── ChartSearchServiceRouter.java
│   │   │   └── ...
│   │   ├── api/
│   │   │   ├── ElasticsearchIndexer.java
│   │   │   ├── LuceneIndexer.java
│   │   │   ├── EmbeddingIndexer.java
│   │   │   ├── HybridRetriever.java
│   │   │   ├── EmbeddingIndexTask.java     # bulk backfill
│   │   │   ├── AuditLogPurgeTask.java
│   │   │   └── (AOP advice: EncounterIndexingAdvice, ObsIndexingAdvice,
│   │   │       PatientDataIndexingAdvice, etc.)
│   │   ├── embedding/
│   │   │   ├── OnnxEmbeddingProvider.java
│   │   │   └── WordPieceTokenizer.java
│   │   ├── serializer/
│   │   │   ├── ObsTextSerializer.java
│   │   │   ├── ConditionTextSerializer.java
│   │   │   ├── DiagnosisTextSerializer.java
│   │   │   ├── AllergyTextSerializer.java
│   │   │   ├── OrderTextSerializer.java
│   │   │   ├── MedicationDispenseTextSerializer.java
│   │   │   ├── PatientProgramTextSerializer.java
│   │   │   ├── PatientRecordLoader.java
│   │   │   └── ConceptNameUtil.java
│   │   └── util/DateFormatUtil.java
│   └── src/test/java/.../chartsearchai/
│       └── api/impl/
│           ├── LlmInferenceServiceTest.java          (cross-query regressions)
│           ├── LlmInferenceServiceEvalTest.java
│           ├── LlmAnswerQualityTest.java             ← 20 clinical questions
│           ├── PromptInjectionEvalTest.java
│           ├── RemoteLlmEngineTest.java
│           ├── LlmProviderTest.java
│           ├── LlmProviderUserMessageTest.java
│           ├── EndToEndSearchTest.java
│           ├── StreamingContextPropagationTest.java
│           ├── ElasticsearchKnnFallbackTest.java
│           └── (eval baselines for EnrichedRetrievalEvalTest, 485 cases)
├── omod/                       # OpenMRS module packaging (.omod artifact)
├── llama-server-natives/       # bundled llama-server binaries per platform
├── docs/images/                # demo screenshots
├── docker-compose.yml          # full O3 + chartsearchai stack
├── Dockerfile.{backend,frontend,gateway}
├── backend-init.sh             # downloads MiniLM + Gemma 4 E4B on first boot
├── README.md                   # 44KB — read sections "Setup" + "Architecture"
└── CLAUDE.md                   # working rules (see §10 below)
```

### querystore
```
openmrs-module-querystore/
├── api/
│   ├── src/main/java/.../querystore/
│   │   ├── QueryStoreConstants.java
│   │   ├── api/QueryStoreService.java       # the v1 consumer API surface
│   │   ├── serialization/
│   │   │   └── PatientProgramRecordSerializer.java  (and others to come)
│   │   └── ...
│   └── src/test/
│       ├── java/.../querystore/eval/
│       │   ├── AbstractRetrievalQualityEvalTest.java
│       │   ├── MysqlRetrievalQualityEvalIntegrationTest.java
│       │   ├── ElasticsearchRetrievalQualityEvalIntegrationTest.java
│       │   ├── RetrievalQualityEvalTest.java
│       │   ├── EvalDataset.java
│       │   ├── EvalCase.java
│       │   └── EvalMetrics.java
│       └── resources/eval/
│           ├── retrieval-eval-dataset.json   ← 153 records, query-recall benchmark
│           └── full-patient-dataset.json
├── omod/
├── docs/
│   ├── adr.md                                ← AUTHORITATIVE spec
│   ├── migration-chartsearchai.md            ← what blocks the migration
│   └── chartsearchai-port-map.md             ← file-level migration pointer
├── README.md
└── CLAUDE.md
```

---

## 4. Local setup — three paths

### Path A — Docker (fastest, full stack)
```bash
git clone https://github.com/openmrs/openmrs-module-chartsearchai.git
cd openmrs-module-chartsearchai
docker compose up --build
# Gateway on port 80, frontend ESM at /openmrs/spa
# backend-init.sh auto-downloads MiniLM (~86MB) + Gemma 4 E4B (~5GB) on first boot.
```

Then point LLM at LM Studio:
- On Mac: replace `localhost` with `host.docker.internal` in the GP URL.
- Admin → Settings → set the GPs (see §6).

### Path B — Standalone zip (~17 GB, bundles 26B MoE)
```bash
curl -LO https://nightly.link/openmrs/openmrs-module-chartsearchai/workflows/build-standalone.yml/main/openmrs-standalone-chartsearchai.zip
unzip openmrs-standalone-chartsearchai.zip
# Launch the bundled OpenMRS standalone
```

### Path C — OpenMRS SDK (dev loop you'll actually use day-to-day)
```bash
# 1. Clone + build the module
git clone https://github.com/openmrs/openmrs-module-chartsearchai.git
cd openmrs-module-chartsearchai
mvn package
# omod/target/chartsearchai-*.omod is the artifact

# 2. Set up an OpenMRS dev server via SDK
mvn openmrs-sdk:setup -DserverId=ai -Ddistro=referenceapplication:2.x
# Drop the .omod into ~/openmrs/ai/modules/
cp omod/target/chartsearchai-*.omod ~/openmrs/ai/modules/

# 3. Place the embedding model + (optional) GGUF model
mkdir -p ~/openmrs/ai/chartsearchai
curl -fsSL https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/onnx/model.onnx -o ~/openmrs/ai/chartsearchai/all-MiniLM-L6-v2.onnx
curl -fsSL https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/vocab.txt -o ~/openmrs/ai/chartsearchai/vocab.txt

# 4. Run
mvn openmrs-sdk:run -DserverId=ai
# Module loads at http://localhost:8080/openmrs
# Admin / Admin123
```

To do the same for querystore (after chartsearchai is up):
```bash
git clone https://github.com/openmrs/openmrs-module-querystore.git
cd openmrs-module-querystore
mvn -pl api install        # this is the "claim of success" contract per querystore CLAUDE.md
```

---

## 5. LM Studio wiring (you have LM Studio installed)

LM Studio exposes OpenAI-compat at `http://localhost:1234/v1` by default. chartsearchai supports this via `remote` engine mode. **All keys verified from `ChartSearchAiConstants.java`**:

| Global Property | Value |
|----|----|
| `chartsearchai.llm.engine` | `remote` |
| `chartsearchai.llm.remote.endpointUrl` | `http://localhost:1234/v1/chat/completions` |
| `chartsearchai.llm.remote.modelName` | *(model id as LM Studio exposes it, e.g. `google/medgemma-1.5-4b-it`)* |
| `chartsearchai.llm.timeoutSeconds` | `300` |
| `chartsearchai.retrieval.pipeline` | `embedding` *(default; also: `lucene`, `hybrid`, `elasticsearch`)* |
| `chartsearchai.embedding.preFilter` | `false` *(true to narrow before LLM; trade-off: misses negative-reasoning)* |
| `chartsearchai.embedding.modelFilePath` | `chartsearchai/all-MiniLM-L6-v2.onnx` |
| `chartsearchai.embedding.vocabFilePath` | `chartsearchai/vocab.txt` |

API key goes in `openmrs-runtime.properties` (NOT the DB, for security):
```
chartsearchai.llm.remote.apikey=lm-studio
```
*(LM Studio doesn't validate, so any string works. Omit if your LM Studio is configured without auth.)*

**Docker note:** on Mac/Win, in the GP URL use `http://host.docker.internal:1234/v1/chat/completions` instead of `localhost`.

**Models to load in LM Studio** (pick by RAM; all work with chartsearchai):
- **MedGemma 1.5 4B** (~6-8 GB) — the OpenMRS AI project's reference target
- **Gemma 4 E4B** (~6-8 GB) — chartsearchai's installed default
- **Gemma 4 26B MoE** (~18-22 GB) — production-recommended, ~3.8B active params/token
- Llama 3.3 8B, Gemma 3 12B, Mistral Nemo 12B are also benchmarked

---

## 6. Full GP reference (every key the module reads)

From `ChartSearchAiConstants.java`:

**LLM**
- `chartsearchai.llm.engine` — `local` | `remote`
- `chartsearchai.llm.modelFilePath` — relative path to .gguf (local engine)
- `chartsearchai.llm.remote.endpointUrl` — chat completions URL (remote engine)
- `chartsearchai.llm.remote.modelName` — model id at remote endpoint
- `chartsearchai.llm.systemPrompt` — override clinical system prompt
- `chartsearchai.llm.timeoutSeconds` — default 300
- `chartsearchai.llm.idleTimeoutMinutes` — default 30 (local engine; 0 = never stop)
- `chartsearchai.llm.serverPort` — default 18085 (local engine)
- `chartsearchai.llm.contextSize` — default 32768 (local engine)

**Embedding & retrieval**
- `chartsearchai.retrieval.pipeline` — `embedding` | `lucene` | `hybrid` | `elasticsearch`
- `chartsearchai.embedding.preFilter` — `false` (default) or `true`
- `chartsearchai.embedding.modelFilePath`, `chartsearchai.embedding.vocabFilePath`
- `chartsearchai.embedding.queryModelFilePath` — separate query encoder (e.g. MedCPT)
- `chartsearchai.embedding.topK` — default 10
- `chartsearchai.embedding.similarityRatio` — default 0.80
- `chartsearchai.embedding.scoreGapMultiplier` — default 2.5
- `chartsearchai.embedding.minScoreGap` — default 0.10
- `chartsearchai.embedding.gapValidationCosineThreshold` — default 0.47
- `chartsearchai.embedding.keywordWeight` — default 0.3
- `chartsearchai.embedding.typeBoostFactor` — default 1.0 (1.0–3.0)
- `chartsearchai.embedding.queryPrefix` — empty for MiniLM; `search_query: ` for BGE
- `chartsearchai.embedding.maxSequenceLength` — default 256

**Ops**
- `chartsearchai.warmupEnabled` — default `true`
- `chartsearchai.rateLimitPerMinute` — default 10 (0 = disable)
- `chartsearchai.cacheTtlMinutes` — default 0 (disabled)
- `chartsearchai.auditLogRetentionDays` — default 90 (0 = retain all)

**Elasticsearch backend (when `retrieval.pipeline=elasticsearch`)**
- `chartsearchai.es.uri` — e.g. `http://localhost:9200`

---

## 7. Privileges (don't forget these or the UI button hides)

Grant to whatever role tests with you:
- **AI Query Patient Data** — execute chart search
- **View AI Audit Logs** — view audit endpoint

The floating-sparkle button only renders when the user has the `AI Query Patient Data` privilege.

---

## 8. Eval scaffolding (this IS the benchmarking work)

### In querystore (retrieval-side, 153 cases)
- **Dataset:** `api/src/test/resources/eval/retrieval-eval-dataset.json`
- **Driver:** `AbstractRetrievalQualityEvalTest` (`TOP_K = 30`, `MIN_AVG_RECALL = 0.4`)
- **Per-backend:** `MysqlRetrievalQualityEvalIntegrationTest`, `ElasticsearchRetrievalQualityEvalIntegrationTest`
- **Run:** `mvn -pl api test -Dtest=*RetrievalQualityEvalIntegrationTest -Dquerystore.eval.modelDir=$HOME/openmrs/ai/chartsearchai`
- **Per-case latency budget:** Lucene-in-JVM ~200ms, ES-over-HTTP ~2000ms

### In chartsearchai (LLM-side + cross-query regressions)
- **Cross-query regressions (485 cases):** `EnrichedRetrievalEvalTest` and the `enriched_*` tests in `LlmInferenceServiceTest`
- **LLM answer quality:** `LlmAnswerQualityTest`
- **Prompt injection robustness:** `PromptInjectionEvalTest`
- **System properties to set:**
  ```
  -Dchartsearchai.llm.quality.endpoint=http://localhost:1234/v1/chat/completions
  -Dchartsearchai.prompt.injection.endpoint=http://localhost:1234/v1/chat/completions
  -Dchartsearchai.eval.model=l6-v2     # or: medcpt — runs different model-specific tuning
  ```
- **Defaults if unset:** `http://localhost:18085/v1/chat/completions` (the embedded llama-server)

### The 20 Clinical Questions (the eval scope)
Source: https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1302790145 (the page header says 20 but only 18 are listed — open question to confirm):

1. Any allergies?
2. What medications is she on right now?
3. What's on the active problem list?
4. What's happened lately?
5. When was the last visit, and what was it for?
6. Most recent vital signs?
7. What's the patient's contact info?
8. Current HIV status and date of last test?
9. How has the patient's weight changed over the past year?
10. Share the history of CD4 counts since coming to clinic.
11. Are immunizations up to date?
12. What things have been ordered for this patient over the past 6 months?
13. Give me the results of the last BMP.
14. Does she have any upcoming appointments?
15. What was recorded for the last patient visit?
16. How old is she?
17. What care programs is the patient in?
18. Tell me all of the patient's lab results that help me understand her current HIV status.

---

## 9. Migration plan: chartsearchai → querystore (from `docs/migration-chartsearchai.md`)

### Four open ADR questions blocking migration
All in `openmrs-module-querystore/docs/adr.md`:
1. **Patient merge handling** — chartsearchai uses AOP today. querystore needs to define repoint/re-index behavior on merge events. Open: does OpenMRS core even emit a merge event?
2. **Initial backfill / bootstrap** — chartsearchai indexes lazily on first chart access + bulk task. querystore needs a clear bootstrap path. (And chartsearchai's current ES path has a chicken-and-egg bug: `EmbeddingIndexTask` only writes MySQL, AOP's `reindexIfActive` returns false for never-indexed patients → ES never auto-populates.)
3. **Long-text chunking for embeddings** — MiniLM's 256-token cap silently truncates. Resolve chunking strategy or inherit the silent-truncation bug.
4. **Sync reliability and reconciliation** — chartsearchai's "best-effort, swallow errors" model is unacceptable for a shared read store. Need durable subscription + DLQ + reconciliation.

### Migration order
1. Resolve the 4 open questions in querystore.
2. chartsearchai swaps query-time embedder to querystore's choice (multilingual-e5 class per Decision 8).
3. chartsearchai retrieval calls `QueryStoreService` querying `openmrs_*` (tier-agnostic).
4. chartsearchai removes its AOP indexing + `chartsearchai-patient-records` index.
5. Validate with the 153-record eval dataset against the new pipeline.

### What stays in chartsearchai unchanged
- LLM inference (local llama-server OR remote OpenAI-compat API)
- Adaptive filtering: gap detection, similarity ratio, z-score gate, coherence filter, type boost
- Post-retrieval scoring and absent-data detection
- Prompt assembly, citation formatting, recency cap, input validation
- Streaming SSE API
- Audit log and rate limiting

---

## 10. Conventions / rules (from both CLAUDE.md files — important if making code changes)

### Both repos
- **Source of truth.** querystore: `docs/adr.md`. chartsearchai: real code + the 485-case eval baseline.
- **Verify OpenMRS APIs against the jar.** Use `javap -p ~/.m2/repository/org/openmrs/api/openmrs-api/*/openmrs-api-*.jar` rather than recalling from training data. The 2.x API has subtle differences (e.g. `Concept.getSynonyms(Locale)` uses strict `Locale.equals` while `Concept.getName(Locale)` does language-level fallback).
- **`mvn -pl api install` is the contract for "done."**

### chartsearchai-specific (these are strict)
- **Never weaken assertions or revert test data** to make tests pass. Fix production code.
- **Tests must call the actual production pipeline** — no mocks/simulations/reimplementations.
- **Tests are the spec.** Modifying tests is changing the spec.
- **TDD:** failing test first, then production code to make it pass.
- **Never commit code with known regressions.** If a change improves one query but breaks another, the root cause is in shared infrastructure (noise profile, score distribution), not the individual stage.
- **Apparent regressions may be improvements.** Check what the "regression" actually returns — many baseline answers were false positives.
- **Combine mechanisms.** Don't declare "architecturally impossible" after only trying thresholds. Combine scoping + thresholds + baseline verification.
- **Model-specific tuning.** Each embedding model has its own `PipelineConfig.forModel()`. Don't use one-size-fits-all constants. Run both `-Dchartsearchai.eval.model=l6-v2` AND `medcpt`.
- **Cross-query regression tests:** before pushing, run `enriched_*` in `LlmInferenceServiceTest` AND `EnrichedRetrievalEvalTest` (485 cases).
- **Category hints:** when adding to new record types, also add to `*_DATASET_CATEGORY_HINTS` in `TestDatasetHelper` and regenerate the eval baseline.

### chartsearchai API entry points (do not bypass)
- Prefixed text → `ChartSearchAiUtils.buildPrefixedText(resourceType, text)` (never call private `getEmbeddingPrefix()` or hardcode prefix strings)
- Query embedding input → `LlmInferenceService.prepareEmbeddingInput(question, queryPrefix)`
- Retrieval pipeline → `LlmInferenceService.findSimilar()`
- Building embeddings → `EmbeddingIndexer.buildEmbeddings()`
- Cosine similarity → `ChartSearchAiUtils.cosineSimilarity()`
- Test datasets → `TestDatasetHelper.{FULL_PATIENT_DATASET,SECOND_PATIENT_DATASET,toSerializedRecords,inferResourceType,stripDatasetPrefixAndDate}`
- Category hints in tests → `TestDatasetHelper.FULL_DATASET_CATEGORY_HINTS`
- Stripping category hints → `ChartSearchAiUtils.stripCategoryHints()`
- Noise profile w/ enrichment → `ModelNoiseProfile.compute(embeddings, provider)` (2-arg form)

### querystore-specific
- **ADR principles to internalize:**
  - CQRS + self-sufficiency (Decision 1): no round-tripping to core to enrich a result
  - Per-type indices, `openmrs_` prefix (Decision 4)
  - Plain-text serialization (Decision 5) — labeled prose, *not* JSON or FHIR
  - Document = text + embedding + structured (Decision 6)
  - Date separation: record timestamps in metadata, not embedded text (Decision 7); clinically significant dates (onset, resolution) stay in embedded text
  - Coded fields = UUID + name (Decision 9)
  - Voided → delete (Decision 10); retired → preserve (Decision 11)
  - Sync = events first (Decision 12), AOP only as scoped gap filler
  - Module contributions via SPI (Decision 13)
- **Mirror the closest sibling.** New impl should match the most-similar shipped one.
- **Promote emergent conventions to the ADR.** When 2+ implementations settle on the same pattern, capture the rule in the relevant Decision.

---

## 11. Who's who

| Person | Role |
|--------|------|
| **Paul Biondich** | Strategic vision; brought EHR Navigator inspiration |
| **Daniel Kayiwa** (`dkayiwa`) | OpenMRS primary dev; built chartsearchai + querystore |
| **Jan Flowers** | DIGI/UW lead; project sponsor; intros & coordination |
| **Veronica** | Eval lead (clinical + user evaluation tracks) |
| **Karla** (Google) | Funder check-ins (monthly/6-week cadence) |
| **Fred** (Google) | MedGemma alignment contact |
| **Rafal** | Primary dev on querystore event-driven pipeline |
| **Ian Bacher** | Architecture oversight (Catalyst-side too) |
| **Beryl** | Community outreach (AI community members) |
| **Jaye** | OMOP ETL lead (related: `openmrs-contrib-omop-etl`) |
| **Piotr** | **Performance / benchmarking evaluation lead + Google Research intro** (as of 2026-05-11) |

---

## 12. Related repos / docs worth knowing

| Resource | Link |
|----------|------|
| OpenMRS AI Confluence space | https://uwdigi.atlassian.net/wiki/spaces/OMRSAI |
| Clinical Questions page | https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1302790145 |
| 2026-05-11 latest meeting notes (your role formalized) | https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1301610503 |
| 2026-01-29 strategic kickoff transcript | https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1041465368 |
| 2026-03-26 Karla check-in | https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1192787971 |
| Google MedGemma EHR Navigator (reference impl) | https://github.com/Google-Health/medgemma/blob/main/notebooks/ehr_navigator_agent.ipynb |
| HuggingFace EHR Navigator Space | https://huggingface.co/spaces/google/ehr-navigator-agent-with-medgemma |
| Live demo | https://chartsearchai.openmrs.org (admin / Admin123) |
| Standalone download | https://nightly.link/openmrs/openmrs-module-chartsearchai/workflows/build-standalone.yml/main/openmrs-standalone-chartsearchai.zip |
| Chart Search wiki | https://openmrs.atlassian.net/wiki/spaces/projects/pages/373325839/Chart+Search+aka+ChartSearchAI |
| MiniLM-L6-v2 (embedding) | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |
| Gemma 4 E4B (default LLM) | https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF |
| Gemma 4 26B MoE (production) | https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF |
| MedGemma 1.5 4B | https://huggingface.co/unsloth/medgemma-1.5-4b-it-GGUF |
| OMOP ETL (CZI work, related read-DB direction) | https://github.com/openmrs/openmrs-contrib-omop-etl |
| Catalyst (parallel OpenELIS effort) | OpenELIS-Global-2 branch `feat/OGC-070-catalyst-assistant-m0-agent-specialization`, `specs/OGC-070-catalyst-assistant/plan.md` |

---

## 13. First 30 minutes of a dev session — recommended order

1. **Clone both repos** (commands in §4).
2. **Read** `openmrs-module-querystore/docs/adr.md` end-to-end — it's the source of truth for the architecture you're modifying around. (~30 min the first time, skim after.)
3. **Read** `openmrs-module-chartsearchai/README.md` sections "Setup" + "Architecture" + "Query behavior" — practical operation.
4. **Read** `openmrs-module-querystore/docs/migration-chartsearchai.md` — what blocks migration.
5. **Read** `openmrs-module-querystore/docs/chartsearchai-port-map.md` — file-level migration pointer.
6. **Skim** `openmrs-module-chartsearchai/CLAUDE.md` rules (§10 above is a digest).
7. **Confirm** `mvn -pl api install` succeeds clean on both repos before changing code.
8. **Run** the live demo on https://chartsearchai.openmrs.org with Betty Williams before touching anything — anchors what "working" looks like.

---

## 14. Open work items relevant to dev today

From 2026-05-11 meeting + earlier:
- **You (Piotr) are leading performance/benchmarking evaluation** — formalized 5/11. Concrete deliverable scope still TBD with Vero/Jan/Daniel/Ian interviews this week.
- **Karla's 1-2 slide ask** (Google-OpenMRS collaboration history) — was due 2026-03-30, still open.
- **Joint OpenMRS↔OpenELIS dev call on querystore** — Jan asked for it 2026-04-28, nothing scheduled.
- **Confirm 18 vs 20 clinical questions** — the wiki page says 20 but lists 18.
- **Get Daniel's confirmation** on which Google AI module is the canonical entry point today (answer based on code: chartsearchai is, with querystore being extracted).
- **Graham Grieve meeting** — Jan-29 action item; no follow-up captured in later notes.
- **Fred / MedGemma alignment status** — explicit Jan-29 ask; status unclear.

---

## 15. Quick reference: commands you'll run repeatedly

```bash
# Build both modules
( cd openmrs-module-chartsearchai && mvn -pl api install )
( cd openmrs-module-querystore     && mvn -pl api install )

# Run chartsearchai tests against LM Studio
cd openmrs-module-chartsearchai
mvn -pl api test \
  -Dtest=LlmAnswerQualityTest \
  -Dchartsearchai.llm.quality.endpoint=http://localhost:1234/v1/chat/completions

# Run prompt-injection eval
mvn -pl api test \
  -Dtest=PromptInjectionEvalTest \
  -Dchartsearchai.prompt.injection.endpoint=http://localhost:1234/v1/chat/completions

# Run 485-case enriched retrieval eval (model-specific tuning)
mvn -pl api test -Dtest=EnrichedRetrievalEvalTest -Dchartsearchai.eval.model=l6-v2
mvn -pl api test -Dtest=EnrichedRetrievalEvalTest -Dchartsearchai.eval.model=medcpt

# Run querystore retrieval-quality eval (153 cases)
cd openmrs-module-querystore
mvn -pl api test \
  -Dtest=MysqlRetrievalQualityEvalIntegrationTest \
  -Dquerystore.eval.modelDir=$HOME/openmrs/ai/chartsearchai
# or for ES:
mvn -pl api test \
  -Dtest=ElasticsearchRetrievalQualityEvalIntegrationTest \
  -Dquerystore.eval.modelDir=$HOME/openmrs/ai/chartsearchai

# OpenMRS SDK lifecycle
mvn openmrs-sdk:setup -DserverId=ai -Ddistro=referenceapplication:2.x
mvn openmrs-sdk:run   -DserverId=ai

# Disassemble OpenMRS API jar to verify method signatures
javap -p ~/.m2/repository/org/openmrs/api/openmrs-api/*/openmrs-api-*.jar | grep <symbol>
```

---

*Save location: `~/Documents/DailyPlanner/openmrs-ai-dev-context.md`. Last code verification: 2026-05-12 (both repos cloned shallow, READMEs + CLAUDE.md + constants files inspected). Re-clone before each major work session — chartsearchai is pushing daily.*
