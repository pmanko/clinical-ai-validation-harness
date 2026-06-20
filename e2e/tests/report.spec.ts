import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

// The report under test: a report.py-rendered HTML artifact. Override with REPORT_HTML.
const REPORT = process.env.REPORT_HTML ||
  path.resolve(__dirname, '../../artifacts/validate/acee0716-526f-4ad0-988e-69a6fd08bd2a/report.html');
const SHOTS = path.resolve(__dirname, '../screenshots');
fs.mkdirSync(SHOTS, { recursive: true });
const url = /^https?:\/\//.test(REPORT) ? REPORT : 'file://' + REPORT;

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  (page as any)._errs = errors;
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.locator('.arm-card').first().waitFor({ timeout: 10_000 }).catch(() => {});
});

// AC1 — every arm shows a path badge identifying single (vanilla chartsearchai) vs team (med-agent-hub).
test('AC1 — every arm shows a single/team path badge', async ({ page }) => {
  const cards = page.locator('.arm-card');
  const n = await cards.count();
  expect(n, 'no arm cards rendered').toBeGreaterThan(0);
  const badges = page.locator('.arm-card .badge');
  expect(await badges.count(), 'one badge per arm card').toBe(n);
  for (let i = 0; i < n; i++) {
    const t = (await badges.nth(i).innerText()).trim().toUpperCase();
    expect(['TEAM', 'SINGLE'], `badge ${i} text="${t}"`).toContain(t);
  }
  await page.locator('.arm-cards').screenshot({ path: path.join(SHOTS, 'AC1-badges.png') });
});

// AC2 — every arm shows its makeup: team → role→model lineup; single → family·params·quant.
test('AC2 — every arm shows its makeup', async ({ page }) => {
  const cards = page.locator('.arm-card');
  const n = await cards.count();
  for (let i = 0; i < n; i++) {
    const card = cards.nth(i);
    // team makeup = role → readable family·params·quant (.mq cells); single = .makeup-single
    const team = await card.locator('.makeup .mq').count();
    const single = await card.locator('.makeup-single').count();
    expect(team > 0 || single > 0, `arm ${i} has neither team makeup nor single makeup`).toBeTruthy();
  }
  await page.locator('.arm-cards').screenshot({ path: path.join(SHOTS, 'AC2-makeup.png') });
});

// AC3 — judged scores lead; engineering metrics collapsed by default.
test('AC3 — scores lead, engineering metrics collapsed', async ({ page }) => {
  const eng = page.locator('details.eng');
  await expect(eng, 'engineering <details> present').toHaveCount(1);
  expect(await eng.evaluate((e: HTMLDetailsElement) => e.open), 'eng details collapsed by default').toBeFalsy();
  const engFollowsArms = await page.evaluate(() => {
    const arms = document.querySelector('.arm-cards');
    const eng = document.querySelector('details.eng');
    if (!arms || !eng) return false;
    return !!(arms.compareDocumentPosition(eng) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(engFollowsArms, 'metrics come after the arms/scores').toBeTruthy();
  await page.screenshot({ path: path.join(SHOTS, 'AC3-headline-first.png'), fullPage: true });
});

// AC4 — every major section has a plain-language "what this shows / how to read it" intro.
test('AC4 — every section has a plain-language intro', async ({ page }) => {
  const sections = page.locator('main > section, main > details.eng > section');
  const n = await sections.count();
  expect(n, 'no sections found').toBeGreaterThan(0);
  const missing: string[] = [];
  for (let i = 0; i < n; i++) {
    const sec = sections.nth(i);
    if ((await sec.locator('.intro').count()) === 0) {
      const h = await sec.locator('h1,h2,h3').first().innerText().catch(() => `(section ${i})`);
      missing.push(h.trim());
    }
  }
  await page.screenshot({ path: path.join(SHOTS, 'AC4-intros.png'), fullPage: true });
  expect(missing, `sections missing an intro: ${missing.join(' | ')}`).toHaveLength(0);
});

// AC5 — every arm has a "how this arm is configured" panel: knobs + system prompts + retrieval.
test('AC5 — every arm has a config (knobs/prompts) panel', async ({ page }) => {
  const cards = page.locator('.arm-card');
  const n = await cards.count();
  const missing: number[] = [];
  for (let i = 0; i < n; i++) {
    const panel = cards.nth(i).locator('details.arm-config');
    if ((await panel.count()) === 0) { missing.push(i); continue; }
    const txt = (await panel.innerText()).toLowerCase();
    const hasKnobs = /temp|dry|seed|ctx|context/.test(txt);
    const hasPrompt = /prompt/.test(txt);
    if (!hasKnobs || !hasPrompt) missing.push(i);
  }
  const first = page.locator('.arm-card details.arm-config').first();
  if (await first.count()) await first.evaluate((d: HTMLDetailsElement) => (d.open = true));
  await page.locator('.arm-cards').screenshot({ path: path.join(SHOTS, 'AC5-config-panel.png') });
  expect(missing, `arms missing a knobs/prompts config panel: ${missing.length}/${n}`).toHaveLength(0);
});

// AC6 — report renders clean: arms + scores populate, no JS error, no empty state.
test('AC6 — report renders clean (no JS error, content populated)', async ({ page }) => {
  expect(await page.locator('.arm-card').count(), 'arms populated').toBeGreaterThan(0);
  expect(await page.locator('table').count(), 'score table populated').toBeGreaterThan(0);
  const errs = (page as any)._errs as string[];
  expect(errs, `page JS errors: ${errs.join(' | ')}`).toHaveLength(0);
  await page.screenshot({ path: path.join(SHOTS, 'AC6-rendered.png'), fullPage: true });
});

// A header is "human-readable" if it is NOT a raw backend/model id: no `med-agent-team-`
// prefix, no raw dashed model id (e.g. gemma-e4b-q8 / lfm2-2.6b), and no token carrying 2+
// hyphens (the dashed-id signature). It MUST read as the title shape: coord/writer/single.
const RAW_ID = /med-agent-team-|gemma-e4b-q8|lfm2-2\.6b|\b\S*-\S*-\S*\b/;
function assertReadable(label: string, txt: string) {
  const t = txt.trim();
  expect(t.length, `${label} empty`).toBeGreaterThan(0);
  expect(t, `${label} still shows a raw backend id: "${t}"`).not.toMatch(/med-agent-team-/);
  expect(t, `${label} still shows a raw model id: "${t}"`).not.toMatch(/gemma-e4b-q8|lfm2-2\.6b/);
  // no token with 2+ hyphens (a dashed machine id like med-agent-team-med-liquid)
  const dashed = t.split(/\s+/).find((w) => (w.match(/-/g) || []).length >= 2);
  expect(dashed, `${label} contains a dashed-id token: "${dashed}" in "${t}"`).toBeUndefined();
  expect(t, `${label} lacks the title shape (coord/writer/single): "${t}"`).toMatch(/coord|writer|single/);
}

// AC7 — every arm-card header AND every judge-grid column header is a human-readable title,
// never a raw dashed machine id.
test('AC7 — arm/judge headers are human-readable titles, not dashed ids', async ({ page }) => {
  const heads = page.locator('.arm-card .arm-name');
  const n = await heads.count();
  expect(n, 'no arm-card headers rendered').toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    assertReadable(`arm-card header ${i}`, await heads.nth(i).innerText());
  }

  // judge-grid (heatmap) column headers — every arm column except the leading "scenario" cell
  const cols = page.locator('table.jheat thead th:not(:first-child)');
  const c = await cols.count();
  expect(c, 'no judge-grid column headers rendered').toBeGreaterThan(0);
  for (let i = 0; i < c; i++) {
    assertReadable(`judge-grid column header ${i}`, await cols.nth(i).innerText());
  }

  await page.locator('.arm-cards').screenshot({ path: path.join(SHOTS, 'AC7-readable-titles.png') });
  await page.locator('table.jheat').screenshot({ path: path.join(SHOTS, 'AC7-judge-titles.png') });
});
