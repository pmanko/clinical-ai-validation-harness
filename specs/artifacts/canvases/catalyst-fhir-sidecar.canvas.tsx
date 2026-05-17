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
  Link,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from 'cursor/canvas';

const pocQuestions = [
  { num: 1, question: 'Show recent lab results for patient X.', resources: ['Patient', 'Observation'] },
  { num: 2, question: 'What tests were ordered for patient X?', resources: ['Patient', 'ServiceRequest'] },
  { num: 3, question: 'Summarize abnormal results for patient X.', resources: ['Patient', 'Observation'] },
  { num: 4, question: 'Which diagnostic reports are available for patient X?', resources: ['Patient', 'DiagnosticReport'] },
  { num: 5, question: 'What results are linked to order Y?', resources: ['ServiceRequest', 'Observation'] },
];

const resourceCoverageRows = [
  ['Patient', 'Yes', 'Yes', 'Required'],
  ['ServiceRequest', 'Yes', 'Yes', 'Required'],
  ['Observation', 'Yes', 'Yes', 'Required'],
  ['DiagnosticReport', 'Yes', 'Yes', 'Required'],
  ['Practitioner', 'Yes', 'Yes', 'Required'],
  ['Organization', 'Yes', 'Yes', 'Required'],
  ['Specimen', 'Partial (via transform)', 'No dedicated provider', 'Gap — document if absent'],
];

const mcpTools = [
  ['search_patient', 'Search patients by name/identifier', 'Patient'],
  ['get_patient_context', 'Demographic + identifier summary', 'Patient'],
  ['get_service_requests', 'Lab orders; optional date range', 'ServiceRequest'],
  ['get_observations', 'Lab result Observations; optional LOINC filter', 'Observation'],
  ['get_diagnostic_reports', 'Diagnostic reports for a patient', 'DiagnosticReport'],
  ['get_resource_by_reference', 'Resolve any FHIR reference (ResourceType/id)', 'Any'],
  ['build_patient_lab_timeline', 'Chronological merge of Observations + DiagnosticReports', 'Observation, DiagnosticReport'],
];

const oe2GapLog = [
  ['HAPI app-layer auth', 'No application-level auth in hapi_application.yaml; CORS allows *', 'Low (dev only)', 'Open'],
  ['nginx /fhir route', 'nginx-prod.conf does not proxy /fhir; direct port 8081/8444 required', 'Medium', 'Open — file upstream'],
  ['Specimen provider', 'No dedicated embedded FHIR Specimen provider; partial via subscription', 'Medium', 'Open — document gap'],
  ['Embedded FHIR auth', 'Spring Security required for /OpenELIS-Global/fhir/*; Basic auth only', 'Low (parity probe)', 'Open'],
  ['Startup FHIR sync', 'transformOnStartup=false; manual backfill via /OEToFhir controller needed', 'High', 'Open — trigger in compose'],
];

const responseContractExample = `{
  "answer": "Patient X has 3 recent lab results...",
  "facts": [
    { "text": "Hemoglobin 10.2 g/dL (Low) on 2026-04-15", "source_ref": "Observation/12345" }
  ],
  "citations": [
    {
      "index": 1,
      "resourceType": "Observation",
      "id": "12345",
      "url": "https://fhir.openelis.org:8444/fhir/Observation/12345",
      "display": "Hemoglobin — 2026-04-15"
    }
  ],
  "uiBlocks": [
    {
      "type": "lab_result_table",
      "rows": [
        { "test": "Hemoglobin", "value": "10.2", "unit": "g/dL",
          "refRange": "12.0-16.0", "flag": "L", "date": "2026-04-15",
          "orderRef": "ServiceRequest/999" }
      ]
    },
    {
      "type": "lab_timeline",
      "events": [
        { "date": "2026-04-15", "resourceType": "Observation",
          "id": "12345", "display": "Hemoglobin 10.2 g/dL", "flag": "abnormal" }
      ]
    }
  ],
  "provenance": {
    "fhir_surface": "hapi",
    "fhir_base_url": "https://fhir.openelis.org:8444/fhir",
    "tools_called": ["search_patient", "get_observations"],
    "resource_ids": ["Patient/42", "Observation/12345"]
  }
}`;

function ArchDiagram() {
  const theme = useHostTheme();
  const w = 740;
  const h = 380;

  const box = (x: number, y: number, bw: number, bh: number, label: string, sub: string, accent: boolean) => (
    <g key={label}>
      <rect x={x} y={y} width={bw} height={bh} rx={6}
        fill={accent ? theme.bg.elevated : theme.bg.surface}
        stroke={accent ? theme.accent.primary : theme.stroke.secondary}
        strokeWidth={accent ? 1.5 : 1}
      />
      <text x={x + bw / 2} y={y + bh / 2 - (sub ? 6 : 0)} textAnchor="middle"
        fontSize={12} fontWeight={600} fill={theme.text.primary} style={{ fontFamily: 'inherit' }}>
        {label}
      </text>
      {sub && (
        <text x={x + bw / 2} y={y + bh / 2 + 11} textAnchor="middle"
          fontSize={10} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
          {sub}
        </text>
      )}
    </g>
  );

  const arrow = (x1: number, y1: number, x2: number, y2: number, dashed = false) => (
    <line x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={theme.stroke.secondary}
      strokeWidth={1.25}
      strokeDasharray={dashed ? '5 4' : undefined}
      markerEnd="url(#arr)"
    />
  );

  return (
    <svg role="img" aria-label="Catalyst FHIR sidecar architecture" width="100%"
      viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX={9} refY={5}
          markerWidth={6} markerHeight={6} orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {/* User */}
      {box(280, 10, 180, 40, 'Lab user / reviewer', '', false)}
      {arrow(370, 50, 370, 72)}

      {/* Sidecar UI */}
      {box(240, 72, 260, 44, 'Catalyst sidecar UI', 'report portal', true)}
      {arrow(370, 116, 370, 138)}

      {/* Gateway */}
      {box(250, 138, 240, 40, 'catalyst-gateway', ':8000 OpenAI-compat', false)}
      {arrow(370, 178, 370, 200)}

      {/* Agents */}
      {box(250, 200, 240, 40, 'catalyst-agents', 'RouterAgent → CatalystAgent', false)}
      {arrow(370, 240, 370, 262)}

      {/* MCP */}
      {box(250, 262, 240, 44, 'catalyst-mcp', ':9102  FHIR + schema tools', true)}

      {/* HAPI */}
      {box(530, 262, 200, 44, 'OE2 HAPI FHIR', 'fhir.openelis.org:8444', false)}
      {arrow(490, 284, 530, 284)}

      {/* Embedded */}
      {box(530, 322, 200, 44, 'OE2 embedded FHIR', '/OpenELIS-Global/fhir/*', false)}
      {arrow(490, 295, 510, 295)}
      {arrow(510, 295, 510, 344)}
      {arrow(510, 344, 530, 344)}

      {/* Parity label */}
      <text x={495} y={292} fontSize={9} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
        parity
      </text>

      {/* OE2 box */}
      <rect x={22} y={290} width={200} height={80} rx={6}
        fill="none" stroke={theme.stroke.secondary} strokeWidth={1} strokeDasharray="5 3" />
      <text x={32} y={308} fontSize={10} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
        OpenELIS Global 2
      </text>
      <text x={32} y={326} fontSize={10} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
        clinlims PostgreSQL
      </text>
      <text x={32} y={342} fontSize={10} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
        FhirTransformService
      </text>
      <text x={32} y={358} fontSize={10} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
        OE webapp
      </text>
    </svg>
  );
}

export default function CatalystFhirSidecarCanvas() {
  const theme = useHostTheme();

  return (
    <Stack gap={24}>
      <Stack gap={6}>
        <H1>Catalyst FHIR Sidecar — Vision Canvas</H1>
        <Text tone="secondary">
          M10 (Planning) — <Link href="../planning/catalyst-fhir-sidecar-brief.md">Source brief</Link> feeds{' '}
          <Code>/speckit-specify</Code> for <Code>011-catalyst-fhir-sidecar-poc</Code>.
          Catalyst is the core project; OpenELIS Global 2 is the supported host platform.
        </Text>
      </Stack>

      <Grid columns={4} gap={16}>
        <Stat value="5" label="Canonical POC questions" />
        <Stat value="6" label="Required FHIR resources" tone="info" />
        <Stat value="7" label="New MCP tools" />
        <Stat value="1" label="OE2 FHIR surface gap (Specimen)" tone="warning" />
      </Grid>

      <Divider />

      <H2>Architecture</H2>
      <Text tone="secondary" size="small">
        Catalyst sidecar talks to OE2's HAPI FHIR server (primary) and embedded FHIR providers (parity probe).
        OE2 is consumed as a sibling checkout via <Code>OPENELIS_ROOT</Code>; not submoduled.
      </Text>
      <ArchDiagram />

      <Divider />

      <Grid columns={2} gap={20}>
        <Stack gap={10}>
          <H2>Canonical POC Question Set</H2>
          <Text tone="secondary" size="small">
            Success criteria require all five questions to be answered with cited, resolvable FHIR resource IDs.
          </Text>
          {pocQuestions.map((q) => (
            <Card key={q.num}>
              <CardHeader trailing={
                <Row gap={4} wrap>
                  {q.resources.map((r) => <Pill key={r} size="sm" tone="info">{r}</Pill>)}
                </Row>
              }>
                Q{q.num}
              </CardHeader>
              <CardBody>
                <Text size="small">{q.question}</Text>
              </CardBody>
            </Card>
          ))}
        </Stack>

        <Stack gap={10}>
          <H2>Sidecar Response Contract</H2>
          <Text tone="secondary" size="small">
            Produced by the gateway; consumed by the sidecar UI and harness adapter.
            <Code>uiBlocks</Code> drive evidence cards, lab-result table, and lab timeline.
          </Text>
          <div style={{ overflowX: 'auto', borderRadius: 6, background: theme.bg.surface,
            border: `1px solid ${theme.stroke.secondary}`, padding: '12px 14px' }}>
            <pre style={{ margin: 0, fontSize: 11, color: theme.text.primary,
              fontFamily: 'monospace', lineHeight: 1.55, whiteSpace: 'pre' }}>
              {responseContractExample}
            </pre>
          </div>
        </Stack>
      </Grid>

      <Divider />

      <H2>FHIR Resource Coverage Matrix</H2>
      <Table
        headers={['Resource', 'OE2 HAPI', 'OE2 Embedded', 'POC requirement']}
        rows={resourceCoverageRows}
        rowTone={resourceCoverageRows.map((r) =>
          r[3].startsWith('Gap') ? 'warning' as const : undefined
        )}
      />

      <Divider />

      <H2>MCP Tool Sketch</H2>
      <Text tone="secondary" size="small">
        These replace/extend the current mock <Code>get_query_context</Code> / <Code>validate_sql</Code> tools.
        Catalyst agents must call via MCP protocol, not the stub <Code>mcp_client.get_schema()</Code> bypass (M10-C).
      </Text>
      <Table
        headers={['Tool', 'Description', 'Primary resource']}
        rows={mcpTools}
      />

      <Divider />

      <Stack gap={10}>
        <H2>OE2 FHIR Layer Gap Log</H2>
        <Text tone="secondary" size="small">
          Gaps recorded here are filed upstream to OE2; not fixed in this harness.
          The parity probe (M10-F) populates this table with measured divergences.
        </Text>
        <Table
          headers={['Gap', 'Detail', 'Severity', 'Status']}
          rows={oe2GapLog}
          rowTone={oe2GapLog.map((r) =>
            r[2] === 'High' ? 'warning' as const : undefined
          )}
        />
      </Stack>

      <Divider />

      <Grid columns={2} gap={20}>
        <Stack gap={8}>
          <H3>Scout-style sidecar UI — panels</H3>
          <Text tone="secondary" size="small">The report/analytics portal presents:</Text>
          {[
            ['Question input', 'Free text + patient/order context selector'],
            ['Answer panel', 'LLM answer with inline citation markers [O/1], [SR/2]'],
            ['Evidence cards', 'Grouped by FHIR resource type; resource ID + display text'],
            ['Lab-result table', 'Test · value · units · ref range · flag · date · order ref'],
            ['Lab timeline', 'Time-ordered Observations + DiagnosticReports; abnormal flags'],
            ['Debug drawer', 'FHIR query plan, raw resource IDs, raw resource snippets (on demand)'],
          ].map(([panel, desc]) => (
            <Row key={panel} gap={8} style={{ alignItems: 'flex-start' }}>
              <Text size="small" weight="semibold" style={{ minWidth: 120, flexShrink: 0 }}>{panel}</Text>
              <Text size="small" tone="secondary">{desc}</Text>
            </Row>
          ))}
        </Stack>

        <Stack gap={8}>
          <H3>Out of scope (POC)</H3>
          {[
            'SQL execution (deferred to OGC-070 M2 Java backend integration)',
            'OE2 frontend / Carbon UI integration',
            'LocalPHI mode — patient data in LLM context',
            'Catalyst RBAC / audit Java backend',
            'Full OE2 FHIR sync / backfill engineering',
            'openelis-catalyst repo housekeeping',
            'OE2 source-tree changes (nginx, HAPI auth)',
          ].map((item) => (
            <Text key={item} size="small" tone="secondary">— {item}</Text>
          ))}

          <Divider />

          <H3>Open questions for /speckit-clarify</H3>
          {[
            'HAPI app-layer auth model for POC',
            'Specimen coverage stance',
            'Lane name: openelis vs catalyst',
            'Sidecar UI hosting: gateway-served vs Vite app',
            'Evidence-card drill-down into OE2 legacy UI',
          ].map((q, i) => (
            <Row key={q} gap={6} style={{ alignItems: 'flex-start' }}>
              <Pill size="sm" tone="neutral">{i + 1}</Pill>
              <Text size="small" tone="secondary">{q}</Text>
            </Row>
          ))}
        </Stack>
      </Grid>

      <Callout tone="info">
        <Text size="small">
          <strong>Next steps:</strong> Run <Code>/speckit-specify</Code> against the{' '}
          <Link href="../planning/catalyst-fhir-sidecar-brief.md">source brief</Link> to produce{' '}
          <Code>specs/011-catalyst-fhir-sidecar-poc/spec.md</Code>, then <Code>/speckit-clarify</Code> to resolve open
          questions, then <Code>/speckit-plan</Code>, <Code>/speckit-tasks</Code>, and finally{' '}
          <Code>/speckit-implement</Code> per the three-phase metaplan.
        </Text>
      </Callout>

      <Text tone="tertiary" size="small">
        Paired brief: specs/artifacts/planning/catalyst-fhir-sidecar-brief.md ·
        Roadmap: M10 (Planning) · Feature folder (Phase 2): specs/011-catalyst-fhir-sidecar-poc/
      </Text>
    </Stack>
  );
}
