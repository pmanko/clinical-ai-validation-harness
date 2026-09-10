import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { marked } from 'marked';
import report from '../../specs/artifacts/project-status/reports/2026-09-06.md?raw';
import mergeReview from '../../specs/artifacts/project-status/reviews/2026-09-06.md?raw';
import maintenance from '../../specs/artifacts/project-status/maintenance.md?raw';
import { inventories, projects, snapshot, prSnapshot, resumeIds, dashboard, filterRows, statusOf, nextOf, sourceHref, relatedRecords, projectFor, type Project, type Row } from './model';
import './style.css';

type Location = { view: string; project: Project; query: string; state: string; kind: string; id: string };
function location(): Location {
  const p = new URLSearchParams(window.location.hash.slice(1));
  const project = p.get('project') || 'all';
  return { view: p.get('view') || 'overview', project: (project in projects ? project : 'all') as Project, query: p.get('q') || '', state: p.get('state') || 'all', kind: p.get('kind') || '', id: p.get('id') || '' };
}
function go(changes: Partial<Location>, replace = false) {
  const next = { ...location(), ...changes };
  const p = new URLSearchParams();
  Object.entries(next).forEach(([key, value]) => { if (value && value !== 'all' && !(key === 'view' && value === 'overview')) p.set(key === 'query' ? 'q' : key, value); });
  if (replace) { history.replaceState(null, '', `#${p}`); window.dispatchEvent(new HashChangeEvent('hashchange')); }
  else window.location.hash = p.toString();
}
function openRecord(kind: string, id: string) { go({ kind, id }); }
function navigate(view: string, extra: Partial<Location> = {}) { go({ view, query: '', state: 'all', id: '', kind: '', ...extra }); }
const date = (value: string) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
const label = (value: string) => ({ next_deliverable: 'Next deliverable', implementation_owner: 'Owner', acceptance: 'Acceptance still needed', implemented: 'Implemented', evidence: 'Recorded evidence', currentSignal: 'Current evidence', nextAction: 'Next action', checks: 'Automated checks', reviews: 'Review evidence', claim_limit: 'What this report establishes', current_or_superseded: 'Authority status', verified_source: 'How this was verified', headSha: 'Head revision', baseSha: 'Base revision', checkedCommitSha: 'Checked revision', relatedEffortIds: 'Related effort identifiers', related_pull_requests: 'Related pull requests', recorded_takeaway: 'Historical report takeaway', in_main_manifest: 'Listed in the main report catalog' }[value] || value.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()));
function tone(value: string) { return value === 'merged' ? 'green' : value === 'open' ? 'blue' : value === 'closed' ? 'gray' : /deferred|superseded|parked/i.test(value) ? 'gray' : 'amber'; }
function Badge({ children }: { children: string }) { return <span className={`badge ${tone(children)}`}>{children}</span>; }
function Reference({ value }: { value: string }) {
  const href = sourceHref(value);
  return href ? <a href={href} target="_blank" rel="noreferrer">{value.startsWith('http') ? value.replace(/^https?:\/\//, '') : value}<span aria-hidden="true"> ↗</span></a> : <span className={value.startsWith('artifacts/') ? 'local-reference' : ''}>{value}{value.startsWith('artifacts/') && <small>Retained local run artifact · not versioned in Git</small>}</span>;
}
function Value({ value, name = '' }: { value: any; name?: string }) {
  if (value === null || value === undefined || value === '') return <span className="muted">{name === 'implementation_owner' ? 'Unassigned' : 'Not recorded'}</span>;
  if (typeof value === 'boolean') return <>{value ? 'Yes' : 'No'}</>;
  if (Array.isArray(value)) return value.length ? <ul className="value-list">{value.map((v, i) => <li key={i}><Value value={v} /></li>)}</ul> : <span className="muted">None recorded</span>;
  if (typeof value === 'object') return <dl className="nested-values">{Object.entries(value).map(([k, v]) => <div key={k}><dt>{label(k)}</dt><dd><Value value={v} name={k} /></dd></div>)}</dl>;
  const effort = inventories.efforts.rows.find(r => r.id === value);
  if (effort) return <button className="text-button" onClick={() => openRecord('efforts', effort.id)}>{effort.title} →</button>;
  return <Reference value={String(value)} />;
}
function Detail({ state }: { state: Location }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const row = inventories[state.kind]?.rows.find(r => String(r.id) === state.id);
  useEffect(() => { if (state.id && !dialog.current?.open) dialog.current?.showModal(); if (!state.id) dialog.current?.close(); }, [state.id]);
  useEffect(() => { if (state.id) dialog.current?.scrollTo(0, 0); }, [state.id, state.kind]);
  const close = () => go({ id: '', kind: '' });
  const preferred = ['intent', 'currentSignal', 'mergeReview', 'implemented', 'evidence', 'acceptance', 'next_deliverable', 'nextAction', 'next_action', 'next_update', 'claim_limit', 'summary', 'recorded_takeaway', 'current_or_superseded', 'dependencies', 'implementation_owner', 'last_checked', 'last_work', 'source_date', 'source', 'sources', 'url', 'path', 'note'];
  const hidden = ['id', 'title', 'state', 'status', 'related_pull_requests', 'relatedEffortIds'];
  return <dialog ref={dialog} className="detail" aria-labelledby="detail-title" onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === dialog.current) close(); }}>
    <div className="detail-content">
      <div className="detail-top"><span className="eyebrow">{inventories[state.kind]?.title || 'Record'}</span><button className="icon-button" aria-label="Close details" onClick={close}>×</button></div>
      <h2 id="detail-title">{row?.title || 'Record not found'}</h2>
      {row ? <><Badge>{statusOf(row)}</Badge><p className="record-id">{row.id}</p>
        <dl className="record-fields">{preferred.filter(k => k in row).map(k => <div key={k}><dt>{label(k)}</dt><dd><Value name={k} value={row[k]} /></dd></div>)}</dl>
        {Object.entries(relatedRecords(row, state.kind)).map(([kind, records]) => records.length > 0 && <section className="related" key={kind}><h3>Related {inventories[kind].title.toLowerCase()} <span className="muted">{records.length}</span></h3>{kind === 'pull-requests' && <p className="small muted">Grouped for navigation; a merged pull request does not establish acceptance.</p>}{records.map(r => <button key={r.id} className="related-row" onClick={() => openRecord(kind, r.id)}><span>{r.title}</span><span className="muted">{r.state || '→'}</span></button>)}</section>)}
        <details className="extra"><summary>More evidence & record details</summary><dl className="record-fields">{Object.keys(row).filter(k => !preferred.includes(k) && !hidden.includes(k)).map(k => <div key={k}><dt>{label(k)}</dt><dd><Value name={k} value={row[k]} /></dd></div>)}</dl></details>
      </> : <p>This link no longer matches the inventory. Close this panel and search for the current record.</p>}
    </div>
  </dialog>;
}
function Markdown({ text }: { text: string }) {
  // Disable raw HTML and unsafe links in the repository-authored narrative.
  const renderer = new marked.Renderer();
  renderer.html = () => '';
  renderer.link = ({ href, tokens }: any) => { const safe = sourceHref(href); const text = renderer.parser.parseInline(tokens); return safe ? `<a href="${safe.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')}" ${safe.startsWith('#') ? '' : 'target="_blank" rel="noreferrer"'}>${text}</a>` : text; };
  renderer.image = () => '';
  return <article className="prose" dangerouslySetInnerHTML={{ __html: marked.parse(text, { renderer }) as string }} />;
}
const cards = dashboard.cards;
function Overview({ project }: { project: Project }) {
  const decisionCount = inventories.decisions.rows.filter(r => !/^Deferred/.test(r.state)).length;
  return <>
    <div className="overview-intro"><div><span className="eyebrow">Resume work</span><h1>Where we are</h1><p>Working implementations. Integration and acceptance still to finish.</p></div><button className="secondary" onClick={() => navigate('report')}>Read the full report <span aria-hidden="true">↗</span></button></div>
    <div className="scope-note"><strong>Latest Catalyst update: question writing is merged.</strong> The shell and appearance iteration is next, followed by Available data, result review, and the complete local dual-source owner gate. The OpenMRS trio and older contributions remain separate review work. <button className="text-button" onClick={() => openRecord('efforts', 'CAT-E11')}>Open the active iteration →</button></div>
    <div className="project-cards">{cards.filter(c => project === 'all' || project === c.project).map(c => <section className={`project-card ${c.project}`} key={c.project}><div className="card-heading"><h2>{c.title}</h2><span className="project-mark" aria-hidden="true">{c.project === 'catalyst' ? 'C' : 'CS'}</span></div><Badge>{c.status}</Badge><p className="card-summary">{c.summary}</p><p className="evidence-note">{c.evidence}</p><div className="card-actions">{c.actions.map(([title, id]) => <button key={id} onClick={() => openRecord('efforts', id)}><span>{title}</span><span aria-hidden="true">→</span></button>)}</div><button className="text-button card-browse" onClick={() => navigate('efforts', { project: c.project as Project })}>Browse {c.title} work →</button></section>)}</div>
    {(project === 'all' || project === 'shared') && <section className="shared-strip"><div><h2>Shared work</h2><p>Restore the environment, preserve local work, and align the public report catalog with the repository.</p></div><button className="text-button" onClick={() => navigate('efforts', { project: 'shared' })}>Browse shared work →</button></section>}
    {project === 'all' && <div className="metrics" aria-label="Inventory snapshot across all projects"><button onClick={() => navigate('pull-requests', { project: 'all', state: 'open' })}><strong>{prSnapshot.counts.byState.open}</strong><span>Open pull requests</span><small>Across maintained and upstream work</small></button><button onClick={() => openRecord('efforts', 'CAT-E11')}><strong>2</strong><span>Usability iteration</span><small>Shell and appearance is next</small></button><button onClick={() => navigate('decisions', { project: 'all' })}><strong>{decisionCount}</strong><span>Findings to resolve</span><small>Plus one explicitly deferred</small></button><button onClick={() => navigate('reports', { project: 'all' })}><strong>{inventories.reports.rows.length}</strong><span>Published reports</span><small>Dated evidence and its limits</small></button></div>}
    <section className="resume-section"><div className="section-heading"><h2>Start with these efforts</h2><button className="text-button" onClick={() => navigate('efforts')}>View {filterRows('efforts', project, '').length} efforts →</button></div><div className="resume-list">{resumeIds.map(id => inventories.efforts.rows.find(r => r.id === id)!).filter(r => project === 'all' || projectFor(r, 'efforts').includes(project)).map((r, i) => <button className="resume-row" key={r.id} onClick={() => openRecord('efforts', r.id)}><span className="step-number">{String(i + 1).padStart(2, '0')}</span><span><strong>{r.title}</strong><small>{r.next_deliverable}</small></span><span className="arrow" aria-hidden="true">→</span></button>)}</div></section>
    <div className="scope-note"><strong>Evidence has a date.</strong> This inventory was checked {date(snapshot)}. It is not a live GitHub feed. Implementation, a passing check, a public demo, and owner acceptance are separate signals. <button className="text-button" onClick={() => navigate('guide')}>How we keep this current →</button></div>
  </>;
}
function Table({ kind, rows }: { kind: string; rows: Row[] }) {
  return <div className="table-wrap"><table><thead><tr><th>{kind === 'pull-requests' ? 'Pull request' : 'Item'}</th><th>{kind === 'reports' ? 'Family / date' : 'Current state'}</th><th>{kind === 'pull-requests' ? 'Evidence / next action' : 'Next step / context'}</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{rows.map(r => <tr key={r.id}><td><button className="row-title" onClick={() => openRecord(kind, String(r.id))}>{r.title}</button><small>{kind === 'pull-requests' ? `${r.repository} · #${r.number}` : projectFor(r, kind).map(p => projects[p]).join(' · ')}</small></td><td>{kind === 'reports' ? <><span>{r.family}</span><small>{r.source_date}</small></> : <><Badge>{statusOf(r)}</Badge>{kind === 'pull-requests' && r.state === 'open' && <small>{r.mergeability?.mergeable === false ? 'Conflicts with base' : r.mergeability?.mergeable === true ? 'Mergeable at snapshot' : 'Mergeability not recorded'}</small>}</>}</td><td><p>{nextOf(r) || r.currentSignal || r.role || 'Open details for the recorded evidence.'}</p></td><td><button className="row-open" aria-label={`Open ${r.title}`} onClick={() => openRecord(kind, String(r.id))}>→</button></td></tr>)}</tbody></table></div>;
}
function Inventory({ state }: { state: Location }) {
  const inv = inventories[state.view];
  if (!inv) return <div className="empty"><h1>Page not found</h1><button className="secondary" onClick={() => navigate('overview')}>Return to overview</button></div>;
  const rows = filterRows(state.view, state.project, state.query, state.state);
  function download() { const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${state.view}-${snapshot}.json`; a.click(); URL.revokeObjectURL(url); }
  return <><div className="page-heading"><div><span className="eyebrow">Inventory</span><h1>{inv.title}</h1><p>{inv.description}</p></div><button className="secondary" onClick={download}>Export this view ↓</button></div><div className="table-toolbar"><span aria-live="polite"><strong>{rows.length}</strong> of {inv.rows.length} records</span><div>{state.view === 'pull-requests' && <select aria-label="Pull request state" value={state.state} onChange={e => go({ state: e.target.value })}><option value="all">All states</option><option value="open">Open</option><option value="conflicting">Open with conflicts</option><option value="merged">Merged</option><option value="closed">Closed without merge</option></select>}{state.view === 'efforts' && <select aria-label="Effort focus" value={state.state} onChange={e => go({ state: e.target.value })}><option value="all">All work</option><option value="resume">Resume first</option><option value="later">Later, deferred & historical</option></select>}{(state.query || state.state !== 'all' || state.project !== 'all') && <button className="text-button" onClick={() => go({ query: '', state: 'all', project: 'all' })}>Clear filters</button>}</div></div>{rows.length ? <Table kind={state.view} rows={rows} /> : <div className="empty"><h2>No matching records</h2><p>Try another phrase or clear the project and status filters.</p><button className="secondary" onClick={() => go({ query: '', state: 'all', project: 'all' })}>Clear filters</button></div>}</>;
}
function Search({ state }: { state: Location }) {
  const results = Object.keys(inventories).map(kind => ({ kind, rows: filterRows(kind, state.project, state.query) })).filter(g => g.rows.length);
  return <><div className="page-heading"><div><span className="eyebrow">Across the inventory</span><h1>Search results</h1><p>{state.query ? `Matches for “${state.query}”` : 'Search by topic, source, repository, or a pull request number.'}</p></div></div>{state.query && (results.length ? results.map(g => <section className="search-group" key={g.kind}><div className="section-heading"><h2>{inventories[g.kind].title} <span className="muted">{g.rows.length}</span></h2><button className="text-button" onClick={() => go({ view: g.kind, state: 'all' })}>View table →</button></div>{g.rows.map(r => <button className="search-result" key={r.id} onClick={() => openRecord(g.kind, String(r.id))}><strong>{r.title}</strong><span>{statusOf(r)}</span></button>)}</section>) : <div className="empty"><h2>No matching records</h2><p>Try a shorter phrase or choose All projects.</p></div>)}</>;
}
function App() {
  const [state, setState] = useState(location);
  const [menu, setMenu] = useState(false);
  useEffect(() => { const onHash = () => setState(location()); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  useEffect(() => { document.title = `${state.view === 'overview' ? 'Project overview' : inventories[state.view]?.title || 'Project status'} · Open Clinical AI`; setMenu(false); window.scrollTo(0, 0); }, [state.view, state.project]);
  const nav = (view: string, title: string, count?: number) => <button key={view} className={`nav-item ${state.view === view ? 'active' : ''}`} aria-current={state.view === view ? 'page' : undefined} onClick={() => navigate(view)}><span>{title}</span>{count !== undefined && <span className="nav-count">{count}</span>}</button>;
  return <><a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to content</a><aside className={`sidebar ${menu ? 'shown' : ''}`}><a className="brand" href="#"><span className="brand-mark">+</span><span>Open Clinical AI<small>Project workspace</small></span></a><nav aria-label="Dashboard">{nav('overview', 'Overview')}{nav('review', 'Merge review')}<span className="nav-label">Work</span>{['efforts', 'pull-requests', 'decisions', 'roadmaps'].map(k => nav(k, inventories[k].title, inventories[k].rows.length))}<span className="nav-label">Reference</span>{['artifacts', 'public-surfaces', 'reports', 'sessions', 'sources'].map(k => nav(k, inventories[k].title, inventories[k].rows.length))}{nav('report', 'Full status report')}{nav('guide', 'Keeping it current')}</nav><div className="sidebar-bottom"><span className="snapshot-dot"/> Snapshot · {date(snapshot)}<small>Maintained in the repository</small></div></aside><div className="workspace"><header className="topbar"><button className="mobile-menu icon-button" aria-label="Toggle navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}>☰</button><div className="search-field"><span aria-hidden="true">⌕</span><input type="search" aria-label="Search inventory" placeholder="Search efforts, pull requests, evidence…" value={state.query} onChange={e => go({ query: e.target.value, view: ['overview', 'report', 'review', 'guide'].includes(state.view) ? 'search' : state.view, id: '', kind: '' }, true)} /></div><span className="checked-date">Checked {date(snapshot)}</span></header><div className="project-tabs" role="group" aria-label="Filter by project">{Object.entries(projects).map(([id, title]) => <button key={id} aria-pressed={state.project === id} className={state.project === id ? 'selected' : ''} onClick={() => go({ project: id as Project, id: '', kind: '' })}>{title}</button>)}</div><main id="main-content" tabIndex={-1}>{state.view === 'overview' ? <Overview project={state.project} /> : state.view === 'search' ? <Search state={state} /> : state.view === 'report' || state.view === 'review' || state.view === 'guide' ? <><div className="report-back"><button className="text-button" onClick={() => navigate('overview')}>← Project overview</button><span className="muted">{state.view === 'review' ? 'Merge review · September 6, 2026' : state.view === 'report' ? 'Dated report · September 6, 2026' : 'Repository is the maintained source'}</span></div><Markdown text={state.view === 'review' ? mergeReview : state.view === 'report' ? report : maintenance} /></> : <Inventory state={state} />}</main><footer>Open Clinical AI · Repository status hub <span>Snapshot, not live status · {date(snapshot)}</span></footer></div><Detail state={state} /></>;
}
const root = createRoot(document.getElementById('root')!);
root.render(<App />);
if (import.meta.hot) import.meta.hot.dispose(() => root.unmount());
