/**
 * Build-time runner for the LLM-readable full-HTML twins. Boots Vite in SSR mode
 * with CANVAS_STATIC=1 (so canvases resolve to the static-HTML backend), loads
 * prerender-entry, and writes every twin + welcome.html + llms.txt + llms-full.txt
 * into dist/ alongside the SPA. Run after `vite build`.
 *
 * Pure I/O glue: all logic lives in prerender-lib (unit-tested) and prerender-entry
 * (covered by prerender-entry.test.ts). This file is verified by running the build.
 */
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const here = path.dirname(fileURLToPath(import.meta.url));

const META = {
  title: 'clinical-ai-validation-harness',
  summary:
    'A validation harness for clinical AI on OpenMRS and OpenELIS — specs, plans, ' +
    'and visual canvases, mirrored here as full static HTML for LLM agents.',
};

export async function prerender({ outDir = path.join(here, 'dist') } = {}) {
  process.env.CANVAS_STATIC = '1';
  const server = await createServer({
    configFile: path.join(here, 'vite.config.ts'),
    root: here,
    logLevel: 'warn',
    server: { middlewareMode: true },
    appType: 'custom',
  });
  try {
    const base = server.config.base;
    const { plan } = await server.ssrLoadModule('/prerender-entry.tsx');
    const { outputs, missing } = plan(base, META);

    if (missing.length) {
      throw new Error(`prerender: ${missing.length} nav leaf/leaves have no source file: ${missing.join(', ')}`);
    }

    const written = [];
    for (const { outPath, contents } of outputs) {
      if (!contents || contents.length < 32) {
        throw new Error(`prerender: refusing to write near-empty file ${outPath} (${contents?.length ?? 0} bytes)`);
      }
      const dest = path.join(outDir, outPath);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.writeFileSync(dest, contents, 'utf8');
      written.push(outPath);
    }
    return written;
  } finally {
    await server.close();
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  prerender()
    .then((written) => {
      console.log(`prerender: wrote ${written.length} LLM-readable files to dist/`);
    })
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}
