import { expect } from '@playwright/test';
import { dashboardURL } from './settings.mjs';
import { sceneFor } from './scenes.mjs';
import { recordsWorkflow } from './policy.mjs';
const recording = new WeakMap();
export function startRecording(page) { recording.set(page,{started:Date.now(),scenes:[]}); }
export async function finishRecording(page, info) {
  const timeline=recording.get(page);
  if(timeline) await info.attach('video-scenes',{body:Buffer.from(JSON.stringify(timeline)),contentType:'application/json'});
}

export const filters = {
  hospital: 'NATIVE_FILTER-yTQKvlEARkQ8t2O7SfLEE',
  location: 'NATIVE_FILTER-BPP7wo77GPPbinIYZiwM8',
  grain: 'NATIVE_FILTER-KyTwDhtSKTATUbbB9Yka_',
};
export const trendTitle = 'Inappropriate UTI diagnosis (time series)';

export async function watchDashboard(page, url = dashboardURL) {
  const replies = new Map();
  const failures = [];
  const captureNotes = [];
  const pending = new Set();
  page.on('response', response => {
    if (!response.url().includes('/api/v1/chart/data')) return;
    const job = (async () => {
    if (!response.ok()) {
      const failure={time:new Date().toISOString(),status:response.status(),server:response.headers().server || null,path:new URL(response.url()).pathname,query:new URL(response.url()).search};
      failures.push(failure);
      try { failure.body=(await response.text()).slice(0,500); } catch { failure.body='Response body unavailable'; }
      return;
    }
    try {
      const request = response.request();
      const payload = request.postDataJSON() || {};
      const urlData = JSON.parse(new URL(response.url()).searchParams.get('form_data') || '{}');
      const id = Number(payload.form_data?.slice_id || urlData.slice_id);
      const body = await response.json();
      if (!response.ok() || body.result?.some(r => (r.status && r.status !== 'success') || r.error)) failures.push({ id, status: response.status(), results: body.result?.map(r => ({status:r.status,error:r.error})), filter: payload.form_data?.viz_type });
      if (id && body.result?.[0]) replies.set(id, { data: body.result[0].data, columns: body.result[0].colnames });
    } catch (error) {
      const requestFailure = response.request().failure()?.errorText;
      if (requestFailure === 'net::ERR_ABORTED' || /Network.getResponseBody.*(?:No resource|No data found)/.test(error.message)) {
        // Superset cancels obsolete requests when filters change. Chromium can
        // also discard their bodies during navigation. Preserve this diagnostic;
        // every asserted result still requires a readable response and UI state.
        captureNotes.push({status:'response body unavailable',requestFailure:requestFailure || 'body discarded'});
      } else failures.push({status:'unreadable chart response',reason:error.message});
    }
    })();
    pending.add(job);
    job.finally(() => pending.delete(job));
  });
  page.on('requestfailed', request => {
    if (request.url().includes('/api/v1/chart/data') && request.failure()?.errorText !== 'net::ERR_ABORTED') failures.push({status:'network failure',reason:request.failure()?.errorText});
  });
  // Observe text actually painted on the canvas, without changing its drawing.
  // This catches a renderer reordering dates after a correct database response.
  await page.addInitScript(() => {
    const proto = CanvasRenderingContext2D.prototype;
    const fill = proto.fillText, clear = proto.clearRect;
    proto.clearRect = function(...args) {
      if (args[0] === 0 && args[1] === 0) this.canvas.__csimPeriodLabels = [];
      return clear.apply(this, args);
    };
    proto.fillText = function(text, x, y, ...rest) {
      if (/^(?:\d{4}(?:-\d{2}| Q[1-4])?|Q[1-4] \d{4}|[A-Z][a-z]{2} \d{4})$/.test(String(text))) {
        const point = new DOMPoint(x, y).matrixTransform(this.getTransform());
        const labels = this.canvas.__csimPeriodLabels ||= [];
        labels.push({ text: String(text), x: point.x, y: point.y });
        if (labels.length > 100) labels.splice(0, labels.length - 100);
      }
      return fill.call(this, text, x, y, ...rest);
    };
  });
  await page.goto(url);
  await expect(page.getByRole('button', { name: 'Apply filters', exact: true })).toBeVisible();
  await expect(page.locator('.chart-container')).toHaveCount(21);
  return { replies, failures, captureNotes, settle: () => Promise.all([...pending]) };
}

export async function chart(page, title) {
  const href = await page.getByRole('link', { name: title, exact: true }).getAttribute('href');
  const id = Number(new URL(href, dashboardURL).searchParams.get('slice_id'));
  expect(id).toBeGreaterThan(0);
  const plot = page.locator(`#chart-id-${id}`);
  await plot.scrollIntoViewIfNeeded();
  await expect(plot.locator('canvas, table, .header-line').first()).toBeVisible();
  return { id, plot };
}

export async function paintedPeriods(plot) {
  return plot.locator('canvas').evaluateAll(canvases => {
    const labels = canvases.flatMap(c => c.__csimPeriodLabels || []);
    const unique = [...new Map(labels.map(v => [v.text, v])).values()];
    return unique.sort((a, b) => a.x - b.x).map(v => v.text);
  });
}

export async function capture(page, info, name, plot) {
  if (plot) {
    // Include the chart title and avoid Superset's sticky dashboard header.
    await plot.evaluate(element => (element.closest('.dashboard-component-chart-holder') || element).scrollIntoView({block:'center',behavior:'instant'}));
  }
  // A target chart can finish before its neighboring charts. Capture the whole
  // visible dashboard only after their requests and loading messages settle.
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('Waiting on CSiM synthetic only', {exact:true})).toHaveCount(0);
  const timeline=recording.get(page);
  if (recordsWorkflow(info.title)) await page.waitForTimeout(1800);
  if(timeline) timeline.scenes.push({...sceneFor(name,timeline.scenes.length,info.title),atSeconds:(Date.now()-timeline.started)/1000});
  await info.attach(name, { body: await page.screenshot(), contentType: 'image/png' });
}

export async function grain(page, name) {
  await page.getByRole('combobox', { name: filters.grain, exact: true }).press('ArrowDown');
  await page.getByRole('option', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
}

export async function range(page, from, until) {
  await page.getByRole('button', { name: 'Time Period', exact: true }).click();
  const editor = page.getByRole('tooltip').filter({ hasText: 'Edit time range' });
  await editor.getByRole('textbox').nth(0).fill(from);
  await editor.getByRole('textbox').nth(1).fill(until);
  await editor.getByRole('button', { name: 'APPLY', exact: true }).click();
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
}

export async function assertTrend(watch, id, labels, values, series = '91') {
  await expect.poll(() => {
    const rows = watch.replies.get(id)?.data;
    return { labels: rows?.map(row => row.time_aggregate), values: rows?.map(row => row[series]) };
  }).toEqual({ labels, values });
}

export async function attachResults(info, watch) {
  await watch.settle();
  expect(watch.failures, 'All chart requests should succeed').toEqual([]);
  await info.attach('capture-notes', {body:Buffer.from(JSON.stringify(watch.captureNotes)),contentType:'application/json'});
  await info.attach('chart-results', {
    body: Buffer.from(JSON.stringify(Object.fromEntries(watch.replies), null, 2)), contentType: 'application/json',
  });
}
