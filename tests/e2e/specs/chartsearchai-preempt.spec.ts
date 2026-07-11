// Behavioral proof that preempting a still-generating In-Depth is accepted end-to-end: sending a
// new question while the prior turn's in-depth is generating must be accepted (not blocked or
// dropped), the new turn must produce its own answer, and the preempted turn must land in a
// terminal state rather than dangling mid-stream.
//
// This spec does NOT assert a wall-clock latency bound. The router-slot-frees-on-disconnect
// invariant (the timing claim) is proven deterministically at the hub — see the hub's
// test_staged_stream.py (a fake-driven test with no model latency to swamp the signal). Asserting
// latency here is unreliable: a fresh answer alone can take ~60-70s on the writer model, which
// swamps any preempt signal. The hub owns that proof; this e2e owns the assembled UI behavior.
import { test, expect, type Page } from '@playwright/test';
import {
  hubCancellationsSince,
  hubCancellationTraceOffset,
  hubTraceOffset,
  hubTraceQuestionsSince,
  login,
  openAiChatPanel,
  openPatientChart,
  resetChatSession,
  selectFastE4BModel,
} from '../support/openmrs';

const QUESTIONS = [
  'In one short sentence, what was the most recent documented clinical visit?',
  'What medications is this patient currently taking?',
  'Has this patient’s weight changed recently?',
];

async function typeAndSend(page: Page, question: string): Promise<void> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await expect(input).toBeEnabled({ timeout: 360_000 });
  await input.fill(question);
  await input.press('Enter');
  await expect(input).toBeDisabled({ timeout: 15_000 });
}

async function waitTurnPhase(
  page: Page,
  turnIndex: number,
  phase: 'in-depth' | 'validating' | 'complete',
  timeout = 360_000,
): Promise<void> {
  await expect(page.locator('[data-turn-phase]').nth(turnIndex)).toHaveAttribute('data-turn-phase', phase, {
    timeout,
  });
}

test.describe('chartsearchai — preempt frees the router slot mid-leg', () => {
  test.beforeEach(async ({ request }) => {
    await resetChatSession(request);
  });

  test('sending a new question while the previous in-depth is generating is accepted and answered, and the preempted turn lands terminal', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const traceOffset = hubTraceOffset();
    const cancellationOffset = hubCancellationTraceOffset();

    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await selectFastE4BModel(page);

    // Q1 — a normal turn allowed to finish completely, establishing the session is healthy before
    // the actual preempt assertion (isolates "preempt is broken" from "the session itself is broken").
    await typeAndSend(page, QUESTIONS[0]);
    await waitTurnPhase(page, 0, 'complete');
    await expect(page.locator('[data-indepth-status]').nth(0)).toHaveAttribute('data-indepth-status', 'complete', {
      timeout: 360_000,
    });

    // Q2 — sent, then we wait for its in-depth to be GENERATING (phase 'in-depth', driven by the
    // hub's indepth_pending) before preempting it, so the test preempts a turn whose in-depth leg is
    // actually running server-side, not a request that hadn't started yet.
    await typeAndSend(page, QUESTIONS[1]);
    await waitTurnPhase(page, 1, 'in-depth');

    // Q3 — sent while Q2's in-depth is generating. The composer is already enabled here
    // (isAnswerSettled is true once a turn reaches 'in-depth'), so this is the actual preempt path.
    await typeAndSend(page, QUESTIONS[2]);

    // Q3 must be accepted and produce its OWN answer end-to-end (reach a terminal phase), proving it
    // was not blocked or dropped. (The slot-frees-mid-leg timing invariant is proven at the hub.)
    await waitTurnPhase(page, 2, 'complete');

    // Q2's row must land terminal — not dangle mid-stream forever — once preempted.
    await waitTurnPhase(page, 1, 'complete', 60_000);
    await expect(page.locator('[data-indepth-status]').nth(1)).toHaveAttribute('data-indepth-status', 'failed', {
      timeout: 60_000,
    });

    // All three turns present — Q3 was accepted, not blocked or dropped.
    await expect(page.locator('[data-turn-phase]')).toHaveCount(3, { timeout: 30_000 });

    // The hub records both sides of the preempt: Q2 positively reports cancellation after its
    // router slot is released, and Q3 reaches the normal completed-turn trace.
    await expect
      .poll(() =>
        hubCancellationsSince(cancellationOffset).some(
          (entry) => entry.question === QUESTIONS[1] && entry.router_lock_released === true,
        ),
      )
      .toBe(true);
    await expect.poll(() => hubTraceQuestionsSince(traceOffset).includes(QUESTIONS[2])).toBe(true);
    expect(hubTraceQuestionsSince(traceOffset)).not.toContain(QUESTIONS[1]);

    expect(errors, `page JS errors: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
