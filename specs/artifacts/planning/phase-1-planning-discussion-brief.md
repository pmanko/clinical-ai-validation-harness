# Phase 1 planning discussion — briefing pack

Purpose: everything needed to run the Phase-1 planning discussion in one
sitting, without re-deriving it. Companion to
`specs/catalyst-program-roadmap.md` (the roadmap; holds the agenda and becomes
the record of decisions). This file is the **decision-support** material:
per agenda item, the facts already established, the options, a recommendation,
and what each answer unblocks.

Status: 2026-08-23. Program goals/order approved; the six decisions below are
what remain before P1 implementation is authorized.

---

## 1. Where things stand

| | State |
| --- | --- |
| Catalyst | `main @ 655b796` — WS7 train merged; both environments deploy from it |
| Harness | `#57`, `#51`, `#52`, `#54` merged; `#55 → #50` (demo media) still open |
| Feature 008 remediation | Closed (WS1–WS7) |
| Feature 008 D1e/M4 | In progress, inherited by **P3** — 15 active gates, contract unchanged |
| Phase 1 | Proposal; blocked only on the six decisions below |

## 2. Pointer map — where everything lives

**Planning / decisions**
- `specs/catalyst-program-roadmap.md` — the program (P1→P3), agenda, and the
  place decisions get recorded. Source of truth.
- `specs/artifacts/planning/what-the-writer-sees.html` — research + evidence +
  recon, self-contained; published at
  <https://claude.ai/code/artifact/e65204a5-7b0e-49fb-ac43-155f41c6cae2>.
  Read §01 (recon) and §02 (six practices with evidence) before the discussion.
- `specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md`
  — governs the remaining PR cleanup (Step 0).
- `specs/008-catalyst-query-workbench/remediation-roadmap.md` — WS1–WS7 log,
  including the WS7 entry and its 2026-08-23 correction.
- `specs/008-catalyst-query-workbench/tasks.md` — D1e/M4 gates that P3 inherits.

**Code the decisions touch** (catalyst repo, `main @ 655b796`)
- `catalyst-gateway/src/catalyst/request.py` — the entire request assembly
  (71 lines). CE2/CE3/CE4 all add bounded blocks here.
- `catalyst-gateway/src/catalyst/workbench.py::build_revision_context` — what
  accumulates today (initial + last 5 instructions, text only) and the
  omission-record discipline any new block should copy.
- `catalyst-gateway/src/catalyst/catalog.py::request_catalog` /
  `approved_view_names` — the writer's visible surface.
- `catalyst-gateway/src/catalyst/query_schemas.py` — the generation grammar;
  `status` is `{"const": "ready"}` (agenda item 2c).
- `catalyst-gateway/src/catalyst/service.py::_failure_summary`,
  `_unresolved_findings`, `_retained_attempt` — WS7 machinery CE3 extends.
- med-agent-hub `server/prompts/catalyst-query-generate.txt` — writer prompt.
- `catalyst-sources/openmrs-hiv/sql/001…002` + `catalog/openmrs-hiv-catalog.json`
  — the curated views, their column comments, and the approved-view declaration.

**Evidence substrate for CE0**
- Per-turn generation evidence:
  `GET /v1/catalyst/workbench/sessions/{s}/turns/{t}/generation-evidence` —
  exact hub request, per-attempt raw outputs, findings, digests, timings.
- ~16 recorded local sessions plus the demo-host set; session
  `c973eeba-9ce2-4000-8cb4-6ec9199e6d1c` is the canonical multi-turn arc.

---

## 3. The six decisions

### D1 · CE0 scenario corpus and run size

**Facts.** Replaying *the same instruction* against *the same profile at
temperature 0* produced four different terminal findings across runs:
`catalog.unknown_column`, `generation.patch_ambiguous`,
`generation.unchanged_candidate` (local) and `output.projection_mismatch`
(server). Latency: ~70–100 s/turn local, 2.5–6 min/turn on the demo host.
Every turn already stores a complete evidence bundle.

**Decision.** Which sessions form the canonical corpus, and how many live
repetitions constitute one measurement.

**Recommendation.** Four scenario classes — *answerable single-turn*,
*multi-turn arc* (seed from `c973eeba`), *ambiguous*, *unanswerable*. Start at
**5 live reps per scenario** and report distributions, not single runs; treat
regression mode (replay of recorded outputs through the deterministic
pipeline) as the CI gate and live mode as the on-demand experiment. At ~90 s a
turn, a 12-scenario × 5-rep live run is roughly 1.5 h wall-clock — acceptable
overnight, not per-PR.

**Unblocks.** Everything; no other lever can be judged without it.

### D2 · Catalog boundary (governance, not code)

**Facts.** `openmrs-hiv-catalog.json` declares exactly **4 approved views**;
the runtime catalog is that file plus discovered relations (**13**), and the
writer receives only the approved 4. The human editor sees all 13 — a
hand-written join to `public.patient_flat` validated `valid` with zero
findings and executed 100 rows. So the approved surface is enforced **on the
model but not on the human**, and the 4-view scope is a real declaration, not
an accident — but its consequence (no patient name exists in the writer's
world) was never a considered decision.

**Decision.** (a) Do generation and execution share one approved surface?
(b) Is human-authored SQL bound by it? (c) Does `patient_flat` — or names
promoted into a curated view — enter the writer's surface?

**Recommendation.** Keep a curated (narrower) generation surface — it is the
semantic-layer practice that the evidence supports — but make it *deliberate*:
record the reason in the data-source contract, and close the specific gap by
adding name fields to the curated patient dimension with real column comments,
rather than exposing raw flat tables. Decide (b) explicitly either way; today's
asymmetry is undocumented.

**Unblocks.** CE1 scope; also determines whether the turn-3 arc becomes a
*passing* scenario or stays an ambiguity test.

### D3 · Playbook entry shape

**Decision.** Free text, or typed (`fact | preference | constraint`)?

**Recommendation.** Free text plus provenance
(`{text, source: human|system, originTurnId, createdAt}`). Typing is a
hardening step once real entries show whether type changes delivery. ACE's
lesson is that entries must stay **itemized and verbatim** — never summarized,
never rewritten — which matters far more than typing.

**Unblocks.** CE2 storage shape; conversation mode later reads the same object.

### D4 · Pin affordances

**Decision.** Composer pin + one-click pin-from-failure only, or also
pin-from-successful-turn?

**Recommendation.** The first two. Pinning a *successful* turn is really the
verified-exemplar path (CE4) and should be measured as such rather than
blurred into guidance.

**Unblocks.** CE2 UI surface (one rail section + two entry points).

### D5 · Guidance token budget and eviction

**Facts.** The revision context is already capped with honest omission records
(≤5 follow-up instructions, ≤50 findings, ≤128 columns, never rows). Stable
prefix ordering matters for cache economics on the local router.

**Decision.** Cap size and eviction rule for the guidance block.

**Recommendation.** Same discipline as the existing caps: a fixed entry cap
(propose 20) + an omission record; evict oldest-first; **no summarization**
(brevity bias) and **no rewriting** (context collapse). Place the block after
the static prefix so caching is preserved.

**Unblocks.** CE2 delivery; the bloat-guard metric in D6.

### D6 · What "measured" means

**Decision.** Agreed numbers on the metric gates.

**Metrics available from the evidence bundles.** Execution accuracy vs golden
digest · first-attempt candidate rate · attempts-to-success · grounding-failure
rate (invented identifiers) · clarification precision/recall · tokens and
latency per turn.

**Recommendation — proposed gates** (numbers to be argued in the discussion):

| Lever | Ships if | Must not |
| --- | --- | --- |
| CE1 | grounding-failure rate falls on the ambiguous/unanswerable classes | reduce accuracy on answerable scenarios |
| CE2 | guided-retry success rises on "correction that should persist" | regress irrelevant-guidance scenarios (bloat guard: tokens + accuracy) |
| CE3 | retry success rises / attempts-to-success falls | increase first-attempt failures |
| CE4 | first-attempt accuracy rises where near-neighbour pairs exist | regress dissimilar questions (exemplar-copying guard) |

**Unblocks.** Every ship/no-ship call in P1.

---

## 4. After the discussion

1. Decisions recorded in `specs/catalyst-program-roadmap.md`; this brief stays
   as the rationale.
2. Three parallel tracks open as separate branches/worktrees — **A** CE0
   harness, **B** CE1 writer's world, **C** CE2 playbook. Disjoint surfaces, so
   building parallelises; only measurement is ordered.
3. Measurement order is fixed: baseline (A) → CE1 ablation → CE2 ablation →
   CE3 → CE4 phase 1.
4. Each lever: deploy to both environments, run the harness on/off, log the
   result in the roadmap, harden into contracts/UI only on a win.
5. P1 exit → scope P2 (conversation mode) on the state P1 built; P3 inherits
   the unchanged D1e/M4 contract.

## 5. Open risks

- **Non-determinism at temperature 0** (four terminal findings for one
  instruction) means single-run comparisons are meaningless; D1's rep count is
  the mitigation and should not be quietly reduced.
- **Live-run cost** — an overnight cadence, not per-PR; regression mode carries
  CI.
- **Guidance bloat** is the most likely way CE2 fails; the irrelevant-guidance
  control scenario is not optional.
- **Demo-host SG rule** was found removed once without action; if it recurs,
  something is auto-revoking it.
