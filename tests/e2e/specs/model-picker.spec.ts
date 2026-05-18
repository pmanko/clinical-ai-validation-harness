import { test, expect, type Page } from '@playwright/test';

const ADMIN_USER = process.env.E2E_USER ?? 'admin';
const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? 'Admin123';
const PATIENT_UUID = process.env.E2E_PATIENT_UUID ?? 'dd553355-1691-11df-97a5-7038c432aabf';

async function login(page: Page): Promise<void> {
  await page.goto('/openmrs/spa/login');
  await page.locator('input#username').fill(ADMIN_USER);
  const cont = page.locator('button[type="submit"]').first();
  if (await cont.isVisible({ timeout: 5000 }).catch(() => false)) await cont.click();
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL(/login\/location|home|patient/, { timeout: 60_000 });
  if (page.url().includes('/login/location')) {
    await page.locator('label.cds--radio-button__label').first().click();
    await page.getByRole('button', { name: /confirm|continue|log in/i }).first().click();
    await page.waitForURL(/home|patient/, { timeout: 60_000 });
  }
}

test.describe('chartsearchai — inline model picker (iteration 1B)', () => {
  test('picker mounts in chat footer, lists LM Studio models, and switches the active model', async ({ page }) => {
    await login(page);
    await page.goto(`/openmrs/spa/patient/${PATIENT_UUID}/chart/Patient%20Summary`);
    await page.waitForLoadState('networkidle').catch(() => {});

    // Open the AI chat panel via the banner button.
    const aiButton = page.locator('button[aria-label*="AI" i]').first();
    await expect(aiButton).toBeVisible({ timeout: 30_000 });
    await aiButton.click();

    // Picker trigger renders in the chat panel footer once /models resolves.
    const trigger = page.getByRole('button', { name: /select model/i }).first();
    await expect(trigger).toBeVisible({ timeout: 30_000 });
    const initialModel = (await trigger.textContent())?.trim() ?? '';
    expect(initialModel.length, 'trigger must show the current model name').toBeGreaterThan(0);

    // Open the popover and assert the listbox has more than one option.
    await trigger.click();
    const listbox = page.getByRole('listbox');
    await expect(listbox).toBeVisible({ timeout: 5_000 });
    const optionCount = await listbox.locator('[role="option"]').count();
    expect(optionCount, 'expected multiple LM Studio models in the picker').toBeGreaterThanOrEqual(2);

    // Pick a model that ISN'T the current one. Filter by accessible name to
    // avoid clicking on the already-selected one.
    const optionLabels: string[] = [];
    for (let i = 0; i < optionCount; i++) {
      optionLabels.push(((await listbox.locator('[role="option"]').nth(i).textContent()) ?? '').trim());
    }
    const targetModel = optionLabels.find((label) => label && label !== initialModel);
    if (!targetModel) {
      throw new Error('no non-current model available to switch to; harness LM Studio must serve >=2 models');
    }
    await page.getByRole('button', { name: new RegExp(targetModel.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&'), 'i') }).first().click();

    // After switch, trigger should show the new model and popover should close.
    await expect(trigger).toHaveText(new RegExp(targetModel.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&'), 'i'), { timeout: 10_000 });
    await expect(listbox).toBeHidden();

    // Backend should reflect the switch — verify via the same REST endpoint
    // the UI calls.
    const response = await page.request.get('/openmrs/ws/rest/v1/chartsearchai/models', {
      headers: { Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}` },
    });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.current).toBe(targetModel);

    // Restore the initial model so subsequent runs / chats use the same model.
    await page.request.post('/openmrs/ws/rest/v1/chartsearchai/model', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}`,
      },
      data: { modelName: initialModel },
    });
  });
});
