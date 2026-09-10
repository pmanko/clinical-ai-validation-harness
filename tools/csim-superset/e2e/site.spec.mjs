import { test, expect } from '@playwright/test';
import { overviewURL, dashboardURL } from './settings.mjs';
import { capture, startRecording, finishRecording } from './helpers.mjs';

// Website checks run alongside dashboard checks, without recordings.
test.use({video:'off'});
test.beforeEach(async ({page}) => startRecording(page));
test.afterEach(async ({page},info) => finishRecording(page,info));

test('01 · Understand the problems and reveal supporting detail', async ({ page }, info) => {
  await page.goto(overviewURL);
  await expect(page.getByRole('heading', { name: 'What is available to use' })).toBeVisible();
  const snapshotLink=page.locator('#snapshot-resource').getByRole('link',{name:'Open CSiM in newer Superset ↗',exact:true});
  expect(await snapshotLink.evaluate(link=>link.href)).toBe('https://catalyst.openelis-global.org/superset-preview/superset/dashboard/csim-full-synthetic/');
  await expect(page.locator('details[open]')).toHaveCount(0);
  await expect(page.locator('#reported-coverage')).toContainText('cached chart references still contain old IDs');
  await expect(page.locator('#reported-coverage tbody tr')).toHaveCount(4);
  await capture(page, info, 'overview-and-available-examples');
  await page.locator('.resource.primary').scrollIntoViewIfNeeded();
  await capture(page, info, 'available-dashboards-and-evidence');
  await page.getByRole('heading', {name:'The underlying reporting need'}).scrollIntoViewIfNeeded();
  await capture(page, info, 'reporting-need');
  await capture(page, info, 'reported-issue-coverage',page.locator('#reported-coverage'));
  await test.step('Read the date-label and grouping solution', async () => {
    await page.locator('#issue-dates summary').click();
    await expect(page.locator('#issue-dates')).toContainText('A fixed Month–Year format does not adapt to quarters or years.');
    await capture(page, info, 'date-labels-and-grouping');
  });
  await test.step('Change the illustrative grouping without changing its date range', async () => {
    await page.getByRole('combobox', { name: 'Time unit', exact: true }).selectOption('quarterly');
    await expect(page.locator('#chart')).toHaveAccessibleName(/Q1 2026: 10%/);
    await capture(page, info, 'quarter-example', page.locator('#chart'));
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(overviewURL);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await capture(page, info, 'mobile-overview');
  await page.locator('.mobile-nav summary').click();
  await page.getByRole('navigation', {name:'Mobile overview sections'}).getByRole('link',{name:'1. Original issues'}).click();
  await expect(page.getByRole('heading',{name:'1. The original issues'})).toBeInViewport();
  await capture(page, info, 'mobile-issues-and-statuses');
  await page.locator('#reported-coverage').scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await capture(page, info, 'mobile-reported-coverage');
});


test('07 · Follow an issue to evidence, the dashboard and back', async ({page, context}, info) => {
  await page.goto(overviewURL+'#issue-dates');
  const issue=page.locator('#issue-dates');
  await expect(issue).toHaveAttribute('open','');
  await issue.getByRole('link',{name:'See Month → Quarter → Year →',exact:true}).click();
  await expect(page).toHaveURL(/evidence\/#time-grouping$/);
  const workflow=page.locator('#time-grouping');
  await expect(workflow.getByRole('heading',{name:'Dates, missing periods and grouping'})).toBeInViewport();
  await expect(workflow.getByText('Expected result',{exact:true})).toBeVisible();
  await expect(page.locator('#filter-options .version')).toHaveText('Superset 6.1.0 · released version');
  await expect(page.locator('#dashboard-time-units .version')).toHaveText('Newer Superset build · unreleased');
  await expect(page.locator('#filter-options').getByRole('link',{name:'Compare with the per-dashboard fix ↓'})).toHaveAttribute('href','#dashboard-time-units');
  await expect(page.locator('#dashboard-time-units').getByRole('link',{name:'Compare with the 6.1.0 workaround ↑'})).toHaveAttribute('href','#filter-options');
  await capture(page,info,'issue-to-recorded-workflow');
  const newPage=context.waitForEvent('page');
  await workflow.getByRole('link',{name:'Try in the full dashboard ↗',exact:true}).click();
  const live=await newPage;
  await expect(live.getByRole('button',{name:'Apply filters',exact:true})).toBeVisible();
  await expect(live).toHaveURL(new RegExp(dashboardURL.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  await live.getByRole('link',{name:'Dashboard overview',exact:true}).click();
  await expect(live.getByRole('heading',{name:'What is available to use'})).toBeVisible();
  await live.close();
  await page.getByRole('link',{name:'Overview',exact:true}).click();
  await expect(page.getByRole('heading',{name:'What is available to use'})).toBeVisible();
  await capture(page,info,'return-to-overview');
});
