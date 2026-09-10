import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { root, overviewURL } from './settings.mjs';

// Check the hosted files and browser playback, in addition to chart assertions
// and the renderer's comparisons of encoded frames with asserted screenshots.
const output = path.join(root, 'output/publication', new Date().toISOString().replace(/[:.]/g, '-'));
fs.mkdirSync(output, { recursive: true });
const galleryURL = new URL('evidence/', overviewURL).href;
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const failures = [];
page.on('pageerror', e => failures.push(e.message));
page.on('response', response => {
  if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
});
try {
  const response = await context.request.get(new URL('summary.json', galleryURL).href);
  assert.equal(response.status(), 200);
  const summary = await response.json();
  assert.equal(summary.completed, true);
  assert.equal(summary.workflows.length, 9);
  const assets = summary.workflows.flatMap(workflow => {
    assert.equal(workflow.status, 'passed');
    assert.equal(workflow.assets.filter(a => a.type === 'video/mp4').length, 1);
    assert.equal(workflow.assets.filter(a => a.type === 'text/vtt').length, 1);
    return workflow.assets;
  });
  assert.equal(new Set(assets.map(a => a.file)).size, assets.length);
  for (let i = 0; i < assets.length; i += 4) {
    await Promise.all(assets.slice(i, i + 4).map(async asset => {
      const result = await context.request.head(new URL(asset.file, galleryURL).href);
      assert.equal(result.status(), 200, asset.file);
      assert.ok(result.headers()['content-type'].startsWith(asset.type), asset.file);
    }));
  }
  await page.goto(galleryURL);
  await expect(page.locator('video')).toHaveCount(9);
  await expect(page.locator('#filter-options .gap')).toContainText('per-dashboard choice open');
  await page.screenshot({ path: path.join(output, 'gallery-desktop.png') });
  const playback = [];
  for (const workflow of summary.workflows) {
    const video = page.locator(`#${workflow.id} video`);
    await video.scrollIntoViewIfNeeded();
    await video.evaluate(async element => {
      element.muted = true;
      element.textTracks[0].mode = 'hidden';
      await element.play();
    });
    await expect.poll(() => video.evaluate(element => element.currentTime)).toBeGreaterThan(0.5);
    const state = await video.evaluate(element => {
      element.pause();
      return { width: element.videoWidth, height: element.videoHeight, duration: element.duration, cues: element.textTracks[0].cues?.length, error: element.error?.message };
    });
    assert.equal(state.width, 1440);
    assert.equal(state.height, 1160);
    assert.ok(Math.abs(state.duration - workflow.videoValidation.durationSeconds) < 0.15);
    assert.ok(state.cues > 0, `Missing captions: ${workflow.id}`);
    assert.equal(state.error, undefined);
    await video.screenshot({ path: path.join(output, `${workflow.id}-playing.png`) });
    playback.push({ workflow: workflow.id, ...state });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(galleryURL + '#filter-options');
  await expect(page.locator('#filter-options h2')).toBeInViewport();
  // Wait for smooth anchor scrolling to finish before judging the framing.
  await expect.poll(() => page.locator('#filter-options').evaluate(element => Math.round(element.getBoundingClientRect().top))).toBe(20);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: path.join(output, 'time-options-mobile.png') });
  await page.locator('#filter-options').getByRole('link', { name: 'Read the related explanation' }).click();
  await expect(page).toHaveURL(new URL('#issue-time-menu', overviewURL).href);
  await expect(page.locator('#issue-time-menu')).toBeInViewport();
  await page.screenshot({ path: path.join(output, 'overview-issue-mobile.png') });
  assert.deepEqual(failures, []);
  fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ galleryURL, run: summary.timestamp, assetsChecked: assets.length, playback, failures }, null, 2));
  console.log(`Verified ${assets.length} hosted assets, nine playing videos with captions, and mobile navigation. Screenshots: ${output}`);
} finally {
  await browser.close();
}
