# Feature 005: med-agent-hub bridge — a chartsearchai-selectable in-process agent team

**Status**: shipped (on branch `004-chartsearchai-adapter`; this spec is retro-authored to make the
numbering honest — the code landed before the spec). **Started**: 2026-05-27.

> Retro-note: feature-005 work shipped under the `004` branch/PR rather than a separate `005` branch (the
> stale `005-med-agent-hub-bridge` branch was scaffold-only and is abandoned). This spec records what was
> built, grounded in the planning docs below; it is not a greenfield plan.

**Detailed design / provenance:**
`specs/artifacts/planning/med-agent-hub-bridge-delta.md` (the as-built delta vs the A2A reboot),
`specs/artifacts/planning/archive/med-agent-team-poc-roadmap.md` (§2–§5, the settled team + KB scope; archived snapshot),
`specs/artifacts/planning/agentic-orchestration-a2a-research.md` (the in-process-ReAct decision),
`specs/artifacts/planning/react-team-orchestration-design.md` (the prompt-driven KB→clinical→compose flow).

## Goal

Stand up `pmanko/med-agent-hub` as a harness submodule that chartsearchai can select as just-another
OpenAI-compat backend, but which internally runs an in-process **agent team** (an orchestrator + a clinical
expert + a knowledge-base tool) and returns chartsearchai's strict `{answer, citations, blocks}` envelope.
No chartsearchai code change is required to *use* it (it's a peer of LM Studio at the endpoint boundary);
the value is the team's orchestration + KB grounding.

## What shipped

- **OpenAI-compat bridge** (`server/openai_compat.py`): `POST /v1/chat/completions` (sync + buffer-then-emit
  SSE) and `GET /v1/models` (advertises the single `med-agent-team` id). Forwards chartsearchai's
  `response_format` (the `chart_answer` json_schema), `temperature`, `max_tokens`, `stream`.
- **In-process ReAct team** (`server/team.py`) — NOT A2A: one orchestrator/synthesizer model
  (`google/gemma-4-e4b`) runs a short tool loop over two typed tools — `kb_search` (FTS5/BM25 KB) and
  `medical_expert` (`medgemma-1.5-4b-it`) — then a final synthesis call bound to the envelope schema. The
  tool loop runs plain (no response_format); only the final synthesis is schema-constrained (sub-7B
  reliability). Guaranteed-valid fallback envelope on any failure.
- **Prompt-driven orchestration** (per `react-team-orchestration-design.md`): the orchestrator is strongly
  *suggested* (not hardcoded) to call `kb_search` first for guideline/dose/threshold questions, then
  `medical_expert` (which reasons GIVEN the retrieved KB context — threaded in code), then compose. Strict
  citation carve-out: integer citations are chart-records-only; KB/expert facts are attributed inline.
- **Tier-1 KB** (`server/kb.py` + `kb_data/corpus.jsonl`): openly-licensed clinical seed (WHO general +
  HIV/ART, OCL/CIEL + OpenMRS data-model context); SQLite FTS5/BM25 + keyword fallback; K=3; abstains on no
  match. (Full KB service = F009.)
- **Harness integration**: submodule at `targets/med-agent-hub/`, compose service (internal-only), Makefile
  targets (`med-agent-hub-build/up/logs/restart/test`), container at `:8080`, model warmup.
- **Picker + per-request selection on chartsearchai** (the consumer side): the endpoint registry GP +
  sectioned Carbon picker, and a **per-request backend override** (`RequestLlmOverride` in `POST /chat`) so a
  caller — the picker or the 006 harness — selects a backend for one request without mutating the
  config-controlled global default.
- **Model consolidation**: the team orchestrator and the gemma single-model comparison backend both use
  `google/gemma-4-e4b` (the tool-capable build); LM Studio's global default context set to model-max so JIT
  loads avoid the 4096 overflow.

## Contract (grounded in chartsearchai's real code)

chartsearchai sends `response_format: json_schema` (strict `chart_answer`: `{answer:string, citations:int[],
blocks:Block[]}`), `temperature:0.0`, `max_tokens:4096`, `stream`. The bridge FORWARDS these; constrained
decoding on the final synthesis enforces the envelope.

## Relationship to other features

- **006-validation-harness-mvp**: drives backends through chartsearchai's REST API (per-request override) and
  compares the `med-agent-team` endpoint against single-model backends, KB-on/off.
- **009 (clinical-kb-brief)**: the Tier-1 KB here is a demo-grade precursor; the full hybrid-retrieval,
  reranked, contextualized, REST+MCP service is F009.

## Out of scope (deferred seams)

A2A agent-cards/executors, the MCP protocol surface, the full KB service (F009), Spark/FHIR tools, a `/v1/agents`
skill surface, deterministic control-flow hardening, and output safety-guards — all measurement-driven per the
synced planning docs.
