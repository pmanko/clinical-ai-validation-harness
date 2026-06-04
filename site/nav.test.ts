import { describe, it, expect } from 'vitest';
import { neighbors, NavSection } from './nav';

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
