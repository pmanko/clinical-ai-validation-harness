import { describe, it, expect } from 'vitest';
import { GO_DEEPER, HERO } from './landing-content';
import { topics } from './topics';
import { canvasModules, repoMd } from './published-content';
import { flattenLeaves } from './nav';

const links = GO_DEEPER.flatMap(card => card.links);
describe('documentation entry and public sources', () => {
  it('introduces documentation rather than a competing project pitch', () => {
    expect(HERO.headline).toBe('Documentation');
    expect(HERO.valueProp).toContain('Setup guides');
    expect(GO_DEEPER.every(card => card.links.length > 0)).toBe(true);
  });

  it.each(links)('$label points to published content at $to', ({to}) => {
    const [, kind, ...rest] = to.split('/');
    const slug = rest.join('/');
    if (kind === 'topic') expect(topics.some(t => t.id === slug)).toBe(true);
    else if (kind === 'canvas') expect(canvasModules[`../${slug}.canvas.tsx`]).toBeDefined();
    else {
      expect(kind).toBe('spec');
      expect(repoMd[`../${slug}.md`]).toBeDefined();
    }
  });

  it('every published source has an explicit navigation owner', () => {
    const leaves = flattenLeaves();
    for (const path of [...Object.keys(repoMd), ...Object.keys(canvasModules)]) {
      const slug = path.slice(3).replace(/\.canvas\.tsx$|\.md$/, '');
      expect(leaves[slug], `Uncurated publication: ${path}`).toBeDefined();
    }
    expect(repoMd['../specs/008-catalyst-query-workbench/plan.md']).toBeUndefined();
  });
});
