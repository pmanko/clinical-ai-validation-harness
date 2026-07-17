# Chart Context and Inference Cache Research Plan

**Date:** 2026-07-15  
**Roadmap:** `MAH-CONSOLIDATION-2026-07-09-v1`  
**Status:** Research-backed future workstream; implementation is deferred until the current release proof is complete  
**Scope:** med-agent-hub, its optional context-source adapters, and the local llama.cpp router

## Decision Summary

Caching should be pursued, but not as one opaque patient-chart cache. The system has four distinct
reuse opportunities:

1. **Model residency:** keep the model weights needed by the active profile loaded when memory permits.
2. **Prompt-prefix/KV reuse:** let the inference server reuse an identical token prefix for repeated
   questions against the same stable context.
3. **Clinical evidence reuse:** avoid repeatedly fetching and normalizing an unchanged patient ledger,
   while preserving source freshness and authorization.
4. **Derived-computation reuse:** avoid repeatedly tokenizing the same records and rebuilding the same
   deterministic chart fragments during context selection.

The hub must never cache a final clinical answer or a question-specific selected view. Temporal facts,
reference-date classification, deterministic gates, review, and grounding still run for every turn.

The recommended order is measurement first, then low-risk computation reuse, then a source-neutral
evidence cache with explicit freshness, and finally prompt-layout and model-residency experiments.
Absolute local latency is not a gate; compare cache-on and cache-off behavior on the same machine and
warm state. The existing local warmup is only a repeatable test and demo control. It is not a product
optimization and is not evidence that chart retrieval or arbitrary future prompts have been cached.

## Current Code Findings

| Finding | Code evidence | Consequence |
|---|---|---|
| The hub fetches the complete patient chart on every patient-context request. | `targets/med-agent-hub/server/context_sources.py`, `QueryStoreSource.fetch`; `targets/med-agent-hub/server/querystore_client.py`, `get_patient_chart` | A multi-turn session repeats all paged HTTP reads and normalization even when the chart is unchanged. |
| The source registry and Querystore client are rebuilt for each context preparation. | `targets/med-agent-hub/server/engine.py`, `_prepare_context`; `SourceRegistry.default` in `context_sources.py` | There is no process-level source cache or persistent HTTP connection owner at this boundary. |
| The current Querystore patient-record endpoint has no validator contract. | `targets/querystore/omod/src/main/java/org/openmrs/module/querystore/web/rest/QueryStoreRestController.java`, `getPatientRecords` | The hub cannot issue a conditional request with `If-None-Match` or prove that a cached ledger is current. |
| Oversized context selection depends on the latest question. | `targets/med-agent-hub/server/context_sources.py`, `_ranked_records` and `select_context` | Different questions can change records near the beginning of the model prompt and destroy most exact-prefix reuse. |
| Oversized fitting now batches rendered-record token costs and exact-checks only bounded assembled candidates. | `targets/med-agent-hub/server/context_sources.py`, `RouterTokenCounter.count_records` and `select_context` | Hub `dad07e6` removes the record-by-record full-prompt recount. One model-specific `/tokenize` request maps token pieces to record ranges; every proposed assembled prompt is still exact-counted before use. |
| The chart is inserted near the start of the answer messages. | `targets/med-agent-hub/server/engine.py`, `_replace_chart_message` | A stable full chart is cache-friendly, but a question-conditioned selected chart changes the early prefix. |
| llama.cpp prompt caching is enabled by default and exposes reused/processed token counts. | Local router uses llama.cpp; official server docs define `cache_n`, `prompt_n`, `prompt_ms`, and prompt-cache controls | The current hub does not retain these fields in its stage trace, so prefix reuse is not measurable per role. |
| The local product launcher unnecessarily limited fresh router starts to one resident model. | `.env.chartsearch.example` and `scripts/chartsearchai-local.sh` previously set `LLAMA_ROUTER_MODELS_MAX=1`; llama.cpp defines `--models-max` | E2B and E4B are only 3.2 GiB and 4.6 GiB on disk and can remain resident together on the reference machine. The local default is corrected to two; the explicit one-model policy remains only for large-model workloads. |

The original 365-record diagnostic observed roughly 10 seconds of context preparation and used
20,475 of a 20,480-token input limit. After eligibility correction but before batched fitting, run
`20a08ef1-6829-4bea-843e-ae523ee11b02` stopped filling the window but still averaged about 9.7 seconds
for E4B and 10.0 seconds for 12B context preparation because the sequential recount remained. Its
end-to-end E4B latency averaged 71.2 seconds versus 98.3 seconds for the packed baseline; 12B averaged
164.9 versus 172.6 seconds. These are diagnostic observations on one local machine, not model-quality
or universal latency claims. The separate two-turn comparison exposed E4B Answers in 11.6 and 15.8
seconds; E2B took 24.4 and 21.5 seconds and produced weaker structured output. Inspection of that
comparison router confirmed `--models-max 4` with both E2B and E4B loaded, so eviction did not explain
E2B's slower result.

## Research Findings

### Source freshness and clinical-data safety

HTTP caching is based on explicit freshness and revalidation, not an assumption that a repeated URL is
unchanged. RFC 9111 defines cache keys, freshness, validators, conditional requests, invalidation, and
special handling for authenticated responses. FHIR applies the same pattern to clinical resources:
servers should return `ETag` and `Last-Modified`, and clients can use `If-None-Match` or
`If-Modified-Since` and accept `304 Not Modified`.

OWASP's RAG security guidance identifies cross-user leakage, stale permissions, and stale or poisoned
content as cache risks. It recommends user/tenant/permission scoping, invalidation on content or
permission changes, bounded retention, and cache-hit audit records. For this project, that means:

- no client-controlled cache namespace;
- no cache hit before the normal product authorization boundary has succeeded;
- no cross-patient, cross-source, cross-deployment, or cross-authorization-scope reuse;
- no stale-on-error fallback for a product clinical answer;
- bounded in-memory retention by default, with no patient ledger written to disk;
- the same provenance and audit metadata on a hit as on a fresh fetch.

The current med-agent-hub endpoint does not derive an end-user authorization scope. ChartSearchAI
authorizes the patient before relaying, while the Querystore adapter uses one configured service
account. A shared or remotely exposed hub therefore needs a trusted caller/authentication contract
before permission-scoped caching can be generalized. A local loopback sidecar may use a
deployment-and-service-principal scope, but must not pretend that this is per-user authorization.

### Prompt-prefix reuse

llama.cpp prompt caching compares a new prompt with prior cache state and reuses only the common token
prefix. Its response exposes `cache_n` for reused prompt tokens and `prompt_n`/`prompt_ms` for newly
processed prompt tokens. OpenAI's prompt-caching guidance states the same core rule: cache hits require
an exact prefix, so stable instructions and context belong before variable content. vLLM's automatic
prefix cache similarly hashes prefix blocks and evicts unused blocks with an LRU-like policy.

This explains the current same-chart behavior. A full under-budget chart is stable and can be reused;
an oversized chart is selected and ordered using the question, so the early chart prefix changes.
The future prompt shape should preserve a deterministic patient-core prefix, then append
question-specific supplemental records and the current question. The core may contain mandatory
safety evidence and a deterministic recent-record slice, but its contents must be evaluated rather
than chosen to fit one benchmark.

### Model residency

llama.cpp router mode can cap simultaneously loaded models with `--models-max`. An idle sleep unloads
both model memory and KV cache. Model residency is therefore a separate source of latency from prompt
processing, but it was not a confound in the recorded E2B/E4B comparison: the router allowed four
resident models and reported both small models loaded. Fresh local product starts should allow at
least the two models declared by the mixed small-model profile. Larger profiles still require a
deterministic free-memory preflight and may need explicit eviction.

A fair writer-speed comparison must still separate answer-only model generation from the full checked
profile and record model load/unload events. The default must remain the simplest profile that is both
fast and clinically usable.

## Planned Work

### C0: Instrument before optimizing

Add trace fields for:

- source fetch, pagination, normalization, and ledger-render durations;
- selector ranking duration, exact-token-count call count, and exact-token-count duration;
- ledger record count and hash, without raw patient text in metrics;
- model load/wait/unload events and the resident model set;
- per-model `cache_n`, `prompt_n`, `prompt_ms`, predicted tokens, and predicted time;
- cache layer, key class, hit/miss/revalidated/bypass outcome, age, validator, and eviction reason.

Checkpoint: reproduce the same two-turn scenario three times and account for context time as source
I/O, deterministic preparation, router prefill, model load, and generation. Do not implement a
clinical ledger cache until this breakdown is available.

### C1: Remove repeated deterministic computation — implemented

Hub `7bb9371` first corrected eligibility: mandatory, exact, bounded clinical-core, and meaningfully
overlapping evidence is eligible, while zero-relevance records are not admitted merely to fill the
window. Hub `dad07e6` then removes the sequential full-prompt recount. The selector ranks once,
tokenizes every eligible rendered record in one model-specific request, maps returned token pieces to
record byte ranges, greedily skips individually oversized records, and exact-counts each bounded
assembled candidate. A boundary-sensitive underestimated first candidate is checked alone and
excluded when it cannot fit. Mandatory overflow still fails closed.

The current exact 12-cell gate retains all 48 required sources while using 13,484-17,569 of the
20,480-token ceiling and selecting 35-84 records; all 3,182 exclusions are explicitly
`zero_relevance`, with no budget exclusion needed in that fixture set. The live router returned
separate `(6, 14)` costs for two records from one batched request. The focused selector/complete-ledger
suite passes 79 tests and the full hub suite passes 549 tests. Independent reviews found and drove
red-first fixes for demographic aliases, relevance-before-recency ordering, numeric and compact
duration collisions, explicit-identifier scoping, canonical-rendering recounts, and oversized-record
blocking. A final review worker did not return before timeout; that missing confirmation is not
represented as a clean independent pass.

### C2: Add a source-neutral evidence cache seam

Add a bounded asynchronous cache around `ContextSource` results, not inside Querystore-specific
business logic. The initial value is the normalized immutable `EvidenceLedger` plus provenance. The
key includes:

- source adapter and source configuration revision;
- patient identifier;
- trusted deployment/service-principal or authenticated authorization-scope fingerprint;
- serializer/ledger format revision;
- source validator when available.

Use single-flight request coalescing so concurrent identical misses make one source request. Keep the
default store in process memory, bounded by entry count and bytes, with configurable TTL and explicit
purge. Do not cache final answers, history, question-conditioned `ContextView`, reference-date
classification, gate results, or grounding verdicts.

Checkpoint: cache on/off produces the same ledger hash, temporal facts, references, answer-gate input,
and final product envelope apart from trace/timing fields. Patient, source, and authorization-scope
isolation tests must fail red before implementation. A source failure after expiry returns an explicit
source error rather than stale clinical data.

### C3: Add validator-based Querystore revalidation

Design a patient-chart validator in Querystore, preferably an HTTP `ETag` backed by a cheap
patient-projection revision rather than hashing and materializing the full chart on every validation.
Support conditional full-chart reads and `304 Not Modified`. Include the validator in every page and
reject a paged read if the validator changes mid-pagination, so a ledger cannot mix chart versions.

Keep the hub source contract generic: adapters may return `value + validator + fetched_at` and may
implement conditional refresh. Sources without validators either use an explicitly configured short
freshness interval or bypass reuse. Querystore remains one optional source, not a hub dependency.

Checkpoint: a repeated unchanged turn performs a conditional validation without re-transferring the
chart; a clinical write changes the validator and the next turn uses the new record; permission or
source-configuration changes cannot reuse the old entry.

### C4: Improve exact-prefix reuse

Record current prefix-hit behavior before changing prompt order. For oversized charts, prototype a
stable, deterministic patient-core prefix followed by question-specific supplemental evidence. Keep
source IDs stable across both sections and compute temporal facts/gates from the complete ledger.
Compare this shape with the current selector across under-budget, oversized, old-but-relevant,
temporal, medication-safety, and multi-turn fixtures.

Checkpoint: prefix reuse rises on repeated same-patient turns, required-source recall and citation
resolution remain unchanged, and no judged or deterministic quality regression is hidden by latency
improvement. If the stable core cannot meet those conditions, retain the current prompt shape.

### C5: Evaluate model residency and role-specific reasoning

Run answer-only E2B/E4B controls before full profiles, with both small models resident. Record load
time, prompt-cache retention, first-Answer latency, tail latency, output quality, and memory high-water
mark. For larger mixed-role profiles, compare resident sets only after memory preflight. Separately
test bounded reasoning only for review, In-Depth, grounding, or specialist roles; the fast Answer
remains the no-reasoning control.

Checkpoint: any residency/default change must improve a distribution of relative warm measurements
without increasing malformed output, temporal/citation failures, unsafe edits, or memory-pressure
failures. Hidden reasoning is never displayed or persisted as clinical evidence.

## Acceptance Criteria

| Area | Pass condition |
|---|---|
| Correctness | Cache on/off yields the same normalized ledger hash and the same clinical product output apart from cache/timing metadata on deterministic fixtures. |
| Freshness | An upstream chart change invalidates or revalidates before the next product answer; no expired entry is served when the source cannot be checked. |
| Isolation | Patient, source, deployment, and trusted authorization scopes cannot collide; permission changes force reauthorization and cache invalidation/bypass. |
| Temporal safety | Temporal facts and every Answer/In-Depth gate still run per turn from the complete current ledger and current anchor. |
| Citation integrity | Stable source IDs and final references are identical on cache hits and misses; prior-turn citation markers cannot bind to a cached current-turn record. |
| Prompt reuse | Hub traces report actual llama.cpp `cache_n` and `prompt_n`; improvements are based on measured common-prefix reuse, not warmup completion alone. |
| Model residency | Model load/eviction is visible in traces; mixed-role experiments disclose resident-model limits and memory preflight outcomes. |
| Security | No raw patient chart or answer is written to disk by default; hit/miss logs contain identifiers/hashes and policy state, not clinical text. |
| Failure behavior | Cache corruption, validator mismatch, authorization uncertainty, and mandatory-context overflow fail closed and remain inspectable. |
| Performance evidence | Same-machine cache-on/off repetitions report medians and spread for source, selection, prefill, generation, Answer-visible, and full-tail durations; no absolute local threshold is claimed. |
| Generality | The cache wrapper passes contract tests with Querystore, inline context, and a mock alternate source; the hub does not import or require Querystore to start. |
| Documentation | Hub, Querystore, local setup, trace schema, and roadmap status document cache scope, freshness, invalidation, privacy, and bypass behavior consistently. |

## Explicit Non-Goals

- caching generated clinical answers;
- treating demo/test warmup as a general product performance improvement;
- restoring the deleted frozen ChartSearchAI session chart snapshot;
- browser-side caching of patient charts or model responses;
- serving stale patient data when a source is unavailable;
- learned retrieval or learned cache admission in this iteration;
- assuming a warmup request proves a reusable prefix without `cache_n`/`prompt_n` evidence;
- increasing residency beyond the two known-small product models without deterministic memory checks.

## References

| Confidence | Source | Relevance |
|---|---|---|
| High | [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html) | Normative freshness, validation, authenticated-response, invalidation, and cache-security semantics. |
| High | [HL7 FHIR R4 HTTP](https://www.hl7.org/fhir/R4/http.html) | Clinical-resource conditional reads using ETag, Last-Modified, If-None-Match, and If-Modified-Since. |
| High | [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | Prompt-cache controls, router resident-model cap, model sleep/unload behavior, and `cache_n`/`prompt_n` timing fields. |
| High | [vLLM Automatic Prefix Caching](https://docs.vllm.ai/en/v0.8.5/design/automatic_prefix_caching.html) | Prefix-block hashing and cache eviction design. |
| High | [SGLang paper](https://papers.nips.cc/paper_files/paper/2024/file/724be4472168f31ba1c9ac630f15dec8-Paper-Conference.pdf) | Peer-reviewed prefix matching and cache-aware scheduling with RadixAttention. |
| High | [OpenAI prompt caching](https://openai.com/index/api-prompt-caching/) | Exact common-prefix reuse and cached-token observability. |
| High | [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html#section-11-caching-risks) | Permission-scoped cache isolation, invalidation, bounded retention, and audit requirements. |
