/**
 * Hand-curated information architecture for the PUBLIC docs site.
 *
 * The public site is the non-technical, public-facing surface: the README, the
 * landing, the visual **canvases**, and the mission/background + research pages.
 * The implementation detail under `specs/` (feature specs, plans, briefs,
 * contracts, planning notes, handoffs, lanes) is dev-internal — it lives in the
 * repo but is NOT published (see the import.meta.glob allowlist in App.tsx /
 * prerender-entry.tsx). Canvases are the one *.canvas.tsx surface that stays public.
 *
 * Each leaf points at an existing route slug:
 *   - home:    'welcome'
 *   - spec:    'README', 'specs/background/<name>', and the published research pages
 *   - canvas:  'specs/roadmap', 'specs/artifacts/canvases/<name>'
 */

export type NavLeaf = {
  kind: 'home' | 'canvas' | 'spec';
  slug: string;            // route slug; matches the toSlug() output in App.tsx
  title: string;           // human label shown in sidebar + cards
  blurb?: string;          // short description (landing-page cards)
};

export type NavSection = {
  title: string;
  intro?: string;          // short description for the section header
  collapsed?: boolean;     // default-collapsed in the sidebar
  items: Array<NavLeaf | NavSection>;
};

export type NavNode = NavLeaf | NavSection;

export function isSection(n: NavNode): n is NavSection {
  return (n as NavSection).items !== undefined;
}

export const navTree: NavSection[] = [
  {
    title: 'Start here',
    items: [
      { kind: 'home',   slug: 'welcome',                                      title: 'Welcome — overview',         blurb: 'The mission in plain terms — the problem, the approach, and where to go deeper.' },
      { kind: 'spec',   slug: 'specs/background/why-local-first-clinical-ai', title: 'Why local-first clinical AI', blurb: 'The cited evidence behind the mission — offline realities, data sovereignty, right-sized open models, and WHO SMART Guidelines.' },
      { kind: 'spec',   slug: 'README',                                       title: 'Project README',             blurb: 'What this harness is, who it is for, how to get started, and key terms.' },
      { kind: 'canvas', slug: 'specs/roadmap',                                title: 'Validation roadmap',         blurb: 'Milestones, lanes, and dependencies — start here to understand sequencing.' },
    ],
  },
  {
    title: 'Project overview',
    intro: 'Visual summaries of what we validate, how we judge it, and the data and research behind it.',
    items: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validation-research',         title: 'Validation research',          blurb: 'Evidence model, evaluation methodology, and the run-manifest traceability spine.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/demo-data-profile',           title: 'Demo-data profile & cohorts',  blurb: 'The loaded OpenMRS 2.8 demo corpus: landscape, completeness, and validation cohorts.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/clinical-ai-research-guidance', title: 'Clinical-AI research guidance', blurb: 'Research vectors, evidence levels, and maturity framing.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/scout-comparative-analysis',  title: 'Scout comparative analysis',   blurb: 'Duke DIHI Scout and what it implies for chartsearchai, openmrs_chatbot, and Catalyst.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/catalyst-demos',              title: 'Catalyst demos',               blurb: 'Query-to-table on two real data sources — watch a two-turn conversation on each.' },
    ],
  },
  {
    title: 'Development',
    intro: 'Architecture, data transformation, and upstream-contribution internals.',
    items: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/concept-mapping-discovery',   title: 'Concept mapping & transformation', blurb: 'Bridge rule, promotion rules, blockers, open decisions.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/sqlmesh-transformation-flow',  title: 'SQLMesh transformation flow',  blurb: 'How the deterministic OpenMRS 2.7 → 2.8 transform is materialized.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/chartsearchai-and-querystore', title: 'chartsearchai & querystore',  blurb: 'Architecture of the chart-search and query-retrieval integration.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/answer-indepth-parity',        title: 'Answer / In-Depth parity',    blurb: 'Evolving Answer and In-Depth into two truly separate, independently-measured responses — current architecture (both setups) and the roadmap.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/answer-flow',                  title: 'Answer flow — what to simplify', blurb: 'med-agent-hub answer-generation flow and where to cut complexity.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/cross-project-comparison',     title: 'Cross-project comparison',     blurb: 'Side-by-side architecture of chartsearchai, openmrs_chatbot, and Catalyst.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/upstream-contribution-and-compatibility', title: 'Upstream contribution & compatibility', blurb: 'The ChartSearchAI relay and med-agent-hub profile integration organized into reviewable OpenMRS contributions.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validator-audit-framework',   title: 'Validator audit framework',    blurb: 'How validator behavior is audited and kept reviewable.' },
    ],
  },
  {
    title: 'Background & research',
    intro: 'The cited grounding behind the mission and the safety approach.',
    items: [
      { kind: 'spec', slug: 'specs/artifacts/planning/global-health-ai-background-research-2026-06-14', title: 'Background & evidence (research)', blurb: 'Cited global-health grounding: WHO SMART Guidelines, LMIC realities, data sovereignty, open-model right-sizing.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/guardrails-methodology-research', title: 'Guardrails methodology (research)', blurb: 'Prompt-injection and unsafe-answer defenses — the safety research behind the harness.' },
    ],
  },
];

/** Flatten the tree into a slug → leaf map. Used by routes to look up content. */
export function flattenLeaves(tree: NavSection[] = navTree): Record<string, NavLeaf> {
  const out: Record<string, NavLeaf> = {};
  function walk(items: NavNode[]) {
    for (const n of items) {
      if (isSection(n)) walk(n.items);
      else out[n.slug] = n;
    }
  }
  walk(tree);
  return out;
}

/** Walk the tree and return every leaf in document order, with the section path. */
export function leafSequence(tree: NavSection[] = navTree): Array<{ leaf: NavLeaf; sectionPath: string[] }> {
  const out: Array<{ leaf: NavLeaf; sectionPath: string[] }> = [];
  function walk(items: NavNode[], path: string[]) {
    for (const n of items) {
      if (isSection(n)) walk(n.items, [...path, n.title]);
      else out.push({ leaf: n, sectionPath: path });
    }
  }
  walk(tree, []);
  return out;
}

/** Find the previous and next leaves around a given slug (for prev/next links). */
export function neighbors(slug: string, tree: NavSection[] = navTree): { prev?: NavLeaf; next?: NavLeaf } {
  const seq = leafSequence(tree);
  const i = seq.findIndex((x) => x.leaf.slug === slug);
  if (i < 0) return {};
  return {
    prev: i > 0 ? seq[i - 1].leaf : undefined,
    next: i < seq.length - 1 ? seq[i + 1].leaf : undefined,
  };
}
