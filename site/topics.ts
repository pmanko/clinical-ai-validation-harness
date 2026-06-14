// Topic axis — navigate the docs by THEME, not by feature folder. Each topic is a
// short plain-language framing plus curated drill-down links into the real specs,
// research, and canvases. Slugs are validated against disk by topics.test.ts.

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
      { kind: 'spec', slug: 'specs/002-openmrs-demo-data-2-8-remap/spec', label: 'Feature 002 — demo-data remap spec' },
    ],
  },
  {
    id: 'local-ai-team',
    title: 'The local AI team — small models, offline',
    blurb: 'Instead of one big cloud model, a coordinated team of small local models (orchestrator, medical expert, synthesizer, validator) that runs on modest hardware and keeps everything on-site.',
    links: [
      { kind: 'spec', slug: 'specs/005-med-agent-hub-bridge/spec', label: 'Feature 005 — med-agent-hub bridge spec' },
      { kind: 'spec', slug: 'specs/artifacts/planning/react-team-orchestration-design', label: 'ReAct team orchestration design' },
      { kind: 'spec', slug: 'specs/artifacts/planning/agentic-orchestration-a2a-research', label: 'Why in-process, not A2A (research)' },
    ],
  },
  {
    id: 'knowledge-base',
    title: 'Knowledge base & local contextualization',
    blurb: 'Openly-licensed clinical reference (WHO IMCI/EML/ANC, MSF guidelines, essential medicines) for low-power models, contextualized to each deployment’s own concepts and drugs — PHI never leaves the site.',
    links: [
      { kind: 'spec', slug: 'specs/artifacts/planning/clinical-kb-brief', label: 'Clinical KB brief (F009)' },
      { kind: 'spec', slug: 'specs/artifacts/planning/clinical-kb-research', label: 'Clinical KB research' },
      { kind: 'spec', slug: 'specs/artifacts/planning/kb-scope', label: 'KB scope' },
    ],
  },
  {
    id: 'evidence',
    title: 'Evidence, evaluation & traceability',
    blurb: 'How an AI answer is judged: scored against the patient chart, every claim traceable to a specific record, recorded on a run-manifest provenance spine — directional evidence, not a leaderboard.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validation-research', label: 'Validation research — the evidence model (canvas)' },
      { kind: 'spec', slug: 'specs/artifacts/planning/eval-methodology-brief', label: 'Evaluation methodology brief' },
      { kind: 'spec', slug: 'specs/006-validation-harness-mvp/spec', label: 'Feature 006 — validation harness MVP spec' },
      { kind: 'spec', slug: 'specs/artifacts/planning/metadata-schema', label: 'Metadata schema' },
    ],
  },
  {
    id: 'safety-governance',
    title: 'Safety & governance',
    blurb: 'Guarding against prompt injection and unsafe answers, and the change-control discipline (PCCP-style records, validator audits) that keeps validation baselines reviewable.',
    links: [
      { kind: 'spec', slug: 'specs/artifacts/planning/guardrails-methodology-research', label: 'Guardrails methodology (research)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/validator-audit-framework', label: 'Validator audit framework (canvas)' },
      { kind: 'spec', slug: 'specs/artifacts/planning/pccp-change-record-template', label: 'PCCP change-record template' },
    ],
  },
  {
    id: 'lab-ai',
    title: 'Lab AI — Catalyst / OpenELIS',
    blurb: 'Extending the harness to lab-system AI: a FHIR-grounded sidecar over OpenELIS Global 2 that answers lab questions with resource-cited evidence — the proof the harness generalizes beyond OpenMRS.',
    links: [
      { kind: 'spec', slug: 'specs/artifacts/planning/catalyst-fhir-sidecar-brief', label: 'Catalyst FHIR sidecar brief (M10)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/catalyst-fhir-sidecar', label: 'Catalyst FHIR sidecar (canvas)' },
    ],
  },
  {
    id: 'upstream',
    title: 'Upstream & compatibility',
    blurb: 'How the harness’s changes to chartsearchai and querystore are organized into reviewable OpenMRS upstream contributions, and how they stay compatible with the out-of-the-box bundled-LLM shape.',
    links: [
      { kind: 'canvas', slug: 'specs/artifacts/canvases/upstream-contribution-and-compatibility', label: 'Upstream contribution & compatibility (canvas)' },
      { kind: 'canvas', slug: 'specs/artifacts/canvases/chartsearchai-and-querystore', label: 'chartsearchai & querystore (canvas)' },
      { kind: 'spec', slug: 'specs/004-real-adapter-entrypoints/spec', label: 'Feature 004 — real adapter entrypoints spec' },
    ],
  },
];
