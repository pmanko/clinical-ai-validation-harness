import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from '@playwright/test';
import { overviewURL, dashboardURL, root, runDir } from './settings.mjs';
import { recordingEnabled } from './policy.mjs';
test.use({video:{mode:recordingEnabled?'on':'off',size:{width:1440,height:1000}}});
import { watchDashboard, chart, paintedPeriods, capture, grain, range, assertTrend, attachResults, trendTitle, filters, startRecording, finishRecording } from './helpers.mjs';

test.beforeEach(async ({page}) => startRecording(page));
test.afterEach(async ({page},info) => finishRecording(page,info));

const months = ['2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05'];

test('02 · Open all 21 charts with the default hospital and care location', async ({ page }, info) => {
  const watch = await watchDashboard(page);
  const titles = await page.locator('a[href*="slice_id="]').allTextContents();
  expect(titles).toHaveLength(21);
  for (let i = 0; i < titles.length; i++) {
    await test.step(titles[i], async () => {
      const { id, plot } = await chart(page, titles[i]);
      await expect.poll(() => watch.replies.get(id)?.data?.length).toBeGreaterThan(0);
      await expect(plot).not.toContainText(/No results|Unexpected error|Unable to load/i);
      await capture(page, info, titles[i], plot);
    });
  }
  await expect(page.getByText('Definition discrepancy:', { exact: false })).toBeVisible();
  await attachResults(info, watch);
});

test('08 · Time choices and comparison selectors fit the reporting task', async ({page}, info) => {
  const watch=await watchDashboard(page);
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('ArrowDown');
  await expect(page.getByRole('option')).toHaveText(['Month','Quarter','Year']);
  await capture(page,info,'month-quarter-year-options');
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('Escape');
  const own=page.getByRole('combobox',{name:'NATIVE_FILTER-PsH68K-xwsp1NWi3i2HxI',exact:true});
  await own.press('ArrowDown');
  await expect(page.getByRole('option')).toHaveText(['91','92']);
  await capture(page,info,'hospital-only-options');
  await own.press('Escape');
  const comparison=page.getByRole('combobox',{name:'NATIVE_FILTER-E7fn9Wg9JfYAppl0ZHbXG',exact:true});
  await comparison.press('ArrowDown');
  // The preceding dropdown remains in the DOM during its closing animation.
  await expect.poll(async()=> (await page.getByRole('option').allTextContents()).sort()).toEqual(['Cohort','TEST-A','TEST-B']);
  await capture(page,info,'comparison-only-options');
  await comparison.press('Escape');
  const sectionLinks=page.locator('.dashboard-markdown a[href^="#HEADER-"]');
  expect(await sectionLinks.count()).toBeGreaterThan(0);
  const pagePath=new URL(page.url()).pathname;
  const link=sectionLinks.last(), href=await link.getAttribute('href');
  await link.click();
  await expect(page.locator(href)).toBeInViewport();
  expect(new URL(page.url()).pathname).toBe(pagePath);
  await capture(page,info,'table-of-contents-section');
  await attachResults(info,watch);
  await page.goto(overviewURL+'#open-time-menu');
  await expect(page.locator('#open-time-menu')).toContainText('entire Superset instance');
  await capture(page,info,'per-dashboard-time-gap');
});

test('03 · Switch Month → Quarter → Year with chronological labels', async ({ page }, info) => {
  const watch = await watchDashboard(page);
  const { id, plot } = await chart(page, trendTitle);
  for (const [unit, labels, values] of [
    ['Month', months, [.2,.1,1,null,0,null,.25]],
    ['Quarter', ['2025 Q4','2026 Q1','2026 Q2'], [.11,.1,.25]],
    ['Year', ['2025','2026'], [.11,3/18]],
  ]) {
    await test.step(`${unit}: selected records and drawn labels agree`, async () => {
      if (unit !== 'Month') await grain(page, unit);
      await assertTrend(watch, id, labels, values);
      await expect.poll(() => paintedPeriods(plot)).toEqual(labels);
      await capture(page, info, `${unit.toLowerCase()}-trend`, plot);
    });
  }
  await attachResults(info, watch);
  await page.goto(overviewURL+'#open-friendly-labels');
  await expect(page.locator('#open-friendly-labels')).toBeInViewport();
  await capture(page,info,'friendly-label-gap');
});

test('04 · A partial quarter excludes January and preserves all-time totals', async ({ page }, info) => {
  const watch = await watchDashboard(page);
  const { id, plot } = await chart(page, trendTitle);
  await range(page, '2026-02-01', '2026-04-01');
  await grain(page, 'Quarter');
  await assertTrend(watch, id, ['2026 Q1'], [0]);
  await expect.poll(() => paintedPeriods(plot)).toEqual(['2026 Q1']);
  await capture(page, info, 'partial-quarter-zero', plot);
  const overall = await chart(page, 'Overall inappropriate UTI diagnosis (across all UC submissions)');
  await expect.poll(() => watch.replies.get(overall.id)?.data?.find(r => r.hosp_code === '91')?.['% inappropriate UTI diagnosis']).toBe(0);
  const own = await chart(page, 'Number of UC submitted by your hospital');
  await expect(own.plot).toContainText('128');
  const cohort = await chart(page, 'Number of UC submitted by the entire cohort');
  await expect(cohort.plot).toContainText('248');
  await capture(page, info, 'all-time-totals', cohort.plot);
  await test.step('Future calendar periods do not advance the newest-data date', async () => {
    await range(page,'2025-10-01','2026-07-01');
    const latest = await chart(page,'Date of most recent data');
    await expect(latest.plot).toContainText('May 2026');
    await capture(page,info,'newest-observation-date',latest.plot);
  });
  await attachResults(info, watch);
});

test('05 · Hospital and care-location filters change the selected records', async ({ page }, info) => {
  const watch = await watchDashboard(page);
  const { id, plot } = await chart(page, trendTitle);
  await range(page, '2026-01-01', '2026-04-01');
  await page.getByRole('combobox', { name: filters.location, exact: true }).press('ArrowDown');
  await page.getByRole('option', { name: 'Emergency Department', exact: true }).click();
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await assertTrend(watch, id, ['2026-01','2026-02','2026-03'], [.5,null,2/6]);
  await capture(page, info, 'emergency-department', plot);
  await test.step('Choose hospital 92 without retaining hospital 91', async () => {
    const hospital = page.getByRole('combobox', {name:filters.hospital,exact:true});
    await hospital.press('Backspace');
    await hospital.press('Backspace');
    await hospital.press('ArrowDown');
    await page.getByRole('option',{name:'92',exact:true}).click();
    await hospital.press('Escape');
    await page.getByRole('button',{name:'Apply filters',exact:true}).click();
    await assertTrend(watch,id,['2026-01','2026-02','2026-03'],[.25,null,null],'92');
    expect(watch.replies.get(id).data.every(row => !Object.hasOwn(row,'91'))).toBe(true);
    await capture(page,info,'hospital-92',plot);
  });
  await attachResults(info, watch);
});

test('06 · Clearing selections does not combine overlapping totals', async ({ page }, info) => {
  const watch = await watchDashboard(page);
  const { id, plot } = await chart(page, trendTitle);
  await expect.poll(() => watch.replies.has(id)).toBe(true);
  await page.waitForLoadState('networkidle');
  await watch.settle();
  await page.getByRole('button', { name: 'Clear all', exact: true }).click();
  const apply = page.getByRole('button', { name: 'Apply filters', exact: true });
  if (await apply.isEnabled()) await apply.click();
  await expect.poll(() => watch.replies.get(id)?.data?.length).toBe(0);
  const emptyChart = page.locator('.dashboard-component-chart-holder').filter({has:page.getByRole('link',{name:trendTitle,exact:true})});
  await expect(emptyChart).toContainText(/No results|No data/i);
  await capture(page, info, 'empty-selections', emptyChart);
  await page.waitForLoadState('networkidle');
  await watch.settle();
  // A fresh canonical URL restores saved defaults instead of a Clear all permalink.
  await page.goto((await import('./settings.mjs')).dashboardURL);
  const restored = await chart(page, trendTitle);
  await assertTrend(watch, id, months, [.2,.1,1,null,0,null,.25]);
  await capture(page, info, 'restored-defaults', restored.plot);
  await attachResults(info, watch);
});


if (process.env.CSIM_IMPORT_EVIDENCE === '1') test('09 · Native import works while cached chart references remain stale', async ({page,context},info) => {
  const imported='http://127.0.0.1:18094/superset/dashboard/csim-full-synthetic/';
  const proof=JSON.parse(fs.readFileSync(path.join(root,'output/bundle-relationships.json')));
  const receipt=JSON.parse(fs.readFileSync(path.join(root,'output/bundle-import-receipt.json')));
  expect(proof).toMatchObject({charts:21,datasets:8,filters:6,changed_chart_identifiers:21});
  // This assertion substantiates the published gap in the pinned release.
  // When a newer importer fixes it, update the recorded claim and this check.
  await test.step('The released importer still has the reported cached-reference gap',async()=>{
    expect(proof.cached_scope_references).toMatchObject({all_match:false,global_matches:false});
    expect(proof.cached_scope_references.filters).toHaveLength(6);
    expect(proof.cached_scope_references.filters.every(f=>f.matches===false)).toBe(true);
  });
  const auth=JSON.parse(fs.readFileSync(path.join(runDir,'.import-auth.json')));
  await context.addCookies(auth.cookies);
  const watch=await watchDashboard(page,imported);
  const links=page.locator('a[href*="slice_id="]');
  const ids=await links.evaluateAll(nodes=>nodes.map(n=>Number(new URL(n.href).searchParams.get('slice_id'))).sort((a,b)=>a-b));
  expect(ids).toEqual(Object.values(receipt.charts).sort((a,b)=>a-b));
  for (const title of await links.allTextContents()) {
    const item=await chart(page,title);
    await expect.poll(()=>watch.replies.get(item.id)?.data?.length).toBeGreaterThan(0);
    await expect(item.plot).not.toContainText(/No results|Unexpected error|Unable to load/i);
  }
  const {id,plot}=await chart(page,trendTitle);
  await assertTrend(watch,id,months,[.2,.1,1,null,0,null,.25]);
  await capture(page,info,'imported-dashboard',plot);
  await grain(page,'Quarter');
  await assertTrend(watch,id,['2025 Q4','2026 Q1','2026 Q2'],[.11,.1,.25]);
  await expect.poll(()=>paintedPeriods(plot)).toEqual(['2025 Q4','2026 Q1','2026 Q2']);
  await capture(page,info,'imported-quarter',plot);
  await attachResults(info,watch);
  await info.attach('import-proof',{body:Buffer.from(JSON.stringify({...proof,bundle_sha256:receipt.bundle_sha256,baseURL:'http://127.0.0.1:18094'})),contentType:'application/json'});
  await page.goto(overviewURL+'#open-promotion');
  await expect(page.locator('#open-promotion')).toContainText('shares 20 charts');
  await capture(page,info,'production-promotion-gap');
});
