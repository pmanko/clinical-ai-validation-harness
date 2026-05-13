import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  computeDAGLayout,
  useHostTheme,
} from "cursor/canvas";

type LaneId = "foundation" | "openmrs" | "safety" | "expansion";

type Feature = {
  id: string;
  num: string;
  title: string;
  slug: string;
  lane: LaneId;
  purpose: string;
  scope: string[];
  evidence: string[];
  needs: string[];
  unlocks: string[];
};

const lanes: Record<
  LaneId,
  { label: string; shortLabel: string; tone: "info" | "neutral" | "warning" | "success"; purpose: string }
> = {
  foundation: {
    label: "Foundation",
    shortLabel: "Foundation",
    tone: "info",
    purpose: "Shared harness contracts, metadata, and real adapter boundaries.",
  },
  openmrs: {
    label: "OpenMRS corpus and eval",
    shortLabel: "OpenMRS",
    tone: "neutral",
    purpose: "Demo data readiness plus retrieval, answer, citation, and abstention validation.",
  },
  safety: {
    label: "Safety and governance",
    shortLabel: "Safety",
    tone: "warning",
    purpose: "Rationale-bearing reviews, red-team cases, and PCCP-style governance records.",
  },
  expansion: {
    label: "Migration and expansion",
    shortLabel: "Expansion",
    tone: "success",
    purpose: "Querystore parity and reuse of the validation spine across sibling projects.",
  },
};

const features: Feature[] = [
  {
    id: "M0",
    num: "M0",
    title: "Harness control plane foundation",
    slug: "001-harness-control-plane-foundation",
    lane: "foundation",
    purpose:
      "Create the umbrella control plane for local and VM-based validation across referenced projects.",
    scope: [
      "Project registry entries and sibling-checkout assumptions.",
      "Local and VM environment profiles.",
      "Artifact/run directory layout.",
      "Compose overlay strategy.",
      "Adapter contract shape for invoking real project commands or APIs.",
    ],
    evidence: [
      "A reproducible harness invocation path exists before downstream claims are made.",
      "Each adapter boundary states what real command or API it will call.",
    ],
    needs: [],
    unlocks: ["M1", "M2", "M3"],
  },
  {
    id: "M1",
    num: "M1",
    title: "OpenMRS demo data remap and import",
    slug: "002-openmrs-demo-data-2-8-remap",
    lane: "openmrs",
    purpose:
      "Transform large-demo-data-2-7-0.sql into a deterministic OpenMRS Platform/Core 2.8 Ref App-compatible import candidate.",
    scope: [
      "Schema diff from source corpus to target OpenMRS 2.8-compatible schema.",
      "Reviewed mapping YAML promoted separately from advisory LLM proposals.",
      "Deterministic transforms that can run from a clean baseline.",
      "Import smoke tests and clinical meaning preservation checks.",
    ],
    evidence: [
      "Record-level examples show how source clinical facts survive the remap.",
      "Counts are supporting signals only, not proof of correctness.",
    ],
    needs: ["M0"],
    unlocks: ["M4"],
  },
  {
    id: "M2",
    num: "M2",
    title: "Validation spine and metadata contract",
    slug: "003-validation-spine-metadata",
    lane: "foundation",
    purpose:
      "Standardize run_manifest.json and events.jsonl across validation lanes.",
    scope: [
      "Project/component, git SHA, dataset version, and mapping version capture.",
      "Model/provider/prompt and retrieval pipeline provenance.",
      "Cited records, reviewer labels, decision rationale, and PCCP-style change links.",
      "OpenTelemetry GenAI alignment where practical.",
    ],
    evidence: [
      "Every durable validation output points back to its inputs and rationale.",
      "Clinical evidence data stays separate from operating metadata.",
    ],
    needs: ["M0"],
    unlocks: ["M4", "M5", "M6", "M7", "M9"],
  },
  {
    id: "M3",
    num: "M3",
    title: "Real adapter entrypoints",
    slug: "004-real-adapter-entrypoints",
    lane: "foundation",
    purpose:
      "Replace adapter notes and stubs with executable contracts for chartsearchai, querystore, openmrs_chatbot, and Catalyst.",
    scope: [
      "Setup and invocation contracts for each real production path.",
      "Adapter-level smoke checks that fail when a real path is unavailable.",
      "Explicit fixture fallback labels when a real path cannot yet be exercised.",
    ],
    evidence: [
      "Validation claims identify the exact real component path exercised.",
      "Simulated paths cannot masquerade as production-path evidence.",
    ],
    needs: ["M0"],
    unlocks: ["M4", "M5", "M6", "M8", "M9"],
  },
  {
    id: "M4",
    num: "M4",
    title: "OpenMRS retrieval evaluation",
    slug: "005-openmrs-retrieval-eval",
    lane: "openmrs",
    purpose:
      "Run stage-aware retrieval checks over imported or clearly labelled fixture-backed OpenMRS data.",
    scope: [
      "Precision@k, recall/coverage@k, miss@k, and empty-answer correctness.",
      "Latency and resource-type breakdowns.",
      "Returned-record snippets for failed cases.",
      "Stage-aware gates that distinguish fixture-backed evidence from release-quality evidence.",
    ],
    evidence: [
      "Failed retrievals preserve enough returned-record context to debug them.",
      "Durable claims depend on M1, M2, and M3 being stable.",
    ],
    needs: ["M1", "M2", "M3"],
    unlocks: ["M5", "M7", "M8"],
  },
  {
    id: "M5",
    num: "M5",
    title: "Answer, citation, and abstention evaluation",
    slug: "006-answer-citation-abstention-eval",
    lane: "openmrs",
    purpose:
      "Evaluate model-dependent answers through a pinned OpenAI-compatible endpoint.",
    scope: [
      "Claim support labels.",
      "Citation precision and recall.",
      "Schema validity and abstention correctness.",
      "Model metadata and rationale-bearing review records.",
    ],
    evidence: [
      "Each accepted answer record explains why its evidence supports or fails the claim.",
      "Model/provider/prompt provenance is pinned for every run.",
    ],
    needs: ["M2", "M3", "M4"],
    unlocks: ["M6", "M7", "M8"],
  },
  {
    id: "M6",
    num: "M6",
    title: "Safety and red-team evaluation",
    slug: "007-safety-red-team-eval",
    lane: "safety",
    purpose:
      "Expand prompt-injection and safety coverage beyond direct user prompts.",
    scope: [
      "Indirect injection through chart text, notes, observations, schema context, and MCP responses.",
      "PHI leakage, system prompt leakage, unsafe obedience, and clinical-harm framing.",
      "Scenario diversity checks to avoid overfitting to narrow prompts.",
    ],
    evidence: [
      "Safety outcomes preserve the triggering record, prompt, response, and review rationale.",
      "Coverage includes diverse clinical and system contexts, not only happy-path prompts.",
    ],
    needs: ["M2", "M3", "M5"],
    unlocks: ["M7", "M9"],
  },
  {
    id: "M7",
    num: "M7",
    title: "Clinician and expert governance review",
    slug: "008-clinician-governance-review",
    lane: "safety",
    purpose:
      "Create the review and change-control process for validation baselines.",
    scope: [
      "Blinded review packets and rubric labels.",
      "Adjudication flow and inter-rater tracking.",
      "Baseline update protocol.",
      "PCCP-style change records for material model, prompt, retrieval, mapping, and pipeline changes.",
    ],
    evidence: [
      "Human review labels include rationale, not just pass/fail judgments.",
      "Material changes have explicit impact records before baselines move.",
    ],
    needs: ["M2", "M4", "M5", "M6"],
    unlocks: ["M9"],
  },
  {
    id: "M8",
    num: "M8",
    title: "Querystore parity testbed",
    slug: "009-querystore-parity-testbed",
    lane: "expansion",
    purpose:
      "Compare the current chartsearchai retrieval path with the future querystore-backed path using the same artifacts.",
    scope: [
      "Retrieval, answer, abstention, and metadata artifact parity.",
      "Migration reports that show where behavior changes.",
      "Go/no-go criteria for moving validation paths toward querystore.",
    ],
    evidence: [
      "Parity reports compare record-level evidence, not just aggregate metric deltas.",
      "A migration decision can point to the exact changed retrieval behavior.",
    ],
    needs: ["M3", "M4", "M5"],
    unlocks: [],
  },
  {
    id: "M9",
    num: "M9",
    title: "Cross-project validation expansion",
    slug: "010-cross-project-validation-expansion",
    lane: "expansion",
    purpose:
      "Apply the shared validation spine to openmrs_chatbot and Catalyst without inventing separate harnesses.",
    scope: [
      "openmrs_chatbot: role-aware chat, multi-turn grounding, and agent handoff traces.",
      "Catalyst: NL-to-SQL correctness, Pass^N consistency, schema allowlist enforcement, RBAC-safe execution, and provider drift.",
      "Shared metadata and review records across projects.",
    ],
    evidence: [
      "Expansion cases reuse M2/M3 contracts and can be compared across projects.",
      "Project-specific risks are captured without fragmenting the harness model.",
    ],
    needs: ["M2", "M3", "M6", "M7"],
    unlocks: [],
  },
];

const featureById = new Map(features.map((feature) => [feature.id, feature]));

const dependencyEdges: Array<{ from: string; to: string }> = features.flatMap((feature) =>
  feature.needs.map((need) => ({ from: need, to: feature.id })),
);

const laneFlows: Record<LaneId, string[]> = {
  foundation: ["M0", "M2", "M3"],
  openmrs: ["M1", "M4", "M5"],
  safety: ["M6", "M7"],
  expansion: ["M8", "M9"],
};

const crossLaneEdges = [
  ["M2", "M4"],
  ["M3", "M4"],
  ["M2", "M5"],
  ["M3", "M5"],
  ["M2", "M6"],
  ["M3", "M6"],
  ["M5", "M6"],
  ["M4", "M8"],
  ["M5", "M8"],
  ["M2", "M9"],
  ["M3", "M9"],
  ["M7", "M9"],
] as const;

const sequencingNotes: Array<[string, string]> = [
  [
    "Default first spec: M0",
    "It gives the other specs stable assumptions about project locations, environment profiles, compose overlays, artifact layout, adapter boundaries, and local/VM workflows.",
  ],
  [
    "M1 can run early",
    "If the immediate goal is clinical corpus readiness, M1 can move in parallel once M0 captures the first control-plane assumptions.",
  ],
  [
    "M2 and M3 should not wait for all demo-data work",
    "The metadata contract and real adapter entrypoints unblock durable evidence for every later lane.",
  ],
  [
    "M4 is the first major convergence point",
    "Retrieval evaluation needs imported or labelled fixture-backed data, metadata capture, and a real adapter path.",
  ],
  [
    "M5 and M6 can start with fixtures but cannot make release-quality claims yet",
    "Answer/citation and safety work can use early cases, but durable claims wait for M1, M2, and M3.",
  ],
  [
    "M7 design starts early and gates late",
    "Review packets and rubric design can start as soon as M2 stabilizes, but governance gates need stable M4/M5/M6 artifacts.",
  ],
  [
    "M8 and M9 are reuse tests",
    "Querystore parity and cross-project expansion should reuse the validation spine rather than create separate harnesses.",
  ],
];

const governanceGates = [
  "Real production paths for validation claims when available.",
  "Deterministic, reviewed data transforms.",
  "Record-level evidence with decision rationale.",
  "Run, trace, response, evaluation, and review metadata captured separately from clinical evidence.",
  "Tests define behavior for remap, metadata, retrieval, answer quality, safety, and governance flows.",
  "Scenario diversity to reduce overfit to narrow prompts or happy-path records.",
];

function laneAccentToken(theme: ReturnType<typeof useHostTheme>, lane: LaneId): string {
  switch (lane) {
    case "foundation":
      return theme.accent.primary;
    case "openmrs":
      return theme.text.secondary;
    case "safety":
      return theme.diff.stripRemoved;
    case "expansion":
      return theme.diff.stripAdded;
  }
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return value.slice(0, max - 3) + "...";
}

function DependencyGraph() {
  const theme = useHostTheme();
  const nodeWidth = 212;
  const nodeHeight = 58;
  const layout = computeDAGLayout({
    nodes: features.map((feature) => ({ id: feature.id })),
    edges: dependencyEdges,
    direction: "vertical",
    nodeWidth,
    nodeHeight,
    rankGap: 64,
    nodeGap: 24,
    padding: 28,
  });

  return (
    <svg
      role="img"
      aria-label="Spec roadmap dependency graph"
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      style={{ display: "block" }}
    >
      <defs>
        <marker
          id="dependency-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {layout.ranks.map((rank) => (
        <rect
          key={`rank-${rank.rank}`}
          x={0}
          y={rank.y - 6}
          width={layout.width}
          height={rank.height + 12}
          rx={6}
          fill={rank.rank % 2 === 0 ? theme.fill.tertiary : "transparent"}
        />
      ))}

      {layout.edges.map((edge, index) => {
        const curve = Math.max(20, (edge.targetY - edge.sourceY) / 2);
        const d = `M ${edge.sourceX} ${edge.sourceY} C ${edge.sourceX} ${edge.sourceY + curve}, ${edge.targetX} ${
          edge.targetY - curve
        }, ${edge.targetX} ${edge.targetY}`;

        return (
          <path
            key={`edge-${index}`}
            d={d}
            fill="none"
            stroke={theme.stroke.secondary}
            strokeWidth={1.25}
            markerEnd="url(#dependency-arrow)"
          />
        );
      })}

      {layout.nodes.map((node) => {
        const feature = featureById.get(node.id);
        if (!feature) return null;

        const accent = laneAccentToken(theme, feature.lane);
        const isStart = feature.needs.length === 0;

        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent}
              strokeWidth={isStart ? 2 : 1.25}
            />
            <text
              x={node.x + 14}
              y={node.y + 22}
              fontSize={13}
              fill={theme.text.primary}
              style={{ fontFamily: "inherit", fontWeight: 600 }}
            >
              {feature.num}
            </text>
            <text
              x={node.x + 44}
              y={node.y + 22}
              fontSize={12}
              fill={theme.text.secondary}
              style={{ fontFamily: "inherit", letterSpacing: "0.04em", textTransform: "uppercase" }}
            >
              {lanes[feature.lane].shortLabel}
            </text>
            <text
              x={node.x + 14}
              y={node.y + 43}
              fontSize={12.5}
              fill={theme.text.primary}
              style={{ fontFamily: "inherit" }}
            >
              {truncate(feature.title, 28)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function ParallelLaneDiagram() {
  const theme = useHostTheme();
  const laneIds = Object.keys(laneFlows) as LaneId[];
  const width = 980;
  const laneHeight = 108;
  const leftLabelWidth = 150;
  const nodeWidth = 136;
  const nodeHeight = 44;
  const gap = 48;
  const top = 20;
  const height = laneIds.length * laneHeight + top;
  const nodePositions = new Map<string, { x: number; y: number; lane: LaneId }>();

  laneIds.forEach((laneId, laneIndex) => {
    const ids = laneFlows[laneId];
    ids.forEach((id, index) => {
      nodePositions.set(id, {
        x: leftLabelWidth + index * (nodeWidth + gap),
        y: top + laneIndex * laneHeight + 32,
        lane: laneId,
      });
    });
  });

  return (
    <svg
      role="img"
      aria-label="Parallel work lane diagram"
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: "block" }}
    >
      <defs>
        <marker
          id="lane-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {laneIds.map((laneId, laneIndex) => {
        const y = top + laneIndex * laneHeight;
        return (
          <g key={`lane-${laneId}`}>
            <rect
              x={0}
              y={y}
              width={width}
              height={laneHeight - 12}
              rx={8}
              fill={laneIndex % 2 === 0 ? theme.fill.tertiary : theme.fill.quaternary}
              stroke={theme.stroke.tertiary}
            />
            <text
              x={18}
              y={y + 40}
              fontSize={13}
              fill={laneAccentToken(theme, laneId)}
              style={{ fontFamily: "inherit", fontWeight: 600 }}
            >
              {lanes[laneId].label}
            </text>
            <text
              x={18}
              y={y + 62}
              fontSize={11}
              fill={theme.text.tertiary}
              style={{ fontFamily: "inherit" }}
            >
              {truncate(lanes[laneId].purpose, 44)}
            </text>
          </g>
        );
      })}

      {Object.entries(laneFlows).flatMap(([laneId, ids]) =>
        ids.slice(0, -1).map((fromId, index) => {
          const toId = ids[index + 1];
          const from = nodePositions.get(fromId);
          const to = nodePositions.get(toId);
          if (!from || !to) return null;
          return (
            <path
              key={`lane-edge-${fromId}-${toId}`}
              d={`M ${from.x + nodeWidth} ${from.y + nodeHeight / 2} L ${to.x - 10} ${to.y + nodeHeight / 2}`}
              stroke={theme.stroke.secondary}
              strokeWidth={1.25}
              fill="none"
              markerEnd="url(#lane-arrow)"
            />
          );
        }),
      )}

      {crossLaneEdges.map(([fromId, toId]) => {
        const from = nodePositions.get(fromId);
        const to = nodePositions.get(toId);
        if (!from || !to) return null;

        const startX = from.x + nodeWidth / 2;
        const startY = from.y + nodeHeight;
        const endX = to.x + nodeWidth / 2;
        const endY = to.y;
        const midY = (startY + endY) / 2;

        return (
          <path
            key={`cross-${fromId}-${toId}`}
            d={`M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`}
            stroke={theme.stroke.secondary}
            strokeWidth={1}
            strokeDasharray="4 4"
            fill="none"
            markerEnd="url(#lane-arrow)"
          />
        );
      })}

      {features.map((feature) => {
        const position = nodePositions.get(feature.id);
        if (!position) return null;
        const accent = laneAccentToken(theme, feature.lane);
        return (
          <g key={`node-${feature.id}`}>
            <rect
              x={position.x}
              y={position.y}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent}
              strokeWidth={1.25}
            />
            <text
              x={position.x + 12}
              y={position.y + 19}
              fontSize={12.5}
              fill={theme.text.primary}
              style={{ fontFamily: "inherit", fontWeight: 600 }}
            >
              {feature.num}
            </text>
            <text
              x={position.x + 12}
              y={position.y + 34}
              fontSize={11}
              fill={theme.text.secondary}
              style={{ fontFamily: "inherit" }}
            >
              {truncate(feature.title, 17)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function FeatureCard({ feature }: { feature: Feature }) {
  const lane = lanes[feature.lane];

  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" tone={lane.tone} active>{lane.shortLabel}</Pill>}>
        {`${feature.num} - ${feature.title}`}
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <Text tone="secondary">{feature.purpose}</Text>
          <Row gap={6} wrap>
            <Text size="small" tone="tertiary">
              Suggested spec slug:
            </Text>
            <Code>{feature.slug}</Code>
          </Row>
          <Divider />
          <Stack gap={4}>
            <Text size="small" weight="semibold">
              Scope
            </Text>
            {feature.scope.map((item) => (
              <Text key={item} size="small" tone="secondary">
                - {item}
              </Text>
            ))}
          </Stack>
          <Stack gap={4}>
            <Text size="small" weight="semibold">
              Evidence standard
            </Text>
            {feature.evidence.map((item) => (
              <Text key={item} size="small" tone="secondary">
                - {item}
              </Text>
            ))}
          </Stack>
          <Row gap={16} wrap>
            <Stack gap={4}>
              <Text size="small" tone="tertiary">
                Needs
              </Text>
              <Row gap={4} wrap>
                {feature.needs.length === 0 ? (
                  <Pill size="sm" tone="neutral">
                    none
                  </Pill>
                ) : (
                  feature.needs.map((need) => (
                    <Pill key={need} size="sm" tone="neutral">
                      {need}
                    </Pill>
                  ))
                )}
              </Row>
            </Stack>
            <Stack gap={4}>
              <Text size="small" tone="tertiary">
                Unlocks
              </Text>
              <Row gap={4} wrap>
                {feature.unlocks.length === 0 ? (
                  <Pill size="sm" tone="neutral">
                    leaf
                  </Pill>
                ) : (
                  feature.unlocks.map((unlock) => (
                    <Pill key={unlock} size="sm" tone="info">
                      {unlock}
                    </Pill>
                  ))
                )}
              </Row>
            </Stack>
          </Row>
        </Stack>
      </CardBody>
    </Card>
  );
}

const tableRows = features.map((feature) => [
  feature.num,
  feature.title,
  lanes[feature.lane].label,
  feature.needs.length === 0 ? "-" : feature.needs.join(", "),
  feature.unlocks.length === 0 ? "-" : feature.unlocks.join(", "),
  feature.slug,
]);

export default function SpecRoadmap() {
  const laneCounts = features.reduce<Record<LaneId, number>>(
    (acc, feature) => {
      acc[feature.lane] = acc[feature.lane] + 1;
      return acc;
    },
    { foundation: 0, openmrs: 0, safety: 0, expansion: 0 },
  );

  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>Spec Roadmap</H1>
        <Text tone="secondary">
          Canonical roadmap for deciding which Spec Kit feature specs to create. This document is dependency-oriented,
          not a strict execution order: some work can proceed in parallel once its prerequisites are in place.
        </Text>
      </Stack>

      <Grid columns={5} gap={16}>
        <Stat value={features.length} label="Planned feature specs" />
        <Stat value={laneCounts.foundation} label="Foundation" tone="info" />
        <Stat value={laneCounts.openmrs} label="OpenMRS corpus/eval" />
        <Stat value={laneCounts.safety} label="Safety/governance" tone="warning" />
        <Stat value={laneCounts.expansion} label="Expansion/migration" tone="success" />
      </Grid>

      <Callout tone="info" title="Default first spec">
        <Text>
          Start with <Code>001-harness-control-plane-foundation</Code>. It creates stable assumptions for project
          locations, environment profiles, compose overlays, artifacts, adapter boundaries, and local/VM workflows.
          <Code>002-openmrs-demo-data-2-8-remap</Code> can still run in parallel as a focused corpus-readiness effort.
        </Text>
      </Callout>

      <Divider />

      <H2>How To Use This Roadmap</H2>
      <Grid columns={3} gap={14}>
        <Card>
          <CardHeader>Pick the next spec</CardHeader>
          <CardBody>
            <Text tone="secondary">
              Prefer the earliest feature whose dependencies are satisfied and whose outputs unblock the most downstream
              validation work.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Run lanes in parallel</CardHeader>
          <CardBody>
            <Text tone="secondary">
              Foundation, OpenMRS data work, safety design, and expansion planning can be staffed separately as long as
              cross-lane gates are respected.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Promote evidence carefully</CardHeader>
          <CardBody>
            <Text tone="secondary">
              Fixture-backed work can shape design, but durable validation claims require real paths, metadata, and
              record-level rationale.
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Constitutional Gates</H2>
      <Text tone="secondary">
        Every feature spec created from this roadmap should pass these gates before implementation begins and again
        before validation claims are promoted.
      </Text>
      <Grid columns={2} gap={10}>
        {governanceGates.map((gate) => (
          <Callout key={gate} tone="neutral">
            <Text>{gate}</Text>
          </Callout>
        ))}
      </Grid>

      <Divider />

      <H2>Dependency Diagram</H2>
      <Text tone="secondary">
        Vertical layers represent dependency depth. A feature can begin as soon as every node feeding into it is stable.
        The heavier border marks the prerequisite-free starting point.
      </Text>
      <Card>
        <CardBody style={{ padding: 12 }}>
          <DependencyGraph />
        </CardBody>
      </Card>
      <Row gap={10} wrap>
        {(Object.keys(lanes) as LaneId[]).map((laneId) => (
          <Pill key={laneId} size="sm" tone={lanes[laneId].tone} active>
            {lanes[laneId].label}
          </Pill>
        ))}
      </Row>

      <Divider />

      <H2>Parallel Work Lanes</H2>
      <Text tone="secondary">
        Solid arrows show the natural within-lane flow. Dashed arrows show cross-lane gates that must be stable before
        downstream claims count as durable evidence.
      </Text>
      <Card>
        <CardBody style={{ padding: 12 }}>
          <ParallelLaneDiagram />
        </CardBody>
      </Card>

      <Divider />

      <H2>Lane Summary</H2>
      <Grid columns={4} gap={14}>
        {(Object.keys(lanes) as LaneId[]).map((laneId) => {
          const laneFeatures = features.filter((feature) => feature.lane === laneId);
          return (
            <Card key={laneId}>
              <CardHeader trailing={<Pill size="sm" tone={lanes[laneId].tone} active>{laneFeatures.length}</Pill>}>
                {lanes[laneId].label}
              </CardHeader>
              <CardBody>
                <Stack gap={10}>
                  <Text size="small" tone="secondary">
                    {lanes[laneId].purpose}
                  </Text>
                  <Divider />
                  {laneFeatures.map((feature) => (
                    <Stack key={feature.id} gap={2}>
                      <Text weight="semibold">
                        {feature.num} - {feature.title}
                      </Text>
                      <Text size="small" tone="tertiary">
                        {feature.slug}
                      </Text>
                    </Stack>
                  ))}
                </Stack>
              </CardBody>
            </Card>
          );
        })}
      </Grid>

      <Divider />

      <H2>Feature Specs</H2>
      <Grid columns={2} gap={14}>
        {features.map((feature) => (
          <FeatureCard key={feature.id} feature={feature} />
        ))}
      </Grid>

      <Divider />

      <H2>Practical Sequencing Notes</H2>
      <Grid columns={2} gap={12}>
        {sequencingNotes.map(([title, body]) => (
          <Stack key={title} gap={2}>
            <Text weight="semibold">{title}</Text>
            <Text tone="secondary">{body}</Text>
          </Stack>
        ))}
      </Grid>

      <H3>Compact Reference</H3>
      <Table
        headers={["#", "Title", "Lane", "Needs", "Unlocks", "Suggested Spec Slug"]}
        rows={tableRows}
        striped
      />
    </Stack>
  );
}
