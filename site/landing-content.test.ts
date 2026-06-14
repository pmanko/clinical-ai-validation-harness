import { describe, it, expect } from 'vitest';
import { GO_DEEPER, DEMO_URL } from './landing-content';
import { topics } from './topics';

// The landing's authored content must not rot: every "go deeper" deep-link has to
// resolve to a real route (a spec/canvas file on disk, or a real topic id) — the
// guard against silent scent-link rot when files move or get renamed.
const specKeys = new Set(Object.keys(import.meta.glob('../specs/**/*.md')));
const repoMdKeys = new Set(Object.keys(import.meta.glob(['../README.md', '../docs/**/*.md'])));
const canvasSlugs = new Set(
  Object.keys(import.meta.glob('../specs/**/*.canvas.tsx')).map((p) =>
    p.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, ''),
  ),
);
const topicIds = new Set(topics.map((t) => t.id));

function specExists(slug: string): boolean {
  const target = slug === 'README' ? '../README.md' : `../${slug}.md`;
  return specKeys.has(target) || repoMdKeys.has(target);
}

const links = GO_DEEPER.flatMap((card) => card.links.map((l) => ({ card: card.title, ...l })));

describe('landing-content GO_DEEPER', () => {
  it('has four reader paths, each with at least two deep-links', () => {
    expect(GO_DEEPER).toHaveLength(4);
    for (const card of GO_DEEPER) expect(card.links.length).toBeGreaterThanOrEqual(2);
  });

  it.each(links)('"$card" → $to resolves to a real route', ({ to }) => {
    const m = /^\/(spec|canvas|topic)\/(.+)$/.exec(to);
    expect(m, `${to} is not a /spec|/canvas|/topic route`).not.toBeNull();
    const [, kind, rest] = m!;
    if (kind === 'spec') expect(specExists(rest), `${rest} (spec) missing on disk`).toBe(true);
    else if (kind === 'canvas') expect(canvasSlugs.has(rest), `${rest} (canvas) missing on disk`).toBe(true);
    else expect(topicIds.has(rest), `${rest} (topic) is not a real topic id`).toBe(true);
  });

  it('points the demo CTA at the live clinical demo', () => {
    expect(DEMO_URL).toContain('openclinai.org');
  });
});
