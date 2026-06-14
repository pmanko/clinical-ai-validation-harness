# L4 — chartsearchai/esm: upstream split + reconcile + integrated smoke

**Status**: Queued (later lane) — no worktree yet.
**Repos**: the `pmanko` forks `openmrs-module-chartsearchai` (Java) + `openmrs-esm-chartsearchai` (React). Branch model: feature branch → upstream PR → consolidate into `harness-integration` → harness pin bump.
**Branch / worktree**: per-PR branches on the forks → upstream PRs; harness pin bump only when `harness-integration` moves. (No standing worktree until kicked off.)
**Brief**: none — upstream-PR mechanics. **Index**: [`dev-roadmap.md`](dev-roadmap.md)

## What & why
Three coupled jobs on the fork repos:
1. **Continue the accumulation PR split** upstream (PRs A–E by hunk; the fork is ~28 ahead of `openmrs/main`).
2. **The deferred R3 reconcile**: `harness-integration` is behind `upstream/main` (clause-scoped citation grounding, thinking-stream SSE, reasoning field, standalone bundles…) with verified content conflicts in `api/.../RemoteLlmEngine.java`, `LlmProviderTest.java`, `LocalLlmEngineTest.java`, `RemoteLlmEngineTest.java`. **Recommended order: split first, then reconcile** — rebasing the fork's slices onto `upstream/main` shrinks the conflict surface incrementally instead of one big conflicted merge.
3. **The integrated chat-path smoke (S1, tabled from launch)**: build `make smoke-chat` wrapping the existing `harness-cli validate run` with a checked-in **1-scenario, 2-backend** set through chartsearchai's real `/chat` on `:8088`. It gets built HERE, where the chartsearchai pipeline is what's changing, and then becomes the standing local gate for chartsearchai/esm pin bumps.

## Scope
**In:** the three jobs above. **Out:** the hub-side MCP work (L1); harness report/spine work (L2/L3).

## Merge / pin-bump gate
- Upstream PRs follow the openmrs review process.
- Harness pin bump (when `harness-integration` moves): runs `make smoke-chat` once L4 builds it (until then, manual chat-UI check). This is the integrated chartsearchai→hub path smoke that L1 deliberately deferred.

## Kickoff prompt (verbatim)
> Resume the chartsearchai/esm upstream PR split: list the A–E PR statuses on the upstream openmrs
> repos, rebase outstanding ones onto `upstream/main`, open the next PR in the sequence; then merge
> `upstream/main` into `harness-integration` (the known conflicts are in `RemoteLlmEngine.java` + 3
> LLM-engine tests), push. Build the `make smoke-chat` integrated smoke (1-scenario, 2-backend
> `validate-run` set) per this dossier, run it green against the local stack, and bump the harness pin
> via a small PR.
