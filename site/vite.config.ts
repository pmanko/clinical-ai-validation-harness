import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import fs from 'node:fs';

// Base path for GitHub Pages user-scope project page.
// pmanko.github.io/clinical-ai-validation-harness/
const BASE = '/clinical-ai-validation-harness/';

// Plugin: import *.md files as { default: rawString, html: renderedHtml, frontmatter, headings }
// Lightweight; uses `marked` at build time to compute html. Keeps the bundle small.
function markdownAsHtml() {
  return {
    name: 'markdown-as-html',
    async transform(src: string, id: string) {
      if (!id.endsWith('.md')) return null;
      const { marked } = await import('marked');
      const html = marked.parse(src);
      const code = `export const raw = ${JSON.stringify(src)};\nexport const html = ${JSON.stringify(html)};\nexport default raw;`;
      return { code, map: null };
    },
  };
}

export default defineConfig({
  base: BASE,
  plugins: [react(), markdownAsHtml()],
  resolve: {
    alias: {
      // Canvases in specs/ import from 'cursor/canvas'; resolve to our polyfill.
      // The prerender pass sets CANVAS_STATIC=1 to swap in the static-HTML
      // backend (charts/graphs -> tables) for the LLM-readable twins; the SPA
      // build leaves it unset and keeps the interactive recharts/SVG polyfill.
      'cursor/canvas': path.resolve(
        __dirname,
        process.env.CANVAS_STATIC ? 'cursor-canvas-static.tsx' : 'cursor-canvas.tsx',
      ),
    },
  },
  // The canvases live OUTSIDE the site/ root; allow Vite to read from the parent tree.
  server: {
    fs: { allow: [path.resolve(__dirname, '..')] },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
