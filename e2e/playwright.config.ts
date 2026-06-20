import { defineConfig } from '@playwright/test';

// e2e acceptance tests for the harness report + dashboard UX. The report is a
// self-contained static HTML artifact (client-renders from embedded JSON); the
// dashboard is the live validate-dashboard.py server. Screenshots are the
// reviewable artifact for each acceptance criterion.
export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  outputDir: './test-results',
  use: {
    viewport: { width: 1280, height: 1400 },
    screenshot: 'on',
  },
});
