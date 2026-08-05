import { test, expect, type Page, type Route } from '@playwright/test';
import { expandAiChatPanel, login, openAiChatPanel, openPatientChart, selectFastE4BModel } from '../support/openmrs';

const MEDS_QUESTION = 'List the medications this patient is on.';

const medicationReference = {
  index: 1,
  resourceType: 'drug_order',
  resourceUuid: 'fixture-drug-order',
  date: '2026-01-26',
  title: 'Lamivudine drug order',
  sourceText: 'Lamivudine. Action: NEW. Urgency: ROUTINE.',
  resolutionStatus: 'resolved',
  groundingStatus: 'supported',
  grounded: true,
};

const medicationBlock = {
  kind: 'table',
  title: 'Current medications',
  columns: [
    { key: 'medication', label: 'Medication' },
    { key: 'status', label: 'Status' },
  ],
  rows: [
    { cells: { medication: { text: 'Lamivudine', refs: [1] }, status: { text: 'Active', refs: [1] } } },
    { cells: { medication: { text: 'Nevirapine', refs: [1] }, status: { text: 'Active', refs: [1] } } },
  ],
};

const finalEnvelope = {
  answer: 'The documented medications are summarized below [1].',
  references: [medicationReference],
  blocks: [medicationBlock],
  model: 'single-e4b-checked',
  confidence: { answer: { level: 'green' }, in_depth: { level: 'green' } },
  answerValidation: {
    status: 'checked',
    label: 'Checked',
    summary: 'Answer checked against chart and deterministic temporal/date rules.',
  },
  inDepth: { status: 'complete', answer: 'Medication details remain linked to the chart source [1].' },
};

function stagedSse(): string {
  const checking = {
    ...finalEnvelope,
    answerValidation: { status: 'checking', label: 'Checking answer' },
    inDepth: { status: 'pending', answer: '' },
  };
  return [
    ['answer_done', checking],
    ['answer_validation', { ...finalEnvelope, inDepth: { status: 'pending', answer: '' } }],
    ['indepth_pending', { ...finalEnvelope, inDepth: { status: 'pending', answer: '' } }],
    ['indepth_done', finalEnvelope],
    ['done', finalEnvelope],
  ]
    .map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join('');
}

async function installTableFixture(page: Page): Promise<void> {
  let completed = false;
  await page.route('**/chartsearchai/chat/stream', async (route: Route) => {
    const body = route.request().postDataJSON() as Record<string, string>;
    expect(body.question).toBe(MEDS_QUESTION);
    completed = true;
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'X-ChartSearchAi-Session': 'table-fixture-session' },
      body: stagedSse(),
    });
  });
  await page.route(/\/chartsearchai\/chat\?patient=/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session: 'table-fixture-session',
        messages: completed
          ? [
              { messageId: 'table-user', role: 'user', content: MEDS_QUESTION, createdAt: Date.now() - 1 },
              {
                messageId: 'table-assistant',
                role: 'assistant',
                content: finalEnvelope.answer,
                references: finalEnvelope.references,
                blocks: finalEnvelope.blocks,
                confidence: finalEnvelope.confidence,
                answerValidation: finalEnvelope.answerValidation,
                inDepth: finalEnvelope.inDepth,
                createdAt: Date.now(),
              },
            ]
          : [],
      }),
    });
  });
}

async function ask(page: Page): Promise<void> {
  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await input.fill(MEDS_QUESTION);
  await input.press('Enter');
}

async function assertMedicationTable(page: Page): Promise<void> {
  const latestTurn = page.locator('[data-turn-phase]').last();
  const medicationHeader = latestTurn.getByRole('columnheader', { name: 'Medication', exact: true });
  await expect(medicationHeader).toBeVisible({ timeout: 30_000 });
  const table = medicationHeader.locator('xpath=ancestor::table[1]');
  await expect(table).toContainText('Lamivudine');
  await expect(table).toContainText('Nevirapine');
  await expect(table.locator('tbody tr')).toHaveCount(2);
}

test('a structured provider envelope renders a medication table and survives hard reload', async ({ page }) => {
  await installTableFixture(page);
  await login(page);
  await openPatientChart(page);
  await openAiChatPanel(page);
  await selectFastE4BModel(page);
  await expandAiChatPanel(page);
  await ask(page);
  await assertMedicationTable(page);

  await page.reload({ waitUntil: 'load' });
  await openAiChatPanel(page);
  await expandAiChatPanel(page);
  await assertMedicationTable(page);
});
