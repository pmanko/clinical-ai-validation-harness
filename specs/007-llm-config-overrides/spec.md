# Feature 007: File-based LLM config overrides (system prompt + params)

**Roadmap slot**: enabler for rapid validation/iteration (feeds 006 validation-harness); backend change on the chartsearchai module.
**Scope of this PR**: make the chartsearchai LLM **system prompt** and **request params** overridable via an optional, operator-editable file pair (a JSON config + a separate prompt `.md`), read at call-time, layered over today's defaults — working unchanged when absent.
**Status**: planned | **Started**: 2026-05-28
**Branch**: chartsearchai fork feature branch (per the paired-PR model: branch on `pmanko`, PR → `openmrs:main` + consolidate into `harness-integration`).

## Why

For validation/iteration we need to rewrite the system prompt and tweak inference params (temperature, max_tokens, …) **fast** — edit a clear file, ask again, no rebuild/restart. Today (grounded in the code):
- System prompt: `LlmProvider.getSystemPrompt()` reads GP `chartsearchai.llm.systemPrompt`, falls back to `LlmProvider.DEFAULT_SYSTEM_PROMPT`. Overridable, but only as a **DB string blob** (admin UI / SQL) — not a file you jump into.
- Params: `temperature` (0.0), `max_tokens` (`DEFAULT_LLM_MAX_OUTPUT_TOKENS` = 4096), `top_k:1` (Claude) are **hardcoded** in `RemoteLlmEngine.buildRequestBody` and `LocalLlmEngine.buildRequestBody`. Not configurable at all.
- Jackson (JSON) is already on the classpath module-wide; no YAML parser is.

Precedent: med-agent-hub uses one YAML per agent (`system_prompt: |` block + `model` + params). We adopt the *spirit* (a clear editable config) but a **zero-new-dependency** shape (JSON + a plain prompt file) so the upstream module PR carries no new build dep and multi-line prompt editing stays escaping-free.

## Success criteria

- **SC-007.1** (default = zero additions): with no config path set and no file present, behavior is byte-identical to today — `DEFAULT_SYSTEM_PROMPT` (or the GP), `temperature 0.0`, `max_tokens 4096`. No new operator setup required.
- **SC-007.2** (live prompt edits): with `chartsearchai.llm.configPath` pointing at a JSON whose `systemPromptFile` references a `.md`, the LLM uses that prompt; editing the `.md` and re-asking uses the new text **with no rebuild or backend restart** (call-time read, mtime-cached).
- **SC-007.3** (params override + passthrough): a `params` block overrides the hardcoded `temperature`/`maxTokens` for **both** remote and local engines, and arbitrary OpenAI-compatible keys (`topP`, `topK`, `seed`, …) pass through to the request body.
- **SC-007.4** (layering): precedence is documented and tested — file `systemPrompt`/`systemPromptFile` → GP `chartsearchai.llm.systemPrompt` → `DEFAULT_SYSTEM_PROMPT`.
- **SC-007.5** (fail-safe): a missing/unreadable/malformed config or prompt file logs a warning and falls back to defaults — it **never breaks a chat turn**.
- **SC-007.6** (harness iteration loop): the harness ships an example config + prompt under `artifacts/openmrs/chartsearchai/`, mounts it into the backend container, and `chartsearch-configure.sh` sets the path GP — so an operator edits the file on the host and the change is live on the next request.

## Functional requirements

- **FR-007.1**: New GP `chartsearchai.llm.configPath` (absolute path to the JSON config). Unset → no file layer.
- **FR-007.2**: Config JSON shape:
  ```jsonc
  {
    "systemPrompt": "...",                       // optional, inline
    "systemPromptFile": "chartsearchai-system-prompt.md",  // optional, relative to the JSON's dir; wins over inline
    "params": { "temperature": 0.0, "maxTokens": 4096, "topP": 0.9, "seed": 42 }
  }
  ```
- **FR-007.3**: A new `LlmConfig` loader (Jackson-based) MUST cache the parsed config keyed by `(path, lastModified)` for both the JSON and the referenced prompt file, so edits are picked up without re-parsing on every call and without a restart.
- **FR-007.4**: `LlmProvider.getSystemPrompt()` MUST consult the file layer first, then the existing GP, then `DEFAULT_SYSTEM_PROMPT`.
- **FR-007.5**: `RemoteLlmEngine.buildRequestBody` and `LocalLlmEngine.buildRequestBody` MUST source `temperature`/`max_tokens` from `LlmConfig.params` when present (else current defaults) and pass through any additional params. The Claude `top_k:1` special-case stays unless overridden by the file.
- **FR-007.6**: No new build dependency — JSON via the already-present Jackson. (A YAML variant is explicitly rejected to keep the upstream PR dependency-free.)
- **FR-007.7**: Loader failures are logged at WARN and fall back to defaults; they never propagate as a chat error.

## Out of scope

- YAML config format (rejected — would add a build dep; revisit only if upstream wants it).
- Per-session / per-request prompt or param overrides (this is a deployment-level config, not a runtime API field).
- A UI for editing the config (it's a file + optional admin GP for the path).
- Per-model or per-backend param profiles (one active config; the endpoint-registry picker in 005 already switches models).

## Verification

1. **Default**: unset the GP, remove the file → existing `LlmProviderTest`/curl smoke produces the same prompt + params (no regression).
2. **Prompt override (live)**: point the GP at a JSON+md, ask a question, confirm the new prompt is used; edit the `.md`, ask again, confirm the new text takes effect with no restart.
3. **Params**: set `temperature`/`maxTokens`/`topP` in the file; assert the outgoing request body (captured via the engine test-seam) carries them.
4. **Layering**: file vs GP vs default precedence asserted in a unit test.
5. **Fail-safe**: malformed JSON + missing prompt file → WARN logged, defaults used, chat still works.
6. **Harness loop**: `make chartsearch-configure` sets the path; editing the mounted file changes the next answer in the browser.
