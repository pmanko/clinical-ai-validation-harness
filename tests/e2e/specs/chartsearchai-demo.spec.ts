// Demo RECORDING spec (not a CI assertion test). Drives a multi-prompt conversation through the
// staged single-12B path, paced for viewing, and showcases the interactive-first UX:
//   - Q1: the quick answer appears + self-checks, then the in-depth analysis fills in (we let it finish).
//   - Q2: you ask the next question WITHOUT waiting for the deep dive — sending Q3 preempts Q2's in-depth.
//   - Q3: the final answer checks and its in-depth completes.
//
// Records at 1280x720 for legible answer text. Run after warming the path:
//   scripts/demo-warmup-chartsearchai.sh
//   yarn --cwd tests/e2e test chartsearchai-demo
// The recorded video.webm lands under tests/e2e/test-results/…/ — convert to mp4 for publishing.

import { test, expect, type Page } from '@playwright/test';
import {
  login,
  openAiChatPanel,
  openPatientChart,
  resetChatSession,
  selectSingle12BModel,
} from '../support/openmrs';

test.use({
  viewport: { width: 1280, height: 720 },
  video: { mode: 'on', size: { width: 1280, height: 720 } },
});

// Pacing knobs — generous defaults so the raw recording is readable without post-processing.
const TYPE_DELAY_MS = Number.parseInt(process.env.DEMO_TYPE_DELAY_MS ?? '45', 10);
const READ_PAUSE_MS = Number.parseInt(process.env.DEMO_READ_PAUSE_MS ?? '4000', 10);
const CAPTION_PAUSE_MS = Number.parseInt(process.env.DEMO_CAPTION_PAUSE_MS ?? '1600', 10);
// How long Q2's in-depth streams (visibly) before we preempt it by asking Q3.
const PREEMPT_AFTER_MS = Number.parseInt(process.env.DEMO_PREEMPT_AFTER_MS ?? '5000', 10);
// Safety cap while waiting for an in-depth to complete.
const INDEPTH_MAX_MS = Number.parseInt(process.env.DEMO_INDEPTH_MAX_MS ?? '120000', 10);

const QUESTIONS = [
  'In one short sentence, what was the most recent documented clinical visit?',
  'What medications is this patient currently taking?',
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
 * disables on submit and re-enables once the answer + validation land (in-depth then streams in the
 * background). Waiting on the composer's own enabled state is the exact "answer is up" signal AND
 * gates the next turn's typing.
 *
 * Types via the keyboard on the focused input (rather than locator.pressSequentially) so it does not
 * re-resolve/re-check the element for each character while a prior turn's in-depth is still streaming
 * — which is exactly the state we type into when preempting. The composer is a flex-shrink:0 footer
 * (the transcript scrolls internally), so it stays put during streaming — a normal click focuses it.
 */
async function typeAndSend(page: Page, question: string): Promise<void> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await expect(input).toBeEnabled({ timeout: 360_000 }); // composer ready for a new turn
  await input.click(); // focus the (layout-stable) composer footer
  await page.keyboard.type(question, { delay: TYPE_DELAY_MS });
  await page.waitForTimeout(400);
  await page.keyboard.press('Enter');
  await expect(input).toBeDisabled({ timeout: 15_000 }); // submission registered (awaiting answer)
  await expect(input).toBeEnabled({ timeout: 360_000 }); // answer + validation settled → composer unlocks
}

/** Wait for the LATEST turn's in-depth to actually FINISH — data-indepth-status flips to 'complete'
 *  only on indepth_done (not the pending/streaming states). Robust to model speed — no blind timer. */
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
  test('interactive-first multi-prompt conversation on the staged single 12B path', async ({ page, request }) => {
    test.setTimeout(900_000);

    await resetChatSession(request);
    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await caption(
      page,
      'ChartSearchAI — ask questions about a patient chart; answers are grounded in the record and independently checked.',
      2600,
    );

    await selectSingle12BModel(page);
    await caption(page, 'Model: single Gemma 12B, routed through med-agent-hub with staged validation.', 2400);

    // Q1 — let the in-depth analysis finish (proves in-depth completes end-to-end).
    await caption(page, 'Question 1 — the quick answer appears first, then it self-checks against the chart.');
    await typeAndSend(page, QUESTIONS[0]);
    await caption(page, 'Answer is up and checked. The in-depth analysis now fills in below…', 1200);
    await waitInDepthComplete(page);
    await page.waitForTimeout(READ_PAUSE_MS);

    // Q2 — ask again without waiting for the deep dive.
    await caption(page, 'Question 2 — you don’t have to wait for the deep dive to ask the next question.');
    await typeAndSend(page, QUESTIONS[1]);
    await waitPhase(page, 'in-depth', 30_000); // confirm Q2's in-depth is actually streaming (something to preempt)
    await caption(page, 'The in-depth is still streaming in the background…', 1000);
    await page.waitForTimeout(PREEMPT_AFTER_MS);

    // Q3 — sending now PREEMPTS Q2's still-streaming in-depth so this answer starts immediately.
    await caption(page, 'Question 3 — asking now preempts the previous deep dive so the new answer starts right away.');
    await typeAndSend(page, QUESTIONS[2]);
    await caption(page, 'The final answer is checked, and its in-depth completes.', 1200);
    await waitInDepthComplete(page);
    await page.waitForTimeout(READ_PAUSE_MS);

    // Proof the preempt worked: all three turns were accepted (Q3 was NOT blocked while Q2's in-depth
    // streamed). data-turn-phase is on every turn's response panel, so a count of 3 == three turns.
    await expect(page.locator('[data-turn-phase]')).toHaveCount(3, { timeout: 30_000 });

    await caption(page, 'Fast answers you can act on immediately — each checked against the chart, depth on demand.', 4000);
  });
});
