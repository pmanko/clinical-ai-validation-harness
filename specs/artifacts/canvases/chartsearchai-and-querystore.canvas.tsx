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

// Measurements pulled 2026-05-16 from upstream chartsearchai + querystore
// GitHub repos. See specs/004-real-adapter-entrypoints/plan.md "Querystore
// situation (measured 2026-05-16)" for the source-of-truth audit.
//
// UPDATE 2026-05-29: querystore is now deployed, enabled, and serving — it
// starts clean and serves kNN charts once the backend runs the temurin rebase
// (compose/Dockerfile.backend; its onnxruntime needs glibc >= 2.27, which the
// stock Amazon Linux 2 backend lacked). The "5 critical runtime bugs",
// "standalone-only today", "querystore.enabled=off", and "backend stays on
// stock :3.6.0" framing below is SUPERSEDED where it conflicts. The corpus
// also moved to the canonical `openmrs` schema (openmrs_test + *_dlt dropped).
// See spec.md's 2026-05-29 update.

const heroStats = [
  { value: '12', label: 'chartsearchai merged PRs (since 2026-03-10)', tone: 'info' as const },
  { value: '1', label: 'querystore merged PRs (scaffold only)', tone: 'warning' as const },
  { value: 'serving', label: 'querystore status — enabled + indexing (2026-05-29)', tone: 'success' as const },
  { value: '4', label: 'open ADR migration questions', tone: 'warning' as const },
  { value: 'on', label: 'chartsearchai.querystore.enabled (this harness)', tone: 'success' as const },
];

// Phase 2 (added 2026-05-18) — multi-turn chat history. The 13 design
// decisions locked with the user; see spec.md "Phase 2" section.
const multiTurnDecisionRows = [
  ['D1', 'Chart placement in message array', 'First user message, byte-stable across turns (cache-friendly prefix)'],
  ['D2', 'Chart freshness', 'Frozen on session open; "New chat" rebuilds'],
  ['D3', 'Pre-filter retrieval in chat', 'Always full chart (chat bypasses chartsearchai.embedding.preFilter)'],
  ['D4', 'Chart persistence shape', 'Snapshot on chat_session row (chart_snapshot + chart_mappings_json)'],
  ['D5', 'Tokenizer', 'chars/4 (POC); jtokkit / llama-server /tokenize is v2 follow-up'],
  ['D6', '/search vs /chat coexistence', 'Both endpoints; AI panel uses /chat only'],
  ['D7', 'Mid-stream client disconnect', 'Persist partial with finish_reason=aborted (POC); consumeStream is v2'],
  ['D8', 'Chat content retention', '90 days (chartsearchai.chat.retentionDays); separate from 6yr audit log'],
  ['D9', 'System prompt stability', 'Live GP; operator edit invalidates cache (rare; acceptable)'],
  ['D11', 'Session uuid client storage', 'Server-side via openOrLoadActiveSession; no localStorage'],
  ['D12', 'Session boundary', 'Per (patient, user)'],
  ['D13', 'Sequencing', 'Ship redesign + browser-verify before opening upstream PRs'],
];

const multiTurnRestRows = [
  ['POST', '/ws/rest/v1/chartsearchai/chat', 'Single-call multi-turn; returns {answer, references, session, messageId}'],
  ['POST', '/ws/rest/v1/chartsearchai/chat/stream', 'SSE; emits X-ChartSearchAi-Session header before stream opens'],
  ['POST', '/ws/rest/v1/chartsearchai/chat/new', 'Close current active session + open fresh ("New chat" button)'],
  ['GET',  '/ws/rest/v1/chartsearchai/chat?patient=', 'Hydrate SPA panel on mount (returns session + ordered messages)'],
];

const multiTurnPrRows = [
  ['openmrs/openmrs-module-chartsearchai', '#20', 'Backend multi-turn chat with frozen-session chart in stable prefix'],
  ['openmrs/openmrs-esm-chartsearchai',    '#9',  'Frontend chat panel routed through /chat/stream'],
  ['pmanko/clinical-ai-validation-harness', '#15', 'Harness: paired submodule pin bumps + Caddy interception'],
];

const moduleStatusRows = [
  ['chartsearchai', 'mature, shipping, hot iteration', 'ab37133 (2026-05-16)', '12 merged PRs', 'Standalone capable; querystore integration code added 2026-05-15 (off by default)'],
  ['querystore', 'pre-alpha, single-author iteration', 'ab371333 (2026-05-16)', '1 merged PR (scaffold)', '5 critical runtime bugs block any backend tier from starting cleanly'],
];

const chartsearchPipelineRows = [
  ['embedding (default)', 'In-process ONNX (MiniLM L6 / MedCPT) + custom scoring', 'Single shared MySQL table (chartsearchai_embedding)', 'Default mode when preFilter=true'],
  ['lucene', 'In-process Apache Lucene BM25 + English stemming', 'Local Lucene index dir under openmrs-data', 'No ONNX model needed; lexical-only'],
  ['hybrid', 'In-process Lucene BM25 + ONNX kNN via RRF fusion', 'Lucene index + chartsearchai_embedding table', 'Best of both without an external service'],
  ['elasticsearch', 'External ES 8.14+ / OpenSearch 2.19+ with RRF retriever', 'chartsearchai-patient-records shared index', 'OpenSearch recommended (RRF is free); ES needs Platinum/Enterprise for RRF'],
];

const portMapRows = [
  ['Per-resource text serializers (Obs, Condition, Diagnosis, Allergy, Order, MedicationDispense, PatientProgram + ConceptNameUtil)', 'moves to querystore'],
  ['OnnxEmbeddingProvider + WordPieceTokenizer', 'moves to querystore'],
  ['PatientRecordLoader (becomes events-first sync entry point)', 'moves to querystore'],
  ['HybridRetriever.fuseRRF (~30 lines)', 'moves to querystore (template for MySQL/Lucene tier fusion)'],
  ['ElasticsearchQueryBuilder + ElasticsearchIndexer + ES/OS auto-detect', 'moves to querystore (ES backend impl)'],
  ['EmbeddingIndexer.replacePatientEmbeddings (delete-then-insert atomic re-projection)', 'moves to querystore (MySQL backend pattern)'],
  ['EmbeddingIndexTask (bulk backfill)', 'moves to querystore (bootstrap path; ADR open question #2)'],
  ['LlmInferenceService + LocalLlmEngine + WarmupExecutor + ChartSearchServiceRouter (~6000 lines)', 'stays in chartsearchai'],
  ['Adaptive filtering: gap detection, similarity ratio, z-score gate, coherence filter, type boost', 'stays in chartsearchai'],
  ['Prompt assembly, citation formatting, recency cap, input validation, streaming SSE', 'stays in chartsearchai'],
  ['ChartCache + ChartCacheInvalidator (full-chart mode)', 'stays in chartsearchai'],
  ['AOP indexing advice (Encounter/Obs/PatientData)', 'replaced by events-first sync from querystore'],
  ['chartsearchai_audit_log table + audit endpoints', 'stays in chartsearchai'],
];

const tierMappingRows = [
  ['embedding (default; chartsearchai)', 'mysql (querystore)', 'querystore improves on this — MySQL FULLTEXT for keyword instead of in-process scoring'],
  ['lucene (chartsearchai)', 'not directly available', 'querystore lucene tier always carries both BM25 and HNSW kNN — no embedding-free option'],
  ['hybrid (chartsearchai)', 'lucene (querystore)', 'querystore stores vectors + text both in Lucene; functionally equivalent at consumer layer'],
  ['elasticsearch (chartsearchai)', 'elasticsearch (querystore)', 'querystore restructures into per-type indices; keeps RRF retriever path'],
];

const querystoreBlockersRows = [
  ['#9', 'MysqlBackendStore no dataSource bean', 'MySQL tier won\'t start', 'open'],
  ['#10', 'BackendStoreSelector deadlocks during Spring init', 'module init hangs', 'open'],
  ['#11', 'Schema manager picks up querystore_bootstrap_progress → BM25/kNN fail', 'queries fail with "Unknown column"', 'open'],
  ['#12', 'BootstrapService not registered with ServiceContext', 'every cold-patient search fails', 'open'],
  ['#13', 'Lucene tier collides with core Hibernate Search Lucene 8.7 codec', 'Lucene tier won\'t start', 'open'],
  ['#2-#6', '5 enhancement gaps (whole-patient listing, patient merge, index-change events, on-demand bootstrap, service-layer filters)', 'feature surface incomplete', 'open'],
  ['#7', 'Auto-index patient on first search when no documents exist', 'fixed in main', 'closed'],
  ['#14', 'ES auto-mapping makes patient_uuid \'text\'; patient-scope filter returns 0 hits', 'fixed in main', 'closed'],
];

const harnessIntegrationRows = [
  ['M3 — chartsearchai adapter, today (this PR)', '004-real-adapter-entrypoints', 'Bring up chartsearchai against openmrs_test (5,284 patients). Manual browser smoke against Zabella Halambe. .omod built from submodule.'],
  ['M3 deferred', '004-real-adapter-entrypoints v2', 'Playwright smoke automation; digest-pinned :nightly-chartsearch images; chartsearchai eval-dataset replay (153 records).'],
  ['M3 — querystore adapter', '004-real-adapter-entrypoints v3', 'Currently impossible — blocked by 5 querystore runtime bugs. Revisit when querystore reaches alpha-usable state.'],
  ['M8 — querystore parity testbed', '009-querystore-parity-testbed', 'Compare chartsearchai-internal vs chartsearchai-via-querystore retrieval on the same questions. Gated on M3 querystore adapter.'],
  ['Related: chatbot adapter', '004 (later iteration)', 'M3 for openmrs_chatbot — separate Python service.'],
  ['Related: Catalyst adapter', '004 (later iteration)', 'M3 for OpenELIS/Catalyst — different upstream entirely; see scout-comparative-analysis.canvas.tsx.'],
];

const assumptionRows = [
  ['Both modules require OpenMRS Platform 2.8.0+', 'Compatibility', 'Our harness backend (RefApp 3.6.0) sits on 2.8 line — compatible.'],
  ['chartsearchai requires Webservices REST 2.44.0+', 'Compatibility', 'Our backend has 3.2.0 — compatible.'],
  ['chartsearchai default = preFilter=false (full-chart mode)', 'Simplicity', 'No ONNX model file required for the PoC; LLM gets the whole chart.'],
  ['chartsearchai LLM engine = remote (OpenAI-compat)', 'PoC scope', 'LM Studio/Anthropic/OpenAI/Ollama all work; bundled llama-server out of scope.'],
  ['chartsearchai.llm.remote.apikey in runtime properties, not DB globals', 'Security', 'Injected via OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY env var (OpenMRS auto-translates).'],
  ['querystore is build-time dep, runtime opt-in', 'Architecture', 'querystore-api compiled into chartsearchai .omod (scope=provided); chartsearchai degrades gracefully if querystore not installed.'],
  ['Chartsearchai eval dataset (153 records) = only available validator', 'Validation', 'Run against querystore-backed retrieval (when ready) to catch regressions vs in-process baseline.'],
];

const referenceRows = [
  ['chartsearchai repo', 'github.com/openmrs/openmrs-module-chartsearchai'],
  ['querystore repo', 'github.com/openmrs/openmrs-module-querystore'],
  ['Querystore ADRs (architectural decisions)', 'targets/querystore/docs/adr.md'],
  ['Chartsearchai port map (what moves to querystore vs stays)', 'targets/querystore/docs/chartsearchai-port-map.md'],
  ['Migration gap analysis', 'targets/querystore/docs/migration-chartsearchai.md'],
  ['Cross-project canvas (chartsearchai in 3-project matrix)', 'cross-project-comparison.canvas.tsx'],
  ['Scout comparative analysis (related Duke DIHI work)', 'scout-comparative-analysis.canvas.tsx'],
  ['Feature 002 transform flow (the upstream data dependency for our PoC)', 'sqlmesh-transformation-flow.canvas.tsx'],
];

type ArchNode = {
  title: string;
  detail: string;
  x: number;
  y: number;
  accent?: boolean;
};

function todayArchitectureNodes(): { nodes: ArchNode[]; edges: Array<[number, number]> } {
  const nodes: ArchNode[] = [
    { title: 'Clinician', detail: 'user in patient chart', x: 20, y: 16 },
    { title: 'AI sparkle / chat panel', detail: '@openmrs/esm-chartsearchai-app (frontend ESM)', x: 240, y: 16 },
    { title: 'chartsearchai REST', detail: 'POST /ws/rest/v1/chartsearchai/search', x: 510, y: 16 },
    { title: 'ChartSearchServiceRouter', detail: 'auth check, rate limit, audit', x: 510, y: 110, accent: true },
    { title: 'Retrieval pipeline', detail: 'embedding | lucene | hybrid | elasticsearch (in-process)', x: 510, y: 200, accent: true },
    { title: 'chartsearchai_embedding', detail: 'MySQL table (text + dense_vector)', x: 240, y: 200 },
    { title: 'Lucene index', detail: 'local dir under openmrs-data', x: 240, y: 290 },
    { title: 'Elasticsearch (optional)', detail: 'external ES/OS 8.14+', x: 240, y: 380 },
    { title: 'LlmInferenceService', detail: 'prompt assembly, JSON schema, streaming', x: 800, y: 110, accent: true },
    { title: 'LLM engine', detail: 'remote OpenAI-compat | local llama-server', x: 800, y: 200 },
    { title: 'OpenAI-compat endpoint', detail: 'LM Studio / Anthropic / OpenAI / Ollama / vLLM', x: 800, y: 290 },
    { title: 'JSON answer + citations', detail: 'streamed SSE back to chat panel', x: 800, y: 16 },
  ];
  const edges: Array<[number, number]> = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [4, 6],
    [4, 7],
    [3, 8],
    [8, 9],
    [9, 10],
    [8, 11],
    [11, 1],
  ];
  return { nodes, edges };
}

function futureArchitectureNodes(): { nodes: ArchNode[]; edges: Array<[number, number]> } {
  const nodes: ArchNode[] = [
    { title: 'Clinician', detail: 'user in patient chart', x: 20, y: 16 },
    { title: 'AI sparkle / chat panel', detail: '@openmrs/esm-chartsearchai-app (unchanged)', x: 240, y: 16 },
    { title: 'chartsearchai REST', detail: 'POST /ws/rest/v1/chartsearchai/search', x: 510, y: 16 },
    { title: 'ChartSearchServiceRouter', detail: 'auth, rate limit, audit (unchanged)', x: 510, y: 110, accent: true },
    { title: 'QueryStoreChartBuilder', detail: 'if chartsearchai.querystore.enabled=true', x: 510, y: 200, accent: true },
    { title: 'QueryStoreService', detail: 'Java API: searchByPatient(uuid, query, topK)', x: 800, y: 200, accent: true },
    { title: 'querystore module', detail: 'per-type indices: openmrs_obs, openmrs_condition, …', x: 800, y: 290 },
    { title: 'Backend SPI (one tier)', detail: 'mysql | lucene | elasticsearch', x: 800, y: 380 },
    { title: 'OpenMRS events', detail: 'EncounterService, ObsService, PatientService, …', x: 240, y: 380 },
    { title: 'querystore event sync', detail: 'events-first projection (Decision 12)', x: 510, y: 380 },
    { title: 'LlmInferenceService', detail: '6000 lines of question-tuned scoring stays here', x: 1080, y: 110, accent: true },
    { title: 'OpenAI-compat endpoint', detail: 'unchanged', x: 1080, y: 200 },
    { title: 'JSON answer + citations', detail: 'unchanged', x: 800, y: 16 },
  ];
  const edges: Array<[number, number]> = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 7],
    [8, 9],
    [9, 6],
    [3, 10],
    [10, 11],
    [10, 12],
    [12, 1],
  ];
  return { nodes, edges };
}

function ArchDiagram({ title, getNodes }: { title: string; getNodes: () => { nodes: ArchNode[]; edges: Array<[number, number]> } }) {
  const theme = useHostTheme();
  const { nodes, edges } = getNodes();
  const nodeW = 200;
  const nodeH = 62;
  const width = 1320;
  const height = 470;

  return (
    <svg
      role="img"
      aria-label={title}
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id={`arch-arrow-${title.replace(/\s+/g, '-')}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
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
            key={`edge-${i}`}
            d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2 - 6} ${y2}`}
            fill="none"
            stroke={theme.stroke.secondary}
            strokeWidth={1.2}
            markerEnd={`url(#arch-arrow-${title.replace(/\s+/g, '-')})`}
          />
        );
      })}
      {nodes.map((node) => (
        <g key={node.title}>
          <rect
            x={node.x}
            y={node.y}
            width={nodeW}
            height={nodeH}
            rx={8}
            fill={node.accent ? theme.fill.secondary : theme.bg.elevated}
            stroke={node.accent ? theme.accent.primary : theme.stroke.primary}
            strokeWidth={node.accent ? 1.5 : 1}
          />
          <text x={node.x + 12} y={node.y + 24} fontSize={12.5} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
            {node.title}
          </text>
          <text x={node.x + 12} y={node.y + 44} fontSize={10.5} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
            {node.detail}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function ChartSearchAIAndQueryStoreArchitecture() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <Row gap={8} wrap>
          <Pill tone="info" active>Feature 004</Pill>
          <Pill tone="info" active>M3 adapter</Pill>
          <Pill tone="warning" active>querystore: pre-alpha</Pill>
          <Pill tone="success" active>chartsearchai: shipping</Pill>
          <Pill tone="info" active>Measured 2026-05-16</Pill>
        </Row>
        <H1>ChartSearchAI + QueryStore — Architecture and Migration</H1>
        <Text tone="secondary">
          Reference canvas for the harness's M3 chartsearchai adapter PoC (feature 004) and the related future M8 querystore parity testbed (feature 009).
          Captures today's standalone chartsearchai shape, the in-flight querystore-backed shape, the port map of what's moving where, and measured upstream-status signals so future planning has a grounded starting point.
        </Text>
      </Stack>

      <Grid columns={5} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      <Callout tone="info" title="One-sentence framing">
        chartsearchai today owns its full retrieval + LLM stack in-process (default <Code>preFilter=false</Code> = full-chart mode), and is actively rewiring the retrieval half to delegate to querystore via <Code>QueryStoreService</Code> — a switch is in place (<Code>chartsearchai.querystore.enabled</Code>, default off) but the querystore module itself is pre-alpha with 5 critical open bugs, so the switch stays off in production today.
      </Callout>

      <H2>Module Status</H2>
      <Table
        headers={['Module', 'Posture', 'HEAD SHA', 'Volume', 'Notes']}
        rows={moduleStatusRows}
        striped
      />

      <Divider />

      <H2>Today's Architecture (querystore disabled)</H2>
      <Text tone="secondary">
        This is what runs in our M3 PoC and what every chartsearchai deployment runs by default. chartsearchai owns serializers, indexing, retrieval, scoring, prompt assembly, and LLM dispatch. No external dependency on querystore at runtime.
      </Text>
      <Card>
        <CardBody style={{ padding: 12 }}>
          <ArchDiagram title="today" getNodes={todayArchitectureNodes} />
        </CardBody>
      </Card>

      <H3>Retrieval pipelines (chartsearchai today)</H3>
      <Table
        headers={['Pipeline', 'Retrieval mechanism', 'Index location', 'When to use']}
        rows={chartsearchPipelineRows}
        striped
      />

      <Divider />

      <Row gap={8} wrap>
        <Pill tone="success" active>Phase 2 — 2026-05-18</Pill>
        <Pill tone="info" active>Multi-turn chat</Pill>
        <Pill tone="info" active>Frozen-session chart</Pill>
        <Pill tone="info" active>3 PRs paired</Pill>
      </Row>
      <H2>Multi-turn Chat History (Phase 2)</H2>
      <Text tone="secondary">
        The Phase 1 PoC shipped single-shot search. Phase 2 (added 2026-05-18) adds multi-turn chat so referential follow-ups ("and her allergies?", "how many did you list?") resolve against prior turns. The load-bearing design choice: <Code>chart</Code> sits in the first user message and is frozen per session, so the LLM's prompt cache hits on the stable system+chart prefix while only the conversation tail varies per turn. Anthropic / OpenAI / llama.cpp prompt-caching docs all converge on this static-at-top / variable-at-end rule.
      </Text>

      <Callout tone="success" title="The message-array shape">
        <Code>{`[system, user(chart envelope — frozen on session), ...prior user/assistant pairs..., user(current question)]`}</Code>
        <br />
        First two messages byte-identical across every turn of a session → <Code>cache_prompt=true</Code> hits → 11K-token chart re-processed only on session create.
      </Callout>

      <H3>13 design decisions (locked with user via structured Q&A)</H3>
      <Table
        headers={['#', 'Decision', 'Choice']}
        rows={multiTurnDecisionRows}
        striped
      />

      <H3>REST surface added</H3>
      <Table
        headers={['Method', 'Path', 'Purpose']}
        rows={multiTurnRestRows}
        striped
      />

      <H3>Paired-PR strategy</H3>
      <Text tone="secondary">
        Three repos, three PRs. Backend + ESM PRs cut from clean slice branches off upstream <Code>main</Code> with squashed commits (one coherent change per PR). The consolidated <Code>harness-integration</Code> branches on each fork carry both this slice and the earlier already-PR'd commits, so the harness submodule pin tracks a single ref instead of N branches.
      </Text>
      <Table
        headers={['Repo', 'PR #', 'Scope']}
        rows={multiTurnPrRows}
        striped
      />

      <Callout tone="warning" title="Phase 2 trade-off">
        Chart snapshot is frozen on session create — new lab results don't appear mid-conversation. Clinician clicks "New chat" to refresh. This is the deliberate cost of cache-eligibility; it matches the user-facing mental model ("opening a new chat = a fresh context view") and is documented in <Code>populateChartSnapshot</Code> Javadoc.
      </Callout>

      <Divider />

      <H2>Tomorrow's Architecture (querystore enabled)</H2>
      <Text tone="secondary">
        When <Code>chartsearchai.querystore.enabled=true</Code>, <Code>QueryStoreChartBuilder</Code> delegates retrieval to <Code>QueryStoreService.searchByPatient(uuid, query, topK)</Code>. chartsearchai's own AOP indexing + EmbeddingIndexTask become no-ops to avoid double-indexing. The ~6000 lines of LLM-coupled scoring + prompt + streaming stays in chartsearchai unchanged.
      </Text>
      <Card>
        <CardBody style={{ padding: 12 }}>
          <ArchDiagram title="tomorrow" getNodes={futureArchitectureNodes} />
        </CardBody>
      </Card>

      <Divider />

      <H2>Port Map — what moves to querystore, what stays</H2>
      <Text tone="secondary">
        From <Code>targets/querystore/docs/chartsearchai-port-map.md</Code>. The general shape: querystore takes over text serialization + embedding generation + index management + retrieval queries; chartsearchai keeps the LLM-adjacent layer (scoring heuristics, prompt assembly, streaming, audit).
      </Text>
      <Table
        headers={['Component', 'Destination']}
        rows={portMapRows}
        striped
      />

      <Divider />

      <H2>Backend Tier Mapping</H2>
      <Text tone="secondary">
        Each chartsearchai retrieval pipeline maps to a querystore backend tier (per <Code>migration-chartsearchai.md</Code>). When the migration completes, deployments pick one querystore tier; chartsearchai uses <Code>QueryStoreService</Code> against whichever is configured.
      </Text>
      <Table
        headers={['chartsearchai pipeline (today)', 'querystore tier (future)', 'Notes']}
        rows={tierMappingRows}
        striped
      />

      <Divider />

      <H2>Querystore Migration Blockers (open issues in upstream)</H2>
      <Text tone="secondary">
        Measured from <Code>gh issue list --repo openmrs/openmrs-module-querystore</Code> at 2026-05-16. Five of the open issues block any backend tier from starting cleanly — these block the M3 querystore adapter and M8 parity testbed.
      </Text>
      <Table
        headers={['Issue', 'Title', 'Impact', 'State']}
        rows={querystoreBlockersRows}
        striped
      />

      <Callout tone="warning" title="Why we don't deploy querystore in M3 PoC">
        Even if we wanted to flip <Code>chartsearchai.querystore.enabled=true</Code>, the querystore module either won't start (#9, #10, #12, #13) or will start but fail every query (#11). Until at least one tier passes a clean bring-up, deploying querystore would be a step backward from chartsearchai's working in-process retrieval. M8 (009-querystore-parity-testbed) revisits when querystore reaches alpha.
      </Callout>

      <Divider />

      <H2>Harness Integration Points</H2>
      <Table
        headers={['Milestone', 'Spec slug', 'What it adds']}
        rows={harnessIntegrationRows}
        striped
      />

      <Divider />

      <H2>Assumptions and Constraints</H2>
      <Table
        headers={['Assumption', 'Category', 'Consequence']}
        rows={assumptionRows}
        striped
      />

      <Divider />

      <H2>Known Open Questions</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>4 ADR Open Questions (querystore-side)</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small"><Text weight="semibold">Patient merge handling:</Text> chartsearchai does this via AOP today; querystore needs repointing/reindexing logic.</Text>
              <Text size="small"><Text weight="semibold">Initial backfill / bootstrap:</Text> chartsearchai indexes lazily + bulk task; querystore must define the bootstrap path before parity.</Text>
              <Text size="small"><Text weight="semibold">Long-text chunking for embeddings:</Text> chartsearchai's MiniLM has 256-token cap → silent truncation. Inherit or fix.</Text>
              <Text size="small"><Text weight="semibold">Sync reliability + reconciliation:</Text> chartsearchai's "best-effort, swallow errors" model is acceptable in-process; not for a shared read store. Need durable subscription, DLQ, reconciliation.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Harness-side decisions to track</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small"><Text weight="semibold">Submodule pin policy:</Text> currently `git submodule update --remote` pulls upstream HEAD. Switch to digest-pinning when first drift bites.</Text>
              <Text size="small"><Text weight="semibold">querystore-api build-time dep:</Text> always install from our submodule so chartsearchai compiles. When chartsearchai stops depending on querystore-api (post-migration), drop the step.</Text>
              <Text size="small"><Text weight="semibold">Backend image tag:</Text> stays on stable :3.6.0 (not :nightly-chartsearch) so our submodule-built .omod doesn't get overwritten by the distribution's baked one on container start.</Text>
              <Text size="small"><Text weight="semibold">Eval dataset re-use:</Text> chartsearchai ships a 153-record eval set. Wire it into the harness when querystore is alpha-usable to catch retrieval regressions.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>References</H2>
      <Table
        headers={['Resource', 'Location']}
        rows={referenceRows}
        striped
      />

      <Callout tone="info" title="When this canvas needs updating">
        Refresh hero stats + module status + querystore blockers list when (a) chartsearchai or querystore upstream activity meaningfully changes (any closed critical bug; any new ADR resolution; any version released to Maven Central); (b) we update our submodule SHAs; (c) we close or open M3-querystore-adapter or M8 in the roadmap.
      </Callout>
    </Stack>
  );
}
