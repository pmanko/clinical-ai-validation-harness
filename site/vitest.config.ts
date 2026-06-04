import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Tests for the static-site prerender layer. The tdd-guard-vitest reporter writes
// the same .claude/tdd-guard/data/test.json the pytest reporter feeds, so the
// in-session red-first gate covers the site's TS/TSX just like the Python harness.
//
// We mirror the two prerender-relevant bits of vite.config.ts so prerender-entry
// resolves the same way under vitest: the markdown-as-html transform (docs get an
// `html` export) and the cursor/canvas alias pinned to the STATIC backend (the
// CANVAS_STATIC=1 path the prerender uses), so plan() is exercised in-process.
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
  plugins: [react(), markdownAsHtml()],
  resolve: {
    alias: {
      'cursor/canvas': path.resolve(__dirname, 'cursor-canvas-static.tsx'),
    },
  },
  test: {
    environment: 'node',
    include: ['**/*.test.ts', '**/*.test.tsx'],
    reporters: [
      'default',
      ['tdd-guard-vitest', { projectRoot: path.resolve(__dirname, '..') }],
    ],
  },
});
