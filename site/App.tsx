import * as React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { isSection, navTree, neighbors, NavLeaf, NavSection } from './nav';

// ---------- raw module discovery (file presence; the IA lives in nav.ts) -----

const canvasModules = import.meta.glob('../specs/**/*.canvas.tsx', { eager: true }) as Record<string, { default: React.ComponentType }>;
const specModules   = import.meta.glob('../specs/**/*.md',        { eager: true }) as Record<string, { html?: string; default: string }>;
const repoMd        = import.meta.glob(['../README.md', '../docs/**/*.md'], { eager: true }) as Record<string, { html?: string; default: string }>;

function pathToSlug(p: string): string {
  return p.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, '').replace(/\.md$/, '').replace(/\.tsx$/, '');
}

function findCanvasModule(slug: string) {
  const key = Object.keys(canvasModules).find((p) => pathToSlug(p) === slug);
  return key ? canvasModules[key] : undefined;
}
function findSpecModule(slug: string) {
  // "README" maps to ../README.md; "specs/foo/bar" → ../specs/foo/bar.md
  const target = slug === 'README' ? '../README.md' : `../${slug}.md`;
  return specModules[target] ?? repoMd[target];
}

// ---------- sidebar tree ----------------------------------------------------

function SidebarSection({ section, depth }: { section: NavSection; depth: number }) {
  const isTop = depth === 0;
  const storageKey = `nav.collapsed.${depth}.${section.title}`;
  const initialCollapsed = section.collapsed === true && depth > 0;
  const [collapsed, setCollapsed] = React.useState(() => {
    if (typeof window === 'undefined') return initialCollapsed;
    const stored = window.localStorage.getItem(storageKey);
    return stored === null ? initialCollapsed : stored === '1';
  });
  React.useEffect(() => {
    if (typeof window !== 'undefined') window.localStorage.setItem(storageKey, collapsed ? '1' : '0');
  }, [storageKey, collapsed]);

  return (
    <div className={`nav-section depth-${depth}`}>
      <button
        type="button"
        className={`nav-section-header${isTop ? ' top' : ''}`}
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
      >
        <span className="caret">{collapsed ? '▸' : '▾'}</span>
        <span className="nav-section-title">{section.title}</span>
      </button>
      {!collapsed && (
        <div className="nav-section-children">
          {section.items.map((it, i) => isSection(it)
            ? <SidebarSection key={`s-${i}-${it.title}`} section={it} depth={depth + 1} />
            : <SidebarLeaf  key={`l-${i}-${it.slug}`}    leaf={it} />)}
        </div>
      )}
    </div>
  );
}

function SidebarLeaf({ leaf }: { leaf: NavLeaf }) {
  const to = leaf.kind === 'home' ? '/'
    : leaf.kind === 'canvas' ? `/canvas/${leaf.slug}`
    : `/spec/${leaf.slug}`;
  return (
    <NavLink to={to} end={leaf.kind === 'home'} className={({ isActive }) => `nav-leaf${isActive ? ' active' : ''}${leaf.kind === 'canvas' ? ' canvas' : ''}`}>
      {leaf.kind === 'canvas' && <span className="nav-leaf-badge">canvas</span>}
      <span className="nav-leaf-title">{leaf.title}</span>
    </NavLink>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-brand">clinical-ai-validation-harness</Link>
      <div className="sidebar-sub">Planning artifacts &amp; canvases</div>
      <nav className="sidebar-nav">
        {navTree.map((s, i) => <SidebarSection key={`top-${i}-${s.title}`} section={s} depth={0} />)}
      </nav>
    </aside>
  );
}

// ---------- views -----------------------------------------------------------

function HomeView() {
  const mod = findSpecModule('README');
  const html = mod?.html ?? '';
  return (
    <div className="content-prose">
      <div dangerouslySetInnerHTML={{ __html: html }} />
      <hr />
      <h2>Where to go from here</h2>
      <div className="card-grid">
        {navTree.flatMap((section) =>
          section.items.filter((x): x is NavLeaf => !isSection(x))
            .filter((x) => x.kind !== 'home')
            .map((leaf) => (
              <Link
                key={section.title + ':' + leaf.slug}
                to={leaf.kind === 'canvas' ? `/canvas/${leaf.slug}` : `/spec/${leaf.slug}`}
                className="dispatch-card"
              >
                <div className="dispatch-card-pill">{leaf.kind === 'canvas' ? 'canvas' : section.title.toLowerCase()}</div>
                <div className="dispatch-card-title">{leaf.title}</div>
                {leaf.blurb && <div className="dispatch-card-blurb">{leaf.blurb}</div>}
              </Link>
            ))
        )}
      </div>
    </div>
  );
}

function NotFoundView({ what }: { what: string }) {
  return (
    <div className="content-prose">
      <h1>Not found</h1>
      <p>No <code>{what}</code> matches that URL. <Link to="/">Back to home</Link>.</p>
    </div>
  );
}

function CanvasView({ slug }: { slug: string }) {
  const mod = findCanvasModule(slug);
  if (!mod) return <NotFoundView what="canvas" />;
  const Comp = mod.default;
  return (
    <div className="canvas-frame">
      <Comp />
      <PrevNext slug={slug} />
    </div>
  );
}

function SpecView({ slug }: { slug: string }) {
  const mod = findSpecModule(slug);
  if (!mod) return <NotFoundView what="document" />;
  const html = mod.html ?? '';
  return (
    <div className="content-prose">
      <div dangerouslySetInnerHTML={{ __html: html }} />
      <PrevNext slug={slug} />
    </div>
  );
}

function PrevNext({ slug }: { slug: string }) {
  const { prev, next } = neighbors(slug);
  if (!prev && !next) return null;
  const toFor = (leaf: NavLeaf) => leaf.kind === 'canvas' ? `/canvas/${leaf.slug}` : leaf.kind === 'home' ? '/' : `/spec/${leaf.slug}`;
  return (
    <div className="prev-next">
      {prev ? (
        <Link to={toFor(prev)} className="prev-next-link prev-next-prev">
          <span className="prev-next-arrow">←</span>
          <span className="prev-next-text">
            <span className="prev-next-label">previous</span>
            <span className="prev-next-title">{prev.title}</span>
          </span>
        </Link>
      ) : <span />}
      {next ? (
        <Link to={toFor(next)} className="prev-next-link prev-next-next">
          <span className="prev-next-text">
            <span className="prev-next-label">next</span>
            <span className="prev-next-title">{next.title}</span>
          </span>
          <span className="prev-next-arrow">→</span>
        </Link>
      ) : <span />}
    </div>
  );
}

// ---------- top app -------------------------------------------------------

export default function App() {
  const loc = useLocation();
  const path = loc.pathname.replace(/^\//, '');
  const [kind, ...rest] = path.split('/');
  const slug = rest.join('/');

  let main: React.ReactNode;
  if (!kind || kind === 'welcome')      main = <HomeView />;
  else if (kind === 'canvas')           main = <CanvasView slug={slug} />;
  else if (kind === 'spec')             main = <SpecView slug={slug} />;
  else                                  main = <HomeView />;

  return (
    <div className="layout">
      <Sidebar />
      <main className="content">{main}</main>
    </div>
  );
}
