# Plan: file-based LLM config overrides (feature 007)

Backend change on the chartsearchai module (Java) + small harness wiring. Branch on the `pmanko` fork; PR → `openmrs:main`; consolidate into `harness-integration`.

> **Superseded by the hub-relay architecture (2026-07):** chartsearchai no longer owns the Java LLM
> engines or prompt assembly described below. Treat this plan as historical context only; implement prompt
> and parameter iteration in med-agent-hub profiles/levels.

## Architectural decisions

### D1 — Zero-dep JSON config + separate prompt `.md`
Config is a JSON file (parsed with the already-present Jackson — no new build dep) holding `params` and a `systemPromptFile` pointer; the prompt lives in a plain `.md` you rewrite without JSON escaping. Rejected: single YAML (nicer but needs `jackson-dataformat-yaml`/snakeyaml — a dependency we don't want on the upstream PR) and single-JSON-with-inline-prompt (escaped `\n` editing pain). Inline `systemPrompt` is still accepted for the short case.

### D2 — Call-time read, mtime-cached
The config + prompt are read lazily and cached keyed by `(path, lastModified)`. Editing either file changes the mtime → next request reloads; unchanged → served from cache (no per-call parse). This is what makes the iteration loop "edit → ask again," no restart — mirroring how the GP-based config is already read fresh per call.

### D3 — Layering, defaults win when absent
System prompt precedence: **file (`systemPromptFile` › inline `systemPrompt`) → GP `chartsearchai.llm.systemPrompt` → `DEFAULT_SYSTEM_PROMPT`**. Params: **file `params` → current hardcoded defaults**. No GP + no file ⇒ today's behavior, byte-identical. This satisfies "works by default with zero additions."

### D4 — Fail-safe
A missing/unreadable/malformed config or referenced prompt file logs WARN and falls back to the next layer. A bad config must never break a chat turn — the worst case degrades to defaults.

### D5 — Params flow into both engines
`temperature`/`max_tokens` move from hardcoded literals in `RemoteLlmEngine.buildRequestBody` + `LocalLlmEngine.buildRequestBody` to values sourced from `LlmConfig.params` (falling back to the current constants). Extra keys (`topP`, `topK`, `seed`, …) are written through to the request JSON generically. The existing Claude `top_k:1` special-case remains unless the file overrides it.

### D6 — Path via GP (+ harness mount)
The config location is GP `chartsearchai.llm.configPath` (absolute). In the harness, an example config + prompt live under `artifacts/openmrs/chartsearchai/`, mounted into the backend container; `chartsearch-configure.sh` sets the GP. Operator edits the host file → live next request. Local-engine and remote-engine both honor it.

## File-level changes

**chartsearchai module (fork branch):**
- `api/.../ChartSearchAiConstants.java` — add `GP_LLM_CONFIG_PATH = "chartsearchai.llm.configPath"` (append-only).
- `api/.../api/impl/LlmConfig.java` (new) — loader: read GP path → parse JSON (Jackson) → resolve `systemPromptFile` relative to the JSON dir → expose `getSystemPrompt()` (nullable) + `getParams()` (Map). `(path,mtime)` cache. All failures → WARN + null/empty so callers fall back.
- `api/.../api/impl/LlmProvider.java` — `getSystemPrompt()` gains the file layer ahead of the GP. **Hot file (being live-edited) — re-read before editing.**
- `api/.../api/impl/RemoteLlmEngine.java` + `LocalLlmEngine.java` — `buildRequestBody` sources params from `LlmConfig`; generic passthrough. **Hot files — re-read before editing.**
- `api/.../impl/LlmConfigTest.java` (new) — loader: parse, prompt-file resolution, mtime reload, layering precedence, fail-safe on malformed/missing. Plus assert engines emit the configured params (via the existing `buildRequestBody` test-seams).

**harness:**
- `artifacts/openmrs/chartsearchai/chartsearchai-llm.example.json` + `chartsearchai-system-prompt.example.md` (committed examples).
- `compose/openmrs-2.8-refapp.yml` — mount `artifacts/openmrs/chartsearchai/` into the backend (read-write so host edits land live).
- `scripts/chartsearch-configure.sh` — set `chartsearchai.llm.configPath` when a config file is present.
- `.env.chartsearch.example` — document the path + the iteration loop.

## Sequencing note (live-edit coordination)

`getSystemPrompt` and `buildRequestBody` are in files under active hand-editing (the `refreshChartSnapshot` / `DEFAULT_SYSTEM_PROMPT` work). Implementation order: land the **collision-free** parts first — `LlmConfig` (new), the new constant (append-only), `LlmConfigTest`, the example files, the harness mount — then apply the three small hot-file hooks last, re-reading current state immediately before each edit to avoid clobbering uncommitted work.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Editing hot files (`LlmProvider`, `RemoteLlmEngine`) collides with concurrent hand-edits | Hooks applied last, re-read each file immediately before editing; keep hooks minimal |
| R2 | Re-reading the file per call adds latency | mtime cache (D2) — parse only on change |
| R3 | A param the backend shouldn't forward (e.g. `stream`) slips through passthrough | allowlist/denylist the passthrough keys; `stream`/`messages`/`model`/`response_format` are owned by the engine, not the config |
| R4 | Mounted file path differs local vs cloud | path is a GP, set per-environment by `chartsearch-configure.sh`; example uses a container-absolute path |
| R5 | Upstream reviewer dislikes a file-config feature in the module | the feature is opt-in + dependency-free + defaults-unchanged; if rejected upstream it still lives on the fork for the harness |
