import { test, expect } from '@playwright/test';
import { previewURL, previewAuthFile } from './settings.mjs';
import { recordingEnabled } from './policy.mjs';
import { watchDashboard, chart, capture, grain, assertTrend, attachResults, trendTitle, filters, startRecording, finishRecording } from './helpers.mjs';

test.use({storageState:previewAuthFile,video:{mode:recordingEnabled?'on':'off',size:{width:1440,height:1000}}});
test.beforeEach(async ({page}) => startRecording(page));
test.afterEach(async ({page},info) => finishRecording(page,info));

test('10 · Different dashboards retain different Time Unit choices in the snapshot', async ({page},info) => {
  const fullURL=previewURL+'/superset/dashboard/csim-full-synthetic/';
  const watch=await watchDashboard(page,fullURL);
  const {id,plot}=await chart(page,trendTitle);
  await assertTrend(watch,id,['2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05'],[.2,.1,1,null,0,null,.25]);
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('ArrowDown');
  await expect(page.getByRole('option')).toHaveText(['Month','Quarter','Year']);
  await capture(page,info,'preview-csim-options');
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('Escape');
  await grain(page,'Quarter');
  await assertTrend(watch,id,['2025 Q4','2026 Q1','2026 Q2'],[.11,.1,.25]);
  await capture(page,info,'preview-csim-quarter',plot);

  await page.goto(previewURL+'/superset/dashboard/hourly-reporting-preview/');
  await expect(page.locator('.chart-container')).toHaveCount(1);
  const hourly=await chart(page,'Specimens by collection time');
  const control=page.getByRole('combobox',{name:'NATIVE_FILTER-preview-hourly',exact:true});
  await expect.poll(()=>watch.replies.get(hourly.id)?.data?.length).toBe(48);
  expect(watch.replies.get(hourly.id).data.map(row=>row.Specimens)).toEqual(Array.from({length:48},(_,i)=>i%2===0?2:4));
  await control.press('ArrowDown');
  await expect.poll(async()=> (await page.getByRole('option').allTextContents()).sort()).toEqual(['Day','Hour','Week']);
  await capture(page,info,'preview-hourly-options');
  await page.getByRole('option',{name:'Day',exact:true}).click();
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await expect.poll(()=>watch.replies.get(hourly.id)?.data?.map(row=>row.Specimens)).toEqual([72,72]);
  await capture(page,info,'preview-daily-totals',hourly.plot);
  await page.reload();
  await control.press('ArrowDown');
  await expect.poll(async()=> (await page.getByRole('option').allTextContents()).sort()).toEqual(['Day','Hour','Week']);
  await control.press('Escape');

  await page.goto(fullURL);
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('ArrowDown');
  await expect(page.getByRole('option')).toHaveText(['Month','Quarter','Year']);
  await page.getByRole('combobox',{name:filters.grain,exact:true}).press('Escape');
  await expect(page.locator('a[href*="slice_id="]')).toHaveCount(21);
  await attachResults(info,watch);
});
