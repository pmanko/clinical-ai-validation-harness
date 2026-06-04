import { describe, it, expect } from 'vitest';
import { completeNav } from './nav-auto';
import { flattenLeaves, NavSection } from './nav';

const CURATED: NavSection[] = [
  {
    title: 'Start here',
    items: [
      { kind: 'home', slug: 'welcome', title: 'Welcome' },
      { kind: 'spec', slug: 'README', title: 'README' },
    ],
  },
];

// The core requirement: every doc/canvas on disk must surface as a nav leaf, so
// the (now-complete) nav drives both the SPA and the prerendered twins — nothing
// is silently omitted, and curated pages are not duplicated.
describe('completeNav', () => {
  it('surfaces every on-disk doc and canvas as a leaf, without duplicating curated ones', () => {
    const docKeys = ['../README.md', '../specs/004-x/spec.md', '../docs/cloud-deploy.md'];
    const canvasKeys = ['../specs/artifacts/canvases/catalyst-fhir-sidecar.canvas.tsx'];
    const slugs = Object.keys(flattenLeaves(completeNav(docKeys, canvasKeys, CURATED)));
    expect(slugs).toContain('specs/004-x/spec');
    expect(slugs).toContain('docs/cloud-deploy');
    expect(slugs).toContain('specs/artifacts/canvases/catalyst-fhir-sidecar');
    expect(slugs.filter((s) => s === 'README')).toHaveLength(1);
  });

  it('places uncurated pages in a deep collapsed section, grouped by directory, after the curated ones', () => {
    const tree = completeNav(
      ['../specs/004-x/spec.md', '../specs/004-x/plan.md', '../docs/cloud-deploy.md'],
      [],
      CURATED,
    );
    expect(tree[0].title).toBe('Start here'); // curated stays first / top-priority
    const more = tree.find((s) => s.title === 'More documents') as NavSection;
    expect(more).toBeTruthy();
    expect(more.collapsed).toBe(true);
    const groupTitles = (more.items as NavSection[]).map((g) => g.title);
    expect(groupTitles).toContain('specs/004-x');
    expect(groupTitles).toContain('docs');
  });
});
