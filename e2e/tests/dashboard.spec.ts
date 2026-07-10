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

  // each arm carries its makeup: team → role→model lineup (.mq cells); single → family·params·quant
  for (let i = 0; i < n; i++) {
    const card = cards.nth(i);
    const team = await card.locator('.makeup .mq').count();
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

// The background /api/status poll must NOT clobber the user's expanded UI state: an
// arm-config panel (and its nested "full prompt") the user opens must survive repeated
// auto-refreshes. Open the first details.arm-config, wait LONGER than one poll interval,
// and assert it is STILL open with its body visible.
test('config panel stays open across auto-refresh polls', async ({ page }) => {
  // Read the poll interval out of the page JS itself (setInterval(tick, N)).
  const pollMs = await page.evaluate(() => {
    const html = document.documentElement.outerHTML;
    const m = html.match(/setInterval\(\s*tick\s*,\s*(\d+)\s*\)/);
    return m ? parseInt(m[1], 10) : 2000;
  });
  expect(pollMs, 'could not find the tick poll interval').toBeGreaterThan(0);

  const first = page.locator('.arm-card details.arm-config').first();
  await first.waitFor({ timeout: 10_000 });

  // Expand the config panel (mimic the user clicking the summary).
  await first.locator('> summary').click();
  await expect(first).toHaveJSProperty('open', true);
  await expect(first.locator('.ac-body')).toBeVisible();

  // Also expand a nested "full prompt" reveal if one exists — it must survive too.
  const nested = first.locator('details.ac-pfull').first();
  const hasNested = (await nested.count()) > 0;
  if (hasNested) {
    await nested.locator('> summary').click();
    await expect(nested).toHaveJSProperty('open', true);
  }

  // Wait across at least TWO full poll cycles so a destructive re-render would collapse it.
  await page.waitForTimeout(pollMs * 2 + 500);

  // Still open + content still visible after the refreshes.
  await expect(first, 'arm-config panel collapsed after an auto-refresh poll').toHaveJSProperty('open', true);
  await expect(first.locator('.ac-body'), 'arm-config body hidden after an auto-refresh poll').toBeVisible();
  if (hasNested) {
    await expect(nested, 'nested full-prompt panel collapsed after an auto-refresh poll').toHaveJSProperty('open', true);
  }

  const errs = (page as any)._errs as string[];
  expect(errs, `page JS errors: ${errs.join(' | ')}`).toHaveLength(0);
});

// A header is "human-readable" if it is NOT a raw backend/model id: no `med-agent-team-`
// prefix, no raw dashed model id (e.g. gemma-e4b-q8 / lfm2-2.6b), and no token carrying 2+
// hyphens. It MUST read as the title shape: coord/writer/single.
function assertReadable(label: string, txt: string) {
  const t = txt.trim();
  expect(t.length, `${label} empty`).toBeGreaterThan(0);
  expect(t, `${label} still shows a raw backend id: "${t}"`).not.toMatch(/med-agent-team-/);
  expect(t, `${label} still shows a raw model id: "${t}"`).not.toMatch(/gemma-e4b-q8|lfm2-2\.6b/);
  const dashed = t.split(/\s+/).find((w) => (w.match(/-/g) || []).length >= 2);
  expect(dashed, `${label} contains a dashed-id token: "${dashed}" in "${t}"`).toBeUndefined();
  expect(t, `${label} lacks the title shape (coord/writer/single): "${t}"`).toMatch(/coord|writer|single/);
}

// AC9 — the dashboard arm headers AND the cell-grid column headers are human-readable
// titles, never raw dashed machine ids.
test('AC9 — dashboard arm/grid headers are human-readable titles', async ({ page }) => {
  const heads = page.locator('.arm-card .arm-name');
  const n = await heads.count();
  expect(n, 'no dashboard arm headers rendered').toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    assertReadable(`dashboard arm header ${i}`, await heads.nth(i).innerText());
  }

  // cell-grid column headers (scenario × arm) — every column except the leading blank corner
  const cols = page.locator('#grid table.grid tr:first-child th:not(:first-child)');
  const c = await cols.count();
  expect(c, 'no cell-grid column headers rendered').toBeGreaterThan(0);
  for (let i = 0; i < c; i++) {
    assertReadable(`dashboard grid column header ${i}`, await cols.nth(i).innerText());
  }

  await page.locator('#arms').screenshot({ path: path.join(SHOTS, 'AC9-dashboard-readable-titles.png') });
  await page.locator('#grid').screenshot({ path: path.join(SHOTS, 'AC9-dashboard-grid-titles.png') });
});
