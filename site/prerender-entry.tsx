/**
 * Vite-SSR entry for the prerender pass. It reuses the SAME import.meta.glob
 * discovery as App.tsx so docs and canvases resolve byte-for-byte the way the SPA
 * sees them — the markdown plugin supplies each doc's rendered `html`, and the
 * cursor/canvas alias (CANVAS_STATIC=1) supplies the static-HTML canvas backend.
 * renderToStaticMarkup turns each canvas component into the agent-readable body;
 * planOutputs (pure, unit-tested) composes the file set the runner writes.
 *
 * Exempt from the red-first gate (it is irreducible Vite/glob glue), but covered
 * end-to-end by prerender-entry.test.ts, which runs this against the real repo.
 */
import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { leafSequence, navTree } from './nav';
import { completeNav } from './nav-auto';
import { planOutputs, type RenderedPage } from './prerender-lib';
import { topics } from './topics';

const canvasModules = import.meta.glob('../specs/**/*.canvas.tsx', { eager: true }) as Record<
  string,
  { default: React.ComponentType }
>;
// Published site = README + canvases + mission/background + research (allowlist); everything
// else under specs/ is dev-internal (mirror of App.tsx).
const repoMd = import.meta.glob([
  '../README.md',
  '../specs/background/**/*.md',
  '../specs/artifacts/planning/global-health-ai-background-research-2026-06-14.md',
  '../specs/artifacts/planning/guardrails-methodology-research.md',
], { eager: true }) as Record<
  string,
  { html?: string; raw?: string; default: string }
>;

function pathToSlug(p: string): string {
  return p.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, '').replace(/\.md$/, '').replace(/\.tsx$/, '');
}
function findCanvas(slug: string) {
  const key = Object.keys(canvasModules).find((p) => pathToSlug(p) === slug);
  return key ? canvasModules[key] : undefined;
}
function findSpec(slug: string) {
  const target = slug === 'README' ? '../README.md' : `../${slug}.md`;
  return repoMd[target];
}

/** Build the full output plan, with every doc/canvas body rendered via Vite. */
export function plan(base: string, meta: { title: string; summary: string }) {
  // Build the nav from the published allowlist (README + background + research) plus
  // all canvases. Dev-internal specs under specs/ are not published. (Mirrors App.tsx.)
  const fullTree = completeNav(
    Object.keys(repoMd),
    Object.keys(canvasModules),
    navTree,
  );
  const leaves = leafSequence(fullTree).map((x) => x.leaf);
  const rendered: Record<string, RenderedPage> = {};
  const missing: string[] = [];
  for (const leaf of leaves) {
    if (leaf.kind === 'spec') {
      const mod = findSpec(leaf.slug);
      if (!mod) {
        missing.push(`spec:${leaf.slug}`);
        continue;
      }
      rendered[leaf.slug] = { innerHtml: mod.html ?? '', raw: mod.raw ?? mod.default ?? '' };
    } else if (leaf.kind === 'canvas') {
      const mod = findCanvas(leaf.slug);
      if (!mod) {
        missing.push(`canvas:${leaf.slug}`);
        continue;
      }
      rendered[leaf.slug] = { innerHtml: renderToStaticMarkup(React.createElement(mod.default)) };
    }
  }
  return { outputs: planOutputs({ leaves, base, meta, rendered, topics }), missing };
}
