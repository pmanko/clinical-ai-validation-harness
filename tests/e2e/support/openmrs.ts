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

export const HUB_PRESETS_PROPERTY = 'chartsearchai.hub.presets';

type HubPresetDefinition = {
  id: string;
  label: string;
  description: string;
  default: boolean;
  model: string;
  execution: Record<string, unknown>;
};

const QUICK_CHECKS = {
  temporal: 'enforce',
  confidence: 'findings',
  drug_safety: true,
};

const VERIFIED_CHECKS = {
  grounding: 'folded',
  temporal: 'enforce',
  confidence: 'levels',
  drug_safety: true,
};

const BASELINE_HUB_PRESETS: HubPresetDefinition[] = [
  {
    id: 'gemma-4-12b',
    label: 'Gemma 4 12B',
    description: 'Balanced clinical chart synthesis (Gemma 4 12B, single pass)',
    default: true,
    model: 'gemma-4-12b',
    execution: { mode: 'quick', preset_id: 'gemma-4-12b', checks: QUICK_CHECKS },
  },
  {
    id: 'gemma-4-26b',
    label: 'Gemma 4 26B',
    description: 'High-capacity clinical chart synthesis (Gemma 4 26B, single pass)',
    default: false,
    model: 'gemma-26b',
    execution: { mode: 'quick', preset_id: 'gemma-4-26b', checks: QUICK_CHECKS },
  },
  {
    id: 'gemma-4-e4b',
    label: 'Gemma 4 E4B (Fast)',
    description: 'Fast clinical chart synthesis (Gemma 4 E4B, single pass)',
    default: false,
    model: 'gemma-e4b',
    execution: { mode: 'quick', preset_id: 'gemma-4-e4b', checks: QUICK_CHECKS },
  },
  {
    id: 'qwen-3.5-9b',
    label: 'Qwen 3.5 9B',
    description: 'Alternative clinical chart synthesis (Qwen 3.5 9B, single pass)',
    default: false,
    model: 'qwen3.5-9b',
    execution: { mode: 'quick', preset_id: 'qwen-3.5-9b', checks: QUICK_CHECKS },
  },
];

const STAGED_VERIFIED_PRESETS: HubPresetDefinition[] = [
  {
    id: 'gemma-4-12b-verified',
    label: 'Gemma 4 12B (Verified)',
    description: 'Verified clinical synthesis with In-Depth (Gemma 4 12B)',
    default: false,
    model: 'gemma-4-12b',
    execution: {
      mode: 'verified',
      indepth: true,
      preset_id: 'gemma-4-12b-verified',
      checks: VERIFIED_CHECKS,
    },
  },
  {
    id: 'gemma-4-e4b-verified',
    label: 'Gemma 4 E4B (Verified)',
    description: 'Fast verified synthesis with In-Depth (Gemma 4 E4B)',
    default: false,
    model: 'gemma-e4b',
    execution: {
      mode: 'verified',
      indepth: true,
      preset_id: 'gemma-4-e4b-verified',
      checks: VERIFIED_CHECKS,
    },
  },
];

function adminAuthHeaders(): Record<string, string> {
  return {
    Authorization: `Basic ${Buffer.from(`${ADMIN_USER}:${ADMIN_PASSWORD}`).toString('base64')}`,
    'Content-Type': 'application/json',
  };
}

export async function getOpenmrsGlobalProperty(request: APIRequestContext, property: string): Promise<string | null> {
  const res = await request.get(
    `/openmrs/ws/rest/v1/systemsetting/${encodeURIComponent(property)}?v=custom:(property,value)`,
    { headers: adminAuthHeaders() },
  );
  if (res.status() === 404) {
    return null;
  }
  expect(res.ok(), `GET systemsetting ${property} failed (${res.status()}): ${await res.text()}`).toBeTruthy();
  const body = (await res.json()) as { value?: unknown };
  return typeof body.value === 'string' ? body.value : null;
}

export async function setOpenmrsGlobalProperty(
  request: APIRequestContext,
  property: string,
  value: string,
): Promise<void> {
  const headers = adminAuthHeaders();
  const updateRes = await request.post(`/openmrs/ws/rest/v1/systemsetting/${encodeURIComponent(property)}`, {
    headers,
    data: { value },
  });
  if (updateRes.ok()) {
    return;
  }
  if (updateRes.status() === 404) {
    const createRes = await request.post('/openmrs/ws/rest/v1/systemsetting', {
      headers,
      data: { property, value },
    });
    expect(
      createRes.ok(),
      `POST systemsetting ${property} failed (${createRes.status()}): ${await createRes.text()}`,
    ).toBeTruthy();
    return;
  }
  expect(
    updateRes.ok(),
    `POST systemsetting/${property} failed (${updateRes.status()}): ${await updateRes.text()}`,
  ).toBeTruthy();
}

/**
 * Temporarily append staged (`mode: 'verified'`, `indepth: true`) Hub presets alongside the existing
 * preset catalog (preserving single-default uniqueness for HubPresetCatalog), returning the prior
 * Global Property value for restoration in `afterAll`.
 */
export async function installStagedHubPresets(request: APIRequestContext): Promise<string | null> {
  const previous = await getOpenmrsGlobalProperty(request, HUB_PRESETS_PROPERTY);
  let base: HubPresetDefinition[];
  if (previous && previous.trim()) {
    const parsed = JSON.parse(previous) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) {
      throw new Error(`Expected ${HUB_PRESETS_PROPERTY} to be a non-empty JSON array when set`);
    }
    base = parsed as HubPresetDefinition[];
  } else {
    base = BASELINE_HUB_PRESETS;
  }

  const byId = new Map<string, HubPresetDefinition>();
  for (const preset of base) {
    byId.set(preset.id, preset);
  }
  const hasDefault = Array.from(byId.values()).some((preset) => preset.default === true);
  for (const staged of STAGED_VERIFIED_PRESETS) {
    const existing = byId.get(staged.id);
    byId.set(staged.id, {
      ...staged,
      default: existing?.default === true && !hasDefault ? true : existing?.default === true,
    });
  }
  if (!Array.from(byId.values()).some((preset) => preset.default === true)) {
    const first = Array.from(byId.values())[0];
    if (first) {
      byId.set(first.id, { ...first, default: true });
    }
  }
  await setOpenmrsGlobalProperty(request, HUB_PRESETS_PROPERTY, JSON.stringify(Array.from(byId.values())));
  return previous;
}

export async function restoreHubPresets(request: APIRequestContext, previousValue: string | null): Promise<void> {
  await setOpenmrsGlobalProperty(request, HUB_PRESETS_PROPERTY, previousValue ?? '');
}

/** Reset the server-side chat session for the demo patient (independent of the browser session). */
export async function resetChatSession(request: APIRequestContext): Promise<void> {
  const res = await request.post('/openmrs/ws/rest/v1/chartsearchai/chat/new', {
    headers: adminAuthHeaders(),
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

/**
 * Ensure med-agent-hub is active. Under single system-wide provider mode (`pickerVisible: false`),
 * the provider picker is intentionally absent and the profile picker is shown directly when Hub
 * is the active system provider; only click the provider picker when it is actually rendered.
 */
export async function selectHubProvider(page: Page): Promise<void> {
  const providerButton = page.getByTestId('chartsearchai-provider-picker');
  const profileButton = page.getByTestId('chartsearchai-profile-picker');
  await expect(profileButton.or(providerButton).first()).toBeVisible({ timeout: 30_000 });
  if (!(await providerButton.isVisible().catch(() => false))) {
    return;
  }
  if (await providerButton.getByText(/Med-Agent Hub|AI Hub/i).isVisible().catch(() => false)) {
    return;
  }
  await providerButton.click();
  const hubOption = page
    .getByRole('menuitemradio', { name: /Med-Agent Hub|AI Hub/i })
    .or(page.getByText(/Med-Agent Hub|AI Hub/i))
    .first();
  await expect(hubOption).toBeVisible({ timeout: 30_000 });
  await hubOption.click();
  await expect(providerButton).toContainText(/Med-Agent Hub|AI Hub/i, { timeout: 30_000 });
}

export async function selectCheckedModel(page: Page, labelPattern: RegExp = /Gemma 4 12B/i): Promise<void> {
  await selectHubProvider(page);
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

/** Select the default validated "Gemma 4 12B" preset so requests route through med-agent-hub validation. */
export async function selectSingle12BModel(page: Page): Promise<void> {
  await selectCheckedModel(page, /Gemma 4 12B/i);
}

/** Select the fast "Gemma 4 E4B (Fast)" preset. */
export async function selectFastE4BModel(page: Page): Promise<void> {
  await selectCheckedModel(page, /Gemma 4 E4B/i);
}

/** Select the verified+in-depth "Gemma 4 E4B (Verified)" preset installed by `installStagedHubPresets`. */
export async function selectStagedE4BModel(page: Page): Promise<void> {
  await selectCheckedModel(page, /Gemma 4 E4B \(Verified\)/i);
}
