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

// Canonical doc order + human labels within a feature folder.
type DocKind = 'spec' | 'plan' | 'research' | 'data-model' | 'quickstart' | 'tasks';
const DOC_META = {
  spec:         { title: 'Spec',       blurb: 'Feature specification: user stories, acceptance, scope.' },
  plan:         { title: 'Plan',       blurb: 'Implementation plan and milestone breakdown.' },
  research:     { title: 'Research',   blurb: 'Background research, references, prior art.' },
  'data-model': { title: 'Data model', blurb: 'Entities, relationships, constraints.' },
  quickstart:   { title: 'Quickstart', blurb: 'Get-started commands and operator flow.' },
  tasks:        { title: 'Tasks',      blurb: 'Task list — what is done, what is pending.' },
} satisfies Record<DocKind, { title: string; blurb: string }>;

// Build leaves for the docs that actually exist in a feature folder. Pass the
// present doc kinds explicitly so we never link a file that isn't there.
function featureDocs(
  feature: string,
  docs: Array<keyof typeof DOC_META> = ['spec', 'plan', 'research', 'data-model', 'quickstart', 'tasks'],
): NavLeaf[] {
  return docs.map((d) => ({ kind: 'spec', slug: `specs/${feature}/${d}`, title: DOC_META[d].title, blurb: DOC_META[d].blurb }));
}

export const navTree: NavSection[] = [
  {
    title: 'Start here',
    items: [
      { kind: 'home',   slug: 'welcome',                                       title: 'Welcome — overview',  blurb: 'Purpose, project overview, canvases, and all docs at a glance.' },
      { kind: 'spec',   slug: 'specs/background/why-local-first-clinical-ai',  title: 'Why local-first clinical AI', blurb: 'The cited evidence behind the mission — offline realities, data sovereignty, right-sized open models, and WHO SMART Guidelines.' },
      { kind: 'spec',   slug: 'README',                                        title: 'Project README',      blurb: 'What this harness is, who it is for, how to get started, and key terms.' },
      { kind: 'canvas', slug: 'specs/roadmap',                                 title: 'Validation roadmap',  blurb: 'Planned validation milestones, lanes, dependencies. Start here to understand sequencing.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validation-research',  title: 'Validation research', blurb: 'Evidence model, evaluation methodology, and the run-manifest traceability spine.' },
      { kind: 'spec',   slug: 'docs/dev-roadmap',                              title: 'Development operating plan', blurb: 'Active lanes, gates, and launch sequence — the operating companion to the roadmap canvas.' },
    ],
  },
  {
    title: 'Active features',
    intro: 'Feature folders. Each carries spec → plan → research → data-model → quickstart → tasks, plus contracts and checklists.',
    items: [
      {
        title: '001 — Harness foundation',
        intro: 'Roadmap M0: cross-project orchestration substrate — target registry, run-manifest schema, CLI scaffold.',
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
        title: '002 — OpenMRS demo-data remap (complete)',
        intro: 'Roadmap M1: legacy 2.7 → CIEL-bound 2.8 Ref App transform. Plus chartsearchai/OpenELIS cross-load analysis.',
        items: [
          ...featureDocs('002-openmrs-demo-data-2-8-remap'),
          { kind: 'canvas', slug: 'specs/artifacts/canvases/concept-mapping-discovery', title: 'Canvas — Concept mapping & transformation', blurb: 'Bridge rule, promotion rules, blockers, open decisions.' },
          { kind: 'canvas', slug: 'specs/artifacts/canvases/sqlmesh-transformation-flow', title: 'Canvas — SQLMesh transformation flow', blurb: 'How feature 002 uses SQLMesh to materialize the deterministic OpenMRS 2.7 to 2.8 transform.' },
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
      {
        title: '004 — Real adapter entrypoints (in progress)',
        intro: 'Roadmap M3: executable contracts for the real production paths — chartsearchai, querystore, openmrs_chatbot, Catalyst.',
        items: [...featureDocs('004-real-adapter-entrypoints', ['spec', 'plan', 'tasks'])],
      },
      {
        title: '005 — med-agent-hub bridge (shipped)',
        intro: 'Roadmap F005: an in-process "AI team" of small local models behind an OpenAI-compatible endpoint that chartsearchai talks to.',
        items: [...featureDocs('005-med-agent-hub-bridge', ['spec'])],
      },
      {
        title: '006 — Validation harness MVP (in progress)',
        intro: 'Roadmap M2 (the validation spine): run the same clinical questions across model backends through chartsearchai’s real API, with human adjudication.',
        items: [...featureDocs('006-validation-harness-mvp', ['spec'])],
      },
      {
        title: '007 — File-based LLM config overrides (planned)',
        intro: 'Roadmap F007: make the chartsearchai system prompt + inference params overridable via an operator-editable file pair — fast iteration without a rebuild.',
        items: [...featureDocs('007-llm-config-overrides', ['spec', 'plan'])],
      },
    ],
  },
  {
    title: 'Cross-cutting canvases',
    intro: 'Topic-scoped dashboards outside any single feature.',
    items: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/upstream-contribution-and-compatibility', title: 'Upstream contribution & compatibility', blurb: 'The chartsearchai integration burst organized into reviewable openmrs PRs (esm + module), plus a live-verified check that the changes do not break the out-of-the-box bundled-LLM shape.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/demo-data-profile', title: 'Demo-data profile & cohorts', blurb: 'Profile of the loaded OpenMRS 2.8 demo corpus: landscape metrics, completeness, content-verified phenotype cohorts, and curated data-rich validation patients.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/scout-comparative-analysis', title: 'Scout comparative analysis', blurb: 'Deep-dive analysis of Duke DIHI Scout and implications for chartsearchai, openmrs_chatbot, and Catalyst.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/cross-project-comparison',    title: 'Cross-project comparison',    blurb: 'Side-by-side architecture of chartsearchai, openmrs_chatbot, Catalyst.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/clinical-ai-research-guidance', title: 'Clinical-AI research guidance', blurb: 'Research vectors, evidence levels, maturity framing.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/chartsearchai-and-querystore', title: 'chartsearchai & querystore', blurb: 'How chart search and the read-optimized query store fit together.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/catalyst-fhir-sidecar',        title: 'Catalyst FHIR sidecar',     blurb: 'FHIR-grounded lab AI over OpenELIS — the lab-AI sidecar architecture canvas.' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validator-audit-framework',    title: 'Validator audit framework', blurb: 'Change-control and validator-audit discipline that keeps validation baselines reviewable.' },
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
      { kind: 'spec', slug: 'specs/artifacts/planning/harness-architecture-brief',       title: 'Harness architecture brief',     blurb: 'How the control-plane pieces fit together.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/eval-methodology-brief',           title: 'Evaluation methodology brief',   blurb: 'How validation quality is measured — the Scout-style rubric and metrics.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/guardrails-methodology-research',  title: 'Guardrails methodology (research)', blurb: 'Prompt-injection and unsafe-answer defenses — the safety research behind the harness.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/global-health-ai-background-research-2026-06-14', title: 'Background & evidence (research)', blurb: 'Cited global-health grounding for the mission: WHO SMART Guidelines, LMIC realities, data sovereignty, open-model right-sizing.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/clinical-kb-brief',                 title: 'Clinical KB brief',       blurb: 'A clinical knowledge base for low-power local models, contextualized per deployment.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/chartsearchai-model-gateway-brief', title: 'Model gateway brief',     blurb: 'A gateway letting chartsearchai reach many model providers behind one URL.' },
      { kind: 'spec', slug: 'specs/artifacts/planning/catalyst-fhir-sidecar-brief',       title: 'Catalyst FHIR sidecar brief', blurb: 'FHIR-grounded lab AI over OpenELIS — the source brief for the lab-AI sidecar POC.' },
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
  // Historical session handoffs (specs/artifacts/handoffs/*) are intentionally
  // omitted from the published nav — they're checkout-internal context, not
  // collaborator-facing docs.
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
