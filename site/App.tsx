import * as React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { isSection, navTree, neighbors, NavLeaf, NavSection } from './nav';
import { completeNav } from './nav-auto';
import { htmlHrefFor } from './prerender-lib';

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
      <nav className="sidebar-nav">
        {fullNavTree.map((s, i) => <SidebarSection key={`top-${i}-${s.title}`} section={s} depth={0} onNavigate={onNavigate} />)}
      </nav>
    </aside>
  );
}

// ---------- views -----------------------------------------------------------

function HomeView() {
  // Pull a flat list of all leaves from the curated tree (so the welcome
  // page stays in lockstep with the sidebar — single source of truth).
  type LeafWithPath = { leaf: NavLeaf; topSection: NavSection; parentSection?: NavSection };
  const allLeaves: LeafWithPath[] = [];
  function walk(items: Array<NavLeaf | NavSection>, topSection: NavSection, parentSection?: NavSection) {
    for (const it of items) {
      if (isSection(it)) walk(it.items, topSection, it);
      else allLeaves.push({ leaf: it, topSection, parentSection });
    }
  }
  for (const top of fullNavTree) walk(top.items, top);

  const canvasLeaves = allLeaves.filter((x) => x.leaf.kind === 'canvas');
  const totalDocs = allLeaves.filter((x) => x.leaf.kind === 'spec').length;
  const totalCanvases = canvasLeaves.length;
  const featureCount = fullNavTree.find((s) => s.title === 'Active features')?.items.filter(isSection).length ?? 0;

  const toFor = (leaf: NavLeaf) =>
    leaf.kind === 'canvas' ? `/canvas/${leaf.slug}` : leaf.kind === 'home' ? '/' : `/spec/${leaf.slug}`;

  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-eyebrow">clinical-ai-validation-harness</div>
        <h1>Validating early clinical AI — with traceable, reviewable evidence</h1>
        <p>
          A validation harness for clinical AI tools built on OpenMRS and OpenELIS. We test real systems
          against realistic health data: chart search, query retrieval, clinical chat, and lab-system AI.
          Every validation claim traces back to specific clinical records, not just aggregate metrics.
        </p>
        <p className="landing-hero-sub">
          A plain-language tour of what we're building and why — with the full specs, research, and roadmap
          underneath, a click away.
        </p>
        <div className="landing-stat-row">
          <div className="landing-stat"><span className="n">{featureCount}</span> <span className="l">feature folders</span></div>
          <div className="landing-stat"><span className="n">{totalCanvases}</span> <span className="l">canvases</span></div>
          <div className="landing-stat"><span className="n">{totalDocs}</span> <span className="l">specs &amp; docs</span></div>
        </div>
      </header>

      <section className="landing-section why">
        <h2>Why this matters</h2>
        <p className="landing-section-sub">
          Much of the world's primary care runs where the cloud doesn't reach. That shapes everything we build.
        </p>
        <div className="why-grid">
          <div className="why-card">
            <h3>Care happens where the cloud doesn't reach</h3>
            <p>
              Many clinics that run OpenMRS have little connectivity, no GPUs, and few IT staff — so the AI has to
              run <strong>offline, on modest hardware</strong>. That's why we test a local "AI team" of small models
              instead of one big cloud model.
            </p>
          </div>
          <div className="why-card">
            <h3>Patient data should stay where the patient is</h3>
            <p>
              Sending charts to a cloud API is a privacy and data-ownership problem. So{' '}
              <strong>patient data never leaves the deployment</strong>, and validation runs against the real local
              systems — not a copy in someone else's datacenter.
            </p>
          </div>
          <div className="why-card">
            <h3>Global guidance has to fit local reality</h3>
            <p>
              Guidelines — and the data most AI is trained on — are written for settings unlike a rural clinic.
              Mirroring WHO's{' '}
              <a href="https://www.who.int/teams/digital-health-and-innovation/smart-guidelines" target="_blank" rel="noreferrer">SMART Guidelines</a>,
              we contextualize a knowledge base to each deployment's own concepts and medicines.
            </p>
          </div>
          <div className="why-card">
            <h3>"Looks right" isn't good enough in medicine</h3>
            <p>
              Low-resource settings can least afford a confidently wrong answer. Every validation claim is{' '}
              <strong>traceable to a specific patient record</strong>, reviewed, and reproducible.
            </p>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <h2>What we're validating</h2>
        <p className="landing-section-sub">Four clinical-AI surfaces, each tested through its real system.</p>
        <div className="surface-grid">
          <div className="surface"><strong>chartsearchai</strong> — the AI inside OpenMRS that searches a patient's chart and answers with citations.</div>
          <div className="surface"><strong>med-agent-hub</strong> — a local "AI team" of small models (orchestrator, expert, synthesizer, validator) that can stand in for one big cloud model.</div>
          <div className="surface"><strong>Catalyst</strong> — lab-result AI over the OpenELIS lab system.</div>
          <div className="surface"><strong>the harness</strong> — the shared bench that runs real questions through these and grades the answers with evidence.</div>
        </div>
      </section>

      <section className="landing-section start-here">
        <h2>Start here</h2>
        <p className="landing-section-sub">New to the project? Read these three, in order.</p>
        <div className="start-steps">
          <Link className="start-step" to="/canvas/specs/roadmap">
            <span className="start-step-n">1</span>
            <span className="start-step-body">
              <span className="start-step-title">The roadmap, in plain terms</span>
              <span className="start-step-blurb">What we're building and why, then the milestones and the work in flight.</span>
            </span>
          </Link>
          <Link className="start-step" to="/canvas/specs/artifacts/canvases/validation-research">
            <span className="start-step-n">2</span>
            <span className="start-step-body">
              <span className="start-step-title">How we judge an AI answer</span>
              <span className="start-step-blurb">The evidence model and evaluation methodology behind every claim.</span>
            </span>
          </Link>
          <Link className="start-step" to="/spec/README">
            <span className="start-step-n">3</span>
            <span className="start-step-body">
              <span className="start-step-title">Project README</span>
              <span className="start-step-blurb">What the harness is, who it's for, and how to run it.</span>
            </span>
          </Link>
        </div>
      </section>

      <section className="landing-section">
        <h2>Canvases</h2>
        <p className="landing-section-sub">Topic-scoped visual summary pages — architecture, data profiles, comparisons, and research.</p>
        <div className="card-grid">
          {canvasLeaves.map(({ leaf, topSection, parentSection }) => (
            <Link key={leaf.slug} to={toFor(leaf)} className="dispatch-card">
              <div className="dispatch-card-pill">canvas</div>
              <div className="dispatch-card-title">{leaf.title}</div>
              {leaf.blurb && <div className="dispatch-card-blurb">{leaf.blurb}</div>}
              <div className="dispatch-card-path">{parentSection?.title ?? topSection.title}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2>Specs &amp; docs</h2>
        <p className="landing-section-sub">Markdown sources in sidebar navigation order. Click any to read; every page has prev/next links at the bottom.</p>
        {fullNavTree.map((top) => {
          // Group leaves by parent section within the top — preserving the curated order.
          type Group = { label: string; leaves: NavLeaf[] };
          const groups: Group[] = [];
          function visit(items: Array<NavLeaf | NavSection>, label: string) {
            const ownLeaves: NavLeaf[] = [];
            for (const it of items) {
              if (isSection(it)) visit(it.items, it.title);
              else ownLeaves.push(it);
            }
            if (ownLeaves.length > 0) groups.push({ label, leaves: ownLeaves });
          }
          visit(top.items, top.title);

          // Only include spec/home leaves in this section (canvases shown above).
          const specGroups = groups
            .map((g) => ({ ...g, leaves: g.leaves.filter((l) => l.kind !== 'canvas') }))
            .filter((g) => g.leaves.length > 0);
          if (specGroups.length === 0) return null;

          return (
            <div className="landing-section-block" key={top.title}>
              <h3>{top.title}</h3>
              {top.intro && <p className="landing-section-block-intro">{top.intro}</p>}
              {specGroups.map((g) => (
                <div key={g.label} className="doc-group">
                  {g.label !== top.title && <h4>{g.label}</h4>}
                  <ul className="doc-list">
                    {g.leaves.map((leaf) => (
                      <li key={leaf.slug}>
                        <Link to={toFor(leaf)}>{leaf.title}</Link>
                        {leaf.blurb && <span className="doc-blurb">{leaf.blurb}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          );
        })}
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
