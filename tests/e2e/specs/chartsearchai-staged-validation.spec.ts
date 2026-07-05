import { test, expect, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { login, openAiChatPanel, openPatientChart, resetChatSession, selectCheckedModel } from '../support/openmrs';

const QUESTION = 'In one short sentence, what was the most recent documented clinical visit?';
const SHOTS = path.resolve(__dirname, '../evidence/staged-validation');
const MODEL_LABEL = process.env.E2E_MODEL_LABEL ?? 'Gemma 12B';
const STEP_PAUSE_MS = Number.parseInt(process.env.E2E_STEP_PAUSE_MS ?? '900', 10) || 0;
const FAST_ANSWER_MAX_MS = process.env.E2E_FAST_ANSWER_MAX_MS
  ? Number.parseInt(process.env.E2E_FAST_ANSWER_MAX_MS, 10)
  : null;

fs.mkdirSync(SHOTS, { recursive: true });

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

test.describe('chartsearchai — staged single answer validation lifecycle', () => {
  test.beforeEach(async ({ request }) => {
    await resetChatSession(request);
  });

  test('single checked answer routes through med-agent-hub and shows quick Answer before validation tail', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const errors: string[] = [];
    let sentAt = 0;
    let answerMs = 0;
    page.on('pageerror', (e) => errors.push(String(e)));

    await test.step('open the patient chart and AI panel', async () => {
      await login(page);
      await openPatientChart(page);
      await openAiChatPanel(page);
      await caption(page, 'AI panel opened on the patient chart.', '01-panel-open.png');
    });

    await test.step('select the staged single checked model', async () => {
      await selectCheckedModel(page, new RegExp(MODEL_LABEL, 'i'));
      await caption(
        page,
        `Single ${MODEL_LABEL} selected; requests route through med-agent-hub with staged validation.`,
        '02-model-selected.png',
      );
    });

    await test.step('send a short clinical question', async () => {
      const input = page.getByPlaceholder(/ask|question|search/i).first();
      await input.fill(QUESTION);
      sentAt = Date.now();
      await input.press('Enter');
    });

    await test.step('fast answer is visible while async validation is running', async () => {
      await expect(page.getByText('Checking answer')).toBeVisible({ timeout: 360_000 });
      answerMs = Date.now() - sentAt;
      if (FAST_ANSWER_MAX_MS) {
        expect(answerMs).toBeLessThan(FAST_ANSWER_MAX_MS);
      }
      await expect(page.getByTestId('section-in-depth')).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText(/Preparing in-depth/i)).toBeVisible({ timeout: 30_000 });
      await caption(
        page,
        `Fast Answer is visible with Checking answer after ${(answerMs / 1000).toFixed(1)}s.`,
        '03-checking-answer.png',
      );
    });

    await test.step('answer validation updates the same assistant message', async () => {
      const finalBadge = page.getByText(/Checked|Updated after check|Needs review|Check unavailable/).first();
      await expect(finalBadge).toBeVisible({ timeout: 360_000 });
      await caption(page, 'Async answer validation completed and updated the same message.', '04-answer-checked.png');
    });

    await test.step('in-depth finishes after answer validation', async () => {
      await expect(page.getByTestId('section-in-depth')).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText(/Preparing in-depth/i)).toHaveCount(0, { timeout: 360_000 });
      await caption(page, 'In-Depth completed after the answer check lifecycle.', '05-indepth-done.png');
    });

    expect(errors, `page JS errors: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
