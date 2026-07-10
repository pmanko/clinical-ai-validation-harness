import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8088';
const VIDEO_MODE: 'on' | 'off' | 'retain-on-failure' =
  process.env.E2E_VIDEO === 'on'
    ? 'on'
    : process.env.E2E_VIDEO === 'off'
      ? 'off'
      : 'retain-on-failure';
const SCREENSHOT_MODE: 'on' | 'off' | 'only-on-failure' =
  process.env.E2E_SCREENSHOT === 'on'
    ? 'on'
    : process.env.E2E_SCREENSHOT === 'off'
      ? 'off'
      : 'only-on-failure';
const SLOW_MO_MS = Number.parseInt(process.env.E2E_SLOWMO_MS ?? '0', 10) || 0;

export default defineConfig({
  testDir: './specs',
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['github']] : [['list']],
  use: {
    baseURL: BASE_URL,
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
    trace: 'retain-on-failure',
    screenshot: SCREENSHOT_MODE,
    video: VIDEO_MODE,
    ignoreHTTPSErrors: true,
    launchOptions: {
      slowMo: SLOW_MO_MS,
    },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
