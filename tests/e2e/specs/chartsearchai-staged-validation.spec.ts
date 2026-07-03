import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const ADMIN_USER = process.env.E2E_USER ?? 'admin';
const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? 'Admin123';
const PATIENT_UUID = process.env.E2E_PATIENT_UUID ?? 'dd75c020-1691-11df-97a5-7038c432aabf';
const QUESTION = 'In one short sentence, what was the most recent documented clinical visit?';
const SHOTS = path.resolve(__dirname, '../evidence/staged-validation');
const STEP_PAUSE_MS = Number.parseInt(process.env.E2E_STEP_PAUSE_MS ?? '900', 10) || 0;
const FAST_ANSWER_MAX_MS = process.env.E2E_FAST_ANSWER_MAX_MS
  ? Number.parseInt(process.env.E2E_FAST_ANSWER_MAX_MS, 10)
  : null;

fs.mkdirSync(SHOTS, { recursive: true });

async function resetChatSession(request: APIRequestContext): Promise<void> {
  const res = await request.post('/openmrs/ws/rest/v1/chartsearchai/chat/new', {
    headers: {
      Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}`,
      'Content-Type': 'application/json',
    },
    data: { patient: PATIENT_UUID },
  });
  expect(res.ok(), `chat/new should succeed but got ${res.status()} ${await res.text()}`).toBeTruthy();
}

async function login(page: Page): Promise<void> {
  await page.goto('/openmrs/spa/login');
  const username = page.locator('input[name="username"], input#username').first();
  if (await username.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await username.fill(ADMIN_USER);
    const continueBtn = page.locator('button:has-text("Continue"), button[type="submit"]').first();
    if (await continueBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await continueBtn.click();
    }
    await page.locator('input[name="password"], input[type="password"]').first().fill(ADMIN_PASSWORD);
    await page.locator('button:has-text("Log in"), button[type="submit"]').first().click();
  }

  await page.waitForURL(/\/openmrs\/spa\/(home|login\/location|patient)/, { timeout: 60_000 });
  if (page.url().includes('/login/location')) {
    await page.locator('label.cds--radio-button__label').first().click();
    await page.getByRole('button', { name: /confirm|continue|log in/i }).first().click();
    await page.waitForURL(/\/openmrs\/spa\/(home|patient)/, { timeout: 60_000 });
  }
}

async function openPatientChart(page: Page): Promise<void> {
  await page.goto(`/openmrs/spa/patient/${PATIENT_UUID}/chart/Patient%20Summary`);
  await expect(page.locator('[data-testid="patient-banner"], .patient-banner, header').first()).toBeVisible({
    timeout: 60_000,
  });
}

async function openAiChatPanel(page: Page): Promise<void> {
  const trigger = page
    .getByRole('button', { name: /ai|chart search|chat/i })
    .or(page.locator('[aria-label*="AI" i]'))
    .first();
  await expect(trigger).toBeVisible({ timeout: 30_000 });
  await trigger.click();
  await expect(page.getByPlaceholder(/ask|question|search/i).first()).toBeVisible({ timeout: 15_000 });
}

async function selectSingle12BModel(page: Page): Promise<void> {
  const modelButton = page
    .getByRole('button')
    .filter({ hasText: /AI Team|Single models|Gemma|No model|validated/i })
    .last();
  await expect(modelButton).toBeVisible({ timeout: 30_000 });
  await modelButton.click();
  const single12b = page
    .getByRole('menuitemradio', { name: /Gemma 12B/i })
    .or(page.getByText(/Gemma 12B/i))
    .first();
  await expect(single12b).toBeVisible({ timeout: 30_000 });
  await single12b.click();
  await expect(modelButton).toContainText(/Gemma 12B/i, { timeout: 10_000 });
}

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

  test('single 12B answer routes through med-agent-hub and shows quick Answer before validation tail', async ({
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

    await test.step('select the staged single 12B model', async () => {
      await selectSingle12BModel(page);
      await caption(
        page,
        'Single Gemma 12B selected; requests route through med-agent-hub answer:* with staged validation.',
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
