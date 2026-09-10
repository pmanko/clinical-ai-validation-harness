import { describe, expect, it } from 'vitest';
import { filterRows, inventories, projectFor, relatedRecords, sourceHref } from './model';

describe('project status browsing', () => {
  it('finds the complete open and conflicting upstream sets without counting merged history', () => {
    expect(filterRows('pull-requests', 'all', '', 'open')).toHaveLength(12);
    const conflicts = filterRows('pull-requests', 'all', '', 'conflicting');
    expect(conflicts).toHaveLength(7);
    expect(conflicts.some(r => r.id === 'openmrs/openmrs-module-querystore#68')).toBe(false);
  });
  it('combines project, search, and state filters and gives an empty result for a miss', () => {
    expect(filterRows('pull-requests', 'chartsearch', 'querystore 68', 'open').map(r => r.id)).toEqual(['openmrs/openmrs-module-querystore#68']);
    expect(filterRows('efforts', 'catalyst', 'Spark').some(r => r.id === 'CAT-E01')).toBe(true);
    expect(filterRows('efforts', 'catalyst', 'no-such-effort-xyz')).toEqual([]);
    expect(projectFor(inventories.efforts.rows.find(r => r.id === 'clinical.hub')!, 'efforts')).toEqual(['shared']);
  });
  it('connects an effort to its actual pull request records and preserves acceptance evidence', () => {
    const effort = inventories.efforts.rows.find(r => r.id === 'clinical.dual_provider')!;
    const linked = relatedRecords(effort, 'efforts')['pull-requests'];
    expect(linked.some(r => r.id === 'openmrs/openmrs-module-chartsearchai#157')).toBe(true);
    expect(new Set(linked.map(r => r.id)).size).toBe(linked.length);
    expect(effort.acceptance).toBeTruthy();
  });
  it('uses portable repository paths and leaves unversioned artifacts as references', () => {
    expect(sourceHref('README.md')).toMatch(/\/blob\/(?:main|[0-9a-f]{40})\/README\.md/);
    expect(sourceHref('javascript:alert(1)')).toBeNull();
    expect(sourceHref('artifacts/chartsearchai-local/relay-probe.json')).toBeNull();
    expect(sourceHref('../pull-requests.md')).toBe('#view=pull-requests');
    expect(sourceHref('maintenance.md')).toBe('#view=guide');
    expect(sourceHref('specs/catalyst-program-roadmap.md:11')).toMatch(/catalyst-program-roadmap.md#L11$/);
  });
  it('keeps Catalyst demo surfaces and the comparison blocker in its project view', () => {
    const surfaces = filterRows('public-surfaces', 'catalyst', '').map(r => r.id);
    expect(surfaces).toEqual(expect.arrayContaining(['spark-video', 'superset-local', 'pipes-local']));
    expect(filterRows('decisions', 'catalyst', '').some(r => r.id === 'comparison-wrapper')).toBe(true);
  });
});
