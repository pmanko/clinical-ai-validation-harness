import { defineConfig } from '@playwright/test';
import { runDir, authFile, baseURL } from './settings.mjs';
export default defineConfig({
  testDir: '.', testMatch: ['workflows.spec.mjs','site.spec.mjs'],
  globalSetup: './setup.mjs', globalTeardown: './teardown.mjs',
  timeout: 240_000, expect: { timeout: 30_000 },
  fullyParallel: false, workers: 1, retries: 0, forbidOnly: !!process.env.CI,
  outputDir: `${runDir}/results`,
  reporter: [['list'], ['json', { outputFile: `${runDir}/results.json` }], ['html', { outputFolder: `${runDir}/playwright-report`, open: 'never' }]],
  use: {
    baseURL, storageState: authFile,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 20_000, navigationTimeout: 60_000,
    screenshot: 'only-on-failure',
    video: 'off',
    // Traces can contain authenticated request headers. Public evidence is limited
    // to screenshots, videos and a curated assertion summary.
    trace: 'off',
  },
});
