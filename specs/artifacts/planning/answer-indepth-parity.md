# Answer / In-Depth Parity — Architecture Dashboard

> Living design + status doc for evolving Answer and In-Depth into two **truly separate,
> independently-measured, asynchronous** responses — for BOTH the vanilla chartsearchai single
> models AND the med-agent-hub teams. Update this as phases land.

**Last updated:** 2026-06-20 · **Owner lane:** clinical-ai-validation-harness

---

## TL;DR — at a glance

| | Answer axis | In-Depth axis |
|---|---|---|
| **Produced by** | arm's native path (router single / hub team) | shared elaboration pass |
| **Want: separate latency** | `latency_answer` (fast) | `latency_indepth` (slow) |
| **Want: separate judging** | → Benchmark (accuracy/completeness/relevance…) | → Background (support/added-value/no-harm) |
| **Want: delivery** | returned quickly | returned later, ideally in parallel |

**Where we are:** answer + in-depth are **separately *judged*** (text is split on the `**In Depth**`
marker) but **combined in delivery + latency** (one call, one round-trip, one timing), and the
**vanilla single models emit no In-Depth at all** — only the two new hub arms do. So we have *partial
judging parity* and *zero latency/independence parity*.

**Target:** every arm returns two independent artifacts — a fast Answer and a separate, slower
In-Depth — each with its own latency and its own judge score, runnable in parallel.

---

## 1. The vision — true parity + independence

Four measured quantities, for **every** arm (single and team), on equal footing:

```
   answer_quality   ·   answer_latency        in_depth_quality   ·   in_depth_latency
        (Benchmark)        (fast)                  (Background)          (slow)
```

Target data flow — **two orthogonal calls per (scenario, arm) cell:**

```
                          ┌───────────────────────────────────────────────────────┐
                          │  ANSWER axis  — fast                                   │
   one (scenario,arm)  ┌──┤    harness ─call→ chartsearchai ─→ answer path         │─→ answer  · latency_A
        cell ──────────┤  │      single → router :8077 (GGUF)                      │   judge → BENCHMARK
                       │  │      team   → hub  : answer-only synthesis             │
                       │  └───────────────────────────────────────────────────────┘
                       │  ┌───────────────────────────────────────────────────────┐
                       └──┤  IN-DEPTH axis  — slow, separate, (parallel?)          │─→ in-depth · latency_I
                          │    harness ─call→ chartsearchai ─→ hub in-depth-only   │   judge → BACKGROUND
                          │      SHARED mechanism for ALL arms  →  parity          │
                          └───────────────────────────────────────────────────────┘
```

Key property: the **In-Depth call is identical for every arm** (same level/prompt/path) → the
in-depth axis becomes a fair comparison, just like the answer axis. The team scaffolding affects the
**Answer**; the In-Depth is a parity pass for everyone.

---

## 2. Where we are right now — both setups

### 2a. med-agent-hub (team arms) — answer + in-depth, but COMBINED

```
   harness ── ONE call ──→ chartsearchai ──→ med-agent-hub  (level selects the mode)
                                                  │
        ┌─────────────────────────────────────────┴───────────────────────────────────┐
        │ two_call:true (validated teams)        two_call:false + indepth_shared (NEW)   │
        │   answer-synth (+validator loop)         answer-synth (parity prompt)          │
        │        ↓                                      ↓                                │
        │   in-depth-synth (+validator loop)       in-depth-synth (ONE shared pass,      │
        │        ↓                                  no validator)                        │
        │        └──────────── _assemble_envelope ──────────┘                           │
        └────────────────────────────────┬──────────────────────────────────────────────┘
                                          ↓
                  ONE response: "**Answer**…\n\n**In Depth**…"   ·   ONE latency
                                          ↓
                       judge splits the text → Benchmark + Background   (latency NOT split)
```

- `two_call:false` (bare parity, no `indepth_shared`) → **answer only**, bare `{answer}` envelope.
- The hub *internally* already runs answer + in-depth as **separate calls** — they're just
  concatenated and timed as one. (This is why Phase 1 below is small.)

### 2b. vanilla chartsearchai (single models) — answer ONLY

```
   harness ── ONE call ──→ chartsearchai /chat ──→ router :8077 (GGUF + DRY) ──→ answer ONLY
                                                                                    │
                                                              judge → Benchmark
                                                              (no **In Depth** → no Background axis)
```

Single arms (`12b-baseline`, `qwen2.5-14b-baseline`, `medgemma-27b-baseline`, `lfm2-24b-baseline`)
have **no In-Depth path** — they are only judged on the Answer.

### 2c. Coverage matrix — which axis each arm produces TODAY

| Arm | Answer | In-Depth | Separate latency | In-Depth model |
|---|:--:|:--:|:--:|---|
| vanilla single (12b / qwen / medgemma / lfm2) | ✅ | ❌ | ❌ | — |
| hub validated team (`two_call:true`) | ✅ | ✅ *(combined)* | ❌ | team synthesizer (+validator) |
| hub `single-12b-indepth` (NEW) | ✅ | ✅ *(combined)* | ❌ | gemma-4-12b (1 shared pass) |
| hub `med-agent-team-parity-indepth` (NEW) | ✅ | ✅ *(combined)* | ❌ | qwen2.5-14b (1 shared pass) |
| **VISION — every arm** | ✅ | ✅ | ✅ | shared, parity (per-arm or fixed) |

---

## 3. The gap (current → vision)

1. **No separate latency** — one round-trip times the whole pair; can't compare answer-speed vs in-depth-speed.
2. **No In-Depth for vanilla singles** — the multi-class single baselines (the whole point of "parity for the single models") are answer-only.
3. **In-Depth is coupled** — generated by elaborating the just-produced answer inside one call; not an independent artifact, can't run async.
4. **Delivery is combined** — the fast answer isn't actually returned early; it waits for the in-depth.

---

## 4. Roadmap — to true parity + independence

```
  P0 ──→ P1 ──────────→ P2 ──────────→ P3 ──────────→ P4
  shared  split hub:     harness         schema+judge    parallelize
  in-depth answer-only / two-call        +report =       (async):
  (judging only-in-depth  orchestration  2 axes, ALL     answer ∥ in-depth
  parity)  modes         (2 latencies,   arms
                          2 artifacts)
```

| Phase | What it delivers | Status |
|---|---|---|
| **P0** | Shared single-pass In-Depth in the hub → separate **judging** on the 2 hub in-depth arms | ✅ **done** (med-agent-hub PR #10 / harness PR #33) |
| **P1** | Split the hub into an **answer-only** and an **in-depth-only** mode/level (in-depth-only takes question+chart [+answer] → in-depth claims). Reuses the existing `_synthesize_indepth`. | ⬜ blocked on decisions below |
| **P2** | Harness **two-call** orchestration per cell: fire Answer + In-Depth as separate calls; record `latency_answer` + `latency_indepth`; results schema `{answer:{…}, indepth:{…}}`. **In-Depth routed the same way for single AND team** → vanilla singles finally get an in-depth. | ⬜ |
| **P3** | Judge + report consume two independent sub-cells: Answer→Benchmark+latency, In-Depth→Background+latency, for **all** arms; report shows both axes side by side. | ⬜ |
| **P4** | Parallelize: answer ∥ in-depth (if independent) → genuinely async, "quick answer + slower in-depth" delivered concurrently. | ⬜ |

### Open decisions (block P1/P2 design)

1. **In-Depth ↔ Answer coupling**
   - **Independent / parallel** — in-depth = broad clinical background for the *question* (not the answer text); the two calls fire concurrently → truly async. Changes the Background "support" axis to "consistent with chart" rather than "supports the answer."
   - **Sequential / elaborate** — in-depth elaborates the delivered answer (today's semantics); coupled, in-depth waits for the answer.
2. **In-Depth model**
   - **Per-arm** — each arm's own writer model does its in-depth → an in-depth *class survey* mirroring the answer survey ("is Gemma-12B's in-depth better than Qwen-14B's?").
   - **Shared-fixed** — one model does every in-depth → isolates the in-depth prompt as the only variable (pure parity).

---

## 5. In-flight right now

- **med-agent-hub PR [#10](https://github.com/pmanko/med-agent-hub/pull/10)** — `indepth_shared` shared single-pass In-Depth + the two new levels. Green hub suite (57). Not merged.
- **harness PR [#33](https://github.com/pmanko/clinical-ai-validation-harness/pull/33)** — multi-class arms, `multiclass-baseline-core` set, publish→index auto-upsert. Not merged.
- **224-cell run** (`014bc42d…`) executing — multi-class single **Answer** survey (Gemma/Qwen/MedGemma/LFM2) + combined In-Depth on the 2 hub arms. Its **answer** data is architecture-independent and worth judging; the combined in-depth is a P0 preview that P1–P4 supersede.
- **reports.openclinai.org** index auto-upsert shipped; three-patient run backfilled + live.

---

*How to use this doc: update the Coverage matrix (§2c) and the Roadmap table (§4) as phases land;
record decisions in §4 when made. This is a dev-lane doc — not part of the public site.*
