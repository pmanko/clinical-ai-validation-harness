import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  computeDAGLayout,
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

const projectRows = [
  [
    'Fast contract',
    'Java/Maven unit and integration tests, eval tag excluded by default',
    'Every local branch and PR',
    'Keep as the first gate; it catches parser, serializer, prompt assembly, API, and DAO regressions without model variance.',
  ],
  [
    'Test-data modernization',
    'Large OpenMRS demo-data SQL corpus, missing 2.8 build, and current Ref App metadata',
    'Before expanding validation beyond synthetic patient fixtures',
    'Target the large demo-data corpus, not the small default generator. First produce a 2.8-compatible mapping across schema and metadata differences, then commit deterministic import scripts and record-level verification.',
  ],
  [
    'Retrieval golden eval',
    'EnrichedRetrievalEvalTest with real ONNX embeddings and exact resultIndices baselines',
    'Pre-merge for retrieval changes; nightly for drift tracking',
    'Keep exact record inspection. Add per-case reason labels so baseline updates are reviewed clinically, not just mechanically.',
  ],
  [
    'LLM answer eval',
    'LlmAnswerQualityTest and PromptInjectionEvalTest against OpenAI-compatible endpoint',
    'Manual/scheduled because model server and model version affect output',
    'Run through LM Studio with pinned model id, model file hash, temperature, endpoint, and prompt version captured.',
  ],
  [
    'Querystore retrieval eval',
    'Future sibling-module contract for read-store retrieval quality',
    'Before chartsearchai delegates retrieval',
    'Compare chartsearchai retrieval behavior with querystore retrieval over its 153-record eval corpus before migration decisions.',
  ],
];

const methodologyRows = [
  [
    'Retrieval',
    'Precision@k, recall/coverage@k, miss@k, empty-answer correctness, latency',
    'Medical RAG studies show retrieval is often the main bottleneck; one large expert eval found only about 22% of top-16 passages relevant.',
  ],
  [
    'Test-data fidelity',
    'Import success, schema compatibility, concept mapping coverage, serialized resource coverage, known-answer fixtures',
    'OpenMRS demo data is version-sensitive; modern Ref App validation needs an importable corpus whose observations, concepts, encounters, notes, and demographics survive indexing.',
  ],
  [
    'Evidence selection',
    'Which retrieved records the answer actually cites or uses',
    'Separate retrieval quality from LLM use of evidence; relevant records can be retrieved and still ignored.',
  ],
  [
    'Answer grounding',
    'Claim-level support against retrieved context; unsupported, partially supported, contradicted',
    'Use RAGAS/TruLens-style faithfulness as a screening metric, but require clinician adjudication for acceptance thresholds.',
  ],
  [
    'Citation quality',
    'Statement-level citation precision and recall',
    'MedCite-style evaluation is a better fit than answer-level citation counts; every clinical claim should map to records.',
  ],
  [
    'Abstention',
    'Correct no-record/no-answer behavior, especially for negative clinical questions',
    'FHIR-AgentBench keeps empty-answer cases; OpenMRS should make absent-data cases first-class, not edge cases.',
  ],
  [
    'Security',
    'Prompt injection, system prompt leakage, schema escape, sensitive data disclosure',
    'OWASP LLM Top 10 2025 maps directly to regression suites plus structured-output validation.',
  ],
  [
    'Clinical review',
    'Blinded clinician scoring, inter-rater agreement, adjudication, reviewer instructions',
    'TRIPOD-LLM asks for assessor qualifications, annotation guidelines, and agreement reporting.',
  ],
  [
    'Governance',
    'Dataset transparency, intended use, change protocol, monitoring, rollback criteria',
    'NIST, CHAI, FDA PCCP, and STANDING Together all point toward documented lifecycle controls.',
  ],
];

const sourceRows = [
  [
    <Link href="https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data">OpenMRS Demo Data</Link>,
    'Documents platform-versioned demo SQL datasets, including large demo data, plus the modern Ref App generator path.',
    'Use the large demo-data corpus as the target dataset; step 1 is producing or verifying the missing 2.8-compatible version.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-referencedemodata">openmrs-module-referencedemodata</Link>,
    'Reference Application module that creates demo patients on startup from the global property path documented by OpenMRS.',
    'Use this as a current Ref App schema/metadata reference and control data path, not as the replacement for the large demo corpus.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-content-referenceapplication-demo">openmrs-content-referenceapplication-demo</Link>,
    'Reference Application demo content package with starter metadata such as labs, diagnoses, drugs, and configuration.',
    'Use as the metadata side of the mapping, especially when legacy SQL concepts do not align with current Ref App concepts.',
  ],
  [
    <Link href="https://arxiv.org/abs/2511.06738">Rethinking RAG for Medicine</Link>,
    'Stage-aware expert evaluation: retrieval, evidence selection, response factuality/completeness.',
    'Use its decomposition as the core OpenMRS validation model.',
  ],
  [
    <Link href="https://arxiv.org/abs/2501.16672">VeriFact</Link>,
    'EHR-grounded fact verification via RAG plus LLM-as-judge, compared with clinician ground truth.',
    'Adapt claim-level support labels for chart answers.',
  ],
  [
    <Link href="https://arxiv.org/abs/2506.06605">MedCite</Link>,
    'Medical citation generation and evaluation with statement-level citation precision and recall.',
    'Use citation precision/recall, not citation count, for answer quality.',
  ],
  [
    <Link href="https://arxiv.org/abs/2509.19319">FHIR-AgentBench</Link>,
    '2,931 clinical questions grounded in FHIR; reports retrieval and answer correctness, including empty answers.',
    'Borrow benchmark structure for querystore and OpenMRS resource-level QA.',
  ],
  [
    <Link href="https://medhelm.org/medhelm">MedHELM</Link>,
    'Holistic medical LLM evaluation emphasizing realistic tasks, safety, and reproducibility.',
    'Use for model-selection discipline, not as a replacement for OpenMRS-specific evals.',
  ],
  [
    <Link href="https://pmc.ncbi.nlm.nih.gov/articles/PMC12104976/">TRIPOD-LLM</Link>,
    'Healthcare LLM reporting checklist with data, metrics, annotation, prompting, compute, and intended-use items.',
    'Turn into metadata requirements for every eval run.',
  ],
  [
    <Link href="https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence">NIST GenAI Profile</Link>,
    'Risk-management lifecycle for design, development, use, and evaluation of GenAI systems.',
    'Use as governance backbone for release gates and monitoring.',
  ],
  [
    <Link href="https://chai.org/workgroup/responsible-ai/responsible-ai-checklists-raic">CHAI RAIC</Link>,
    'Healthcare AI self-review across usefulness, fairness, safety, transparency, privacy/security.',
    'Use for clinical-readiness checklist and review packet.',
  ],
  [
    <Link href="https://www.datadiversity.org/recommendations">STANDING Together</Link>,
    'Dataset diversity, inclusivity, generalisability, and transparency recommendations.',
    'Track who is represented in eval patients and clinical question sets.',
  ],
  [
    <Link href="https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/">OWASP LLM Top 10 2025</Link>,
    'Security risk taxonomy for prompt injection, leakage, vector weaknesses, misinformation, and more.',
    'Expand PromptInjectionEvalTest into a maintained red-team corpus.',
  ],
  [
    <Link href="https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/">RAGAS Faithfulness</Link>,
    'Claim-support scoring against retrieved context.',
    'Good automated screen; do not use as sole clinical acceptance criterion.',
  ],
  [
    <Link href="https://www.trulens.org/getting_started/core_concepts/rag_triad/">TruLens RAG Triad</Link>,
    'Context relevance, groundedness, and answer relevance.',
    'Matches the desired OpenMRS split: retrieve right records, cite facts, answer the question.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-querystore/blob/main/docs/migration-chartsearchai.md">Querystore migration notes</Link>,
    'Defines migration blockers: merge handling, bootstrap, long-text chunking, sync reliability, and tier-drift in evals.',
    'Treat read-store validation as a separate backend parity problem, not just a chartsearchai refactor.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-querystore/blob/main/docs/chartsearchai-port-map.md">Querystore port map</Link>,
    'Identifies serializers, embedding provider, RRF, ES builder, indexing task, and AOP coverage map relevant to migration.',
    'Use as the checklist for which validation fixtures must survive the port.',
  ],
  [
    <Link href="https://github.com/anichiti/openmrs_chatbot">openmrs_chatbot</Link>,
    'Parallel OpenMRS clinical chatbot (Python) with patient/doctor interfaces, workflow tracing, and agent-team scaffolding.',
    'Compare validation primitives for multi-turn role-conditioned answers and trace-aware evaluation.',
  ],
  [
    <Link href="https://github.com/DIGI-UW/OpenELIS-Global-2/tree/develop/projects/catalyst">OpenELIS Catalyst</Link>,
    'Lab-system AI: catalyst-gateway + catalyst-agents + catalyst-mcp (Python) with allowlisted schema RAG, LM Studio/Gemini providers, and RBAC-gated SQL execution.',
    'Validation primitives for NL->SQL, schema RAG, allowlist enforcement, multi-agent traces; shared infrastructure with the chartsearchai spine.',
  ],
];

const parallelComparisonRows = [
  [
    'Domain',
    'OpenMRS chart QA',
    'OpenMRS clinical chat',
    'OpenELIS lab assistant',
  ],
  [
    'Architecture',
    'Embedded Java module in OpenMRS; ONNX + Lucene + RRF retrieval over serialized chart records.',
    'Python chatbot with patient/doctor UIs and agent-team workflow scaffolding.',
    'Multi-service Python: catalyst-gateway + catalyst-agents + catalyst-mcp with provider abstraction (LM Studio + Gemini).',
  ],
  [
    'Retrieval mode',
    'Embedding-driven retrieval over patient chart records; ranks by cosine + BM25 + RRF.',
    'Conversational retrieval/orchestration over OpenMRS data; role-aware context shaping.',
    'MCP serves allowlisted schema context; LLM generates SQL, OE backend executes after user review.',
  ],
  [
    'Generation surface',
    'Structured JSON answer with chart-record citations.',
    'Multi-turn role-conditioned response (patient or doctor view).',
    'Generated SQL plus structured answer over query results; SQL is reviewed before execution.',
  ],
  [
    'Validation maturity',
    '485-case enriched retrieval, citation eval, absent-data eval, prompt-injection eval; planned spine and clinician adjudication.',
    'Early; setup, debug, and workflow-trace docs imply iterative manual eval; no published harness.',
    'M0/M1 milestones with provider and multi-agent E2E smoke scripts; allowlist + RBAC as guardrails.',
  ],
  [
    'Privacy/safety stance',
    'PHI handled through OpenMRS module boundary; PromptInjectionEvalTest covers direct injection.',
    'Patient/doctor role isolation in UI; safety surface needs definition.',
    'Schema allowlist + read-only DB user + RBAC at execution; defense-in-depth across MCP and OE.',
  ],
  [
    'Test data path',
    'Synthetic patient fixtures + planned large demo-data 2.8 remap.',
    'Likely in-app test fixtures; corpus and reproducibility unclear from public docs.',
    'Schema-only allowlist for non-PHI tables; uses real OpenELIS DB for execution under RBAC.',
  ],
];

const primitiveMatrixRows = [
  ['Test-data fidelity', 'Planned (2.8 remap)', 'Implementation-defined', 'Schema allowlist + dev DB'],
  ['Retrieval QA', 'Yes (golden baselines, 485 cases)', 'Implied (response coverage)', 'Schema-RAG QA (allowlisted)'],
  ['NL->SQL QA', 'Not applicable', 'Not applicable', 'Yes (primary surface)'],
  ['Agent-team trace QA', 'Not applicable', 'Yes (workflow trace docs)', 'Yes (multi-agent E2E)'],
  ['Citation/grounding', 'Yes (record-level)', 'Needs definition', 'Result-row attribution'],
  ['Abstention/empty answer', 'Yes (AbsentDataEvalTest)', 'Needs definition', 'No-result handling'],
  ['Prompt injection / safety', 'Yes (PromptInjectionEvalTest)', 'Needs definition', 'Allowlist + SQL validation + RBAC'],
  ['Clinician/expert review', 'Planned (P6 clinician adjudication)', 'Implied (debug docs)', 'Lab-tech review path on SQL'],
  ['Governance metadata', 'Planned (run-manifest from spine)', 'Limited', 'Provider/version pinning, env templates'],
];

const archLabels: Record<string, string> = {
  demo: 'Demo data sources',
  mapping: 'LLM mapping spec',
  corpus: 'Imported patient corpus',
  cases: 'Eval case sets',
  onnx: 'ONNX models',
  llm: 'LM Studio (LLM)',
  contract: 'Contract tests',
  retrieval: 'Retrieval eval',
  answer: 'Answer eval',
  safety: 'Safety eval',
  manifest: 'Run manifest',
  jsonl: 'JSONL traces',
  summary: 'Summary CSV',
  dashboard: 'Dashboard',
  baseline: 'Baseline diff',
  review: 'Clinician review',
  gates: 'Release gates',
};

const archEdges: Array<[string, string]> = [
  ['demo', 'mapping'], ['mapping', 'corpus'], ['corpus', 'cases'],
  ['corpus', 'retrieval'], ['corpus', 'answer'], ['corpus', 'safety'],
  ['cases', 'contract'], ['cases', 'retrieval'], ['cases', 'answer'], ['cases', 'safety'],
  ['onnx', 'retrieval'], ['onnx', 'answer'],
  ['llm', 'answer'], ['llm', 'safety'],
  ['contract', 'manifest'], ['retrieval', 'manifest'], ['answer', 'manifest'], ['safety', 'manifest'],
  ['retrieval', 'jsonl'], ['answer', 'jsonl'], ['safety', 'jsonl'],
  ['retrieval', 'summary'], ['answer', 'summary'], ['safety', 'summary'],
  ['manifest', 'dashboard'], ['jsonl', 'dashboard'], ['summary', 'dashboard'],
  ['jsonl', 'baseline'], ['jsonl', 'review'],
  ['dashboard', 'gates'], ['baseline', 'gates'], ['review', 'gates'],
];

const archAccent = new Set(['mapping', 'corpus', 'retrieval', 'answer', 'safety', 'review', 'gates']);

const archRankTitles = ['Sources', 'Mapping', 'Corpus', 'Cases', 'Drivers', 'Artifacts', 'Sinks'];

function ArchitectureDiagram() {
  const theme = useHostTheme();
  const nodeWidth = 156;
  const nodeHeight = 42;
  const layout = computeDAGLayout({
    nodes: Object.keys(archLabels).map((id) => ({ id })),
    edges: archEdges.map(([from, to]) => ({ from, to })),
    direction: 'horizontal',
    nodeWidth,
    nodeHeight,
    rankGap: 64,
    nodeGap: 14,
    padding: 24,
  });

  return (
    <svg
      role="img"
      aria-label="Target validation architecture"
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height + 22}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {layout.ranks.map((rank, idx) => (
        <g key={rank.rank}>
          <rect
            x={rank.x}
            y={rank.y + 22}
            width={rank.width}
            height={rank.height}
            fill={theme.fill.tertiary}
            rx={8}
          />
          <text
            x={rank.x + rank.width / 2}
            y={rank.y + 14}
            fontSize={11}
            textAnchor="middle"
            fill={theme.text.tertiary}
            style={{ fontFamily: 'inherit', letterSpacing: '0.06em', textTransform: 'uppercase' }}
          >
            {archRankTitles[idx] ?? `Rank ${idx + 1}`}
          </text>
        </g>
      ))}

      {layout.edges.map((edge, i) => {
        const dx = Math.max(20, (edge.targetX - edge.sourceX) / 2);
        const d = `M ${edge.sourceX} ${edge.sourceY + 22} C ${edge.sourceX + dx} ${edge.sourceY + 22}, ${edge.targetX - dx} ${edge.targetY + 22}, ${edge.targetX} ${edge.targetY + 22}`;
        return (
          <path
            key={i}
            d={d}
            stroke={theme.stroke.secondary}
            strokeWidth={1}
            fill="none"
            markerEnd="url(#arch-arrow)"
          />
        );
      })}

      {layout.nodes.map((node) => {
        const accent = archAccent.has(node.id);
        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y + 22}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={accent ? 1.5 : 1}
            />
            <text
              x={node.x + nodeWidth / 2}
              y={node.y + 22 + nodeHeight / 2 + 4}
              fontSize={12}
              textAnchor="middle"
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit' }}
            >
              {archLabels[node.id]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const flowLabels: Record<string, string> = {
  question: 'Clinical question',
  retrieve: 'Retrieve (ONNX/Lucene/RRF)',
  filter: 'Filter & rank',
  context: 'Build chart context',
  generate: 'LLM generate',
  parse: 'Parse JSON answer',
  faithful: 'Faithfulness',
  citation: 'Citation P/R',
  absent: 'Abstention check',
  schema: 'Schema/safety',
  label: 'Case label',
  aggregate: 'Aggregate metrics',
};

const flowEdges: Array<[string, string]> = [
  ['question', 'retrieve'],
  ['retrieve', 'filter'],
  ['filter', 'context'],
  ['context', 'generate'],
  ['generate', 'parse'],
  ['parse', 'faithful'],
  ['parse', 'citation'],
  ['parse', 'absent'],
  ['parse', 'schema'],
  ['faithful', 'label'],
  ['citation', 'label'],
  ['absent', 'label'],
  ['schema', 'label'],
  ['label', 'aggregate'],
];

const flowAccent = new Set(['retrieve', 'generate', 'label']);
const flowRankTitles = ['Input', 'Retrieve', 'Filter', 'Context', 'Generate', 'Parse', 'Grade', 'Label', 'Roll-up'];

function ValidationFlowDiagram() {
  const theme = useHostTheme();
  const nodeWidth = 168;
  const nodeHeight = 42;
  const layout = computeDAGLayout({
    nodes: Object.keys(flowLabels).map((id) => ({ id })),
    edges: flowEdges.map(([from, to]) => ({ from, to })),
    direction: 'horizontal',
    nodeWidth,
    nodeHeight,
    rankGap: 56,
    nodeGap: 12,
    padding: 24,
  });

  return (
    <svg
      role="img"
      aria-label="Per-case validation flow"
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height + 22}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {layout.ranks.map((rank, idx) => (
        <g key={rank.rank}>
          <rect
            x={rank.x}
            y={rank.y + 22}
            width={rank.width}
            height={rank.height}
            fill={theme.fill.tertiary}
            rx={8}
          />
          <text
            x={rank.x + rank.width / 2}
            y={rank.y + 14}
            fontSize={11}
            textAnchor="middle"
            fill={theme.text.tertiary}
            style={{ fontFamily: 'inherit', letterSpacing: '0.06em', textTransform: 'uppercase' }}
          >
            {flowRankTitles[idx] ?? `Step ${idx + 1}`}
          </text>
        </g>
      ))}

      {layout.edges.map((edge, i) => {
        const dx = Math.max(20, (edge.targetX - edge.sourceX) / 2);
        const d = `M ${edge.sourceX} ${edge.sourceY + 22} C ${edge.sourceX + dx} ${edge.sourceY + 22}, ${edge.targetX - dx} ${edge.targetY + 22}, ${edge.targetX} ${edge.targetY + 22}`;
        return (
          <path
            key={i}
            d={d}
            stroke={theme.stroke.secondary}
            strokeWidth={1}
            fill="none"
            markerEnd="url(#flow-arrow)"
          />
        );
      })}

      {layout.nodes.map((node) => {
        const accent = flowAccent.has(node.id);
        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y + 22}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={accent ? 1.5 : 1}
            />
            <text
              x={node.x + nodeWidth / 2}
              y={node.y + 22 + nodeHeight / 2 + 4}
              fontSize={12}
              textAnchor="middle"
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit' }}
            >
              {flowLabels[node.id]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const testDataLabels: Record<string, string> = {
  wiki: 'Demo Data wiki',
  legacy: 'large-demo-data SQL',
  refapp: 'Current Ref App DB',
  content: 'Demo content package',
  schemaDiff: '2.8 schema diff',
  extract: 'Metadata extract',
  llmMap: 'LLM mapping proposal',
  review: 'Human review',
  migration: '2.8 import plan',
  importRun: 'Local Ref App import',
  smoke: 'Import smoke tests',
  indexRun: 'chartsearchai indexing',
  labels: 'Known-answer labels',
  corpus: 'Validation corpus',
};

const testDataEdges: Array<[string, string]> = [
  ['wiki', 'legacy'],
  ['wiki', 'refapp'],
  ['legacy', 'schemaDiff'],
  ['refapp', 'schemaDiff'],
  ['schemaDiff', 'extract'],
  ['content', 'extract'],
  ['extract', 'llmMap'],
  ['llmMap', 'review'],
  ['review', 'migration'],
  ['migration', 'importRun'],
  ['importRun', 'smoke'],
  ['smoke', 'indexRun'],
  ['indexRun', 'labels'],
  ['labels', 'corpus'],
];

const testDataAccent = new Set(['schemaDiff', 'llmMap', 'review', 'migration', 'smoke', 'corpus']);
const testDataRankTitles = ['Sources', 'Raw Data', 'Schema Diff', 'Metadata', 'Map', 'Review', 'Plan', 'Import', 'Smoke', 'Index', 'Label', 'Corpus'];

function TestDataMappingDiagram() {
  const theme = useHostTheme();
  const nodeWidth = 164;
  const nodeHeight = 42;
  const layout = computeDAGLayout({
    nodes: Object.keys(testDataLabels).map((id) => ({ id })),
    edges: testDataEdges.map(([from, to]) => ({ from, to })),
    direction: 'horizontal',
    nodeWidth,
    nodeHeight,
    rankGap: 48,
    nodeGap: 12,
    padding: 24,
  });

  return (
    <svg
      role="img"
      aria-label="Demo data mapping and import flow"
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height + 22}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="test-data-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {layout.ranks.map((rank, idx) => (
        <g key={rank.rank}>
          <rect
            x={rank.x}
            y={rank.y + 22}
            width={rank.width}
            height={rank.height}
            fill={theme.fill.tertiary}
            rx={8}
          />
          <text
            x={rank.x + rank.width / 2}
            y={rank.y + 14}
            fontSize={11}
            textAnchor="middle"
            fill={theme.text.tertiary}
            style={{ fontFamily: 'inherit', letterSpacing: '0.06em', textTransform: 'uppercase' }}
          >
            {testDataRankTitles[idx] ?? `Step ${idx + 1}`}
          </text>
        </g>
      ))}

      {layout.edges.map((edge, i) => {
        const dx = Math.max(20, (edge.targetX - edge.sourceX) / 2);
        const d = `M ${edge.sourceX} ${edge.sourceY + 22} C ${edge.sourceX + dx} ${edge.sourceY + 22}, ${edge.targetX - dx} ${edge.targetY + 22}, ${edge.targetX} ${edge.targetY + 22}`;
        return (
          <path
            key={i}
            d={d}
            stroke={theme.stroke.secondary}
            strokeWidth={1}
            fill="none"
            markerEnd="url(#test-data-arrow)"
          />
        );
      })}

      {layout.nodes.map((node) => {
        const accent = testDataAccent.has(node.id);
        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y + 22}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={accent ? 1.5 : 1}
            />
            <text
              x={node.x + nodeWidth / 2}
              y={node.y + 22 + nodeHeight / 2 + 4}
              fontSize={12}
              textAnchor="middle"
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit' }}
            >
              {testDataLabels[node.id]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const demoDataWorkRows = [
  [
    'large-demo-data-2-7-0.sql.zip / legacy corpus',
    'This is the dataset Paul is pointing at: a full, complete, large OpenMRS corpus with enough diversity for retrieval validation.',
    'High: it originates from OpenMRS 1.x-era metadata and older platform schemas; no 2.8-compatible build is available yet.',
    'Make the 2.8 remap the first milestone: compare 2.7/lower SQL to a clean 2.8 Ref App DB, map metadata, then create a deterministic 2.8 import artifact.',
  ],
  [
    'Ref App demo generator',
    'Modern default demo-data path: set referencedemodata.createDemoPatientsOnNextStartup and restart.',
    'Medium: it is not the target dataset; it is useful as a current Ref App metadata/schema reference and a smoke-test fallback.',
    'Use to understand expected current metadata and to generate control patients, but do not treat it as replacing the large corpus.',
  ],
  [
    'Demo content package',
    'Reference metadata for labs, diagnoses, drugs, and configuration.',
    'Medium: metadata can drift from local distro versions or installed module set.',
    'Map legacy concepts to current metadata before importing observations; flag unmapped concepts for manual review.',
  ],
  [
    'LLM mapping proposal',
    'Fast way to compare lower-version SQL schema, 2.8 schema, concept names, encounter types, obs groups, and Ref App metadata.',
    'Controlled: LLM output is analysis only, not executable truth; schema differences must be verified from real DB dumps.',
    'Require Daniel/Ian-style review plus unit-tested SQL/Liquibase scripts before any local import is accepted.',
  ],
  [
    'Validation labels',
    'Known-answer clinical questions tied to specific imported records.',
    'High if labels are inferred after the fact from noisy demo data.',
    'Create labels from inspected records and store record ids/snippets with every expected answer.',
  ],
];

type Phase = {
  id: string;
  week: string;
  title: string;
  goal: string;
  entry: string;
  exit: string;
  deliverables: string[];
  tone: 'success' | 'info' | 'warning' | 'neutral';
};

const phases: Phase[] = [
  {
    id: 'P0',
    week: 'Week 1',
    title: 'Local baseline & runbook',
    goal: 'Reproducible local dev loop and a v0 baseline of every metric we already produce.',
    entry: 'chartsearchai cloned, mvn -pl api install green, LM Studio installed.',
    exit: 'eval-results.csv captured, EnrichedRetrievalEvalTest (L6 + MedCPT) passes locally, runbook checked in.',
    deliverables: [
      'Local-dev runbook (commands, env, caveats)',
      'Baseline metrics snapshot (CSV + git tag)',
      'Skipped-test inventory with reasons',
    ],
    tone: 'success',
  },
  {
    id: 'P1',
    week: 'Week 2',
    title: 'Large demo-data 2.8 remap',
    goal: 'Produce or verify a Platform/Core 2.8-compatible version of the large OpenMRS demo-data corpus, mapped to current Ref App metadata.',
    entry: 'Phase 0 baseline captured.',
    exit: 'Disposable local Ref App import succeeds from a deterministic 2.8 artifact; chartsearchai indexes imported patients; known-answer seed cases reference inspected records.',
    deliverables: [
      'Source inventory for large-demo-data SQL versions, with 2.7.0 as the likely starting artifact and 2.8.0 gap documented',
      'LLM-assisted schema and metadata mapping report for lower-version SQL -> Platform/Core 2.8 + current Ref App metadata',
      'Deterministic 2.8 import artifact/runbook plus import smoke tests',
    ],
    tone: 'warning',
  },
  {
    id: 'P2',
    week: 'Week 3',
    title: 'Validation spine',
    goal: 'One canonical artifact schema written by every eval suite, including demo-data provenance.',
    entry: 'Phase 1 import path and source inventory are stable.',
    exit: 'Each eval test class emits run-manifest.json + JSONL trace + appends to summary CSV with dataset/source metadata.',
    deliverables: [
      'EvalRecord writer (shared utility)',
      'Run-manifest helper aligned to OpenTelemetry GenAI conventions (model, embedding, git SHA, prompt version, dataset source)',
      'Surefire wiring + README section on artifact layout',
    ],
    tone: 'info',
  },
  {
    id: 'P3',
    week: 'Week 4',
    title: 'Stage-aware retrieval metrics',
    goal: 'Move beyond exact baseline match to multi-metric retrieval health.',
    entry: 'Spine emits JSONL traces per case.',
    exit: 'precision@k, recall@k, miss@k, latency, per-resource-type breakdowns published per case for L6 and MedCPT.',
    deliverables: [
      'Retrieval aggregation report (per model + per dataset)',
      'Baseline diff tool that surfaces returned record snippets',
      'Per-case "expected absent" vs "missed evidence" labels',
    ],
    tone: 'info',
  },
  {
    id: 'P4',
    week: 'Week 5',
    title: 'Answer & citation grading',
    goal: 'Grade generated answers against retrieved evidence for citation correctness, faithfulness, and abstention.',
    entry: 'LM Studio endpoint pinned with model id and file hash.',
    exit: 'Nightly LM Studio harness emits citation precision/recall, faithfulness flags, abstention correctness per case.',
    deliverables: [
      'Claim extractor + JSON-schema validator',
      'Expanded AbsentDataEvalTest with chart-grounded expectations',
      'Generation harness reusing production prompt assembly',
    ],
    tone: 'info',
  },
  {
    id: 'P5',
    week: 'Week 6',
    title: 'Safety & red team',
    goal: 'Expand prompt-injection coverage to OWASP LLM Top 10 and indirect injection through chart text.',
    entry: 'Phase 4 generation harness operational.',
    exit: 'Maintained injection corpus with direct, indirect, obfuscated, and PHI-leak categories; nightly safety report.',
    deliverables: [
      'Expanded prompt-injection-eval-dataset.json',
      'Indirect-injection cases planted in observation/note text',
      'Safety dashboard panel + escalation criteria',
    ],
    tone: 'warning',
  },
  {
    id: 'P6',
    week: 'Week 7',
    title: 'Clinician adjudication & governance',
    goal: 'Make clinical sign-off reproducible and gate baseline updates on clinician review.',
    entry: 'Stable artifacts and dashboard from earlier phases.',
    exit: 'Clinician review packet + rubric labels + TRIPOD-LLM/CHAI checklist filled per release candidate.',
    deliverables: [
      'Blinded review tool + scoring template',
      'Inter-rater agreement tracking',
      'Baseline change-control protocol',
    ],
    tone: 'info',
  },
  {
    id: 'P7',
    week: 'Week 8+',
    title: 'Querystore parity testbed',
    goal: 'Run the same suites against today\'s chartsearchai pipeline and the querystore-backed pipeline.',
    entry: 'querystore module locally built; chartsearchai retrieval delegated through a backend selector.',
    exit: 'Identical JSONL artifacts produced by both backends; tier-aware comparison report.',
    deliverables: [
      'Backend selector flag + adapter',
      'Parity report (precision@k, citation, abstention) per backend',
      'Migration go/no-go criteria document',
    ],
    tone: 'neutral',
  },
];

function PhaseCard({ phase }: { phase: Phase }) {
  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" tone={phase.tone} active>{phase.week}</Pill>}>
        {`${phase.id} · ${phase.title}`}
      </CardHeader>
      <CardBody>
        <Stack gap={8}>
          <Text><Text weight="semibold">Goal:</Text> {phase.goal}</Text>
          <Text tone="secondary"><Text weight="semibold">Entry:</Text> {phase.entry}</Text>
          <Text tone="secondary"><Text weight="semibold">Exit:</Text> {phase.exit}</Text>
          <Stack gap={4}>
            <Text weight="semibold">Deliverables</Text>
            {phase.deliverables.map((d) => (
              <Text key={d} tone="secondary">• {d}</Text>
            ))}
          </Stack>
        </Stack>
      </CardBody>
    </Card>
  );
}

function MilestoneTimeline() {
  const theme = useHostTheme();
  const totalWeeks = 9;
  const items = phases.map((p, idx) => {
    const start = idx;
    const span = idx === phases.length - 1 ? totalWeeks - start : 1;
    return { ...p, start, span };
  });
  const headerHeight = 28;
  const rowHeight = 32;
  const rowGap = 8;
  const padX = 12;
  const viewWidth = 960;
  const innerWidth = viewWidth - padX * 2;
  const colWidth = innerWidth / totalWeeks;
  const viewHeight = headerHeight + items.length * (rowHeight + rowGap) + 12;

  return (
    <svg
      role="img"
      aria-label="Validation milestone timeline"
      width="100%"
      viewBox={`0 0 ${viewWidth} ${viewHeight}`}
      style={{ display: 'block' }}
    >
      {Array.from({ length: totalWeeks }).map((_, i) => (
        <g key={`col-${i}`}>
          <line
            x1={padX + i * colWidth}
            y1={headerHeight - 4}
            x2={padX + i * colWidth}
            y2={viewHeight - 4}
            stroke={theme.stroke.tertiary}
            strokeWidth={1}
          />
          <text
            x={padX + i * colWidth + colWidth / 2}
            y={18}
            fontSize={11}
            textAnchor="middle"
            fill={theme.text.tertiary}
            style={{ fontFamily: 'inherit', letterSpacing: '0.06em' }}
          >
            W{i + 1}
          </text>
        </g>
      ))}
      <line
        x1={padX + totalWeeks * colWidth}
        y1={headerHeight - 4}
        x2={padX + totalWeeks * colWidth}
        y2={viewHeight - 4}
        stroke={theme.stroke.tertiary}
        strokeWidth={1}
      />

      {items.map((item, idx) => {
        const y = headerHeight + idx * (rowHeight + rowGap);
        const x = padX + item.start * colWidth + 4;
        const width = item.span * colWidth - 8;
        return (
          <g key={item.id}>
            <rect
              x={x}
              y={y}
              width={width}
              height={rowHeight}
              rx={6}
              fill={theme.fill.secondary}
              stroke={theme.accent.primary}
              strokeWidth={1}
            />
            <text
              x={x + 10}
              y={y + rowHeight / 2 + 4}
              fontSize={12}
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit' }}
            >
              {item.id} · {item.title}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const coverageCategories = [
  'Demo-data import smoke',
  'Retrieval L6-v2',
  'Retrieval MedCPT',
  'Citation eval',
  'Absent-data eval',
  'Prompt injection',
  'Clinician rubric',
  'Red-team OWASP',
];

const verifiedCoverage = [0, 485, 485, 10, 29, 33, 0, 0];

export default function ValidationResearch() {
  return (
    <Stack gap={18}>
      <Stack gap={8}>
        <H1>Clinical AI Validation Research</H1>
        <Text tone="secondary">
          Anchored in chartsearchai and querystore validation, with comparative context on two parallel approaches:
          openmrs_chatbot (Python multi-agent OpenMRS chatbot) and OpenELIS Catalyst (NL-to-SQL lab assistant).
          The recommended shape is a layered validation system: modern test data first, deterministic retrieval gates next,
          model-dependent answer gates after that, and clinician adjudication and governance around all of it.
        </Text>
        <Row gap={8} wrap>
          <Pill tone="info" active>Clinical RAG</Pill>
          <Pill tone="info" active>EHR QA</Pill>
          <Pill tone="info" active>NL-to-SQL</Pill>
          <Pill tone="info" active>Agent traces</Pill>
          <Pill tone="info" active>Test data</Pill>
          <Pill tone="info" active>Citations</Pill>
          <Pill tone="info" active>Safety</Pill>
          <Pill tone="info" active>Governance</Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="5" label="Validation lanes" tone="info" />
        <Stat value="485" label="Chartsearchai enriched retrieval cases" tone="success" />
        <Stat value="3" label="Core RAG quality edges" tone="info" />
        <Stat value="1" label="Main warning: RAG can regress clinical answers" tone="warning" />
      </Grid>

      <Callout tone="warning" title="Main takeaway">
        Treat retrieval, evidence use, final answer quality, and safety as separate gates. Recent medical RAG evidence argues against a single end-to-end score:
        irrelevant retrieval can degrade answers, and relevant retrieval does not guarantee the LLM will use the evidence correctly.
      </Callout>

      <H2>Project-Fit Validation Lanes</H2>
      <Table
        headers={['Lane', 'Current/OpenMRS asset', 'When to run', 'Recommendation']}
        rows={projectRows}
        striped
      />

      <H2>Methodology Map</H2>
      <Table
        headers={['Dimension', 'Metric or review target', 'Why it matters here']}
        rows={methodologyRows}
        striped
      />

      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>Near-term architecture</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text><Text weight="semibold">1. Deterministic gates:</Text> Maven contract, serializer tests, exact retrieval baselines, absent-data cases.</Text>
              <Text><Text weight="semibold">2. Model-dependent gates:</Text> LM Studio answer quality, prompt injection, citation support, JSON schema compliance.</Text>
              <Text><Text weight="semibold">3. Human review:</Text> clinician adjudication packets for baseline changes, clinical question coverage, and failure labels.</Text>
              <Text><Text weight="semibold">4. Governance:</Text> run metadata, model hashes, dataset composition, intended-use notes, and change-control records.</Text>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Data model for eval results</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text>Every eval run should emit machine-readable records with query id, patient/dataset id, model id, retrieval pipeline, retrieved record ids, cited record ids, answer JSON, latency, pass/fail, and reviewer notes.</Text>
              <Text>Every baseline update should preserve the returned records, not just counts, because false positives can look like progress until a clinician inspects the actual chart evidence.</Text>
              <Text>Model-dependent runs need pinned LM Studio model name, model file/hash where available, temperature, context length, prompt version, and endpoint URL.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Recommended First Backlog</H2>
      <Grid columns="1.2fr 1fr" gap={16}>
        <Stack gap={8}>
          <H3>Build the validation spine</H3>
          <Text>Normalize all existing eval outputs into one CSV/JSONL schema and keep `eval-results.csv` as a compatibility artifact if needed.</Text>
          <Text>Add a run manifest capturing model, embedding files, Git SHA, pipeline config, prompt version, and dataset version.</Text>
          <Text>Make retrieval failures explainable by storing returned record snippets for failed cases.</Text>
          <Text>Separate “expected empty answer” cases from “retriever missed evidence” cases.</Text>
        </Stack>
        <Stack gap={8}>
          <H3>Prepare clinician review</H3>
          <Text>Create a blinded review packet for the 18/20 clinical questions: question, answer, citations, source snippets, and rubric.</Text>
          <Text>Use labels: supported, partially supported, unsupported, contradicted, omitted, over-inclusive, safe abstention.</Text>
          <Text>Track inter-rater agreement and require adjudication before promoting new golden baselines.</Text>
        </Stack>
      </Grid>

      <H2>Sources To Reuse</H2>
      <Table
        headers={['Source', 'Evidence note', 'OpenMRS use']}
        rows={sourceRows}
        striped
      />

      <Divider />

      <H2>Demo Data Modernization</H2>
      <Text tone="secondary">
        The target dataset is the large OpenMRS demo-data SQL corpus, for example `large-demo-data-2-7-0.sql.zip`, not merely the
        default Ref App demo-patient generator. The blocker is that the corpus comes from older OpenMRS metadata and there is no
        confirmed 2.8-compatible version yet. First milestone: build or verify a 2.8 remap, then import only through a reviewed
        deterministic path.
      </Text>
      <Callout tone="warning" title="Dataset clarification">
        Treat the large demo-data corpus as the validation dataset. Treat `referencedemodata.createDemoPatientsOnNextStartup` as a
        modern Ref App control path and metadata reference. The hard work is database schema differences between 2.8 and lower
        versions, plus remapping legacy concepts, encounter types, orders, obs groups, and other metadata to the current Ref App.
      </Callout>
      <Card>
        <CardBody>
          <TestDataMappingDiagram />
        </CardBody>
      </Card>
      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>LLM-assisted mapping contract</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Inputs:</Text> `large-demo-data-2-7-0.sql.zip` or closest available large corpus, current 2.8 Ref App schema, module list, concept names, encounter types, obs groups, and demo content metadata.</Text>
              <Text><Text weight="semibold">Allowed output:</Text> proposed schema deltas, concept mappings, metadata substitutions, import blockers, and review questions.</Text>
              <Text><Text weight="semibold">Not allowed:</Text> executable migrations accepted on trust. Every change must become a deterministic script with smoke tests.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Import acceptance gates</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>Disposable DB import completes from a clean Platform/Core 2.8 + Ref App setup, then repeats without manual repair.</Text>
              <Text>Schema-diff report accounts for changed/removed tables, columns, indexes, module-owned data, and Liquibase state.</Text>
              <Text>Patient, encounter, obs, concept, note, condition, medication, and allergy records serialize through chartsearchai.</Text>
              <Text>At least 50 imported/generated patients produce retrievable records and 10+ inspected known-answer validation cases.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>
      <Table
        headers={['Input', 'Value for validation', 'Compatibility risk', 'Mapping action']}
        rows={demoDataWorkRows}
        striped
      />

      <Divider />

      <H2>Target Validation Architecture</H2>
      <Text tone="secondary">
        Seven layers, left to right: demo data sources become an LLM-reviewed mapping spec, then an imported patient corpus,
        then golden case sets and pinned models feed the eval drivers. Every driver writes the same artifacts; artifacts feed
        dashboards, baseline diffs, and clinician review; gates consume reviewed evidence to allow PR merges, nightly green,
        and release sign-off. Accent borders mark the lanes that change behavior most often.
      </Text>
      <Card>
        <CardBody>
          <ArchitectureDiagram />
        </CardBody>
      </Card>
      <Row gap={8} wrap>
        <Pill tone="info" active>Sources</Pill>
        <Pill tone="info" active>Drivers</Pill>
        <Pill tone="info" active>Artifacts</Pill>
        <Pill tone="info" active>Sinks</Pill>
        <Pill tone="neutral">Accent border = high-change lane</Pill>
      </Row>

      <H2>Per-Case Validation Flow</H2>
      <Text tone="secondary">
        Each clinical question runs through the production pipeline once, then is graded by four parallel checks before being labeled.
        This is the contract every eval driver must implement so cross-suite comparison stays honest.
      </Text>
      <Card>
        <CardBody>
          <ValidationFlowDiagram />
        </CardBody>
      </Card>
      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>What each grade gate produces</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Faithfulness:</Text> per-claim support label against retrieved context (supported, partial, contradicted).</Text>
              <Text><Text weight="semibold">Citation P/R:</Text> per-statement citation precision and recall against the cited record set.</Text>
              <Text><Text weight="semibold">Abstention:</Text> correctness on absent-data cases, including negative clinical questions.</Text>
              <Text><Text weight="semibold">Schema/safety:</Text> JSON shape, no system-prompt leakage, no obedience markers, no PHI exfiltration.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>What every case record carries</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>Query id, dataset id, patient id, retrieval pipeline, k, retrieved record ids, cited record ids.</Text>
              <Text>Latency per stage (retrieve, generate, parse), token counts, prompt version, model id and file hash.</Text>
              <Text>Per-grader label and rationale, final case label, reviewer notes, baseline diff summary.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Validation Spine Roadmap</H2>
      <Text tone="secondary">
        Eight phases. Order matters: the demo-data phase prevents validation from being trapped in tiny synthetic fixtures, the spine
        then makes every metric comparable, and clinician/governance gates only make sense once retrieval and answer artifacts are stable.
      </Text>

      <Grid columns="1fr 1fr" gap={14}>
        {phases.map((p) => (
          <PhaseCard key={p.id} phase={p} />
        ))}
      </Grid>

      <Callout tone="info" title="Critical path">
        P0 → P1 → P2 is mandatory before broad validation. P3, P4, and P5 can run in parallel once the spine emits artifacts,
        but P4 and P5 share LM Studio access so plan capacity. P6 (clinician adjudication) gates baseline updates from P3/P4/P5.
        P7 reuses every artifact format, so no eval suite needs to be rewritten when querystore goes live.
      </Callout>

      <H2>Milestone Timeline</H2>
      <Text tone="secondary">
        Indicative weeks, single contributor pace. Slips compress P6/P7, not P1-P4; demo-data import, the spine, and retrieval metrics are the load-bearing work.
      </Text>
      <Card>
        <CardBody>
          <MilestoneTimeline />
        </CardBody>
      </Card>

      <H2>Current Eval Coverage</H2>
      <Text tone="secondary">
        Case counts from the eval datasets shipped in <Code>api/src/test/resources/eval/</Code>. Growth targets are intentionally
        left qualitative until the team commits explicit coverage goals.
      </Text>
      <Card>
        <CardBody>
          <BarChart
            categories={coverageCategories}
            series={[
              { name: 'Verified current cases', data: verifiedCoverage, tone: 'info' },
            ]}
            height={260}
          />
        </CardBody>
      </Card>
      <Text tone="secondary" size="small">
        Citation eval has 10 cases, absent-data eval has 29 cases, prompt-injection eval has 33 cases, and each enriched retrieval baseline has 485 cases. Demo-data import smoke, clinician rubric, and red-team OWASP lanes are planned lanes without implemented cases yet.
      </Text>

      <H2>Operating Cadence Per Lane</H2>
      <Table
        headers={['Lane', 'Local pre-push', 'PR check', 'Nightly', 'Release']}
        rows={[
          ['Contract tests', 'Required', 'Required', 'Required', 'Required'],
          ['Demo-data import smoke', 'On import change', 'On import/mapping change', 'Required', 'Required + inspected records'],
          ['Retrieval eval (L6-v2)', 'Optional', 'Required (full 485)', 'Required', 'Required + diff review'],
          ['Retrieval eval (MedCPT)', 'Optional', 'On retrieval-pipeline change', 'Required', 'Required + diff review'],
          ['Citation/answer eval', 'On-demand', 'On prompt or pipeline change', 'Required', 'Required + clinician review'],
          ['Absent-data eval', 'On-demand', 'On prompt change', 'Required', 'Required'],
          ['Prompt injection', 'On-demand', 'On prompt change', 'Required', 'Required + red-team sign-off'],
          ['Clinician rubric', 'No', 'No', 'Sample', 'Required (blinded)'],
        ]}
        striped
      />

      <Callout tone="success" title="Definition of done for the spine">
        Every eval test class — including future querystore equivalents — emits the same JSON record per case, references a single
        run-manifest, records dataset provenance, and stores both numeric metrics and the actual records returned. When that holds,
        demo-data, retrieval, answer, safety, and clinician work can iterate independently without breaking comparability.
      </Callout>

      <Divider />

      <H2>Parallel Approaches Under Validation</H2>
      <Text tone="secondary">
        Three different clinical-AI architectures with overlapping validation needs: chartsearchai (this repo, embedded chart QA),
        openmrs_chatbot (parallel multi-agent OpenMRS chatbot), and OpenELIS Catalyst (NL-to-SQL lab assistant). Treat the comparison
        as exploratory — where validation primitives overlap, share the harness; where they diverge, keep per-project gates.
      </Text>

      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>Java / OpenMRS</Pill>}>
            chartsearchai (this repo)
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Architecture:</Text> embedded Java module; ONNX + Lucene + RRF retrieval over serialized chart records.</Text>
              <Text><Text weight="semibold">Generation:</Text> structured JSON answer with chart-record citations.</Text>
              <Text><Text weight="semibold">Validation today:</Text> 485-case enriched retrieval, citation, absent-data, prompt-injection.</Text>
              <Text tone="secondary"><Text weight="semibold">Open question:</Text> can the validation spine schema be reused unchanged by the other two?</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>Python / Multi-UI</Pill>}>
            openmrs_chatbot
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text tone="secondary" size="small"><Link href="https://github.com/anichiti/openmrs_chatbot">github.com/anichiti/openmrs_chatbot</Link></Text>
              <Text><Text weight="semibold">Architecture:</Text> Python clinical chatbot with patient/doctor interfaces, agent-team scaffolding, workflow tracing docs.</Text>
              <Text><Text weight="semibold">Generation:</Text> multi-turn role-conditioned responses; debug + workflow trace guides in repo.</Text>
              <Text><Text weight="semibold">Validation today:</Text> early; setup and trace docs imply iterative manual eval.</Text>
              <Text tone="secondary"><Text weight="semibold">Open question:</Text> what role-aware abstention and citation primitives apply when the user is a patient vs a doctor?</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>OpenELIS / Lab</Pill>}>
            Catalyst (your effort)
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text tone="secondary" size="small"><Link href="https://github.com/DIGI-UW/OpenELIS-Global-2/tree/develop/projects/catalyst">github.com/DIGI-UW/OpenELIS-Global-2 · projects/catalyst</Link></Text>
              <Text><Text weight="semibold">Architecture:</Text> multi-service Python (catalyst-gateway / catalyst-agents / catalyst-mcp) over OpenELIS; provider abstraction (LM Studio + Gemini).</Text>
              <Text><Text weight="semibold">Generation:</Text> NL-to-SQL with allowlisted schema context from MCP; OE backend executes after user review under RBAC.</Text>
              <Text><Text weight="semibold">Validation today:</Text> M0/M1 milestones with provider and multi-agent E2E smoke; allowlist + read-only DB user.</Text>
              <Text tone="secondary"><Text weight="semibold">Open question:</Text> what shared NL-to-SQL grading rubric maps to chart-record citation precision/recall?</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H2>Comparative Validation View</H2>
      <Text tone="secondary">
        Dimensional comparison across the three projects. Useful for spotting where validation work generalizes vs where each project
        has unique surface area.
      </Text>
      <Table
        headers={['Dimension', 'chartsearchai', 'openmrs_chatbot', 'Catalyst']}
        rows={parallelComparisonRows}
        striped
      />

      <H2>Validation Primitive Coverage</H2>
      <Text tone="secondary">
        Cells reflect today's state, not the target. The point is to see which primitives are shared so the validation spine is
        designed to absorb retrieval-grade, NL-to-SQL-grade, and trace-grade cases without bespoke per-project tooling.
      </Text>
      <Table
        headers={['Validation primitive', 'chartsearchai', 'openmrs_chatbot', 'Catalyst']}
        rows={primitiveMatrixRows}
        striped
      />

      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>Shared validation primitives</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Test-data fidelity:</Text> all three need a documented, reproducible corpus and provenance recorded per run.</Text>
              <Text><Text weight="semibold">Citation/grounding:</Text> chart-record citations (chartsearchai), result-row attribution (Catalyst), and message-level grounding (chatbot) all reduce to "what evidence did the model use".</Text>
              <Text><Text weight="semibold">Abstention:</Text> "no record / no result / refuse" needs to be a first-class case label in all three.</Text>
              <Text><Text weight="semibold">Safety:</Text> prompt injection, system-prompt leakage, and PHI exfiltration share an OWASP LLM Top 10 backbone.</Text>
              <Text><Text weight="semibold">Governance:</Text> run manifest with model/provider/version/dataset metadata is identical across stacks.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Project-specific primitives</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">chartsearchai:</Text> exact-baseline retrieval, model-aware noise profile, querystore parity once delegated.</Text>
              <Text><Text weight="semibold">openmrs_chatbot:</Text> role-aware response coverage (patient vs doctor), multi-turn dialogue grounding, agent handoff correctness.</Text>
              <Text><Text weight="semibold">Catalyst:</Text> NL-to-SQL syntactic and semantic correctness, allowlist enforcement, RBAC-honoring execution preview, schema-drift detection.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="info" title="Cross-project synthesis">
        The chartsearchai validation spine schema (per-case JSONL + run-manifest with model, dataset, provider, prompt version) is
        portable. If openmrs_chatbot and Catalyst adopt the same record shape, cross-project validation can share dashboards,
        baselines, and clinician/expert review tooling. NL-to-SQL grading and agent-trace grading become extra grade-gate types,
        not separate harnesses.
      </Callout>
    </Stack>
  );
}
