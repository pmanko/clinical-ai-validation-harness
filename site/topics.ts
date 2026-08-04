// Topic axis — navigate the public docs by THEME, not by category. Each topic is a
// short plain-language framing plus curated drill-down links into the visual canvases
// (the public surface). Slugs are validated against disk by topics.test.ts.
//
// Note: the detailed feature specs, planning briefs and research that some of these
// themes also cover are dev-internal and live in the repo, not on the published site.

export type TopicLink = { kind: 'spec' | 'canvas'; slug: string; label: string };
export type Topic = { id: string; title: string; blurb: string; links: TopicLink[] };

export const topics: Topic[] = [
  {
    id: 'data-corpus',
    title: 'The data we test against',
    blurb: 'A realistic 5,284-patient OpenMRS demo corpus, modernized from the public 2.7 demo and bound to the CIEL clinical terminology — so validation runs against believable charts, not toy fixtures.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/demo-data-profile', label: 'Demo-data profile & cohorts (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/concept-mapping-discovery', label: 'Concept mapping & transformation (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/sqlmesh-transformation-flow', label: 'SQLMesh transformation flow (canvas)' },
    ],
  },
  {
    id: 'evidence',
    title: 'Evidence, evaluation & traceability',
    blurb: 'How an AI answer is judged: scored against the patient chart, every claim traceable to a specific record, recorded on a run-manifest provenance spine — directional evidence, not a leaderboard.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validation-research', label: 'Validation research — the evidence model (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/clinical-ai-research-guidance', label: 'Clinical-AI research guidance (canvas)' },
    ],
  },
  {
    id: 'safety-governance',
    title: 'Safety & governance',
    blurb: 'Guarding against unsafe answers, and the change-control discipline (validator audits, PCCP-style records) that keeps validation baselines reviewable.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validator-audit-framework', label: 'Validator audit framework (canvas)' },
    ],
  },
  {
    id: 'lab-ai',
    title: 'Catalyst — query-to-table for lab and program data',
    blurb: 'Ask a clinical question in plain language; a writer/reviewer model team drafts governed SQL against a database-generated catalog, a deterministic policy enforces read-only execution, and the result is a typed table — running today on two independent data sources, OpenELIS lab data and OpenMRS HIV/ART program data.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/catalyst-demos', label: 'Demos — see it answer real questions (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/catalyst-fhir-sidecar', label: 'Earlier design exploration (canvas)' },
    ],
  },
  {
    id: 'upstream',
    title: 'Upstream & compatibility',
    blurb: 'How the ChartSearchAI relay, med-agent-hub profiles, and optional Querystore source are organized into reviewable OpenMRS upstream contributions.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/upstream-contribution-and-compatibility', label: 'Upstream contribution & compatibility (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/chartsearchai-and-querystore', label: 'chartsearchai & querystore (canvas)' },
    ],
  },
];
