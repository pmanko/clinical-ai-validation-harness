import { test, expect, type Page, type APIRequestContext } from '@playwright/test';

const ADMIN_USER = process.env.E2E_USER ?? 'admin';
const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? 'Admin123';
const PATIENT_UUID = process.env.E2E_PATIENT_UUID ?? 'dd553355-1691-11df-97a5-7038c432aabf';
const MEDS_QUESTION = 'List the medications this patient is on.';

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
  await page.locator('input[name="username"], input#username').first().fill(ADMIN_USER);
  // Reference Application splits username + password across two pages
  const continueBtn = page.locator('button:has-text("Continue"), button[type="submit"]').first();
  if (await continueBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await continueBtn.click();
  }
  await page.locator('input[name="password"], input[type="password"]').first().fill(ADMIN_PASSWORD);
  await page.locator('button:has-text("Log in"), button[type="submit"]').first().click();

  // Refapp 3.x adds a location picker after password — pick the first option
  // (the harness seeds with the standard refapp locations; any is fine).
  await page.waitForURL(/\/openmrs\/spa\/(home|login\/location|patient)/, { timeout: 60_000 });
  if (page.url().includes('/login/location')) {
    // Carbon's RadioButton has a visual span over the input; click the label.
    await page.locator('label.cds--radio-button__label').first().click();
    await page.getByRole('button', { name: /confirm|continue|log in/i }).first().click();
    await page.waitForURL(/\/openmrs\/spa\/(home|patient)/, { timeout: 60_000 });
  }
}

async function openPatientChart(page: Page): Promise<void> {
  await page.goto(`/openmrs/spa/patient/${PATIENT_UUID}/chart/Patient Summary`);
  // Banner is the cheapest "chart loaded" signal across refapp versions.
  await expect(page.locator('[data-testid="patient-banner"], .patient-banner, header').first()).toBeVisible({
    timeout: 60_000,
  });
}

async function openAiChatPanel(page: Page): Promise<void> {
  // The chartsearchai extension mounts an icon button into the patient banner
  // tags slot. Try the accessible name first, fall back to the title attribute
  // the component sets when icons are decorative.
  const trigger = page
    .getByRole('button', { name: /ai|chart search|chat/i })
    .or(page.locator('[aria-label*="AI" i]'))
    .first();
  await expect(trigger).toBeVisible({ timeout: 30_000 });
  await trigger.click();
  // The chat input is the canonical mounted-panel signal.
  await expect(
    page.getByPlaceholder(/ask|question|search/i).first(),
  ).toBeVisible({ timeout: 15_000 });
}

async function askAndWait(page: Page, question: string): Promise<void> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await input.fill(question);
  await input.press('Enter');
}

test.describe('chartsearchai — structured table blocks', () => {
  test.beforeEach(async ({ request }) => {
    await resetChatSession(request);
  });

  test('meds-list query renders a Carbon DataTable below the prose, and survives hard-reload', async ({ page }) => {
    await login(page);
    await openPatientChart(page);
    await openAiChatPanel(page);
    await askAndWait(page, MEDS_QUESTION);

    // The table appears once the SSE `done` event lands. Anchor on a Carbon
    // table with at least one column header — DataTable renders `<table>` with
    // role=columnheader elements we can assert. Long timeout because cold
    // medgemma inference takes ~30–60s.
    const table = page.locator('table').filter({ has: page.getByRole('columnheader') }).first();
    await expect(table).toBeVisible({ timeout: 180_000 });

    // The Medication column should be present (semantic, not auto-generated
    // "References") — proof the prompt's structured-tables directive landed.
    await expect(table.getByRole('columnheader', { name: /medication/i })).toBeVisible();

    // At least 2 rows (chart has > 10 unique meds; 2 is a safe lower bound
    // that tolerates the occasional small-model drop-some-rows behavior).
    const rowCount = await table.locator('tbody tr').count();
    expect(rowCount, 'Medications table should render at least 2 unique-med rows').toBeGreaterThanOrEqual(2);

    // Hard-reload → hydration path restores the table from chat_message.content.
    await page.reload({ waitUntil: 'load' });
    await openAiChatPanel(page);
    const rehydratedTable = page.locator('table').filter({ has: page.getByRole('columnheader') }).first();
    await expect(rehydratedTable).toBeVisible({ timeout: 60_000 });
    await expect(rehydratedTable.getByRole('columnheader', { name: /medication/i })).toBeVisible();
  });
});
