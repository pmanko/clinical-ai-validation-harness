import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

// The dashboard under test: the LIVE validate-dashboard.py server (scripts/validate-dashboard.py),
// a long-running monitor on :8099. Override host with DASH_URL.
const DASH = process.env.DASH_URL || 'http://localhost:8099';
const SHOTS = path.resolve(__dirname, '../screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  (page as any)._errs = errors;
  await page.goto(DASH, { waitUntil: 'networkidle' });
  // The arms render after the first /api/status poll resolves.
  await page.locator('.arm-card').first().waitFor({ timeout: 10_000 }).catch(() => {});
});

// AC7 — every backend/arm in the dashboard carries a single/team path badge + its makeup
// (team → role→model; single → family·params·quant), visible on the page.
test('AC7 — every arm shows a single/team path badge + makeup', async ({ page }) => {
  const cards = page.locator('.arm-card');
  const n = await cards.count();
  expect(n, 'no arm cards rendered on the dashboard').toBeGreaterThan(0);

  // exactly one path badge per arm card, reading TEAM or SINGLE
  const badges = page.locator('.arm-card .badge');
  expect(await badges.count(), 'one badge per arm card').toBe(n);
  for (let i = 0; i < n; i++) {
    const t = (await badges.nth(i).innerText()).trim().toUpperCase();
    expect(['TEAM', 'SINGLE'], `badge ${i} text="${t}"`).toContain(t);
  }

  // each arm carries its makeup: team → role→model lineup; single → family·params·quant
  for (let i = 0; i < n; i++) {
    const card = cards.nth(i);
    const team = await card.locator('.makeup .mdl').count();
    const single = await card.locator('.makeup-single').count();
    expect(team > 0 || single > 0, `arm ${i} has neither team makeup nor single makeup`).toBeTruthy();
    if (single > 0) {
      const mq = (await card.locator('.makeup-single').innerText()).trim();
      expect(mq.length, `arm ${i} single makeup text empty`).toBeGreaterThan(0);
    }
  }
  await page.locator('#arms').screenshot({ path: path.join(SHOTS, 'AC7-dashboard-badges.png') });
});

// AC8 — the user can reach a "how this arm is configured" panel per arm
// (knobs + system prompts + retrieval). Assert knob text (temp/seed/ctx/dry) AND prompt text.
test('AC8 — every arm has a config (knobs/prompts) panel', async ({ page }) => {
  const cards = page.locator('.arm-card');
  const n = await cards.count();
  expect(n, 'no arm cards rendered on the dashboard').toBeGreaterThan(0);

  const missing: number[] = [];
  for (let i = 0; i < n; i++) {
    const panel = cards.nth(i).locator('details.arm-config');
    if ((await panel.count()) === 0) { missing.push(i); continue; }
    const txt = (await panel.innerText()).toLowerCase();
    const hasKnobs = /temp|dry|seed|ctx|context/.test(txt);
    const hasPrompt = /prompt/.test(txt);
    if (!hasKnobs || !hasPrompt) missing.push(i);
  }
  expect(missing, `arms missing a knobs/prompts config panel: ${missing.length}/${n}`).toHaveLength(0);

  // open the first panel + screenshot the expanded config
  const first = page.locator('.arm-card details.arm-config').first();
  await first.evaluate((d: HTMLDetailsElement) => (d.open = true));
  await expect(first.locator('.ac-body')).toBeVisible();
  await page.locator('#arms').screenshot({ path: path.join(SHOTS, 'AC8-dashboard-config.png') });

  const errs = (page as any)._errs as string[];
  expect(errs, `page JS errors: ${errs.join(' | ')}`).toHaveLength(0);
});
