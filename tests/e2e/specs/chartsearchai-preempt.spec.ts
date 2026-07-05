// Preempting a still-streaming In-Depth must free the hub's router slot mid-leg, not queue
// the next question behind the whole in-depth generation. This is a CI-assertion test (unlike
// chartsearchai-demo.spec.ts, which paces the same scenario for a human-watchable recording and
// makes no hard latency claim) — it fails if the preempt is cosmetic (UI moves on) but the server
// still serializes the next answer behind the old in-depth call.
import { test, expect, type Page } from '@playwright/test';
import { login, openAiChatPanel, openPatientChart, resetChatSession, selectSingle12BModel } from '../support/openmrs';

// Same semantics as the trivial multi-turn spec's threshold: how long a fresh Answer call is allowed
// to take. If the router slot were NOT freed, Q3 would instead have to wait for the ENTIRE prior
// in-depth generation to finish first — an order of magnitude slower — so this bound is what
// distinguishes "preempted" from "queued behind the old leg".
const PREEMPT_ANSWER_MAX_MS = Number.parseInt(process.env.E2E_PREEMPT_ANSWER_MAX_MS ?? '60000', 10);

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

  test('sending a new question while the previous in-depth streams preempts it, and the new answer is fast', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await selectSingle12BModel(page);

    // Q1 — a normal turn allowed to finish completely, establishing the session is healthy before
    // the actual preempt assertion (isolates "preempt is broken" from "the session itself is broken").
    await typeAndSend(page, QUESTIONS[0]);
    await waitTurnPhase(page, 0, 'complete');
    await expect(page.locator('[data-indepth-status]').nth(0)).toHaveAttribute('data-indepth-status', 'complete', {
      timeout: 360_000,
    });

    // Q2 — sent, then we wait for its in-depth to actually be STREAMING (not just pending) before
    // preempting it, so the test proves preemption of live server work, not a request that hadn't
    // started yet.
    await typeAndSend(page, QUESTIONS[1]);
    await waitTurnPhase(page, 1, 'in-depth');

    // Q3 — sent immediately while Q2's in-depth is live. The composer is already enabled here
    // (isAnswerSettled is true once a turn reaches 'in-depth'), so this is the actual preempt path.
    const preemptSentAt = Date.now();
    await typeAndSend(page, QUESTIONS[2]);
    await waitTurnPhase(page, 2, 'validating');
    const q3AnswerMs = Date.now() - preemptSentAt;

    expect(
      q3AnswerMs,
      `Q3's answer took ${q3AnswerMs}ms — if the router slot were not freed mid-leg, this would ` +
        `instead be gated behind Q2's full in-depth generation, not a fresh Answer call.`,
    ).toBeLessThan(PREEMPT_ANSWER_MAX_MS);

    // Q2's row must land in a terminal state — not left dangling mid-stream forever — once preempted.
    await waitTurnPhase(page, 1, 'complete', 30_000);
    await expect(page.locator('[data-indepth-status]').nth(1)).toHaveAttribute('data-indepth-status', 'complete', {
      timeout: 30_000,
    });

    // All three turns present — Q3 was accepted, not blocked or dropped.
    await expect(page.locator('[data-turn-phase]')).toHaveCount(3, { timeout: 30_000 });

    expect(errors, `page JS errors: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
