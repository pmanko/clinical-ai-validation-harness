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

const HEALTH_QUESTION = 'In one short sentence, what was the most recent documented clinical visit?';
const PREEMPT_CANDIDATES = [
  'What was documented at the most recent clinical visit?',
  'What is the latest recorded weight?',
  'Summarize the documented CD4 history.',
];
const REPLACEMENT_QUESTION = 'Has this patient’s weight changed recently?';

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
  phase: 'in-depth' | 'checking' | 'complete',
  timeout = 360_000,
): Promise<void> {
  await expect(page.locator('[data-turn-phase]').nth(turnIndex)).toHaveAttribute('data-turn-phase', phase, {
    timeout,
  });
}

async function findPreemptibleTurn(page: Page): Promise<{ question: string; turnIndex: number }> {
  for (const question of PREEMPT_CANDIDATES) {
    const turnIndex = await page.locator('[data-turn-phase]').count();
    await typeAndSend(page, question);
    await expect
      .poll(() => page.locator('[data-turn-phase]').nth(turnIndex).getAttribute('data-turn-phase'), {
        timeout: 360_000,
      })
      .toMatch(/^(in-depth|complete)$/);
    const phase = await page.locator('[data-turn-phase]').nth(turnIndex).getAttribute('data-turn-phase');
    if (phase === 'in-depth') {
      return { question, turnIndex };
    }
    await expect(page.getByPlaceholder(/ask|question|search/i).first()).toBeEnabled({ timeout: 30_000 });
  }
  throw new Error('No candidate turn reached the cancellable In-Depth phase.');
}

test.describe('chartsearchai — preempt frees the router slot mid-leg', () => {
  test.beforeEach(async ({ request }) => {
    await resetChatSession(request);
  });

  test('sending a new question while the previous in-depth is generating is accepted and answered, and the preempted turn lands terminal', async ({
    page,
  }) => {
    test.setTimeout(900_000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const traceOffset = hubTraceOffset();
    const cancellationOffset = hubCancellationTraceOffset();

    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await selectFastE4BModel(page);

    // Q1 reaches a healthy terminal state before the actual preempt assertion. A safety-withheld
    // In-Depth is valid here; a transport/runtime failure is not.
    await typeAndSend(page, HEALTH_QUESTION);
    await waitTurnPhase(page, 0, 'complete');
    await expect(page.locator('[data-indepth-status]').nth(0)).toHaveAttribute(
      'data-indepth-status',
      /^(complete|needs_review)$/,
      { timeout: 360_000 },
    );

    // Review can withhold In-Depth, so try a small fixed set instead of relying on one draft.
    const preempted = await findPreemptibleTurn(page);

    // The replacement is sent while the selected turn's in-depth is generating. The composer is already enabled here
    // (isAnswerSettled is true once a turn reaches 'in-depth'), so this is the actual preempt path.
    await typeAndSend(page, REPLACEMENT_QUESTION);
    const replacementIndex = preempted.turnIndex + 1;

    // Q3 must be accepted and produce its OWN answer end-to-end (reach a terminal phase), proving it
    // was not blocked or dropped. (The slot-frees-mid-leg timing invariant is proven at the hub.)
    await waitTurnPhase(page, replacementIndex, 'complete');

    // Q2's row must land terminal — not dangle mid-stream forever — once preempted.
    await waitTurnPhase(page, preempted.turnIndex, 'complete', 60_000);
    await expect(page.locator('[data-indepth-status]').nth(preempted.turnIndex)).toHaveAttribute('data-indepth-status', 'failed', {
      timeout: 60_000,
    });

    // Every attempted turn plus the replacement is present; the replacement was not blocked or dropped.
    await expect(page.locator('[data-turn-phase]')).toHaveCount(replacementIndex + 1, { timeout: 30_000 });

    // The hub records both sides of the preempt: Q2 positively reports cancellation after its
    // router slot is released, and Q3 reaches the normal completed-turn trace. Q2 may retain a
    // partial audit trace; the explicit cancellation record is the authoritative preempt signal.
    await expect
      .poll(() =>
        hubCancellationsSince(cancellationOffset).some(
          (entry) => entry.question === preempted.question && entry.router_lock_released === true,
        ),
      )
      .toBe(true);
    await expect.poll(() => hubTraceQuestionsSince(traceOffset).includes(REPLACEMENT_QUESTION)).toBe(true);

    expect(errors, `page JS errors: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
