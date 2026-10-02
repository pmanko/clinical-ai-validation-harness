# Chart-context and inference-cache experiments

The harness owns measurement and interpretation. [Hub source/cache behavior](https://github.com/pmanko/med-agent-hub/blob/main/README.md#querystore-context-and-freshness),
[QueryStore validators](https://github.com/pmanko/openmrs-module-querystore/blob/main/docs/rest-api.md)
and [OpenClinAI scheduling](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#5-track-a-openmrs-contribution-delivery)
have separate owners. This protocol does not authorize cache implementation,
profile changes, router management or a new source contract.

## Research question and controls

Separate model residency, prompt-prefix reuse, source/ledger retrieval and
deterministic preparation costs. Compare cache-on/off or cold/warm cases on the
same machine, source, model and declared configuration. Demo warmup is a control,
not proof of a general product improvement. Record actual backend reused/input
tokens and prompt timing; loading weights alone cannot establish prefix reuse.

Do not impose an absolute latency threshold. Report medians and spread across
reviewed repetitions, separating source I/O, normalization, selection, exact
counting, prefill, model load, generation, first visible Answer and full tail.
Collection is deliberately initiated, not a recurring product acceptance gate.

## Retained research checkpoints

| ID | Owner and evidence |
| --- | --- |
| C0 | Harness measurement: source/pagination/normalization/render timing, ranking and token-count calls, ledger identity/count, residency events, prompt tokens/timing and cache hit/revalidation/bypass/eviction state. Keep clinical text out of operating metrics. |
| C1 | Hub deterministic fitting is implemented; retain its [dated measurements][history], including the invalid contended 12B timing comparison. Measure remaining sub-stage costs before claiming another optimization. |
| C2 | Hub owns any generic cache extension, isolation, bounds and purge. Experiment evidence compares deterministic ledger/check/reference outcomes on hit/miss, with temporal facts recomputed. |
| C3 | QueryStore owns the implemented snapshot/ETag contract. Exercise unchanged conditional reads, chart change, mixed pages, source failure and permission/configuration changes through actual interfaces; do not redesign validators in the harness. |
| C4 | Deferred prefix research: compare actual reuse across under-budget, oversized, old-but-relevant, temporal, safety and multi-turn cases. A proposed stable core must preserve required-source recall, citation resolution and deterministic/reader quality. Keep the existing prompt shape if it fails. |
| C5 | Residency and role reasoning: compare answer-only E2B/E4B controls before checked profiles. Record actual resident sets, load/eviction, first/tail latency, quality and memory high-water marks. Review role-specific reasoning separately; the fast Answer control remains without reasoning. |

A residency/default change requires relative measurements and product review.
The caller sets memory-safe residency; this experiment does not override the
umbrella's selected CPU-host capacity. Hidden model reasoning is not clinical
evidence. Cache corruption, authorization uncertainty, incomplete context and
source failure remain explicit observations, never a faster successful answer.

For deterministic fixtures, compare ledger hashes, temporal facts, current source
identities, references and gate inputs on cache hit/miss. Do not require identical
stochastic prose. Real product claims require real interfaces; alternate-source
test doubles establish only the tested source contract. A controlled benchmark
must disclose missing metadata, competing work and changed resident models.

## Historical evidence and current limits

The [July record][history] contains selection/fitting measurements and earlier
cache proposals. Its claims that QueryStore has no validators or the Hub fetches
every page unconditionally are obsolete. Its proposed TTL-only source reuse and
mandatory two-model residency do not override current product freshness or host
capacity. Full-chart prefix work remains deferred under OpenMRS G13.

[history]: https://github.com/pmanko/clinical-ai-validation-harness/blob/9b5b87ef67397fe7705b37467b98d3550c8d0e47/specs/artifacts/planning/chart-context-cache-research-plan-2026-07-15.md

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
