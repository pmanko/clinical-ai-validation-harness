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
  useHostTheme,
} from 'cursor/canvas';

const phaseRows = [
  [
    '1. Profile and prepare inputs',
    'Load the 2.7 demo dump into legacy_27_raw; boot the O3 RefApp baseline with CIEL loaded into openmrs; compute schema diff and Liquibase cost.',
    'M2-A',
  ],
  [
    '2. Freeze reviewed mapping inputs',
    'Accepted FHIR ConceptMap remains the terminology source of truth; seed_emit expands it into SQLMesh CSV seeds.',
    'M2-C',
  ],
  [
    '3. Materialize SQLMesh models',
    'SQLMesh reads legacy_27_raw + openmrs + seeds and writes refapp_28_demo through seed, staging, clinical, module, and audit-view models.',
    'M2-D/E',
  ],
  [
    '4. Run conformance gates',
    'The harness invokes sqlmesh plan, run, audit; custom audits emit zero rows on pass and record-level failures on fail.',
    'M2-E',
  ],
  [
    '5. Export and validate downstream',
    'Dump refapp_28_demo.sql, boot/import against the real O3 stack, run binding checks, chartsearchai path checks, and sampler evidence.',
    'M2-F/G',
  ],
];

const sqlmeshLayers = [
  [
    'config.yaml',
    'Gateway and variables',
    'Pins the harness gateway to MariaDB and declares legacy_27_raw, openmrs, and refapp_28_demo schemas.',
  ],
  [
    'models/seeds/',
    'Reviewed and emitted inputs',
    'concept_translation.csv from ConceptMap; module_table_policy.csv for legacy-only module tables.',
  ],
  [
    'models/staging/',
    '1:1 source staging',
    'Staging models mirror selected legacy tables into the SQLMesh graph so downstream models can depend on stable names.',
  ],
  [
    'models/clinical/',
    'Clinical remap and promotion',
    'Rebound obs stays in obs; selected obs rows promote into drug_order, conditions, allergy, and test_order.',
  ],
  [
    'models/modules/',
    'Module-table policy',
    'Legacy-only module tables are carried forward, dropped, installed, or remapped according to reviewed policy.',
  ],
  [
    'audits/',
    'Acceptance gates',
    'Concept coverage, FK closure, policy bucket coverage, uniqueness, and not-null checks.',
  ],
];

const reviewerRows = [
  [
    'Concept identity bridge',
    'ConceptMap bridge rule plus concept_translation.csv',
    'Every legacy concept_id gets a target CIEL UUID via RPAD(concept_id, 36, A); obs-referenced concepts must have 100% coverage.',
  ],
  [
    'Structural promotions',
    'clinical/drug_order.sql, conditions.sql, allergy.sql, test_order.sql',
    'Only four typed-table promotion rules are reviewed; residual obs remains in obs for provenance and chartsearchai indexing.',
  ],
  [
    'Module table decisions',
    'module_table_policy.csv and modules/* models',
    'Each legacy-only module table needs an explicit carry-forward, drop, install-module, or remap policy with rationale.',
  ],
  [
    'Pre-staged Liquibase work',
    'clinical/modules models plus liquibase cost report',
    'Expensive post-2.7 changesets can be produced directly by SQLMesh so import startup does not pay full-table copy cost.',
  ],
  [
    'Audit failures',
    'audits/*.sql and transform artifacts',
    'A failing custom audit emits the exact concept, row, or FK problem; aggregate counts alone are not accepted evidence.',
  ],
];

const commandRows = [
  ['Seed emit', 'python -m harness.conceptmap.seed_emit --conceptmap datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json'],
  ['Static parse', 'sqlmesh -p datasets/transforms/sqlmesh parse'],
  ['Plan', 'sqlmesh -p datasets/transforms/sqlmesh plan --no-prompts'],
  ['Dry run', 'sqlmesh -p datasets/transforms/sqlmesh run --dry-run'],
  ['Execute via harness', 'python -m harness.transform.run --project-dir datasets/transforms/sqlmesh'],
  ['Audit', 'sqlmesh -p datasets/transforms/sqlmesh audit'],
  ['Export', 'mariadb-dump refapp_28_demo -> artifacts/<run>/transform/refapp_28_demo.sql'],
];

const outputRows = [
  [
    'refapp_28_demo',
    'Live MariaDB schema materialized by SQLMesh',
    'Candidate 2.8-compatible transformed corpus.',
  ],
  [
    'refapp_28_demo.sql',
    'Deterministic dump artifact',
    'Downstream import input for O3 RefApp, chartsearchai, and reviewer reproduction.',
  ],
  [
    'transform.report.json',
    'Run-level checksums and status',
    'Captures ConceptMap checksum, SQLMesh project checksum, seed checksums, dump checksum, audit status.',
  ],
  [
    'sqlmesh-*.txt',
    'Plan/run/audit logs',
    'Human-readable evidence when a stage fails.',
  ],
];

function FlowDiagram() {
  const theme = useHostTheme();
  const nodes = [
    { title: 'legacy_27_raw', detail: '2.7 demo dump', x: 20, y: 36 },
    { title: 'openmrs', detail: 'CIEL-loaded O3 baseline', x: 20, y: 130 },
    { title: 'ConceptMap', detail: 'reviewed mapping grammar', x: 20, y: 224 },
    { title: 'Seed emit', detail: 'concept_translation.csv', x: 245, y: 224 },
    { title: 'SQLMesh graph', detail: 'seed -> staging -> clinical -> modules', x: 470, y: 130 },
    { title: 'Audits', detail: 'zero rows on pass', x: 690, y: 130 },
    { title: 'refapp_28_demo', detail: 'materialized target schema', x: 905, y: 130 },
    { title: 'Dump + validate', detail: 'O3, chartsearchai, sampler', x: 905, y: 224 },
  ];
  const edges = [
    [0, 4],
    [1, 4],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 7],
  ];
  const width = 1120;
  const height = 340;
  const nodeW = 178;
  const nodeH = 68;

  return (
    <svg role="img" aria-label="Feature 002 SQLMesh transformation flow" width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        <marker id="sqlmesh-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>
      {edges.map(([from, to], i) => {
        const a = nodes[from];
        const b = nodes[to];
        const x1 = a.x + nodeW;
        const y1 = a.y + nodeH / 2;
        const x2 = b.x;
        const y2 = b.y + nodeH / 2;
        const midX = (x1 + x2) / 2;
        return (
          <path
            key={`e-${i}`}
            d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2 - 6} ${y2}`}
            fill="none"
            stroke={theme.stroke.secondary}
            strokeWidth={1.2}
            markerEnd="url(#sqlmesh-arrow)"
          />
        );
      })}
      {nodes.map((n, i) => {
        const accent = n.title === 'SQLMesh graph' || n.title === 'refapp_28_demo';
        return (
          <g key={n.title}>
            <rect
              x={n.x}
              y={n.y}
              width={nodeW}
              height={nodeH}
              rx={8}
              fill={accent ? theme.fill.secondary : theme.bg.elevated}
              stroke={accent ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={accent ? 1.5 : 1}
            />
            <text x={n.x + 12} y={n.y + 26} fontSize={13} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
              {n.title}
            </text>
            <text x={n.x + 12} y={n.y + 47} fontSize={11} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
              {n.detail}
            </text>
            {i === 4 && (
              <text x={n.x + 12} y={n.y + 86} fontSize={10.5} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
                plan / run / audit
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function SQLMeshTransformationFlow() {
  return (
    <Stack gap={18}>
      <Stack gap={8}>
        <Row gap={8} wrap>
          <Pill tone="info" active>Feature 002</Pill>
          <Pill tone="info" active>SQLMesh</Pill>
          <Pill tone="success" active>Deterministic transform</Pill>
          <Pill tone="warning" active>Reviewer-gated</Pill>
        </Row>
        <H1>How Feature 002 Uses SQLMesh</H1>
        <Text tone="secondary">
          Feature 002 turns the OpenMRS 2.7 demo dump into a 2.8/O3-compatible corpus by using SQLMesh as the
          deterministic SQL-to-SQL transformation layer. SQLMesh does not decide mappings; it executes reviewed
          ConceptMap and module-policy decisions against MariaDB and produces a reproducible target schema.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="3" label="Input schemas: legacy_27_raw, openmrs, refapp_28_demo" tone="info" />
        <Stat value="5" label="Core SQLMesh layers: seeds, staging, clinical, modules, audits" tone="info" />
        <Stat value="4" label="Typed-table promotion models from obs" tone="success" />
        <Stat value="0" label="Audit rows required for acceptance" tone="success" />
      </Grid>

      <Callout tone="info" title="One-sentence version">
        The harness freezes reviewed mapping decisions into CSV seeds, SQLMesh materializes the remapped clinical corpus
        into <Code>refapp_28_demo</Code>, then audits and dumps that schema for real OpenMRS and chartsearchai validation.
      </Callout>

      <Card>
        <CardBody>
          <FlowDiagram />
        </CardBody>
      </Card>

      <H2>Process In Five Phases</H2>
      <Table
        headers={['Phase', 'What happens', 'Milestone']}
        rows={phaseRows}
        striped
      />

      <Divider />

      <H2>The SQLMesh Project Shape</H2>
      <Text tone="secondary">
        The project root is <Code>datasets/transforms/sqlmesh/</Code>. SQLMesh is intentionally thin: model files are
        reviewable SQL, seeds are deterministic inputs, and audits are the acceptance gates.
      </Text>
      <Table
        headers={['Layer', 'Role', 'Feature 002 usage']}
        rows={sqlmeshLayers}
        striped
      />

      <Grid columns="1fr 1fr" gap={14}>
        <Card>
          <CardHeader>Inputs SQLMesh Reads</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">legacy_27_raw:</Text> the loaded 2.7 demo dump, treated as read-only source.</Text>
              <Text><Text weight="semibold">openmrs:</Text> the clean O3/Core 2.8 baseline after deterministic CIEL import.</Text>
              <Text><Text weight="semibold">concept_translation.csv:</Text> emitted from the accepted ConceptMap; not hand-edited.</Text>
              <Text><Text weight="semibold">module_table_policy.csv:</Text> reviewed policy for legacy-only module tables.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Outputs SQLMesh Produces</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">refapp_28_demo:</Text> materialized MariaDB target schema.</Text>
              <Text><Text weight="semibold">clinical typed tables:</Text> drug_order, conditions, allergy, test_order synthesized from obs where rules match.</Text>
              <Text><Text weight="semibold">rebound obs:</Text> residual observations remain available for provenance and chartsearchai indexing.</Text>
              <Text><Text weight="semibold">audit evidence:</Text> failing concepts, FK gaps, or policy gaps are emitted as rows.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Reviewer Surface</H2>
      <Text tone="secondary">
        The key design goal is to keep human review small and explicit. Reviewers do not inspect every row in the dump;
        they inspect the deterministic rules and the evidence rows that prove those rules covered the corpus.
      </Text>
      <Table
        headers={['Decision surface', 'Artifact', 'What reviewer checks']}
        rows={reviewerRows}
        striped
      />

      <H2>Command Flow</H2>
      <Table
        headers={['Step', 'Command or action']}
        rows={commandRows}
        striped
      />

      <H2>Run Artifacts</H2>
      <Table
        headers={['Artifact', 'What it is', 'Why it matters']}
        rows={outputRows}
        striped
      />

      <Divider />

      <H2>Load-Bearing Rules</H2>
      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader>Concept Identity Bridge</CardHeader>
          <CardBody>
            <Text>
              The accepted bridge rule maps legacy concept <Code>N</Code> to the seeded CIEL concept whose UUID is
              <Code> RPAD(N, 36, 'A')</Code>. The seed CSV expands this to one row per legacy concept, while the audit
              requires every obs-referenced concept to be covered.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Obs Preservation</CardHeader>
          <CardBody>
            <Text>
              Promotion does not erase provenance. Selected obs rows create typed records, while residual obs remains
              in <Code>clin__obs</Code>. This keeps chartsearchai retrieval and reviewer traceability intact.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Determinism Boundary</CardHeader>
          <CardBody>
            <Text>
              SQLMesh gives content-fingerprinted model versions and reproducible materialization, but the harness must
              keep seeds, UUID generation, dump flags, and runtime inputs deterministic too.
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="warning" title="Implementation caveat to resolve before M2-E signoff">
        The design says promoted-row UUIDs should be deterministic UUID v5 values, but the current
        <Code> clinical/drug_order.sql</Code> model uses <Code>UUID()</Code>. That should be replaced before claiming
        SC-004 byte-identical transform output.
      </Callout>

      <Callout tone="success" title="What SQLMesh buys us here">
        Feature 002 gets a reviewed, standards-based transform graph instead of ad hoc SQL scripts: the mapping decisions
        are externalized, the executable shape is visible in model files, and the acceptance gates are executable with
        <Code> sqlmesh plan</Code>, <Code> run</Code>, and <Code> audit</Code>.
      </Callout>
    </Stack>
  );
}
