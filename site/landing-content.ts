// Authored content for the mission-first landing page. Kept as data (not JSX) so
// the copy lives in one place, the page component stays thin, and tests can assert
// on it directly. The landing reads as a single inverted-pyramid narrative; the
// four GO_DEEPER cards route four kinds of reader by task — never by an audience
// label — each link a specific promise to a real page (validated in tests).

export const DEMO_URL = 'https://openmrs.openclinai.org';

export const HERO = {
  eyebrow: 'clinical-ai-validation-harness',
  headline: 'Clinical AI that works where care actually happens',
  valueProp:
    "Most of the world's primary care runs offline, on modest hardware, far from the cloud — and far from the data and guidelines most AI is built on. This is a proving ground for clinical AI that runs locally, keeps patient data on site, and backs every answer with evidence you can check — tested against real systems and realistic patient records, not just benchmarks.",
};

export const PROBLEM = {
  heading: 'Why this matters',
  paragraphs: [
    "Clinical AI is usually built one way: a large model in someone else's cloud, with the patient's data sent out to get an answer. For the clinics where much of the world's care actually happens, that approach quietly fails on every count.",
    'These clinics often have intermittent power and connectivity and little IT support, so the AI has to run offline, on modest hardware. The data and guidelines behind most models come from far better-resourced places, so the answers fit those patients better than the one in the room. Sending charts to an outside service is a privacy and data-ownership problem in its own right. And in medicine, an answer that merely looks right is the most dangerous kind.',
    "What has changed is that it no longer has to be this way. Open models small enough to run on local hardware are now good enough to do real clinical work — if you give them the right knowledge, keep them grounded in the patient's actual record, and check their answers instead of trusting them.",
  ],
};

export const APPROACH = {
  heading: 'How we do it differently',
  lead: 'The harness exists to test a different way of building clinical AI — and to prove, with evidence, that it holds up.',
  pillars: [
    {
      title: 'A local team of small models',
      body: 'Instead of one big cloud model, a coordinated team of small models that runs on local hardware — matching the right-sized model to each job.',
    },
    {
      title: 'Patient data never leaves the site',
      body: "Charts stay inside the deployment. Validation runs against the real local systems, not a copy in someone else's datacenter.",
    },
    {
      title: 'A knowledge base tuned to each clinic',
      body: "Openly-licensed clinical reference, contextualized to each deployment's own conditions, medicines, and terminology — so the AI reflects the patients actually in front of it.",
    },
    {
      title: 'Every answer traced to a record',
      body: "Each claim points back to a specific entry in the chart, and a stronger model grades the result — because a small model can't safely check its own work.",
    },
  ],
};

export const PROOF = {
  heading: 'How we prove it',
  body: "The harness runs real clinical questions through real systems — OpenMRS chart search, query retrieval, clinical chat, and lab-system AI on OpenELIS — against a realistic demo corpus, and grades each answer on whether it is accurate, grounded in the record, and safe. Every result is recorded so any claim can be traced back and reproduced.",
  demoLabel: 'Try the live demo',
  demoUrl: DEMO_URL,
  honesty:
    'This is an advisory, clinician-in-the-loop research demonstrator — not a production medical device.',
};

export type GoDeeperLink = { label: string; to: string };
export type GoDeeperCard = { title: string; outcome: string; links: GoDeeperLink[] };

// Four reader paths, routed by task (not by audience). The titles are verbs +
// outcomes so the right reader recognises their path by information scent.
export const GO_DEEPER: GoDeeperCard[] = [
  {
    title: 'See the evidence behind the approach',
    outcome: 'The research and roadmap that ground every claim on this page.',
    links: [
      { label: 'Why local-first clinical AI', to: '/spec/specs/background/why-local-first-clinical-ai' },
      { label: 'The validation roadmap', to: '/canvas/specs/roadmap' },
    ],
  },
  {
    title: 'See how an AI answer is judged',
    outcome: 'The evidence model and scoring behind every result.',
    links: [
      { label: 'The evidence model', to: '/canvas/specs/artifacts/canvases/validation-research' },
      { label: 'Evaluation methodology', to: '/spec/specs/artifacts/planning/eval-methodology-brief' },
      { label: 'Evidence & traceability', to: '/topic/evidence' },
    ],
  },
  {
    title: 'Run the harness yourself',
    outcome: 'Set it up, point it at real systems, and inspect a run.',
    links: [
      { label: 'Project README & setup', to: '/spec/README' },
      { label: 'The validation harness (MVP)', to: '/spec/specs/006-validation-harness-mvp/spec' },
      { label: 'Development operating plan', to: '/spec/docs/dev-roadmap' },
    ],
  },
  {
    title: 'Bring this to a deployment',
    outcome: 'How it contextualizes to a clinic and stays safe in real use.',
    links: [
      { label: 'Contextualized knowledge base', to: '/spec/specs/artifacts/planning/clinical-kb-brief' },
      { label: 'Safety & governance', to: '/topic/safety-governance' },
      { label: 'The demo data & cohorts', to: '/canvas/specs/artifacts/canvases/demo-data-profile' },
    ],
  },
];
