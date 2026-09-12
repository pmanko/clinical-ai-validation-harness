import { describe, expect, it } from 'vitest';
import { filterRows, inventories, projectFor, relatedRecords, sourceHref } from './model';

describe('project status browsing', () => {
  it('distinguishes active contributions, conflicts, and retired proposals across repositories', () => {
    const open = filterRows('pull-requests', 'all', '', 'open');
    expect(open.filter(r => r.repository.startsWith('openmrs/'))).toHaveLength(12);
    expect(open.some(r => r.id === 'DIGI-UW/catalyst-ai#117')).toBe(true);
    expect(open.some(r => r.id === 'pmanko/clinical-ai-validation-harness#151')).toBe(false);
    expect(filterRows('pull-requests', 'all', '151', 'closed').map(r => r.id)).toContain('pmanko/clinical-ai-validation-harness#151');
    const conflicts = filterRows('pull-requests', 'all', '', 'conflicting');
    expect(conflicts.some(r => r.id === 'openmrs/openmrs-module-chartsearchai#157')).toBe(true);
    expect(conflicts.some(r => r.id === 'DIGI-UW/openelis-work#268')).toBe(true);
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
    expect(sourceHref('reviews/2026-09-12.md')).toBe('#view=review');
    expect(sourceHref('specs/catalyst-program-roadmap.md:11')).toMatch(/catalyst-program-roadmap.md#L11$/);
  });
  it('keeps Catalyst demo surfaces and the comparison blocker in its project view', () => {
    const surfaces = filterRows('public-surfaces', 'catalyst', '').map(r => r.id);
    expect(surfaces).toEqual(expect.arrayContaining(['spark-video', 'superset-local', 'pipes-local']));
    expect(filterRows('decisions', 'catalyst', '').some(r => r.id === 'comparison-wrapper')).toBe(true);
  });
});
