// Demo RECORDING spec (not a CI assertion test). Drives a multi-prompt conversation through the
// staged E4B path, paced for viewing, and showcases the interactive-first UX:
//   - Q1: the quick answer appears + self-checks, then the in-depth analysis fills in (we let it finish).
//   - Q2: you ask a simple follow-up, then sending Q3 preempts Q2's unfinished in-depth.
//   - Q3: the final answer checks and its in-depth completes.
//
// Records at 1280x720 for legible answer text. Run after warming the path:
//   scripts/demo-warmup-chartsearchai.sh
//   yarn --cwd tests/e2e test chartsearchai-demo
// The recorded video.webm lands under tests/e2e/test-results/…/ — convert to mp4 for publishing.

import { test, expect, type Page } from '@playwright/test';
import {
  ADMIN_PASSWORD,
  ADMIN_USER,
  PATIENT_UUID,
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

test.use({
  viewport: { width: 1280, height: 720 },
  video: { mode: 'on', size: { width: 1280, height: 720 } },
});

// Pacing knobs — generous defaults so the raw recording is readable without post-processing.
const TYPE_DELAY_MS = Number.parseInt(process.env.DEMO_TYPE_DELAY_MS ?? '45', 10);
const READ_PAUSE_MS = Number.parseInt(process.env.DEMO_READ_PAUSE_MS ?? '4000', 10);
const CAPTION_PAUSE_MS = Number.parseInt(process.env.DEMO_CAPTION_PAUSE_MS ?? '1600', 10);
// Safety cap while waiting for an in-depth to complete.
const INDEPTH_MAX_MS = Number.parseInt(process.env.DEMO_INDEPTH_MAX_MS ?? '360000', 10);

const QUESTIONS = [
  'In one short sentence, what was the most recent documented clinical visit?',
  'What was documented on the visit date you just gave? Include that same date in your answer.',
  'Has this patient’s weight changed recently?',
];

/** On-screen narration overlay (visible in the recording). Left-aligned so it never covers the chat input. */
async function caption(page: Page, text: string, dwellMs = CAPTION_PAUSE_MS): Promise<void> {
  await page.evaluate((captionText) => {
    let node = document.querySelector<HTMLElement>('[data-e2e-caption]');
    if (!node) {
      node = document.createElement('div');
      node.setAttribute('data-e2e-caption', 'true');
      node.style.position = 'fixed';
      node.style.left = '24px';
      node.style.bottom = '24px';
      node.style.maxWidth = 'min(720px, 52vw)';
      node.style.zIndex = '2147483647';
      node.style.padding = '14px 18px';
      node.style.borderRadius = '8px';
      node.style.background = 'rgba(15, 15, 20, 0.9)';
      node.style.color = '#fff';
      node.style.font = '600 18px/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      node.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.4)';
      node.style.pointerEvents = 'none';
      document.body.appendChild(node);
    }
    node.textContent = captionText;
  }, text);
  if (dwellMs > 0) await page.waitForTimeout(dwellMs);
}

/**
 * Type a question at a visible speed and send it, then wait for the ANSWER to settle — the composer
 * disables on submit and re-enables once the answer + validation land (In-Depth then runs in the
 * background). Waiting on the composer's own enabled state is the exact "answer is up" signal AND
 * gates the next turn's typing.
 *
 * Types via the keyboard on the focused input (rather than locator.pressSequentially) so it does not
 * re-resolve/re-check the element for each character while a prior turn's In-Depth is still running
 * — which is exactly the state we type into when preempting. The composer is a flex-shrink:0 footer
 * (the transcript scrolls internally), so it stays put during updates — a normal click focuses it.
 */
async function typeAndSend(
  page: Page,
  question: string,
  fastAnswerCaption?: string,
  typeDelayMs = TYPE_DELAY_MS,
  postTypePauseMs = 400,
): Promise<void> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  const answerSections = page.getByTestId('section-answer');
  const priorAnswerCount = await answerSections.count();
  await expect(input).toBeEnabled({ timeout: 360_000 }); // composer ready for a new turn
  await input.click(); // focus the (layout-stable) composer footer
  await page.keyboard.type(question, { delay: typeDelayMs });
  await page.waitForTimeout(postTypePauseMs);
  await page.keyboard.press('Enter');
  await expect(input).toBeDisabled({ timeout: 15_000 }); // submission registered (awaiting answer)
  await expect(answerSections).toHaveCount(priorAnswerCount + 1, { timeout: 360_000 });
  await expect(answerSections.last()).toBeVisible();
  if (fastAnswerCaption) {
    await caption(page, fastAnswerCaption, 1800);
  }
  await expect(input).toBeEnabled({ timeout: 360_000 }); // answer + validation settled → composer unlocks
}

/** Wait for the LATEST turn's In-Depth to actually FINISH — data-indepth-status flips to 'complete'
 *  only on indepth_done (not the pending/generating states). Robust to model speed — no blind timer. */
async function waitInDepthComplete(page: Page, timeout = INDEPTH_MAX_MS): Promise<void> {
  await expect(page.locator('[data-indepth-status]').last()).toHaveAttribute('data-indepth-status', 'complete', {
    timeout,
  });
}

/** Wait for the LATEST turn to reach a lifecycle phase. data-turn-phase is the coarse turn state
 *  (answering → validating → settled → in-depth → complete); 'in-depth' (entered on the hub's
 *  indepth_pending) means the deep-dive is generating server-side — i.e. there is live work to preempt. */
async function waitPhase(page: Page, phase: 'in-depth' | 'complete', timeout = INDEPTH_MAX_MS): Promise<void> {
  await expect(page.locator('[data-turn-phase]').last()).toHaveAttribute('data-turn-phase', phase, { timeout });
}

test.describe('chartsearchai — demo recording', () => {
  test('interactive-first multi-prompt conversation on the staged E4B path', async ({ page, request }) => {
    test.setTimeout(900_000);

    await resetChatSession(request);
    const traceOffset = hubTraceOffset();
    const cancellationOffset = hubCancellationTraceOffset();
    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await caption(
      page,
      'ChartSearchAI — ask questions about a patient chart; answers are checked against chart, temporal, and citation rules.',
      2600,
    );

    await selectFastE4BModel(page);
    await caption(page, 'Profile: fast checked E4B, routed through med-agent-hub with staged validation.', 2400);

    // Q1 — let the in-depth analysis finish (proves in-depth completes end-to-end).
    await caption(page, 'Question 1 — the quick answer appears first, then it self-checks against the chart.');
    await typeAndSend(page, QUESTIONS[0], 'The fast Answer is visible while its check is still settling.');
    await caption(
      page,
      'The check settles visibly as Checked, Updated, or Needs review. In-Depth is a separate phase below…',
      1200,
    );
    await waitInDepthComplete(page);
    await page.waitForTimeout(READ_PAUSE_MS);

    // Q2 — a trivial follow-up that proves the prior answer is available as turn context.
    await caption(page, 'Question 2 — a simple follow-up uses the visit date from the prior turn.');
    await typeAndSend(page, QUESTIONS[1], 'The follow-up Answer appears before its In-Depth finishes.');
    const input = page.getByPlaceholder(/ask|question|search/i).first();
    const answerSections = page.getByTestId('section-answer');
    const priorAnswerCount = await answerSections.count();
    await input.fill(QUESTIONS[2]);
    await caption(
      page,
      'Question 3 is ready — it will send as soon as the previous deep dive begins.',
      0,
    );
    await waitPhase(page, 'in-depth'); // confirm Q2 has active background work to preempt

    // Q3 — sending now PREEMPTS Q2's unfinished In-Depth so this answer can start.
    await input.press('Enter');
    await expect(input).toBeDisabled({ timeout: 15_000 });
    await expect(answerSections).toHaveCount(priorAnswerCount + 1, { timeout: 360_000 });
    await expect(answerSections.last()).toBeVisible();
    await caption(page, 'The new fast Answer is visible; its check continues asynchronously.', 1800);
    await expect(input).toBeEnabled({ timeout: 360_000 });
    await caption(page, 'The final answer shows its check outcome, and its In-Depth completes.', 1200);
    await waitInDepthComplete(page);
    await page.waitForTimeout(READ_PAUSE_MS);

    // Proof the preempt worked: Q2 lands terminal/failed and all three turns were accepted.
    await expect(page.locator('[data-indepth-status]').nth(1)).toHaveAttribute('data-indepth-status', 'failed', {
      timeout: INDEPTH_MAX_MS,
    });
    await expect(page.locator('[data-turn-phase]')).toHaveCount(3, { timeout: INDEPTH_MAX_MS });

    // Bind the visual proof to server persistence. A DOM-only nth() assertion can accidentally
    // select the wrong status element, and a very fast In-Depth may finish during narration.
    const history = await request.get(
      `/openmrs/ws/rest/v1/chartsearchai/chat?patient=${PATIENT_UUID}`,
      {
        headers: {
          Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}`,
        },
      },
    );
    expect(history.ok(), `chat history should load: ${history.status()} ${await history.text()}`).toBeTruthy();
    const persisted = (await history.json()) as {
      messages: Array<{
        role: string;
        inDepth?: { status?: string };
        references?: Array<{ groundingStatus?: string }>;
      }>;
    };
    const assistantTurns = persisted.messages.filter((message) => message.role === 'assistant');
    expect(assistantTurns).toHaveLength(3);
    expect(assistantTurns[1].inDepth?.status).toBe('failed');
    expect(assistantTurns[1].references?.every((reference) => reference.groundingStatus !== 'checking')).toBe(true);
    await expect
      .poll(() =>
        hubCancellationsSince(cancellationOffset).some(
          (entry) => entry.question === QUESTIONS[1] && entry.router_lock_released === true,
        ),
      )
      .toBe(true);
    await expect.poll(() => hubTraceQuestionsSince(traceOffset).includes(QUESTIONS[2])).toBe(true);
    expect(hubTraceQuestionsSince(traceOffset)).not.toContain(QUESTIONS[1]);

    await caption(page, 'Fast answers to inspect immediately, with visible checking, evidence, and depth on demand.', 4000);
  });
});
