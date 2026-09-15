// Documentation entry copy. Project introductions and demonstrations live on openclinai.org.
export const HERO = {
  eyebrow: 'Open Clinical AI',
  headline: 'Documentation',
  valueProp: 'Setup guides, component architecture and validation methods for the Open Clinical AI projects. Choose a topic below or search the documentation.',
};

export type GoDeeperLink = { label: string; to: string };
export type GoDeeperCard = { title: string; outcome: string; links: GoDeeperLink[] };

export const GO_DEEPER: GoDeeperCard[] = [
  {
    title: 'Set up and run the harness',
    outcome: 'Prepare an environment and understand the demo records used in validation.',
    links: [
      { label: 'Setup and commands', to: '/spec/README' },
      { label: 'Demo data and cohorts', to: '/canvas/specs/artifacts/canvases/demo-data-profile' },
    ],
  },
  {
    title: 'Understand the components',
    outcome: 'Explore the application integrations, shared services and data flows.',
    links: [
      { label: 'Component architecture', to: '/canvas/specs/artifacts/canvases/cross-project-comparison' },
      { label: 'ChartSearchAI and Query Store', to: '/canvas/specs/artifacts/canvases/chartsearchai-and-querystore' },
      { label: 'Catalyst technical examples', to: '/canvas/specs/artifacts/canvases/catalyst-demos' },
    ],
  },
  {
    title: 'Inspect validation methods',
    outcome: 'See how runs capture evidence and where review and safety checks fit.',
    links: [
      { label: 'Evidence and traceability', to: '/topic/evidence' },
      { label: 'Safety and governance', to: '/topic/safety-governance' },
    ],
  },
  {
    title: 'Read the background research',
    outcome: 'Find the cited research behind local deployment and clinical AI evaluation.',
    links: [
      { label: 'Local-first clinical AI', to: '/spec/specs/background/why-local-first-clinical-ai' },
      { label: 'Clinical AI research guidance', to: '/canvas/specs/artifacts/canvases/clinical-ai-research-guidance' },
    ],
  },
];
