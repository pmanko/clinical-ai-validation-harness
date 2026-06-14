import { describe, it, expect } from 'vitest';
import { filterEntries, SearchEntry } from './search';

const E: SearchEntry[] = [
  { title: 'Validation research', kind: 'canvas', slug: 'a', blurb: 'evidence model', text: 'traceable records' },
  { title: 'Clinical KB brief', kind: 'spec', slug: 'b', blurb: 'knowledge base', text: 'WHO IMCI offline local models' },
];

describe('filterEntries', () => {
  it('requires every term to match, ranks title over body, and ignores short queries', () => {
    // title hit
    expect(filterEntries(E, 'validation').map((e) => e.slug)).toEqual(['a']);
    // body-only multi-term hit on the other entry
    expect(filterEntries(E, 'offline models').map((e) => e.slug)).toEqual(['b']);
    // a term that matches nothing → no results (AND semantics)
    expect(filterEntries(E, 'offline zzzznope')).toEqual([]);
    // too short → no results
    expect(filterEntries(E, 'x')).toEqual([]);
  });
});
