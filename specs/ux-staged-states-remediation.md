# Context dump — align the chartsearchai frontend to the backend staged-answer states

Handoff for a **fresh session** to do the UX remediation. This is a **map, not a substitute for the
code.** First action in the fresh session: open and read the cited files and **confirm every "current"
claim here against the code** — treat this doc as a set of hypotheses that may have drifted. Keep this
file updated as a living handoff (offload state here, don't rely on chat memory).

## The goal — one explicit, tightly-managed state
The frontend must represent the backend's staged turn lifecycle as **ONE explicit per-turn `phase`** (a
discriminated union / enum) that is the single source of truth and drives all three of:
1. **behavior** — composer enabled/disabled, Stop-vs-Send, submit/speech/mic guards, focus;
2. **rendering** — each phase visually distinct;
3. **DOM** — a `data-*` attribute so the phase is observable (cheap verification, not slow demo-guessing).

Frontend state has no reason to be implicit or scattered. Today it is four overlapping flags encoding one
lifecycle — **that is the debt to pay down**, not a constraint to work around.

## Backend truth — the staged turn state machine (verify in code)
- Endpoint `/chat/stream` → the hub relay `ChartSearchAiRestController.handleHubStagedEvent`
  (`targets/chartsearchai/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java`),
  which forwards the hub's phase-boundary events verbatim.
- Per-turn SSE events (the phases to mirror): `answer_done` → `answer_validation`
  (validating → checked | edited | needs_review | unavailable) → `indepth_pending` →
  `indepth_done` → `done`; plus `indepth_error`. The hub does **not** token-stream — the answer
  arrives whole on `answer_done` and the in-depth whole on `indepth_done`.
- Distilled phases: **answer → validating → answer-settled → in-depth (generating) → complete**
  (| failed | preempted).
- Physical constraints: answer + in-depth both run on the **writer** model (gemma for
  `answer:gemma-4-12b`); validation on qwen. The llama-router is **single-slot per model**
  (`scripts/llama-router.ini` `parallel=1`) → answer and in-depth cannot generate at once, and
  **concurrent same-session turns are UNSAFE** (unsynchronized `getLastOrdinal()+1`,
  `ChatServiceImpl` ~L198). ⇒ keep answers single-flight; in-depth yields to the next question (preempt).

## The phase model (decided + being implemented this session)
One field `phase: TurnPhase` on each `ChatMessage`, set explicitly by every SSE/stop/preempt handler,
mirroring the backend events 1:1. All behavior + render + DOM derive from it via predicates in
`src/hooks/turn-phase.ts` (no other lifecycle booleans — `isLoading`/`answerSettled`/`isAnyLoading` are gone).

| phase | backend trigger | composer | notes |
|---|---|---|---|
| `answering` | created | locked | answer generating; "Thinking..." indicator |
| `validating` | `answer_done` | locked | answer text done; self-check running; sections split |
| `settled` | `answer_validation` | **unlocked** | answer available + checked; preemptable |
| `in-depth` | `indepth_pending` | unlocked | in-depth generating in background (delivered whole on `indepth_done`); preemptable |
| `complete` | `done` / `indepth_done` / `indepth_error` / stop / preempt | unlocked | terminal; answer available |
| `error` | `onError` | unlocked | terminal; answer generation itself failed |

Predicates: `isAwaitingAnswer(phase)` = `answering|validating` (drives composer `disabled`, submit/speech/mic
guards, Stop-vs-Send, focus-restore); `isAnswerSettled(phase)` = `settled|in-depth|complete` (preempt
eligibility); `isTerminal(phase)` = `complete|error` (render actions/blocks/copy). DOM: `data-turn-phase`
on the response container (coarse phase) + existing `data-indepth-status` (in-depth outcome) — both observable.

## Frontend BEFORE this session (the debt now consolidated)
Files: `targets/chartsearchai-esm/src/hooks/useChartSearchAi.ts`,
`src/components/ai-chat-content.component.tsx`, `src/components/ai-response-panel.component.tsx`.
- The hook receives every staged SSE event (`onAnswerDone`/`onAnswerValidation`/`onInDepthPending`/
  `onInDepthDone`/`onInDepthError`/`onDone`)
  but exposes state as **scattered flags**, not one phase:
  - on `ChatMessage`: `isLoading` (true until terminal `done`), `answerSettled` (set on `answer_validation`),
    `inDepth.status` (`pending|complete|failed`), `answerValidation.status`.
  - derived in the hook: `isAnyLoading` (last msg `isLoading`), `isAwaitingAnswer` (`isLoading && !answerSettled`).
- Behavior currently keys off `isAwaitingAnswer` (composer `disabled`, submit/speech guards, mic,
  Stop-vs-Send, focus-restore) in `ai-chat-content.component.tsx`.
- Preempt: `submitQuestion` (hook ~L277) aborts a **settled** turn's trailing in-depth + finalizes it
  `complete`, then starts the new turn. Single source of truth for "settled" = `message.answerSettled`
  (read from the store, ~L286). Single-flight preserved for answers.
- Render (`ai-response-panel.component.tsx` ~L272): `showSections` once `answerValidation`/`inDepth`
  present; in-depth wrapper exposes **`data-indepth-status`** (`pending|complete|failed`) via
  `display:contents` (~L301).
- **The consolidation:** collapse `isLoading` + `answerSettled` + `inDepth.status` + `answerValidation.status`
  into a single derived `phase` per message, and drive behavior + render + DOM off it. Fold the flags below
  into that model rather than leaving them as separate signals.

## Done (verified)
- **The phase model is implemented and unit-tested** (esm commit `6ba52c8` on `harness-integration`).
  The four flags are gone; `phase` (`src/hooks/turn-phase.ts`) is the single source of truth, set by
  every SSE/stop/preempt handler. Composer + render + DOM derive from it. `data-turn-phase` (coarse) +
  `data-indepth-status` (in-depth outcome) both on the response container. **206 esm tests green,
  typecheck + lint clean.** Includes a red-first `tracks the turn phase through the staged lifecycle`
  hook test (asserted RED before the refactor).
- **NOT yet verified end-to-end:** the live recording/acceptance test has not been re-run against the
  built bundle; whether preempt actually frees the single-slot router fast (client abort → hub → router
  cancellation) is still unmeasured. Next: `make chartsearch-esm-build` → warm → record `chartsearchai-demo`.

## Acceptance test = definition of done
`tests/e2e/specs/chartsearchai-demo.spec.ts` (warm first: `scripts/demo-warmup-chartsearchai.sh`) must
record **and assert**:
- **Q1:** answer settles fast → in-depth **completes**.
- **Q2:** answer settles → in-depth **generating** (phase `in-depth`, `data-indepth-status="pending"`).
- **Q3:** sent while Q2's in-depth is pending → **preempts** it (Q3 accepted) → Q3 in-depth completes.
- all three turns reach a terminal in-depth phase (asserted via `data-indepth-status`).
Waits key off the phase signal (composer-enabled / `data-indepth-status`), **never blind timers**. Records
at 1280×720. The video is proof the capability works — **do not hack the test to pass it.**

## Constraints / gotchas
- Single-slot router → no true parallel answer+in-depth (future work: second resident model or
  `parallel=2`; out of scope now).
- Never edit bind-mounted files (`levels.yaml`, `prompts/`) during a live run.
- esm deploy = `make chartsearch-esm-build` (live via Caddy).
- Server: concurrent same-session turns unsafe → keep answers single-flight (preempt, don't parallelize).
- Client `.catch` filters `AbortError` (`api/chartsearchai.ts` ~L608) → preempt won't stamp a spurious error.

## How to work it (fresh session)
1. Read the cited files; confirm this map against the code.
2. Design the single `phase` model → wire behavior + render + DOM off it → unit-test the phase transitions →
   run the demo (acceptance test) → record.
3. Tight loop: one change → verify via a real signal (test / `data-*` / probe) → next. No big-bang, no
   pre-decomposition. Update this doc as you learn.

See also: `specs/agent-collaboration-playbook.md` (how to run the session).
