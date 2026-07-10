import { test, expect, type Page } from '@playwright/test';
import { login, openAiChatPanel, openPatientChart, resetChatSession } from '../support/openmrs';

const MEDS_QUESTION = 'List the medications this patient is on.';

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
