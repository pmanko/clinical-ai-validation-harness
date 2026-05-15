/**
 * Hand-curated information architecture for the docs site.
 *
 * The flat auto-discovery (import.meta.glob in App.tsx) tells us *what files
 * exist*. This file tells us *how to organize them* — labels, ordering, which
 * stubs to hide, what's a section index vs. a leaf, and the human-meaningful
 * narrative arc through the documentation.
 *
 * Each leaf points at an existing route slug:
 *   - canvases:  'specs/roadmap', 'specs/artifacts/canvases/<name>'
 *   - specs:     'specs/<feature>/<file>', 'README', 'specs/artifacts/README'
 *
 * Files that exist but are intentionally omitted (e.g. docs/README stub) are
 * simply not referenced — they get no sidebar entry and no landing-page card.
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

// Canonical doc order within a feature folder.
function featureDocs(feature: string): NavLeaf[] {
  return [
    { kind: 'spec', slug: `specs/${feature}/spec`,        title: 'Spec',         blurb: 'Feature specification: user stories, acceptance, scope.' },
    { kind: 'spec', slug: `specs/${feature}/plan`,        title: 'Plan',         blurb: 'Implementation plan and milestone breakdown.' },
    { kind: 'spec', slug: `specs/${feature}/research`,    title: 'Research',     blurb: 'Background research, references, prior art.' },
    { kind: 'spec', slug: `specs/${feature}/data-model`,  title: 'Data model',   blurb: 'Entities, relationships, constraints.' },
    { kind: 'spec', slug: `specs/${feature}/quickstart`,  title: 'Quickstart',   blurb: 'Get-started commands and operator flow.' },
    { kind: 'spec', slug: `specs/${feature}/tasks`,       title: 'Tasks',        blurb: 'Task list — what is done, what is pending.' },
  ];
}

export const navTree: NavSection[] = [
  {
    title: 'Start here',
    items: [
      { kind: 'home',   slug: 'welcome',                                       title: 'Welcome — dashboard', blurb: 'Front door: canvases, features, and everything else at a glance.' },
      { kind: 'spec',   slug: 'README',                                        title: 'Project README',      blurb: 'What this harness is and how its pieces fit together.' },
      { kind: 'canvas', slug: 'specs/roadmap',                                 title: 'Feature roadmap',     blurb: 'Top-level lanes, priorities, dependency graph.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validation-research',  title: 'Validation research', blurb: 'Lanes, primitives, evals, the run-manifest spine.' },
    ],
  },
  {
    title: 'Active features',
    intro: 'Feature folders. Each carries spec → plan → research → data-model → quickstart → tasks, plus contracts and checklists.',
    items: [
      {
        title: '001 — Harness control plane foundation',
        intro: 'M0: cross-project orchestration substrate. Targets registry, run-manifest schema, CLI scaffold.',
        items: [
          ...featureDocs('001-harness-control-plane-foundation'),
          {
            title: 'Contracts',
            items: [
              { kind: 'spec', slug: 'specs/001-harness-control-plane-foundation/contracts/cli', title: 'CLI contract' },
            ],
          },
          {
            title: 'Checklists',
            collapsed: true,
            items: [
              { kind: 'spec', slug: 'specs/001-harness-control-plane-foundation/checklists/requirements', title: 'Requirements checklist' },
            ],
          },
        ],
      },
      {
        title: '002 — OpenMRS demo data remap (M2-A in flight)',
        intro: 'Legacy 2.7 → CIEL-bound 2.8 RefApp transform. Plus chartsearchai/OpenELIS cross-load analysis.',
        items: [
          ...featureDocs('002-openmrs-demo-data-2-8-remap'),
          { kind: 'canvas', slug: 'specs/artifacts/canvases/concept-mapping-discovery', title: 'Canvas — Concept mapping & transformation', blurb: 'Bridge rule, promotion rules, blockers, open decisions.' },
          {
            title: 'Contracts',
            items: [
              { kind: 'spec', slug: 'specs/002-openmrs-demo-data-2-8-remap/contracts/conceptmap.profile',        title: 'ConceptMap profile' },
              { kind: 'spec', slug: 'specs/002-openmrs-demo-data-2-8-remap/contracts/openelis_skeleton.profile', title: 'OpenELIS skeleton profile' },
              { kind: 'spec', slug: 'specs/002-openmrs-demo-data-2-8-remap/contracts/sqlmesh_project.profile',   title: 'SQLMesh project profile' },
            ],
          },
          {
            title: 'Checklists',
            collapsed: true,
            items: [
              { kind: 'spec', slug: 'specs/002-openmrs-demo-data-2-8-remap/checklists/requirements', title: 'Requirements checklist' },
            ],
          },
        ],
      },
    ],
  },
  {
    title: 'Cross-cutting canvases',
    intro: 'Topic-scoped dashboards outside any single feature.',
    items: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/cross-project-comparison',    title: 'Cross-project comparison',    blurb: 'Side-by-side architecture of chartsearchai, openmrs_chatbot, Catalyst.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/clinical-ai-research-guidance', title: 'Clinical-AI research guidance', blurb: 'Research vectors, evidence levels, maturity framing.' },
    ],
  },
  {
    title: 'Planning artifacts',
    intro: 'Durable planning documents that support the feature roadmap.',
    items: [
      { kind: 'spec', slug: 'specs/artifacts/README',                       title: 'Index — what lives where',        blurb: 'Inventory of canvases, planning docs, governance templates, handoffs.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/data-remap-2.8',      title: 'Data remap 2.8',                  blurb: 'Demo-data remap plan for OpenMRS 2.8-compatible import work.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/metadata-schema',     title: 'Metadata schema',                 blurb: 'Manifest and event schema notes for emitted validation metadata.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/pccp-change-record-template', title: 'PCCP change record template', blurb: 'Governance template for material validation changes.' },
    ],
  },
  {
    title: 'Sibling-project context',
    intro: 'Read-only durable snapshots of dev-context from the sibling target repositories.',
    items: [
      { kind: 'spec', slug: 'specs/artifacts/sibling-context/README',                                          title: 'Inventory — what snapshots live here', blurb: 'Source repos, snapshot dates, purposes.' },
      { kind: 'spec', slug: 'specs/artifacts/sibling-context/chartsearchai-local-dev-validation-runbook',     title: 'chartsearchai — local dev validation runbook' },
      { kind: 'spec', slug: 'specs/artifacts/sibling-context/chartsearchai-openmrs-ai-dev-context',           title: 'chartsearchai — OpenMRS AI dev-context dump' },
    ],
  },
  {
    title: 'Handoffs',
    collapsed: true,
    intro: 'Historical session handoff snapshots.',
    items: [
      { kind: 'spec', slug: 'specs/artifacts/handoffs/session-handoff-2026-05-12', title: 'Session handoff — 2026-05-12' },
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
export function neighbors(slug: string): { prev?: NavLeaf; next?: NavLeaf } {
  const seq = leafSequence();
  const i = seq.findIndex((x) => x.leaf.slug === slug);
  if (i < 0) return {};
  return {
    prev: i > 0 ? seq[i - 1].leaf : undefined,
    next: i < seq.length - 1 ? seq[i + 1].leaf : undefined,
  };
}
