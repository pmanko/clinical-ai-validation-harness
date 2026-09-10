import efforts from '../../specs/artifacts/project-status/efforts.json';
import prs from '../../specs/artifacts/project-status/pull-requests.json';
import roadmaps from '../../specs/artifacts/project-status/roadmaps.json';
import artifacts from '../../specs/artifacts/project-status/artifacts.json';
import surfaces from '../../specs/artifacts/project-status/public-surfaces.json';
import reports from '../../specs/artifacts/project-status/reports.json';
import decisions from '../../specs/artifacts/project-status/decisions.json';
import sessions from '../../specs/artifacts/project-status/sessions.json';
import sources from '../../specs/artifacts/project-status/sources.json';
import overview from '../../specs/artifacts/project-status/dashboard.json';

export type Row = Record<string, any>;
export type Project = 'all' | 'chartsearch' | 'catalyst' | 'shared';
export const projects = { all: 'All projects', chartsearch: 'ChartSearchAI', catalyst: 'Catalyst', shared: 'Shared work' };
export const inventories: Record<string, { title: string; description: string; rows: Row[] }> = {
  efforts: { title: 'Efforts', description: efforts.description, rows: efforts.rows },
  'pull-requests': { title: 'Pull requests', description: 'Open contributions and recent history. All maintained-repository pull requests updated since August 1, plus open upstream contributions by pmanko and relevant predecessors. Not an all-time export.', rows: prs.pullRequests },
  roadmaps: { title: 'Roadmaps & plans', description: roadmaps.description, rows: roadmaps.rows },
  artifacts: { title: 'Artifacts & evidence', description: artifacts.description, rows: artifacts.rows },
  decisions: { title: 'Findings & decisions', description: decisions.description, rows: decisions.rows },
  'public-surfaces': { title: 'Sites & dashboards', description: surfaces.description, rows: surfaces.rows },
  reports: { title: 'Published reports', description: reports.description, rows: reports.rows },
  sessions: { title: 'Codex & Claude work', description: sessions.description, rows: sessions.rows },
  sources: { title: 'Source references', description: sources.description, rows: sources.rows.map((r) => ({ ...r, id: r.path, title: r.path })) },
};
export const snapshot = efforts.as_of;
export const prSnapshot = prs;
export const dashboard = overview;
export const resumeIds = overview.resumeIds;
export const laterIds = overview.laterIds;

function effortProject(id: string): Project {
  if (id.startsWith('CAT-')) return 'catalyst';
  if (id === 'clinical.hub') return 'shared';
  return /^(clinical\.|querystore\.|upstream\.)/.test(id) ? 'chartsearch' : 'shared';
}
export function projectFor(row: Row, kind: string): Project[] {
  const explicit = overview.projectAssociations[row.id];
  if (explicit) return explicit as Project[];
  if (kind === 'efforts') return [effortProject(row.id)];
  if (kind === 'pull-requests') {
    const related = (row.relatedEffortIds || []).map(effortProject);
    if (/openmrs/.test(row.repository)) related.push('chartsearch');
    if (/catalyst/.test(row.repository)) related.push('catalyst');
    return [...new Set<Project>(related.length ? related : ['shared'])];
  }
  const linked = String(row.effort || '').split(/;\s*/).filter(Boolean);
  if (linked.length) return [...new Set<Project>(linked.map(effortProject))];
  if (/^CAT-/.test(row.id) || /catalyst|spark/i.test(`${row.title} ${row.family} ${row.path || ''}`)) return ['catalyst'];
  if (/chartsearch|querystore|openmrs|clinical-acceptance|old-pr-disposition|prefix-reuse/i.test(`${row.id} ${row.title} ${row.family} ${row.path || ''}`)) return ['chartsearch'];
  return ['shared'];
}
export function statusOf(row: Row): string { return row.state || row.status || row.current_or_superseded || row.role || 'Reference'; }
export function nextOf(row: Row): string { return row.next_deliverable || row.nextAction || row.next_action || row.next_update || row.claim_limit || row.note || ''; }
export function filterRows(kind: string, project: Project, query: string, state = 'all'): Row[] {
  const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return (inventories[kind]?.rows || []).filter((row) => {
    if (project !== 'all' && !projectFor(row, kind).includes(project)) return false;
    if (!words.every((word) => kind === 'pull-requests' && /^#?\d+$/.test(word)
      ? row.number === Number(word.replace('#', ''))
      : JSON.stringify(row).toLowerCase().includes(word))) return false;
    if (state === 'resume' && !resumeIds.includes(row.id)) return false;
    if (state === 'later' && !laterIds.includes(row.id)) return false;
    if (['open', 'merged', 'closed'].includes(state) && row.state !== state) return false;
    if (state === 'conflicting' && !(row.state === 'open' && row.mergeability?.mergeable === false)) return false;
    return true;
  }).sort((a, b) => kind === 'pull-requests'
    ? ({ open: 0, merged: 1, closed: 2 }[a.state] ?? 3) - ({ open: 0, merged: 1, closed: 2 }[b.state] ?? 3) || String(b.updatedAt).localeCompare(String(a.updatedAt))
    : 0);
}
export function sourceHref(value: string): string | null {
  if (typeof value !== 'string') return null;
  if (/^https?:\/\//.test(value)) return value;
  const internal = value.replace(/^(\.\.\/|\.\/)+/, '').replace(/\.md$/, '');
  if (inventories[internal]) return `#view=${internal}`;
  if (internal === 'maintenance') return '#view=guide';
  if (internal === 'reviews/2026-09-06' || internal === 'specs/artifacts/project-status/reviews/2026-09-06') return '#view=review';
  const [, path, line] = value.match(/^(.*?)(?::(\d+))?$/) || [];
  const reference = inventories.sources.rows.find(r => r.path === path || r.repository_relative_path === path);
  if (reference?.url) return line ? reference.url.replace(/#.*$/, '') + `#L${line}` : reference.url;
  if (/^(specs|harness|scripts|datasets|landing|site|\.specify)\/[^\s]+$/.test(path) || path === 'README.md' || path === 'WORKSPACE.md') return `https://github.com/pmanko/clinical-ai-validation-harness/blob/main/${path}${line ? `#L${line}` : ''}`;
  return null;
}
export function relatedRecords(row: Row, kind: string) {
  if (kind === 'efforts') return {
    'pull-requests': inventories['pull-requests'].rows.filter(p => p.relatedEffortIds?.includes(row.id)),
    artifacts: inventories.artifacts.rows.filter(a => String(a.effort || '').split(/;\s*/).includes(row.id) || row.sources?.includes(a.path)),
  };
  if (kind === 'pull-requests') return { efforts: inventories.efforts.rows.filter(e => row.relatedEffortIds?.includes(e.id)) };
  return { efforts: inventories.efforts.rows.filter(e => String(row.effort || '').split(/;\s*/).includes(e.id) || e.sources?.includes(row.path || row.url)) };
}
