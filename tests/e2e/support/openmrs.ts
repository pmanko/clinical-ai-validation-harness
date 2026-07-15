// Shared OpenMRS SPA helpers for the chartsearchai e2e specs. Keep login and the
// chart/panel navigation in ONE place so the specs cannot drift (they did: one
// spec's login gated the whole flow on a 5s isVisible() that silently skipped
// submitting credentials on a cold SPA render — see the git history of this file).

import { expect, type APIRequestContext, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

export const ADMIN_USER = process.env.E2E_USER ?? 'admin';
export const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? 'Admin123';
export const PATIENT_UUID = process.env.E2E_PATIENT_UUID ?? 'dd75c020-1691-11df-97a5-7038c432aabf';

const HUB_TRACE_PATH =
  process.env.E2E_HUB_TRACE_PATH ?? path.resolve(process.cwd(), '../../artifacts/hub-trace/trace.jsonl');
const HUB_CANCELLATION_TRACE_PATH =
  process.env.E2E_HUB_CANCELLATION_TRACE_PATH ??
  path.resolve(process.cwd(), '../../artifacts/hub-trace/cancellations.jsonl');

function fileOffset(file: string): number {
  return fs.existsSync(file) ? fs.statSync(file).size : 0;
}

function jsonLinesSince<T>(file: string, offset: number): T[] {
  if (!fs.existsSync(file)) return [];
  return fs
    .readFileSync(file)
    .subarray(offset)
    .toString('utf8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

export function hubTraceOffset(): number {
  return fileOffset(HUB_TRACE_PATH);
}

export function hubTraceQuestionsSince(offset: number): string[] {
  return jsonLinesSince<{ question?: string }>(HUB_TRACE_PATH, offset).map(
    (entry) => entry.question ?? '',
  );
}

export type HubTraceEntry = {
  question?: string;
  steps?: Array<{
    role?: string;
    prior_message_count?: number;
    prior_turn_count?: number;
    prior_roles?: string[];
    prior_messages_sha256?: string;
  }>;
};

export function hubTraceEntriesSince(offset: number): HubTraceEntry[] {
  return jsonLinesSince<HubTraceEntry>(HUB_TRACE_PATH, offset);
}

export type HubCancellation = {
  event?: string;
  level_id?: string;
  question?: string;
  router_lock_released?: boolean;
};

export function hubCancellationTraceOffset(): number {
  return fileOffset(HUB_CANCELLATION_TRACE_PATH);
}

export function hubCancellationsSince(offset: number): HubCancellation[] {
  return jsonLinesSince<HubCancellation>(HUB_CANCELLATION_TRACE_PATH, offset);
}

/** Reset the server-side chat session for the demo patient (independent of the browser session). */
export async function resetChatSession(request: APIRequestContext): Promise<void> {
  const res = await request.post('/openmrs/ws/rest/v1/chartsearchai/chat/new', {
    headers: {
      Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}`,
      'Content-Type': 'application/json',
    },
    data: { patient: PATIENT_UUID },
  });
  expect(res.ok(), `chat/new should succeed but got ${res.status()} ${await res.text()}`).toBeTruthy();
}

/**
 * Log in through the OpenMRS 3 SPA. Robust against a cold first render: the login-app
 * mounts the form asynchronously after the `load` event, which on a cold start routinely
 * takes longer than a few seconds. We WAIT for the username field (and fail loudly if it
 * never appears) rather than racing it — the previous `isVisible({ timeout: 5_000 })`
 * gate returned false on a slow render and skipped the login entirely, leaving the test
 * to time out on the still-empty login page.
 */
export async function login(page: Page): Promise<void> {
  await page.goto('/openmrs/spa/login');

  const username = page.locator('input[name="username"], input#username').first();
  await expect(username, 'login username field never rendered').toBeVisible({ timeout: 60_000 });
  await username.fill(ADMIN_USER);

  // Reference Application 3.x splits username + password across two steps; older/other
  // builds show both at once. Click Continue only when the password field isn't present yet.
  const password = page.locator('input[name="password"], input[type="password"]').first();
  if (!(await password.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /continue/i }).first().click();
  }
  await expect(password, 'login password field never rendered').toBeVisible({ timeout: 30_000 });
  await password.fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /log in/i }).first().click();

  // Refapp 3.x may add a location picker after password.
  await page.waitForURL(/\/openmrs\/spa\/(home|login\/location|patient)/, { timeout: 60_000 });
  if (page.url().includes('/login/location')) {
    // Carbon RadioButton has a visual span over the input; click the label.
    await page.locator('label.cds--radio-button__label').first().click();
    await page.getByRole('button', { name: /confirm|continue|log in/i }).first().click();
    await page.waitForURL(/\/openmrs\/spa\/(home|patient)/, { timeout: 60_000 });
  }
}

/** Open a patient chart; resolves once the banner (cheapest "loaded" signal) is visible. */
export async function openPatientChart(page: Page): Promise<void> {
  await page.goto(`/openmrs/spa/patient/${PATIENT_UUID}/chart/Patient%20Summary`);
  await expect(
    page.locator('[data-testid="patient-banner"], .patient-banner, header').first(),
  ).toBeVisible({ timeout: 60_000 });
}

/**
 * Open the chartsearchai floating chat panel. Target the launcher FAB by its exact accessible name
 * ("AI Search", from ai-search-button.component.tsx aria-label) — a fuzzy /ai/i match resolved
 * `.first()` to a different button (e.g. the "Ask AI" action-menu button) that does not open the
 * floating panel, so the input never appeared. Resolves once the composer input is visible.
 */
export async function openAiChatPanel(page: Page): Promise<void> {
  const trigger = page.getByRole('button', { name: 'AI Search' }).first();
  await expect(trigger, 'AI Search launcher (floating FAB) never appeared').toBeVisible({ timeout: 30_000 });
  await trigger.click();
  await expect(page.getByPlaceholder(/ask|question|search/i).first()).toBeVisible({ timeout: 15_000 });
}

/** Maximize the floating chat so answers, tables, and evidence are readable in proof recordings. */
export async function expandAiChatPanel(page: Page): Promise<void> {
  const maximize = page.getByRole('button', { name: /maximize/i }).first();
  await expect(maximize, 'chat maximize control never appeared').toBeVisible({ timeout: 15_000 });
  await maximize.click();
  await expect(page.getByRole('button', { name: /restore/i }).first()).toBeVisible({ timeout: 15_000 });
}

export async function selectCheckedModel(page: Page, labelPattern: RegExp = /Gemma 12B/i): Promise<void> {
  const modelButton = page.getByTestId('chartsearchai-profile-picker');
  await expect(modelButton).toBeVisible({ timeout: 30_000 });
  await modelButton.click();
  const modelOption = page
    .getByRole('menuitemradio', { name: labelPattern })
    .or(page.getByText(labelPattern))
    .first();
  await expect(modelOption).toBeVisible({ timeout: 30_000 });
  await modelOption.click();
  await expect(modelButton).toContainText(labelPattern, { timeout: 10_000 });
}

/** Select the staged single Gemma 12B model so requests route through med-agent-hub validation. */
export async function selectSingle12BModel(page: Page): Promise<void> {
  await selectCheckedModel(page, /Gemma 12B/i);
}

/** Select the default fast checked E4B product profile. */
export async function selectFastE4BModel(page: Page): Promise<void> {
  await selectCheckedModel(page, /Fast checked answer \(E4B\)|E4B/i);
}
