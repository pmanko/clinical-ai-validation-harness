import { describe, it, expect } from 'vitest';
import { neighbors, navTree, flattenLeaves, NavSection } from './nav';

const TREE: NavSection[] = [
  {
    title: 'S',
    items: [
      { kind: 'spec', slug: 'a', title: 'A' },
      { kind: 'spec', slug: 'b', title: 'B' },
      { kind: 'spec', slug: 'c', title: 'C' },
    ],
  },
];

// prev/next must work across the COMPLETE (auto-merged) tree, not just the
// curated default — otherwise auto-discovered pages get no prev/next links.
describe('neighbors', () => {
  it('finds prev/next within a provided tree', () => {
    const { prev, next } = neighbors('b', TREE);
    expect(prev?.slug).toBe('a');
    expect(next?.slug).toBe('c');
  });
});

// Policy invariant: the public site is README + the visual canvases only. Feature
// specs / plans / briefs under specs/ are dev-internal and must NOT appear in the
// published nav. (Canvases are the exception that stays public.)
describe('public nav excludes dev specs', () => {
  const curated = flattenLeaves(navTree);
  const specMdFiles = Object.keys(import.meta.glob('../specs/**/*.md'));

  it('curates only home, README, and canvases (no spec markdown)', () => {
    for (const leaf of Object.values(curated)) {
      const ok = leaf.kind === 'home' || leaf.kind === 'canvas' || leaf.slug === 'README';
      expect(ok, `${leaf.slug} (${leaf.kind}) should not be in the public nav`).toBe(true);
    }
  });

  it.each(specMdFiles)('does not publish dev spec %s', (key) => {
    const slug = key.replace(/^\.\.\//, '').replace(/\.md$/, '');
    expect(curated[slug], `${slug} is a dev spec and must stay off the public nav`).toBeUndefined();
  });
});
