import fs from 'node:fs';
import { chromium, expect } from '@playwright/test';
import path from 'node:path';
import { baseURL, password, username, authFile, runDir, root } from './settings.mjs';
export default async function setup() {
  if (!password) throw new Error('Set CSIM_ADMIN_PASSWORD or provide the private demo env file.');
  fs.mkdirSync(runDir, { recursive: true, mode: 0o700 });
  const browser = await chromium.launch();
  // Authentication is outside the recorded test context.
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.goto(`${baseURL}/login/`);
    await page.locator('input#username').fill(username);
    await page.locator('input#password').fill(password);
    await page.locator('input[type="submit"], button[type="submit"]').click();
    await expect(page).not.toHaveURL(/\/login\//);
    await context.storageState({ path: authFile });
    fs.chmodSync(authFile, 0o600);
    if(process.env.CSIM_IMPORT_EVIDENCE === '1') {
      const localEnv=fs.readFileSync(path.join(root,'.env.local'),'utf8');
      const importPassword=localEnv.match(/^CSIM_ADMIN_PASSWORD=(.+)$/m)?.[1];
      if(!importPassword)throw new Error('Missing independent import-test credentials');
      // Cookies share a hostname across ports; authenticate each installation
      // in its own context so the first login cannot bypass the second form.
      const importContext=await browser.newContext();
      try {
        const importPage=await importContext.newPage();
        await importPage.goto('http://127.0.0.1:18094/login/');
        await importPage.locator('input#username').fill('demo');
        await importPage.locator('input#password').fill(importPassword);
        await importPage.locator('input[type="submit"], button[type="submit"]').click();
        await expect(importPage).not.toHaveURL(/\/login\//);
        const importAuth=path.join(runDir,'.import-auth.json');
        await importContext.storageState({path:importAuth});
        fs.chmodSync(importAuth,0o600);
      } finally { await importContext.close(); }
    }
  } finally { await browser.close(); }
}
