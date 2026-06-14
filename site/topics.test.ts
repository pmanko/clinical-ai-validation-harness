import { describe, it, expect } from 'vitest';
import { topics } from './topics';

// Every topic link must point at a real doc/canvas on disk (red-when-broken if a
// slug is typo'd or a target is deleted). Discovered the same way App.tsx resolves.
const specSlugs = new Set(
  Object.keys(import.meta.glob('../specs/**/*.md')).map((k) => k.replace(/^\.\.\//, '').replace(/\.md$/, '')),
);
const canvasSlugs = new Set(
  Object.keys(import.meta.glob('../specs/**/*.canvas.tsx')).map((k) => k.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, '')),
);

const allLinks = topics.flatMap((t) => t.links.map((l) => ({ topic: t.id, kind: l.kind, slug: l.slug })));

describe('topic links resolve to real pages', () => {
  it.each(allLinks)('$topic → $kind $slug exists', ({ kind, slug }) => {
    const found = kind === 'canvas' ? canvasSlugs.has(slug) : specSlugs.has(slug) || slug === 'README';
    expect(found, `${kind} "${slug}" not found on disk`).toBe(true);
  });
});
