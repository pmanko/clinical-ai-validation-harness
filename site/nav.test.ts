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

// Consistency invariant: every feature folder's spec.md must be CURATED in the
// hand-written navTree (human title + blurb), not left to nav-auto's collapsed
// "More documents" junk drawer. Discovered the same way App.tsx discovers specs.
describe('curated nav coverage', () => {
  const specFiles = Object.keys(import.meta.glob('../specs/*/spec.md'));
  const curated = flattenLeaves(navTree);

  it.each(specFiles)('curates %s (not relegated to More documents)', (key) => {
    const slug = key.replace(/^\.\.\//, '').replace(/\.md$/, '');
    expect(curated[slug], `${slug} is not in the curated navTree`).toBeDefined();
  });
});
