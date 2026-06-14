# Development Roadmap — operating plan

Operational companion to the visual roadmap in
[`specs/roadmap.canvas.tsx`](../specs/roadmap.canvas.tsx). The canvas carries the
milestone/feature dependency model and the in-flight lane cards; this doc carries
the **operating detail** — branch/worktree mechanics, per-lane merge gates,
verification, and the remediation record — so the program plan lives in the repo,
not in an ephemeral working note.

## North-star goals

1. **Grounded validation evidence** — real systems, realistic data (the 5,284-patient corpus), every claim traceable to specific records.
2. **Single-model vs. agent-team comparison** via judged runs.
3. **Reusable harness** — the control plane (compose, manifests, provenance, validate/judge/report pipeline) generalizes to new targets; Catalyst/OpenELIS is the proof.
4. **Demo platform** — a working, stable, human- and LLM-readable showcase of local-first clinical AI with cloud parity.

## Current state (as of 2026-06-12)

Foundation remediation ("Part A") is **complete**; `main` is the single trunk and merges are **squash-only**.

**Remediation record:**
- **R1 (PR #23):** caught `main` up to the de-facto trunk (validator pipeline, demo-data date-transplant, dashboard/reports). The DB-coupled SQLMesh conformance tests were converted to the in-process `render_query_or_raise()` path so they run in CI without a warehouse; a masked diff-cover gap was closed by deleting dead confidence helpers and adding end-to-end confidence-inversion tests.
- **R2 (PR #24):** defused the `gen_modules` date-transplant landmine — the generator now introspects each carry-forward table and emits `@shift_date(...)` for date columns, reproducing all 16 committed models byte-identically (`harness/transform/gen_modules.py`).
- **R3:** branch/stash sweep; the chartsearchai upstream reconcile turned out to be ~27 commits behind upstream with engine-file conflicts → deferred to **L4**.
- **R4:** local picker verified serving all three model sections (LM Studio, llama-server, med-agent-hub).

**med-agent-hub restructure (PRs #9, #25):** first CI (`hub-ci.yml`: `unit-and-contract` over the `/v1` OpenAI-compat contract + `docker-build`), dead A2A/fake-MCP tests removed, README aligned to the shipped architecture (declarative `server/levels.yaml`, validator + per-section confidence, temporal grounding, trace artifact). The `harness-integration` buffer branch was retired — the hub is our own repo, so it pins `main` and the harness `.gitmodules` tracks it directly.

**Submodule branch models differ by repo:** chartsearchai / chartsearchai-esm are forks → feature branch → upstream PR → consolidate into `harness-integration` → harness pin bump. med-agent-hub is our own repo → feature branch → PR → `hub-ci` green → `main` → harness pin bump (no buffer branch).

## Development lanes

Each lane = one feature branch + one worktree + one PR, branched from the current `main` of the repo it touches.

### L1 — med-agent-hub MCP-ification
Replace the hub's hand-rolled tool dispatch and homegrown fake-"MCP" layer with one valid FastMCP server mounted at `/mcp`; `kb_search` becomes a real MCP tool, `medical_expert` stays an in-process role; delete the legacy A2A/fake-MCP modules. The `/v1` contract test (`tests/test_bridge.py`) must stay green throughout.
- **Lane:** hub branch `feat/real-mcp-tools` off hub `main`; worktree `~/code/hub-wt-mcp`.
- **Pin-bump gate (hub-boundary smoke):** after merge, rebuild the container and run the README `/v1` curl with real local models + assert a `-validated` level returns the confidence block and `trace.jsonl` grows — then bump the harness pin. (The integrated chartsearchai→hub smoke belongs to L4.)

### L2 — Reports & human feedback
Evolve feature 006's report layer: scores as percentages, per-scenario rubric judgement inline, an "AI team" explainer, "Unsafe Answers" links, and a two-part split (machine deep-dive vs. a human-feedback view with ranking/annotation); redesign the `feedback.jsonl` export. **Parity is structural:** extract the confidence-inversion + formatting rules into one shared module imported by both `harness/validate/report.py` and `scripts/validate-dashboard.py`, plus parity tests rendering one fixture through both.
- **Lane:** harness branch `feat/report-human-feedback`; worktree `~/code/harness-wt-report`.

### L3 — Validation spine: specs/006 as-built + close M2-F.1
Bring `specs/006-validation-harness-mvp` to as-built (judge.jsonl + scoring skill, validator confidence, run-index, live dashboard all postdate it) and close **M2-F.1 / SC-015**: produce the four `chartsearchai-live/` artifacts against the running stack and verify every citation resolves to a translated demo record.
- **Lane:** harness branch `docs/006-validation-spine-asbuilt`; worktree `~/code/harness-wt-spine`. POSTs to the live stack served from the main checkout.

### L4 — chartsearchai/esm: upstream split + reconcile + integrated smoke
Three coupled jobs on the fork repos: continue the accumulation PR split upstream; perform the deferred reconcile of `harness-integration` (~27 behind upstream, conflicts in `RemoteLlmEngine.java` + three LLM-engine tests — split first, then reconcile to shrink the conflict surface); and build the integrated `make smoke-chat` chat-path gate (1-scenario, 2-backend `validate-run` through chartsearchai's real `/chat`), which then gates chartsearchai/esm pin bumps.

### L5 — Catalyst FHIR sidecar (M10), ground-up design
Speckit design from the existing brief + canvas mockup: the sidecar's FHIR surface over OpenELIS-Global-2, the harness adapter entrypoint (reusing the 004 interface), and the first judged lab-AI scenario. Design-first. Requires the OpenELIS-Global-2 sibling checkout.

### Parked
- UCD / real-user requirements gathering (until real reviewers exist; questions derive from the corpus). M4/M5 evaluation depth beyond M2-F.1; M8 querystore (blocked on upstream runtime bugs); M6 safety red-team; M7 governance.
- **Docs-site IA remediation** — non-technical landscape → smooth technical drill-down (separate plan).

## Launch sequence

L1/L2/L3 run in parallel, each in its own git worktree and session:

```bash
# from the harness checkout root
git -C targets/med-agent-hub worktree add ~/code/hub-wt-mcp -b feat/real-mcp-tools origin/main
git worktree add ~/code/harness-wt-report -b feat/report-human-feedback main && (cd ~/code/harness-wt-report && uv sync --all-extras)
git worktree add ~/code/harness-wt-spine -b docs/006-validation-spine-asbuilt main && (cd ~/code/harness-wt-spine && uv sync --all-extras)
```

Harness worktrees don't need `git submodule update` (pytest ignores `targets/`), and the live stack keeps running from the main checkout. File sets are disjoint, so lanes merge independently. The only cross-lane edge: L1's harness pin bump waits on the hub PR merging **and** the hub-boundary smoke passing.

## Verification

- **Before opening a lane:** harness `main` clean and pushed; `git submodule status` shows no drift; pins reachable on their tracked branches.
- **Per lane:** one squash PR with green CI (harness: pytest + diff-cover ≥90% on changed lines; hub: `hub-ci`). Pin bumps run their gate (L1 hub-boundary smoke; chartsearchai/esm the `make smoke-chat` gate once L4 builds it).
- **L1:** `tests/test_bridge.py` green at every commit; hub-boundary smoke before the pin bump.
- **L3:** the four M2-F.1 artifacts exist under `artifacts/<run>/chartsearchai-live/` and the citation-resolution check passes.
