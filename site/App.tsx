import * as React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

// Auto-discover every canvas .tsx and every spec .md in specs/. Vite resolves
// the glob at build time relative to vite.config.ts's root (= site/), so we
// reach up one level.
const canvasModules = import.meta.glob('../specs/**/*.canvas.tsx', { eager: true }) as Record<string, { default: React.ComponentType }>;
const specModules   = import.meta.glob('../specs/**/*.md',        { eager: true, query: '?raw' }) as Record<string, { html?: string; default: string }>;
// Top-level markdown (README, docs/README) — also surface them
const repoMd        = import.meta.glob(['../README.md', '../docs/**/*.md'], { eager: true, query: '?raw' }) as Record<string, { html?: string; default: string }>;

function toSlug(p: string): string {
  // ../specs/artifacts/canvases/concept-mapping-discovery.canvas.tsx
  //   → specs/artifacts/canvases/concept-mapping-discovery
  // ../specs/002-.../tasks.md
  //   → specs/002-.../tasks
  return p.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, '').replace(/\.md$/, '').replace(/\.tsx$/, '');
}

function prettyName(p: string): string {
  const base = p.split('/').pop() ?? p;
  return base
    .replace(/\.canvas\.tsx$|\.md$/g, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

type Entry = { slug: string; group: string; name: string; kind: 'canvas' | 'spec' };

const canvases: Entry[] = Object.keys(canvasModules).sort().map((p) => ({
  slug: toSlug(p),
  group: p.replace(/^\.\.\//, '').split('/').slice(0, -1).join('/') || 'specs',
  name: prettyName(p),
  kind: 'canvas',
}));

const specs: Entry[] = [...Object.keys(specModules), ...Object.keys(repoMd)].sort().map((p) => ({
  slug: toSlug(p),
  group: p.replace(/^\.\.\//, '').split('/').slice(0, -1).join('/') || '(root)',
  name: prettyName(p),
  kind: 'spec',
}));

function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = key(it);
    (out[k] ??= []).push(it);
  }
  return out;
}

function Sidebar() {
  const canvasGroups = groupBy(canvases, (e) => e.group);
  const specGroups = groupBy(specs, (e) => e.group);
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <Link to="/welcome" className="sidebar-brand">clinical-ai-validation-harness</Link>
      </div>
      <div className="sidebar-section">
        <div className="sidebar-section-label">Canvases</div>
        {Object.entries(canvasGroups).map(([group, entries]) => (
          <div key={group} className="sidebar-group">
            <div className="sidebar-group-label">{group}</div>
            {entries.map((e) => (
              <NavLink key={e.slug} to={`/canvas/${e.slug}`} className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
                {e.name}
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <div className="sidebar-section">
        <div className="sidebar-section-label">Specs &amp; Docs</div>
        {Object.entries(specGroups).map(([group, entries]) => (
          <div key={group} className="sidebar-group">
            <div className="sidebar-group-label">{group}</div>
            {entries.map((e) => (
              <NavLink key={e.slug} to={`/spec/${e.slug}`} className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
                {e.name}
              </NavLink>
            ))}
          </div>
        ))}
      </div>
    </aside>
  );
}

function blurbForCanvas(slug: string): string | undefined {
  const map: Record<string, string> = {
    'specs/roadmap':
      'Top-level feature roadmap. Lanes, priorities, dependency graph.',
    'specs/artifacts/canvases/concept-mapping-discovery':
      'M2-A — the legacy 2.7 → CIEL bridge. Transform pipeline, promotion rules, blockers, open decisions.',
    'specs/artifacts/canvases/validation-research':
      'Validation research foundation. Lanes, primitives, evals, the run-manifest spine.',
    'specs/artifacts/canvases/cross-project-comparison':
      'Side-by-side architecture of chartsearchai, openmrs_chatbot, Catalyst.',
    'specs/artifacts/canvases/clinical-ai-research-guidance':
      'Clinical-AI research vectors, evidence levels, maturity framing.',
  };
  return map[slug];
}

const docGroups: Array<{ label: string; pred: (g: string) => boolean }> = [
  { label: 'Repository overview',     pred: (g) => g === '(root)' || g === 'docs' },
  { label: 'Feature 001 (M0)',        pred: (g) => g.includes('001-harness-control-plane') },
  { label: 'Feature 002 (M2-A)',      pred: (g) => g.includes('002-openmrs-demo-data-2-8-remap') && !g.includes('contracts') && !g.includes('checklists') },
  { label: 'Feature 002 contracts',   pred: (g) => g.includes('002-openmrs-demo-data-2-8-remap/contracts') },
  { label: 'Feature 002 checklists',  pred: (g) => g.includes('002-openmrs-demo-data-2-8-remap/checklists') },
  { label: 'Planning artifacts',      pred: (g) => g.includes('artifacts/planning') },
  { label: 'Sibling-project context', pred: (g) => g.includes('artifacts/sibling-context') },
  { label: 'Handoffs',                pred: (g) => g.includes('artifacts/handoffs') },
];

function Welcome() {
  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-eyebrow">clinical-ai-validation-harness</div>
        <h1>Planning artifacts &amp; canvases</h1>
        <p>
          Public reading view for the harness's specs and canvases. Auto-deployed from <code>main</code>.
          The canvases here are rendered via a plain-React polyfill of <code>cursor/canvas</code>;
          for the authoritative version, open the matching <code>.canvas.tsx</code> in Cursor.
        </p>
        <div className="landing-stat-row">
          <div className="landing-stat"><span className="n">{canvases.length}</span> <span className="l">canvases</span></div>
          <div className="landing-stat"><span className="n">{specs.length}</span> <span className="l">specs &amp; docs</span></div>
          <div className="landing-stat"><span className="n">5</span> <span className="l">tracked sibling projects</span></div>
        </div>
      </header>

      <section className="landing-section">
        <h2>Canvases</h2>
        <p className="landing-section-sub">Topic-scoped visual dashboards. Each canvas is a single <code>.canvas.tsx</code> rendered by the polyfill.</p>
        <div className="card-grid">
          {canvases.map((c) => (
            <Link key={c.slug} to={`/canvas/${c.slug}`} className="dispatch-card">
              <div className="dispatch-card-pill">canvas</div>
              <div className="dispatch-card-title">{c.name}</div>
              <div className="dispatch-card-blurb">{blurbForCanvas(c.slug) ?? c.group}</div>
              <div className="dispatch-card-path">{c.group}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2>Specs &amp; docs</h2>
        <p className="landing-section-sub">26 markdown files: spec.md, plan.md, tasks.md, research.md, contracts, planning artifacts.</p>
        {docGroups.map(({ label, pred }) => {
          const items = specs.filter((s) => pred(s.group));
          if (items.length === 0) return null;
          return (
            <div className="doc-group" key={label}>
              <h3>{label}</h3>
              <ul className="doc-list">
                {items.map((s) => (
                  <li key={s.slug}>
                    <Link to={`/spec/${s.slug}`}>{s.name}</Link>
                    <span className="doc-path">{s.group.replace(/^specs\//, '')}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>
    </div>
  );
}

function CanvasView({ slug }: { slug: string }) {
  // Find the entry whose canonical slug matches.
  const moduleKey = Object.keys(canvasModules).find((p) => toSlug(p) === slug);
  if (!moduleKey) {
    return <div className="content-prose"><h1>Canvas not found</h1><p>No canvas registered for <code>{slug}</code>.</p></div>;
  }
  const Comp = canvasModules[moduleKey].default;
  return (
    <div className="canvas-frame">
      <Comp />
    </div>
  );
}

function SpecView({ slug }: { slug: string }) {
  const moduleKey = [...Object.keys(specModules), ...Object.keys(repoMd)].find((p) => toSlug(p) === slug);
  if (!moduleKey) {
    return <div className="content-prose"><h1>Document not found</h1><p>No markdown file registered for <code>{slug}</code>.</p></div>;
  }
  const mod = (specModules[moduleKey] ?? repoMd[moduleKey]);
  const html = mod.html ?? '';
  return (
    <div className="content-prose" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export default function App() {
  const loc = useLocation();
  const path = loc.pathname.replace(/^\//, '');
  const [kind, ...rest] = path.split('/');
  const slug = rest.join('/');

  let main: React.ReactNode;
  if (!kind || kind === 'welcome') main = <Welcome />;
  else if (kind === 'canvas') main = <CanvasView slug={slug} />;
  else if (kind === 'spec')    main = <SpecView slug={slug} />;
  else main = <Welcome />;

  return (
    <div className="layout">
      <Sidebar />
      <main className="content">{main}</main>
    </div>
  );
}
