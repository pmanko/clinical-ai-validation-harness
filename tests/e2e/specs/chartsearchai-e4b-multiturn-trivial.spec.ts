import { test, expect, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { login, openAiChatPanel, openPatientChart, resetChatSession, selectCheckedModel } from '../support/openmrs';

const MODEL_LABEL = process.env.E2E_MODEL_LABEL ?? 'Gemma E4B';
const STEP_PAUSE_MS = Number.parseInt(process.env.E2E_STEP_PAUSE_MS ?? '900', 10) || 0;
const FAST_ANSWER_MAX_MS = Number.parseInt(process.env.E2E_FAST_ANSWER_MAX_MS ?? '60_000'.replace('_', ''), 10);
const SHOTS = path.resolve(__dirname, '../evidence/e4b-multiturn-trivial');

// Multi-turn continuity, end-to-end. Turn 1 makes the model COMMIT to one medication — an arbitrary
// choice among the several in the chart. Turn 2 refers back to "the medication you just named", a
// referent that can ONLY resolve from turn-1's answer: the chart alone can't say which one the model
// picked. An earlier version used a non-clinical codeword, but the clinical-synthesis pipeline strips
// tokens like that from the answer, so it could never survive. A medication name is clinical (survives
// synthesis) yet still history-dependent — the CHOICE lives only in the conversation, not the chart.
//
// NOTE (honest scope): this is the assembled end-to-end continuity check. The DEFINITIVE proof that
// prior turns are relayed to the hub is the Java unit test (ChartSearchAiRestController's
// priorTurnsForRelay assertion); this spec confirms the behavior end-to-end, it is not the sole guard.
const QUESTIONS = [
  'Name one medication this patient is currently taking. Reply with only the medication name, nothing else.',
  'Is the medication you just named usually taken once daily or more often? Name that medication in your answer.',
];

fs.mkdirSync(SHOTS, { recursive: true });

test.use({
  viewport: { width: 1280, height: 720 },
  video: { mode: 'on', size: { width: 1280, height: 720 } },
});

async function caption(page: Page, text: string, shotName: string): Promise<void> {
  await page.evaluate((captionText) => {
    let node = document.querySelector<HTMLElement>('[data-e2e-caption]');
    if (!node) {
      node = document.createElement('div');
      node.setAttribute('data-e2e-caption', 'true');
      node.style.position = 'fixed';
      node.style.left = '24px';
      node.style.right = '24px';
      node.style.bottom = '24px';
      node.style.zIndex = '2147483647';
      node.style.padding = '12px 16px';
      node.style.borderRadius = '4px';
      node.style.background = 'rgba(22, 22, 22, 0.88)';
      node.style.color = '#fff';
      node.style.font = '600 15px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      node.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.35)';
      node.style.pointerEvents = 'none';
      document.body.appendChild(node);
    }
    node.textContent = captionText;
  }, text);

  if (STEP_PAUSE_MS > 0) {
    await page.waitForTimeout(STEP_PAUSE_MS);
  }
  await page.screenshot({ path: path.join(SHOTS, shotName), fullPage: true });
}

async function sendTurn(page: Page, question: string, turnNumber: number): Promise<number> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await expect(input).toBeEnabled({ timeout: 360_000 });
  await input.fill(question);

  const sentAt = Date.now();
  await input.press('Enter');
  await expect(input).toBeDisabled({ timeout: 15_000 });
  await expect(page.locator('[data-turn-phase]')).toHaveCount(turnNumber, { timeout: 360_000 });
  await expect(page.getByText('Checking answer').last()).toBeVisible({ timeout: 360_000 });

  const answerMs = Date.now() - sentAt;
  expect(answerMs).toBeLessThan(FAST_ANSWER_MAX_MS);
  await caption(
    page,
    `Turn ${turnNumber}: fast Answer visible with Checking answer after ${(answerMs / 1000).toFixed(1)}s.`,
    `${String(turnNumber).padStart(2, '0')}-checking.png`,
  );

  await expect(input).toBeEnabled({ timeout: 360_000 });
  const latestTurn = page.locator('[data-turn-phase]').nth(turnNumber - 1);
  await expect(latestTurn).toHaveAttribute('data-turn-phase', /settled|in-depth|complete/, { timeout: 360_000 });
  await expect(page.getByText(/Checked|Updated after check|Needs review|Check unavailable/).last()).toBeVisible({
    timeout: 360_000,
  });
  await caption(page, `Turn ${turnNumber}: answer check completed and the composer is ready.`, `${String(turnNumber).padStart(2, '0')}-checked.png`);

  return answerMs;
}

test.describe('chartsearchai - Gemma E4B trivial multi-turn proof', () => {
  test.beforeEach(async ({ request }) => {
    await resetChatSession(request);
  });

  test('returns a quick checked answer, then handles a tiny follow-up turn in the same session', async ({
    page,
  }) => {
    test.setTimeout(720_000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await caption(page, 'AI panel opened on the patient chart.', '00-panel-open.png');

    await selectCheckedModel(page, new RegExp(MODEL_LABEL, 'i'));
    await caption(page, `${MODEL_LABEL} selected for a tiny two-turn session proof.`, '01-model-selected.png');

    const firstAnswerMs = await sendTurn(page, QUESTIONS[0], 1);

    // The medication turn 1 committed to: the longest clinical word in its answer, ignoring citation
    // markers and generic scaffolding words. Turn 2's referent ("the medication you just named") can
    // only resolve to THIS if turn-1's answer was relayed to the hub as prior context.
    const firstTurnText = await page.locator('[data-turn-phase]').nth(0).innerText({ timeout: 30_000 });
    const STOPWORDS = new Set([
      'patient', 'taking', 'medication', 'medications', 'currently', 'this', 'that', 'with', 'their', 'name',
    ]);
    const committedMed = (firstTurnText.match(/[A-Za-z]{4,}/g) ?? [])
      .filter((w) => !STOPWORDS.has(w.toLowerCase()))
      .sort((a, b) => b.length - a.length)[0];
    expect(committedMed, `turn 1 should name a medication; got:\n${firstTurnText}`).toBeTruthy();

    const secondAnswerMs = await sendTurn(page, QUESTIONS[1], 2);

    await expect(page.locator('[data-turn-phase]')).toHaveCount(2, { timeout: 30_000 });
    const secondTurnText = await page.locator('[data-turn-phase]').nth(1).innerText({ timeout: 30_000 });
    // Turn 2 must reference the SAME medication turn 1 chose — only possible if the server relayed
    // turn-1's prose answer as prior context (the chart can't say which one the model picked).
    expect(secondTurnText.toLowerCase()).toContain(committedMed.toLowerCase());

    await expect(page.locator('[data-indepth-status]').last()).toHaveAttribute('data-indepth-status', 'complete', {
      timeout: 360_000,
    });
    await caption(
      page,
      `Two turns completed. Fast answer timings: ${(firstAnswerMs / 1000).toFixed(1)}s, ${(secondAnswerMs / 1000).toFixed(1)}s.`,
      '03-two-turns-complete.png',
    );

    expect(errors, `page JS errors: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
