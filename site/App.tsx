import * as React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { isSection, leafSequence, navTree, neighbors, NavLeaf, NavSection } from './nav';
import { completeNav } from './nav-auto';
import { htmlHrefFor } from './prerender-lib';
import { topics } from './topics';
import { filterEntries, toPlainText, SearchEntry } from './search';
import { HERO, PROBLEM, APPROACH, PROOF, GO_DEEPER } from './landing-content';

// Link from the interactive view to its full-static-HTML twin (the LLM-readable
// mirror emitted by the prerender pass). Same mirror-routes-minus-hash mapping.
function PlainHtmlLink({ kind, slug }: { kind: 'spec' | 'canvas'; slug: string }) {
  const href = htmlHrefFor({ kind, slug, title: '' }, import.meta.env.BASE_URL);
  return <a className="plain-html-link" href={href} title="Full static HTML — readable without JavaScript">View as plain HTML ↗</a>;
}

// ---------- raw module discovery (file presence; the IA lives in nav.ts) -----

const canvasModules = import.meta.glob('../specs/**/*.canvas.tsx', { eager: true }) as Record<string, { default: React.ComponentType }>;
const specModules   = import.meta.glob('../specs/**/*.md',        { eager: true }) as Record<string, { html?: string; default: string }>;
const repoMd        = import.meta.glob(['../README.md', '../docs/**/*.md'], { eager: true }) as Record<string, { html?: string; default: string }>;

// The curated nav defines priority/order; every other doc and canvas on disk is
// auto-discovered and appended into deep sections, so the SPA and the prerendered
// twins surface the whole repo from one source of truth.
const fullNavTree = completeNav(
  [...Object.keys(specModules), ...Object.keys(repoMd)],
  Object.keys(canvasModules),
  navTree,
);

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

// Client-side search index, built once from the same globs the SPA already loads:
// every curated/auto doc + canvas (spec bodies full-text, canvases by title/blurb)
// plus the topic pages. Works in dev and prod with no fetch.
const searchIndex: SearchEntry[] = (() => {
  const out: SearchEntry[] = [];
  for (const { leaf } of leafSequence(fullNavTree)) {
    if (leaf.kind !== 'spec' && leaf.kind !== 'canvas') continue;
    let text = '';
    if (leaf.kind === 'spec') {
      const mod = findSpecModule(leaf.slug);
      text = toPlainText(mod?.default ?? '').slice(0, 4000);
    }
    out.push({ title: leaf.title, kind: leaf.kind, slug: leaf.slug, blurb: leaf.blurb ?? '', text });
  }
  for (const t of topics) out.push({ title: t.title, kind: 'topic', slug: t.id, blurb: t.blurb, text: '' });
  return out;
})();

function searchHref(e: SearchEntry): string {
  return e.kind === 'topic' ? `/topic/${e.slug}` : e.kind === 'canvas' ? `/canvas/${e.slug}` : `/spec/${e.slug}`;
}

function SearchBox({ onNavigate }: { onNavigate: () => void }) {
  const [q, setQ] = React.useState('');
  // Prefer the prerendered search.json (canvas bodies indexed full-text); fall
  // back to the client-built index (specs full-text) when it's absent, e.g. dev.
  const [index, setIndex] = React.useState<SearchEntry[]>(searchIndex);
  React.useEffect(() => {
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}search.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (alive && Array.isArray(data) && data.length) setIndex(data as SearchEntry[]); })
      .catch(() => { /* dev / offline: keep the client index */ });
    return () => { alive = false; };
  }, []);
  const results = React.useMemo(() => filterEntries(index, q), [index, q]);
  const noMatch = q.trim().length >= 2 && results.length === 0;
  return (
    <div className="search">
      <input
        className="search-input"
        type="search"
        placeholder="Search docs…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search documentation"
      />
      {results.length > 0 && (
        <ul className="search-results">
          {results.map((e) => (
            <li key={`${e.kind}-${e.slug}`}>
              <Link to={searchHref(e)} onClick={() => { setQ(''); onNavigate(); }}>
                <span className="search-result-title">{e.title}</span>
                <span className="search-result-kind">{e.kind}</span>
                {e.blurb && <span className="search-result-blurb">{e.blurb}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {noMatch && <div className="search-empty">No matches.</div>}
    </div>
  );
}

// ---------- sidebar tree ----------------------------------------------------

function SidebarSection({ section, depth, onNavigate }: { section: NavSection; depth: number; onNavigate: () => void }) {
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
            ? <SidebarSection key={`s-${i}-${it.title}`} section={it} depth={depth + 1} onNavigate={onNavigate} />
            : <SidebarLeaf  key={`l-${i}-${it.slug}`}    leaf={it} onNavigate={onNavigate} />)}
        </div>
      )}
    </div>
  );
}

function SidebarLeaf({ leaf, onNavigate }: { leaf: NavLeaf; onNavigate: () => void }) {
  const to = leaf.kind === 'home' ? '/'
    : leaf.kind === 'canvas' ? `/canvas/${leaf.slug}`
    : `/spec/${leaf.slug}`;
  return (
    <NavLink to={to} end={leaf.kind === 'home'} onClick={onNavigate} className={({ isActive }) => `nav-leaf${isActive ? ' active' : ''}${leaf.kind === 'canvas' ? ' canvas' : ''}`}>
      {leaf.kind === 'canvas' && <span className="nav-leaf-badge">canvas</span>}
      <span className="nav-leaf-title">{leaf.title}</span>
    </NavLink>
  );
}

function Sidebar({ onClose, onNavigate }: { onClose: () => void; onNavigate: () => void }) {
  return (
    <aside id="site-sidebar" className="sidebar">
      <div className="sidebar-header">
        <Link to="/" className="sidebar-brand" onClick={onNavigate}>clinical-ai-validation-harness</Link>
        <button type="button" className="sidebar-close" onClick={onClose} aria-label="Close navigation">Close</button>
      </div>
      <div className="sidebar-sub">Planning artifacts &amp; canvases</div>
      <SearchBox onNavigate={onNavigate} />
      <nav className="sidebar-nav">
        <div className="nav-section depth-0">
          <div className="nav-section-header top nav-section-static">
            <span className="caret">▾</span><span className="nav-section-title">Browse by topic</span>
          </div>
          <div className="nav-section-children">
            {topics.map((t) => (
              <NavLink key={t.id} to={`/topic/${t.id}`} end onClick={onNavigate} className={({ isActive }) => `nav-leaf${isActive ? ' active' : ''}`}>
                <span className="nav-leaf-title">{t.title}</span>
              </NavLink>
            ))}
          </div>
        </div>
        {fullNavTree.map((s, i) => <SidebarSection key={`top-${i}-${s.title}`} section={s} depth={0} onNavigate={onNavigate} />)}
      </nav>
    </aside>
  );
}

// ---------- views -----------------------------------------------------------

function HomeView() {
  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-eyebrow">{HERO.eyebrow}</div>
        <h1>{HERO.headline}</h1>
        <p>{HERO.valueProp}</p>
      </header>

      <section className="landing-section why">
        <h2>{PROBLEM.heading}</h2>
        {PROBLEM.paragraphs.map((para, i) => (
          <p className="landing-prose" key={i}>{para}</p>
        ))}
        <p className="landing-prose">
          <Link className="landing-inline-link" to="/spec/specs/background/why-local-first-clinical-ai">
            See the evidence behind these claims →
          </Link>
        </p>
      </section>

      <section className="landing-section approach">
        <h2>{APPROACH.heading}</h2>
        <p className="landing-section-sub">{APPROACH.lead}</p>
        <div className="surface-grid">
          {APPROACH.pillars.map((pillar) => (
            <div className="surface" key={pillar.title}>
              <strong>{pillar.title}</strong> — {pillar.body}
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section proof">
        <h2>{PROOF.heading}</h2>
        <p className="landing-prose">{PROOF.body}</p>
        <div className="proof-actions">
          <a className="proof-demo-cta" href={PROOF.demoUrl} target="_blank" rel="noreferrer">{PROOF.demoLabel} ↗</a>
        </div>
        <p className="proof-honesty">{PROOF.honesty}</p>
      </section>

      <section className="landing-section go-deeper">
        <h2>Go deeper</h2>
        <p className="landing-section-sub">Follow the path that fits what you came for.</p>
        <div className="card-grid">
          {GO_DEEPER.map((card) => (
            <div className="go-deeper-card" key={card.title}>
              <div className="go-deeper-card-title">{card.title}</div>
              <div className="go-deeper-card-outcome">{card.outcome}</div>
              <div className="go-deeper-card-links">
                {card.links.map((l) => (
                  <Link className="go-deeper-link" key={l.to} to={l.to}>{l.label} →</Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
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
      <div className="plain-html-bar"><PlainHtmlLink kind="canvas" slug={slug} /></div>
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
      <div className="plain-html-bar"><PlainHtmlLink kind="spec" slug={slug} /></div>
      <div dangerouslySetInnerHTML={{ __html: html }} />
      <PrevNext slug={slug} />
    </div>
  );
}

function TopicView({ id }: { id: string }) {
  const topic = topics.find((t) => t.id === id);
  if (!topic) return <NotFoundView what="topic" />;
  return (
    <div className="content-prose">
      <p className="topic-eyebrow"><Link to="/">← all topics</Link></p>
      <h1>{topic.title}</h1>
      <p className="topic-blurb">{topic.blurb}</p>
      <ul className="doc-list">
        {topic.links.map((l) => (
          <li key={`${l.kind}-${l.slug}`}>
            <Link to={l.kind === 'canvas' ? `/canvas/${l.slug}` : `/spec/${l.slug}`}>{l.label}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PrevNext({ slug }: { slug: string }) {
  const { prev, next } = neighbors(slug, fullNavTree);
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
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const path = loc.pathname.replace(/^\//, '');
  const [kind, ...rest] = path.split('/');
  const slug = rest.join('/');

  React.useEffect(() => {
    setSidebarOpen(false);
  }, [loc.pathname]);

  React.useEffect(() => {
    if (!sidebarOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setSidebarOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [sidebarOpen]);

  let main: React.ReactNode;
  if (!kind || kind === 'welcome')      main = <HomeView />;
  else if (kind === 'canvas')           main = <CanvasView slug={slug} />;
  else if (kind === 'spec')             main = <SpecView slug={slug} />;
  else if (kind === 'topic')            main = <TopicView id={slug} />;
  else                                  main = <HomeView />;

  return (
    <div className={`layout${sidebarOpen ? ' sidebar-open' : ''}`}>
      <button
        type="button"
        className="mobile-nav-toggle"
        onClick={() => setSidebarOpen(true)}
        aria-controls="site-sidebar"
        aria-expanded={sidebarOpen}
        aria-label="Open navigation"
      >
        Menu
      </button>
      <Sidebar onClose={() => setSidebarOpen(false)} onNavigate={() => setSidebarOpen(false)} />
      <button
        type="button"
        className="sidebar-scrim"
        onClick={() => setSidebarOpen(false)}
        aria-label="Close navigation"
      />
      <main className="content">{main}</main>
    </div>
  );
}
