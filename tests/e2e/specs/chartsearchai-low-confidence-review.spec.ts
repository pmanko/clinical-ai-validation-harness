import { expect, test, type Page, type Route } from '@playwright/test';
import { login, openAiChatPanel, openPatientChart, selectFastE4BModel } from '../support/openmrs';

const QUESTION = 'Show the flagged review fixture.';

const originalBlock = {
  kind: 'table',
  title: 'Pre-check weight table',
  columns: [{ key: 'weight', label: 'Weight' }],
  rows: [{ cells: { weight: { text: '6.2 kg', refs: [1] } } }],
};

const originalReference = {
  index: 1,
  resourceType: 'obs',
  resourceUuid: 'draft-observation',
  date: '2026-01-01',
  title: 'Draft weight observation',
  sourceText: 'Weight 6.2 kg',
  resolutionStatus: 'resolved',
};

const finalReference = {
  index: 2,
  resourceType: 'obs',
  resourceUuid: 'final-observation',
  date: '2026-02-02',
  title: 'Final reviewed observation',
  sourceText: 'Reviewed chart record',
  resolutionStatus: 'resolved',
  groundingStatus: 'unsupported',
  grounded: false,
};

const finalEnvelope = {
  answer: 'Flagged final answer [2].',
  references: [finalReference],
  blocks: [],
  model: 'single-e4b-checked',
  confidence: {
    answer: { level: 'red', note: 'The date could not be verified against the chart.' },
    in_depth: { level: 'red', note: 'In-Depth was withheld.' },
  },
  answerValidation: {
    status: 'needs_review',
    label: 'Needs review',
    originalAnswer: 'Original model answer [1].',
    originalReferences: [originalReference],
    originalBlocks: [originalBlock],
  },
  inDepth: {
    status: 'needs_review',
    answer: '',
    error: 'In-Depth was withheld.',
    reviewDraft: '- Rejected In-Depth claim [1].',
    reviewReferences: [originalReference],
  },
};

function stagedSse(): string {
  const checking = {
    ...finalEnvelope,
    answer: 'Original model answer [1].',
    references: [originalReference],
    confidence: { answer: { level: 'yellow', note: 'Checks are running.' } },
    answerValidation: { status: 'checking', label: 'Checking answer' },
    inDepth: { status: 'pending', answer: '' },
  };
  return [
    ['answer_done', checking],
    ['answer_validation', { ...finalEnvelope, inDepth: { status: 'pending', answer: '' } }],
    ['indepth_error', finalEnvelope],
    ['done', finalEnvelope],
  ]
    .map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join('');
}

async function installReviewFixture(page: Page): Promise<void> {
  let completed = false;
  await page.route('**/chartsearchai/chat/stream', async (route: Route) => {
    const request = route.request();
    const body = request.postDataJSON() as Record<string, string>;
    expect(body.question).toBe(QUESTION);
    expect(body.requestId).toBeTruthy();
    completed = true;
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'X-ChartSearchAi-Session': 'fixture-session' },
      body: stagedSse(),
    });
  });
  await page.route(/\/chartsearchai\/chat\?patient=/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session: 'fixture-session',
        messages: completed
          ? [
              {
                messageId: 'fixture-user',
                role: 'user',
                content: QUESTION,
                createdAt: Date.now() - 1,
              },
              {
                messageId: 'fixture-assistant',
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

async function assertReviewArtifacts(page: Page): Promise<void> {
  const answer = page.getByTestId('section-answer').last();
  await expect(answer).toContainText('Low confidence');
  await expect(answer).toContainText('The date could not be verified against the chart.');
  await expect(answer).toContainText('Flagged final answer');
  await expect(page.getByText('Needs review').last()).toBeVisible();

  const original = page.getByText('Original model answer', { exact: true }).last().locator('..');
  await expect(original).toContainText('Original model answer [1].');
  await expect(original).toContainText('Pre-check weight table');
  await expect(original).toContainText('6.2 kg');

  await expect(page.getByText('Model draft for review').last()).toBeVisible();
  await expect(page.getByText(/Rejected In-Depth claim/).last()).toBeVisible();
  await expect(page.getByText('Final reviewed observation').last()).toBeVisible();
}

test('flagged Answer and review-only artifacts stay visible through reload', async ({ page }) => {
  await installReviewFixture(page);
  await login(page);
  await openPatientChart(page);
  await openAiChatPanel(page);
  await selectFastE4BModel(page);

  const input = page.getByPlaceholder(/ask|question|search/i).first();
  await input.fill(QUESTION);
  await input.press('Enter');
  await assertReviewArtifacts(page);

  await page.reload({ waitUntil: 'load' });
  await openAiChatPanel(page);
  await assertReviewArtifacts(page);
});
