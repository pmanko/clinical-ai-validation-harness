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

const projectStages = {
  chartsearchai: {
    name: 'chartsearchai',
    badge: 'Java / OpenMRS',
    user: 'Clinician',
    entry: 'O3 floating button or workspace dock',
    context: 'Serialized chart records (text + embedding + metadata)',
    retrieve: 'ONNX (MiniLM L6 / MedCPT) + Lucene + RRF',
    generate: 'Embedded llama-server or remote OpenAI-compat (LM Studio)',
    execute: 'In-process Java; AOP indexing; rate-limited; audit log',
    output: 'Structured JSON answer with chart-record citations',
  },
  chatbot: {
    name: 'openmrs_chatbot',
    badge: 'Python / Multi-UI',
    user: 'Patient or doctor (separate UIs)',
    entry: 'Patient chat UI / doctor chat UI',
    context: 'OpenMRS data + dialogue state + role context',
    retrieve: 'Conversational orchestration; agent-team scaffolding',
    generate: 'LLM via agent team (provider unspecified in public docs)',
    execute: 'In-process Python; setup + workflow trace docs in repo',
    output: 'Multi-turn role-conditioned message',
  },
  catalyst: {
    name: 'Catalyst',
    badge: 'Selected target · implementation open',
    user: 'Analyst or clinician',
    entry: 'Catalyst browser -> Gateway',
    context: 'Explicit dialect + complete connection-readable schema',
    retrieve: 'Live schema discovery; optional descriptions do not filter it',
    generate: 'Selected model team through med-agent-hub',
    execute: 'User selects exact SQL; configured source enforces access',
    output: 'Bounded typed rows or the database error',
  },
};

type StageKey = 'user' | 'entry' | 'context' | 'retrieve' | 'generate' | 'execute' | 'output';

const stageRows: Array<{ key: StageKey; label: string }> = [
  { key: 'user', label: 'User' },
  { key: 'entry', label: 'Entry surface' },
  { key: 'context', label: 'Context layer' },
  { key: 'retrieve', label: 'Retrieval / RAG' },
  { key: 'generate', label: 'LLM generation' },
  { key: 'execute', label: 'Execution boundary' },
  { key: 'output', label: 'Returned to user' },
];

function ArchitectureMatrixDiagram() {
  const theme = useHostTheme();
  const projects: Array<keyof typeof projectStages> = ['chartsearchai', 'chatbot', 'catalyst'];
  const colWidth = 280;
  const colGap = 18;
  const labelColWidth = 140;
  const padX = 20;
  const headerHeight = 36;
  const rowHeight = 64;
  const rowGap = 8;
  const totalWidth = padX * 2 + labelColWidth + projects.length * (colWidth + colGap) - colGap;
  const totalHeight = headerHeight + 12 + stageRows.length * (rowHeight + rowGap);

  return (
    <svg
      role="img"
      aria-label="Per-project architecture matrix"
      width="100%"
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="cmp-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {projects.map((p, idx) => {
        const x = padX + labelColWidth + idx * (colWidth + colGap);
        return (
          <g key={`hdr-${p}`}>
            <rect
              x={x}
              y={4}
              width={colWidth}
              height={headerHeight - 4}
              rx={6}
              fill={theme.fill.tertiary}
              stroke={theme.stroke.secondary}
              strokeWidth={1}
            />
            <text
              x={x + 12}
              y={headerHeight - 12}
              fontSize={13}
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit', fontWeight: 600 }}
            >
              {projectStages[p].name}
            </text>
            <text
              x={x + colWidth - 12}
              y={headerHeight - 12}
              fontSize={11}
              textAnchor="end"
              fill={theme.text.tertiary}
              style={{ fontFamily: 'inherit' }}
            >
              {projectStages[p].badge}
            </text>
          </g>
        );
      })}

      {stageRows.map((stage, ridx) => {
        const y = headerHeight + 12 + ridx * (rowHeight + rowGap);
        return (
          <g key={`row-${stage.key}`}>
            <text
              x={padX + labelColWidth - 12}
              y={y + rowHeight / 2 + 4}
              fontSize={11}
              textAnchor="end"
              fill={theme.text.tertiary}
              style={{ fontFamily: 'inherit', letterSpacing: '0.04em', textTransform: 'uppercase' }}
            >
              {stage.label}
            </text>

            {projects.map((p, idx) => {
              const x = padX + labelColWidth + idx * (colWidth + colGap);
              const text = projectStages[p][stage.key];
              const accent = stage.key === 'retrieve' || stage.key === 'execute';
              const lines = wrapToLines(text, 36);
              return (
                <g key={`cell-${p}-${stage.key}`}>
                  <rect
                    x={x}
                    y={y}
                    width={colWidth}
                    height={rowHeight}
                    rx={8}
                    fill={theme.bg.elevated}
                    stroke={accent ? theme.accent.primary : theme.stroke.primary}
                    strokeWidth={accent ? 1.5 : 1}
                  />
                  {lines.map((line, lidx) => (
                    <text
                      key={lidx}
                      x={x + 12}
                      y={y + 22 + lidx * 14}
                      fontSize={12}
                      fill={theme.text.primary}
                      style={{ fontFamily: 'inherit' }}
                    >
                      {line}
                    </text>
                  ))}

                  {ridx < stageRows.length - 1 && (
                    <line
                      x1={x + colWidth / 2}
                      y1={y + rowHeight}
                      x2={x + colWidth / 2}
                      y2={y + rowHeight + rowGap}
                      stroke={theme.stroke.secondary}
                      strokeWidth={1}
                      markerEnd="url(#cmp-arrow)"
                    />
                  )}
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

function wrapToLines(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = '';
  for (const w of words) {
    if ((current + ' ' + w).trim().length > maxChars && current) {
      lines.push(current);
      current = w;
    } else {
      current = (current ? current + ' ' : '') + w;
    }
    if (lines.length >= 2) break;
  }
  if (lines.length < 3 && current) lines.push(current);
  if (lines.length === 3 && (current.length > maxChars || words.length > lines.join(' ').split(' ').length)) {
    lines[2] = lines[2].slice(0, maxChars - 1) + '…';
  }
  return lines.slice(0, 3);
}

const dimensionRows = [
  ['Repository', 'github.com/openmrs/openmrs-module-chartsearchai', 'github.com/anichiti/openmrs_chatbot', 'github.com/DIGI-UW/openelis-catalyst'],
  ['Language / runtime', 'Java 11+ inside OpenMRS Platform 2.8', 'Python (Flask/Django-style)', 'React workbench + Python Gateway + med-agent-hub'],
  ['Spec / status', 'Live demo at chartsearchai.openmrs.org; 485-case eval', 'Setup + workflow-trace docs only; no public eval', 'Feature 008 generic connection, Spark reference path, and comparison open'],
  ['Domain', 'Patient chart natural-language QA', 'Patient/doctor chat over OpenMRS data', 'Natural-language-to-SQL analysis and dashboards'],
  ['User type', 'Clinician at point of care', 'Patient or doctor (different UIs)', 'Analyst or clinician'],
  ['Architecture pattern', 'Embedded EMR module + ESM frontend', 'Multi-UI chatbot with agent teams', 'Browser -> Gateway -> med-agent-hub + configured SQL source'],
  ['Retrieval mode', 'Embedding + BM25 + RRF over serialized chart records', 'Conversational orchestration over OpenMRS data', 'No separate retrieval layer; live complete readable schema is supplied directly'],
  ['Generation surface', 'Structured JSON answer + record citations', 'Multi-turn role-conditioned chat reply', 'SQL, clarification, or unsupported response; execution remains explicit'],
  ['Provider/LLM', 'Embedded llama-server (default Gemma 4 E4B) or LM Studio remote (MedGemma 1.5 4B / Gemma 4 26B MoE)', 'Provider unspecified in public docs', 'Selected med-agent-hub profile with resolved models recorded'],
  ['Indexing/data sync', 'AOP advice today; events in querystore migration', 'Implementation-defined', 'External deployment owns ingestion; Catalyst discovers the source-readable schema'],
  ['Privacy stance', 'PHI handled inside OpenMRS module boundary; PromptInjectionEvalTest', 'Patient/doctor role isolation in UI', 'Source/deployment access boundary; current work uses non-sensitive demo data'],
  ['Validation today', '485 enriched retrieval, citation, absent-data, prompt injection; 153 querystore retrieval', 'Iterative manual eval implied by debug docs', 'One suite per selected team and one full-context reader after generic-connection implementation'],
];

const riskRows = [
  [
    'Hallucination',
    'Retrieve-then-cite contract; absent-data eval; structured JSON',
    'Needs definition; multi-turn dialog amplifies risk',
    'SQL preview before execution makes hallucinated SQL inspectable',
    'Wiki: "constrain LLM to only return data it can cite"; programmatic verification before display',
  ],
  [
    'PHI exposure',
    'OpenMRS module boundary; local llama-server keeps prompts on box',
    'Role isolation in UI; full surface unclear',
    'Selected demo uses non-sensitive data; source and deployment controls define access',
    'Wiki: clinical data must not be sent to outside SaaS; expect local LLM hosting',
  ],
  [
    'Prompt injection',
    'PromptInjectionEvalTest (33 cases); structured JSON output',
    'Needs definition',
    'Advisory findings remain visible; read-only access and query bounds are enforced at the connection',
    'Indirect injection via record text and lab notes is the cross-project gap',
  ],
  [
    'Schema / metadata drift',
    'Embeddings re-indexed; per-resource serializers',
    'Implementation-defined',
    'Live discovery reflects every object readable through the configured connection',
    'Each project needs a periodic drift check, not just one-time setup',
  ],
  [
    'Provider drift',
    'Model id + file hash captured per eval run',
    'Unclear',
    'Resolved model-team configuration is fixed and recorded for one comparison batch',
    'Capture provider/model/version in run-manifest across all three',
  ],
  [
    'Network / latency',
    'Embedded llama-server stops idle after 30 minutes',
    'Unknown',
    'Model and source interruptions are recorded separately from model behavior',
    'Resource-poor sites are the design baseline (chart-search wiki)',
  ],
];

const providerRows = [
  ['Default local LLM', 'Embedded llama-server (Gemma 4 E4B)', 'Unspecified in public docs', 'Selected Phase 1 profile through med-agent-hub'],
  ['Production-recommended', 'Gemma 4 26B MoE', '—', 'No production recommendation in Phase 1'],
  ['Reference healthcare model', 'MedGemma 1.5 4B', '—', 'No required healthcare-specific model'],
  ['Embedding models', 'all-MiniLM-L6-v2 (default), MedCPT', 'Unspecified', 'None in Catalyst core; the readable schema is supplied directly'],
  ['Endpoint pattern', 'http://localhost:18085/v1/chat/completions (local) or LM Studio remote', 'Unknown', 'Gateway calls the selected med-agent-hub profile'],
  ['Provider switch contract', 'Global Property: chartsearchai.llm.engine + remote endpoint', 'Unknown', 'Profile, models, prompts, and settings are resolved and recorded'],
];

const validationCoverageRows = [
  ['Test-data fidelity', 'Planned (large demo-data 2.8 remap)', 'Implementation-defined', 'Retained non-sensitive demo data through FHIR Data Pipes -> Parquet -> Spark'],
  ['Retrieval QA', 'Yes (485 enriched cases, 153 querystore)', 'Implied (response coverage)', 'Not applicable; model and editor receive the complete readable schema'],
  ['NL-to-SQL QA', 'Not applicable', 'Not applicable', 'Static design-time reference plus exact selected SQL executed once'],
  ['Agent-team trace QA', 'Not applicable', 'Yes (workflow trace docs)', 'Actual model context and resolved team configuration are recorded'],
  ['Citation / grounding', 'Yes (record-level citations)', 'Needs definition', 'Reader compares rows or database error with the static reference and rubric'],
  ['Abstention / empty answer', 'Yes (AbsentDataEvalTest)', 'Needs definition', 'Ready, needs clarification, and unsupported are retained as distinct outcomes'],
  ['Prompt injection / safety', 'Yes (PromptInjectionEvalTest)', 'Needs definition', 'Configured connection access plus time and returned-row limits'],
  ['Clinician/expert review', 'Planned (validation roadmap P6)', 'Implied (debug docs)', 'One full-context reader pass followed by owner review'],
  ['Governance metadata', 'Planned (run-manifest from spine)', 'Limited', 'Source, dialect, schema, models, prompts, query, and result provenance'],
];

const decisionRows = [
  ['Single-shot chart query at point of care', 'Best fit', 'Possible', 'Out of scope'],
  ['Multi-turn conversational over EMR', 'Out of scope', 'Best fit', 'Out of scope'],
  ['Natural-language query over a tabular system', 'Out of scope', 'Possible', 'Best fit'],
  ['Embedded inside OpenMRS distribution', 'Best fit', 'Out of scope', 'Out of scope'],
  ['Provider-portable (local + cloud LLM)', 'Partial (local + OpenAI-compat)', 'Unknown', 'Possible through configured med-agent-hub profiles'],
  ['Read-only schema-grounded NL-to-SQL', 'Out of scope', 'Out of scope', 'Best fit'],
  ['Strict no-PHI-in-LLM-context', 'Partial (chart text in context)', 'Implementation-defined', 'Not a product guarantee; the reference deployment uses non-sensitive demo data'],
  ['Operates on resource-poor networks', 'Best fit (embedded LLM)', 'Unknown', 'Possible (depends on provider)'],
];

const lessonsRows = [
  [
    'RAG can INCREASE hallucination',
    'Baseline clinical RAG produced 43.6% unsupported claims; structured patient artifacts with explicit provenance reduced this to 8.4% (40% relative reduction).',
    '2026 medRxiv (Representation Before Retrieval)',
    'chartsearchai\'s serialized text + structured metadata pattern is the right shape; double down on labeled prose + structured fields rather than pivoting to JSON-only or FHIR-only contexts.',
  ],
  [
    'Retrieval is the bottleneck, not generation',
    'Large medical RAG eval found only 22% of top-16 passages relevant; evidence selection precision 41-43%, recall 27-49%.',
    '2025 arXiv:2511.06738 (Rethinking RAG for Medicine)',
    'Retrieval-based projects need stage-aware retrieval metrics. Catalyst instead needs complete schema context, exact execution evidence, and reader review.',
  ],
  [
    'Optimization Paradox',
    'Best-of-breed components scoring 85.5% information accuracy yielded 67.7% diagnostic accuracy on 2,400 real cases. An integrated multi-agent system hit 77.4%.',
    '2026 arXiv:2506.06574',
    'Component-level metrics are insufficient. Validate each system end-to-end on real cases before trusting component scores.',
  ],
  [
    'Multi-agent is task-specific, not universal',
    'Multi-agent helps clinical workflow automation, but textual MQA and EHR-prediction often do as well or better with single LLMs or specialized methods.',
    '2026 npj AI review',
    'openmrs_chatbot should justify multi-agent per task type; Catalyst compares complete team setups without claiming causal isolation.',
  ],
  [
    'Repeated trials can expose model variability',
    'EHR-ChatQA agents reach Pass@5 over 90% but Pass^5 (all 5 trials succeed) drops by up to 60 percentage points.',
    '2025 arXiv:2509.23415 (EHR-ChatQA)',
    'Useful follow-up research, but Catalyst Phase 1 runs each selected team once and imposes no consistency threshold.',
  ],
  [
    'Silent provider-switch drift',
    'Single model handoff mid-conversation moves accuracy by -8 to +13 percentage points; about 70% of variance is captured by per-model prefix-influence + suffix-susceptibility.',
    '2026 arXiv (silent performance drift)',
    'Catalyst keeps resolved profiles fixed within a comparison batch; provider-handoff research remains separate.',
  ],
  [
    'Indirect injection is architectural',
    'LLMs cannot separate instructions from data on the same token stream. Spotlighting reduces attack success rate from over 50% to under 2% with minimal task degradation.',
    '2026 industry SOTA (Microsoft, Zylos, MPIB)',
    'Expand prompt-injection coverage from direct to indirect (chart text, lab notes, MCP responses); adopt spotlighting + Meta\'s Rule of Two.',
  ],
  [
    'Live benchmarks resist contamination',
    'LiveClin uses biannually-refreshed contemporary case reports across 1,407 cases / 6,605 questions; even top models hit only 35.7% case accuracy.',
    '2026 arXiv:2602.16747 (LiveClin)',
    'Plan a benchmark refresh cadence. Especially important once chartsearchai\'s 485-case set ages into model training corpora.',
  ],
];

const futureProofActions = {
  chartsearchai: [
    'Add an indirect-injection corpus where attack payloads ride in chart text (notes, observations, FHIR Bundle values), not just user queries.',
    'Encode a PCCP-style change protocol: every retrieval/prompt change ships with Modification Description + Modification Protocol + Impact Assessment.',
    'Treat structured-artifact provenance as a first-class evaluable surface; preserve per-cited-record snippets in JSONL traces.',
    'Schedule a quarterly clinical-question refresh so the 485-case baseline stays contamination-resistant as models train on it.',
  ],
  chatbot: [
    'Justify multi-agent vs single-LLM empirically per task type before committing architecture.',
    'Adopt observable-signals eval (intent analysis, message-level quality, explicit user feedback) since full retrieval traces may not exist.',
    'Apply Meta\'s Rule of Two: do not combine untrusted-input + sensitive-system + state-changing actions in one agent.',
    'Define a role-aware abstention contract (patient vs doctor) with separate empty-answer expectations per role.',
  ],
  catalyst: [
    'Implement the generic source, explicit dialect, and complete readable schema.',
    'Prove the FHIR Data Pipes -> Parquet -> Spark reference deployment through Catalyst and Superset.',
    'Run one complete suite for each selected team and retain the full conversation, context, SQL, rows or error, static reference, rubric, and provenance.',
    'Use one full-context reader without automatic scoring, ranking, disqualification, or winner selection.',
  ],
};

const defenseLayers = [
  { id: 'spot', label: 'Spotlighting', detail: 'Mark and isolate untrusted content in the prompt', evidence: 'ASR >50% → <2% (research)' },
  { id: 'shields', label: 'Prompt shields', detail: 'Detect and sanitize injection patterns in input', evidence: 'Microsoft Azure AI Content Safety' },
  { id: 'ifc', label: 'Information flow control', detail: 'Policy-based isolation of untrusted content via metadata', evidence: 'Microsoft IFC pattern' },
  { id: 'plan', label: 'Plan drift detection', detail: 'Monitor multi-step reasoning for deviation from intended task', evidence: 'Critic / planner separation' },
  { id: 'critic', label: 'Critic agents', detail: 'Audit inputs and outputs in real time for risky actions', evidence: 'Defense-in-depth recommendation' },
  { id: 'lp', label: 'Least privilege (Rule of Two)', detail: 'At most 2 of: untrusted input, sensitive system, state change', evidence: "Meta's Rule of Two (2026)" },
];

function DefenseInDepthDiagram() {
  const theme = useHostTheme();
  const padX = 16;
  const padY = 16;
  const layerHeight = 56;
  const layerGap = 8;
  const viewWidth = 920;
  const viewHeight = padY * 2 + defenseLayers.length * (layerHeight + layerGap) - layerGap;

  return (
    <svg
      role="img"
      aria-label="Defense in depth against indirect prompt injection"
      width="100%"
      viewBox={`0 0 ${viewWidth} ${viewHeight}`}
      style={{ display: 'block' }}
    >
      {defenseLayers.map((layer, idx) => {
        const y = padY + idx * (layerHeight + layerGap);
        const accent = layer.id === 'lp' || layer.id === 'spot';
        return (
          <g key={layer.id}>
            <rect
              x={padX}
              y={y}
              width={viewWidth - padX * 2}
              height={layerHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={accent ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={accent ? 1.5 : 1}
            />
            <text
              x={padX + 18}
              y={y + 24}
              fontSize={14}
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit', fontWeight: 600 }}
            >
              {layer.label}
            </text>
            <text
              x={padX + 18}
              y={y + 44}
              fontSize={12}
              fill={theme.text.secondary}
              style={{ fontFamily: 'inherit' }}
            >
              {layer.detail}
            </text>
            <text
              x={viewWidth - padX - 18}
              y={y + 32}
              fontSize={11}
              textAnchor="end"
              fill={theme.text.tertiary}
              style={{ fontFamily: 'inherit', letterSpacing: '0.04em' }}
            >
              {layer.evidence}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const metadataFlow = [
  { id: 'run', label: 'Run manifest', detail: 'project, git SHA, prompt version', span: 'resource + gen_ai.system' },
  { id: 'query', label: 'Query event', detail: 'user role, intent, dataset/patient id', span: 'agent invocation span' },
  { id: 'retrieval', label: 'Retrieval event', detail: 'top-k evidence, scores, filters', span: 'tool / retrieval span' },
  { id: 'model', label: 'Model event', detail: 'model id, provider, tokens, latency', span: 'gen_ai.request.model' },
  { id: 'response', label: 'Response event', detail: 'claims, citations, abstention flag', span: 'model output event' },
  { id: 'eval', label: 'Evaluation event', detail: 'faithfulness, citation P/R, safety', span: 'eval / reviewer span' },
];

function MetadataEventFlowDiagram() {
  const theme = useHostTheme();
  const padX = 20;
  const nodeWidth = 142;
  const nodeHeight = 72;
  const nodeGap = 16;
  const viewWidth = padX * 2 + metadataFlow.length * nodeWidth + (metadataFlow.length - 1) * nodeGap;
  const viewHeight = 240;
  const y = 32;
  const storeY = 148;

  return (
    <svg
      role="img"
      aria-label="Operating metadata event flow"
      width="100%"
      viewBox={`0 0 ${viewWidth} ${viewHeight}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="metadata-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {metadataFlow.map((step, idx) => {
        const x = padX + idx * (nodeWidth + nodeGap);
        return (
          <g key={step.id}>
            <rect
              x={x}
              y={y}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={theme.bg.elevated}
              stroke={idx === 0 || idx === metadataFlow.length - 1 ? theme.accent.primary : theme.stroke.primary}
              strokeWidth={idx === 0 || idx === metadataFlow.length - 1 ? 1.5 : 1}
            />
            <text x={x + 10} y={y + 20} fontSize={12} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
              {step.label}
            </text>
            <text x={x + 10} y={y + 39} fontSize={10.5} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
              {step.detail}
            </text>
            <text x={x + 10} y={y + 58} fontSize={10.5} fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
              {step.span}
            </text>
            {idx < metadataFlow.length - 1 && (
              <line
                x1={x + nodeWidth}
                y1={y + nodeHeight / 2}
                x2={x + nodeWidth + nodeGap - 4}
                y2={y + nodeHeight / 2}
                stroke={theme.stroke.secondary}
                strokeWidth={1}
                markerEnd="url(#metadata-arrow)"
              />
            )}
            <line
              x1={x + nodeWidth / 2}
              y1={y + nodeHeight}
              x2={x + nodeWidth / 2}
              y2={storeY}
              stroke={theme.stroke.tertiary}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          </g>
        );
      })}

      <rect
        x={padX}
        y={storeY}
        width={viewWidth - padX * 2}
        height={50}
        rx={10}
        fill={theme.fill.tertiary}
        stroke={theme.stroke.secondary}
      />
      <text x={viewWidth / 2} y={storeY + 22} fontSize={14} textAnchor="middle" fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
        Operating metadata store
      </text>
      <text x={viewWidth / 2} y={storeY + 40} fontSize={11} textAnchor="middle" fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
        append-only traces for dashboards, baseline diffs, clinician review, and PCCP-style change records
      </text>
    </svg>
  );
}

const metadataRows = [
  ['Run manifest', 'project, component, git_sha, environment, prompt_version, dataset_version', 'OpenTelemetry resource attributes + gen_ai.system'],
  ['Query event', 'case_id, role, intent, patient/dataset id, user-visible question', 'agent invocation span'],
  ['Retrieval event', 'retrieval_pipeline, top_k, returned ids, scores, filters, omitted candidates', 'tool span / retrieval span'],
  ['Model event', 'provider, model id, model hash, endpoint, temperature, token counts, latency', 'gen_ai.request.model, gen_ai.response.model'],
  ['Response event', 'answer JSON/text, cited record ids, extracted claims, abstention flag', 'model output event'],
  ['Evaluation event', 'faithfulness, citation precision/recall, prompt-injection outcome, reviewer label', 'eval span + human review metadata'],
];

const sourceLinks = [
  [
    <Link href="https://openmrs.atlassian.net/wiki/spaces/projects/pages/373325839/Chart+Search+aka+ChartSearchAI">Chart Search (aka ChartSearchAI) wiki</Link>,
    'Project framing: clinician time pressure, retrieval-then-verify pattern, hallucination/PHI risks, "tell the LLM to be bold about saying it doesn\'t have an answer".',
    'Use as the cross-project risk and acceptance-stance reference.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-chartsearchai">openmrs-module-chartsearchai</Link>,
    'Embedded Java module; ONNX retrieval; embedded llama-server or LM Studio remote; live demo at chartsearchai.openmrs.org.',
    'Reference architecture for embedded EMR chart QA.',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-querystore">openmrs-module-querystore</Link>,
    'CQRS read store being extracted from chartsearchai; per-type indices; document = text + embedding + structured metadata.',
    'Where chart-record retrieval is heading; informs cross-project shared infrastructure.',
  ],
  [
    <Link href="https://github.com/anichiti/openmrs_chatbot">openmrs_chatbot</Link>,
    'Parallel Python chatbot with patient/doctor UIs and workflow trace docs.',
    'Comparator for conversational, role-aware clinical chat.',
  ],
  [
    <Link href="https://github.com/DIGI-UW/openelis-catalyst">Catalyst</Link>,
    'Catalyst source and reference-deployment packaging; the Feature 008 product boundary is a generic SQL-connected workbench.',
    'Comparator for question-to-SQL review with an explicit dialect, complete readable schema, and exact execution.',
  ],
  [
    <Link href="https://github.com/Google-Health/medgemma/blob/main/notebooks/ehr_navigator_agent.ipynb">Google MedGemma EHR Navigator</Link>,
    'Reference implementation of an EHR navigator agent.',
    'Closest external comparator for chartsearchai\'s reasoning surface.',
  ],
  [
    <Link href="https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1302790145">OpenMRS AI Clinical Questions</Link>,
    '20 (currently 18 listed) clinical questions used as the eval scope for chartsearchai answers.',
    'Use as the canonical question set when comparing answer quality across approaches.',
  ],
  [
    <Link href="https://medrxiv.org/cgi/content/short/2026.02.13.26346256v1">Representation Before Retrieval (medRxiv 2026)</Link>,
    'Structured patient artifacts cut unsupported claims 43.6% → 8.4%. Multi-step verification + provenance.',
    'Validates chartsearchai\'s text + structured-metadata serialization; pushes against pure JSON or pure FHIR contexts.',
  ],
  [
    <Link href="https://arxiv.org/abs/2511.06738">Rethinking RAG for Medicine (arXiv 2025)</Link>,
    'Stage-aware expert eval: retrieval, evidence selection, response factuality. Only 22% of top-16 medical RAG passages relevant.',
    'Anchors the validation spine\'s separation of retrieval / selection / answer gates.',
  ],
  [
    <Link href="https://www.medrxiv.org/content/10.64898/2026.01.26.26344757v1.full">Retrospective Quality Analysis of a Clinical RAG Chatbot (medRxiv 2026)</Link>,
    'Observable signals (intent, message-level quality, explicit feedback) when full retrieval traces are unavailable.',
    'Practical eval pattern for openmrs_chatbot where full pipeline observability is unclear.',
  ],
  [
    <Link href="https://arxiv.org/html/2603.03541v1">RAG-X (arXiv 2026)</Link>,
    'Diagnostic framework for medical RAG; 14% gap between perceived success and evidence-based grounding.',
    'Adopt diagnostic-style decomposition where a project actually has a retrieval stage; do not invent one for Catalyst.',
  ],
  [
    <Link href="https://arxiv.org/abs/2506.06574">The Optimization Paradox in Clinical AI Multi-Agent Systems (arXiv 2026)</Link>,
    'Best-of-breed components → 67.7% diagnostic accuracy vs 77.4% integrated. End-to-end matters.',
    'Cross-project warning: never sign off on architecture changes from component metrics alone.',
  ],
  [
    <Link href="http://www.nature.com/articles/s44401-026-00077-0">Orchestrated multi-agents sustain accuracy under workload (npj Health Systems 2026)</Link>,
    'Multi-agent: 90.6% → 65.3% at 80 tasks vs single-agent 73.1% → 16.6%. Up to 65× fewer tokens.',
    'Useful research context for both projects, not a Catalyst Phase 1 acceptance gate.',
  ],
  [
    <Link href="http://www.nature.com/articles/s44387-026-00076-4">AI agent in healthcare: applications, evaluations, future directions (npj AI 2026)</Link>,
    'Multi-agent is task-specific. Not always better than single LLMs or specialized methods.',
    'Forces empirical justification of multi-agent design choices.',
  ],
  [
    <Link href="https://arxiv.org/abs/2509.23415v2">EHR-ChatQA (arXiv 2025)</Link>,
    'NL-to-SQL agents reach Pass@5 over 90% but Pass^5 drops by up to 60 percentage points.',
    'Motivates optional variability research; it does not set Catalyst Phase 1 run counts or thresholds.',
  ],
  [
    <Link href="https://arxiv.org/abs/2601.09876">CLINSQL (arXiv 2026)</Link>,
    '633 expert-annotated tasks on MIMIC-IV v3.1. GPT-5-mini 74.7% execution, Gemini 2.5-Pro drops 85.5% → 67.2% on hard.',
    'Useful external research shape, not an automatic Catalyst scoring gate.',
  ],
  [
    <Link href="https://arxiv.org/html/2605.02240v1">PhysicianBench (arXiv 2026)</Link>,
    'Execution-grounded EHR agent eval; 100 long-horizon tasks, 670 checkpoints. Best LLM agent only 46% success.',
    'Sets realistic expectation ceiling for chartsearchai-style end-to-end EHR tasks.',
  ],
  [
    <Link href="https://arxiv.org/abs/2602.16747v1">LiveClin (arXiv 2026)</Link>,
    'Live clinical benchmark refreshed biannually; resists training-data contamination.',
    'Plan benchmark refresh cadence; supplement static reference sets.',
  ],
  [
    <Link href="https://zylos.ai/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content">Indirect Prompt Injection: 2026 SOTA (Zylos)</Link>,
    'Architectural framing; spotlighting + IFC + Rule of Two + critic agents as defense in depth.',
    'Backbone for the cross-project indirect-injection program.',
  ],
  [
    <Link href="https://learn.microsoft.com/en-us/security/zero-trust/sfi/defend-indirect-prompt-injection">Microsoft: Defend against indirect prompt injection</Link>,
    'Spotlighting reduces ASR over 50% → under 2% with minimal task degradation.',
    'Operational reference for spotlighting and prompt-shield patterns.',
  ],
  [
    <Link href="https://www.aptible.com/hipaa-ai-security/prompt-injection">Aptible: Prompt injection in healthcare AI</Link>,
    'HIPAA-aware framing of injection risks: dosing, triage, downplaying symptoms, privacy violations.',
    'Cross-project clinical-harm framing for safety-eval design.',
  ],
  [
    <Link href="https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence">FDA PCCP guidance (final 2024 / impl 2025)</Link>,
    'Modification Description + Modification Protocol + Impact Assessment for AI device changes.',
    'Use as the change-control template even outside SaMD scope; embed in validation roadmap.',
  ],
  [
    <Link href="https://www.anthropic.com/research/teaching-claude-why">Teaching Claude why (Anthropic)</Link>,
    'Principle-driven reasoning and constitutional documents generalize better than targeted rule patches for agentic behavior.',
    'Supports moving project guidance from rule stuffing to constitution + examples + traceability.',
  ],
  [
    <Link href="https://opentelemetry.io/docs/specs/semconv/gen-ai">OpenTelemetry GenAI semantic conventions</Link>,
    'Development-stage standard for GenAI model, agent, tool, event, exception, and metrics spans.',
    'Use as the metadata-store interoperability target across chartsearchai, openmrs_chatbot, and Catalyst.',
  ],
];

export default function CrossProjectComparison() {
  return (
    <Stack gap={18}>
      <Stack gap={8}>
        <H1>Cross-Project Clinical AI Comparison</H1>
        <Text tone="secondary">
          Three early-prototype clinical-AI explorations compared against each other and against current research SOTA:
          chartsearchai (embedded EMR chart QA, MVP-tier), openmrs_chatbot (parallel multi-agent OpenMRS chatbot, POC-tier),
          and Catalyst (generic SQL workbench with its Phase 1 implementation and comparison open). Comparative synthesis, not a buying guide.
        </Text>
        <Row gap={8} wrap>
          <Pill tone="info" active>Early prototypes</Pill>
          <Pill tone="info" active>Embedded chart QA</Pill>
          <Pill tone="info" active>Conversational chat</Pill>
          <Pill tone="info" active>NL-to-SQL</Pill>
          <Pill tone="info" active>Agent teams</Pill>
          <Pill tone="info" active>Readable schema context</Pill>
          <Pill tone="warning" active>Mid-2026 SOTA</Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="3" label="Early-prototype approaches" tone="info" />
        <Stat value="7" label="Architecture stages compared" tone="info" />
        <Stat value="9" label="Shared validation primitives" tone="success" />
        <Stat value="3" label="Distinct prototype scopes" tone="warning" />
      </Grid>

      <Callout tone="warning" title="How to read these tables">
        These are <Text weight="semibold">early prototypes exploring different architectures</Text>, not mature products being
        compared head-to-head. The Catalyst architecture and validation columns are labelled as the selected target because
        its generic connection and Spark deployment are not yet implemented.
      </Callout>

      <Callout tone="info" title="Working hypothesis">
        The chartsearchai validation spine — per-case JSONL trace plus a run-manifest pinning provider, model, dataset, and
        prompt version — should be portable to openmrs_chatbot and Catalyst. Catalyst will use the shared record shape to assemble
        a full-context reader packet; automated checks establish collection and contract facts rather than a score.
      </Callout>

      <H2>Prototype Snapshots</H2>
      <Text tone="secondary">
        Each card shows the prototype's exploration focus, what it has implemented today, and what is explicitly out of scope
        for its current tier. Maturity tier (POC, MVP, etc.) sits in the header as a reminder.
      </Text>

      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>MVP-tier</Pill>}>
            chartsearchai · embedded chart QA
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text tone="secondary" size="small"><Link href="https://github.com/openmrs/openmrs-module-chartsearchai">github.com/openmrs/openmrs-module-chartsearchai</Link></Text>
              <Text><Text weight="semibold">Exploring:</Text> can an embedded OpenMRS module surface chart-grounded answers with record-level citations, low compute, in resource-constrained settings.</Text>
              <Text><Text weight="semibold">Built today:</Text> live demo; 485 enriched retrieval cases; citation eval; absent-data eval; prompt-injection eval (direct only).</Text>
              <Text><Text weight="semibold">Out of scope at this tier:</Text> production deployment; clinician adjudication SOP; indirect-injection coverage; PCCP-shaped change records.</Text>
              <Text tone="secondary"><Text weight="semibold">Next watch:</Text> querystore migration extracts retrieval; demo-data 2.8 remap; structured-artifact provenance per cited record.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="warning" active>POC-tier</Pill>}>
            openmrs_chatbot · conversational chat
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text tone="secondary" size="small"><Link href="https://github.com/anichiti/openmrs_chatbot">github.com/anichiti/openmrs_chatbot</Link></Text>
              <Text><Text weight="semibold">Exploring:</Text> can a Python clinical chatbot serve patient and doctor interfaces with role-aware multi-turn dialogue and agent-team orchestration over OpenMRS data.</Text>
              <Text><Text weight="semibold">Built today:</Text> setup + workflow-trace + debug docs; agent-team scaffolding; iterative manual evaluation implied.</Text>
              <Text><Text weight="semibold">Out of scope at this tier:</Text> public eval contract; declared provider/model contract; defined safety surface.</Text>
              <Text tone="secondary"><Text weight="semibold">Next watch:</Text> role-aware abstention; eval primitive definitions; Rule of Two declaration.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="warning" active>Implementation open</Pill>}>
            Catalyst · generic SQL workbench
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text tone="secondary" size="small"><Link href="https://github.com/DIGI-UW/openelis-catalyst">github.com/DIGI-UW/openelis-catalyst</Link></Text>
              <Text><Text weight="semibold">Exploring:</Text> can a person turn a question into reviewable SQL against any configured source, inspect rows or its database error, and carry a successful query into a dashboard.</Text>
              <Text><Text weight="semibold">Built today:</Text> conversation, notebook, immutable query versions, explicit Run, results, and the Dashboard Builder base; the generic connection is open.</Text>
              <Text><Text weight="semibold">Selected reference deployment:</Text> FHIR Data Pipes → Parquet → Spark SQL, with Catalyst and Superset as SQL clients; not yet implemented.</Text>
              <Text tone="secondary"><Text weight="semibold">Next:</Text> implement the generic source and complete-schema behavior, run one suite per selected team, and publish one full-context reader report before Phase 2 and Phase 3.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Architecture Matrix</H2>
      <Text tone="secondary">
        Same seven stages compared across all three projects. Accent borders mark the load-bearing stages where the projects
        diverge most: retrieval/RAG and execution boundary.
      </Text>
      <Card>
        <CardBody>
          <ArchitectureMatrixDiagram />
        </CardBody>
      </Card>

      <H2>Dimensional Comparison</H2>
      <Table
        headers={['Dimension', 'chartsearchai', 'openmrs_chatbot', 'Catalyst selected target']}
        rows={dimensionRows}
        striped
      />

      <H2>Provider &amp; Model Surface</H2>
      <Text tone="secondary">
        Different provider strategies translate directly to different validation needs. chartsearchai pins a model file hash;
        Catalyst resolves and records a complete model-team profile for a comparison batch; openmrs_chatbot has not yet declared a contract.
      </Text>
      <Table
        headers={['Concern', 'chartsearchai', 'openmrs_chatbot', 'Catalyst Phase 1 contract']}
        rows={providerRows}
        striped
      />

      <Divider />

      <H2>Risk Taxonomy Across Projects</H2>
      <Text tone="secondary">
        Risks framed by the OpenMRS Chart Search wiki — hallucination, PHI, and prompt injection in particular — apply to all three
        projects. The chartsearchai and openmrs_chatbot cells describe current state; the Catalyst column states selected target behavior.
      </Text>
      <Table
        headers={['Risk', 'chartsearchai', 'openmrs_chatbot', 'Catalyst selected target', 'Cross-project note']}
        rows={riskRows}
        striped
      />

      <H2>Operating Metadata Store</H2>
      <Text tone="secondary">
        The shared substrate should not be another prompt. It should be an append-only operating metadata store that records
        what the agent was asked, what it retrieved, which model answered, how the answer was evaluated, and which governance
        change record it belongs to. Use OpenTelemetry GenAI semantic conventions as the interoperability target, not as a
        replacement for project-specific eval fields.
      </Text>
      <Card>
        <CardBody>
          <MetadataEventFlowDiagram />
        </CardBody>
      </Card>
      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>Why this matters</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">For chartsearchai:</Text> reconstruct every answer from model, prompt, retrieval records, citations, and eval labels.</Text>
              <Text><Text weight="semibold">For openmrs_chatbot:</Text> turn workflow traces into comparable agent-run records instead of free-form debugging logs.</Text>
              <Text><Text weight="semibold">For Catalyst:</Text> align session, turn, actual model context, query version, execution, and reader evidence under one trace shape.</Text>
              <Text tone="secondary">This is the practical version of "teach why": the constitution guides behavior; the metadata store proves what happened.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Prototype mapping</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">chartsearchai:</Text> run manifest + retrieval JSONL + answer JSON + evaluator output.</Text>
              <Text><Text weight="semibold">openmrs_chatbot:</Text> user role + conversation turn + agent handoff + tool call + response label.</Text>
              <Text><Text weight="semibold">Catalyst:</Text> source and dialect + readable schema + model context + selected SQL + rows or database error + reader rationale.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>
      <Table
        headers={['Event', 'Minimum fields', 'OTel / GenAI alignment']}
        rows={metadataRows}
        striped
      />

      <H2>Validation Primitive Coverage</H2>
      <Text tone="secondary">
        The chartsearchai and openmrs_chatbot cells describe their current state. Because Catalyst's generic connection implementation remains
        open, its column describes the accepted target and must not be read as implemented evidence.
      </Text>
      <Table
        headers={['Validation primitive', 'chartsearchai', 'openmrs_chatbot', 'Catalyst accepted target']}
        rows={validationCoverageRows}
        striped
      />

      <Divider />

      <H2>Architectural Fit per Problem Shape</H2>
      <Text tone="secondary">
        This is an <Text weight="semibold">architectural-shape fit</Text> view, not a deployment-readiness view. Cells reflect
        which prototype's architecture best matches the problem shape, not which one is currently mature enough to ship for it.
        Today none of these prototypes is deployment-ready in the SaMD sense; the table answers "which exploration is structurally
        the right vehicle to investigate this problem".
      </Text>
      <Table
        headers={['Problem shape', 'chartsearchai architecture', 'openmrs_chatbot architecture', 'Catalyst selected architecture']}
        rows={decisionRows}
        striped
      />

      <Grid columns="1fr 1fr" gap={16}>
        <Card>
          <CardHeader>Convergence opportunities</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Validation spine schema:</Text> per-case JSONL plus run-manifest is portable.</Text>
              <Text><Text weight="semibold">Run-manifest fields:</Text> model id, model file hash, provider, prompt version, dataset version, git SHA. Identical across stacks.</Text>
              <Text><Text weight="semibold">Risk framework:</Text> hallucination, PHI, prompt injection, schema/provider drift apply to all three.</Text>
              <Text><Text weight="semibold">Clinician/expert review tooling:</Text> blinded review packets and rubric labels generalize.</Text>
              <Text><Text weight="semibold">Red-team corpus:</Text> OWASP LLM Top 10 categories and indirect injection cases can be shared.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Intentional divergence</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">chartsearchai:</Text> exact-baseline retrieval, model-aware noise profile, querystore parity once retrieval is delegated.</Text>
              <Text><Text weight="semibold">openmrs_chatbot:</Text> role-aware response coverage, multi-turn dialogue grounding, agent handoff correctness.</Text>
              <Text><Text weight="semibold">Catalyst:</Text> complete readable-schema grounding, advisory findings, exact selected-SQL execution, static references, and reader interpretation.</Text>
              <Text tone="secondary">Sharing the run envelope does not mean unifying evaluation. Each project keeps its own evidence and review method.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Research Grounding (2025-2026)</H2>
      <Text tone="secondary">
        Recent peer-reviewed and arXiv work that changes how to architect, evaluate, and govern these systems. None of these
        projects should be designed against the older "RAG always helps" or "more agents always wins" priors.
      </Text>

      <Grid columns={4} gap={12}>
        <Stat value="43.6%" label="Baseline clinical RAG hallucination rate (medRxiv 2026)" tone="warning" />
        <Stat value="22%" label="Top-16 medical RAG passages relevant (arXiv 2511.06738)" tone="warning" />
        <Stat value="67.7%" label="Best-of-breed components vs 77.4% integrated diagnostic accuracy" tone="info" />
        <Stat value="46%" label="Top LLM agent success on PhysicianBench EHR tasks" tone="info" />
      </Grid>

      <H3>Lessons applied</H3>
      <Table
        headers={['Lesson', 'Evidence', 'Source / year', 'Cross-project implication']}
        rows={lessonsRows}
        striped
      />

      <H2>Defense In Depth For Indirect Prompt Injection</H2>
      <Text tone="secondary">
        Industry SOTA in 2026 for indirect-injection mitigation is a layered architecture, not a single fix. Spotlighting and
        Meta's Rule of Two are the two highest-leverage layers; the rest are reinforcing. Read top to bottom as defenses you
        can stack, not alternatives.
      </Text>
      <Card>
        <CardBody>
          <DefenseInDepthDiagram />
        </CardBody>
      </Card>

      <H2>Future-Proof Actions Per Project</H2>
      <Text tone="secondary">
        Direct application of the lessons above to each project's current shape. These are designed to be added to the
        existing roadmap without restructuring it.
      </Text>
      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>chartsearchai</Pill>}>
            Embedded chart QA
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {futureProofActions.chartsearchai.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>openmrs_chatbot</Pill>}>
            Conversational chat
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {futureProofActions.chatbot.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>Catalyst</Pill>}>
            Supervised SQL workbench and Dashboard Builder
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {futureProofActions.catalyst.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Grid columns="1fr 1fr 1fr" gap={12}>
        <Callout tone="warning" title="Optimization Paradox">
          Improving a component does not improve the system. Trust end-to-end multi-case evaluation, not benchmark wins on
          isolated pieces. Especially relevant when adopting a new embedding model, LLM provider, or retrieval pipeline.
        </Callout>
        <Callout tone="warning" title="Rule of Two">
          No agent should hold all three of: process untrusted inputs, access sensitive systems, change state externally.
          Catalyst currently relies on the configured source or deployment for access, with read-only query access and time
          and row bounds; production identity and authorization remain later work.
        </Callout>
        <Callout tone="warning" title="Silent provider-switch drift">
          Provider portability is a feature; uncalibrated provider switching is a regression risk. Capture per-provider
          performance per case so handoff drift is detectable when models change.
        </Callout>
      </Grid>

      <Callout tone="info" title="Governance shape: PCCP">
        FDA's Predetermined Change Control Plan (final guidance Dec 2024, implementation recs Aug 2025; over 1,400 AI medical
        devices authorized as of Dec 2025) gives the right shape for change control even outside SaMD scope. Each
        model/prompt/retrieval change should ship with a <Code>Modification Description</Code>, <Code>Modification Protocol</Code>,
        and <Code>Impact Assessment</Code>. Use it as the validation roadmap's release-gate template.
      </Callout>

      <Divider />

      <H2>Cross-Project Synthesis</H2>
      <Grid columns="1.2fr 1fr" gap={16}>
        <Stack gap={8}>
          <H3>What this comparison is for</H3>
          <Text>
            Treat the three projects as <Text weight="semibold">parallel experiments</Text>, not as competitors or as products
            being compared on equal footing. Each one is exploring a different architectural question against the same backdrop
            of fast-moving 2025-2026 research. The comparison is useful exactly to the degree that it helps each project
            calibrate against current SOTA expectations and avoid reinventing primitives.
          </Text>
          <Text>
            Concretely: anchor the validation work in one place rather than three. The comparison gives a stable shape for what
            counts as a case record, a grade label, a run, and governance metadata. Below those four contracts, each prototype
            stays project-specific.
          </Text>
          <Text>
            For chartsearchai the yield is a portable spine schema. For openmrs_chatbot the yield is a place to graft evaluation
            onto without inventing primitives from scratch. For Catalyst the yield is a reader packet and review tooling over
            the same run and evidence records rather than a second scoring harness.
          </Text>
        </Stack>
        <Stack gap={8}>
          <H3>Open questions</H3>
          <Text>What is openmrs_chatbot's actual provider/model contract? Public docs do not say.</Text>
          <Text>Should the 18/20 OpenMRS clinical questions be evaluated against the chatbot's patient and doctor interfaces too, with role-aware expectations?</Text>
          <Text>Which human or frontier-model reader should perform Catalyst's full-context Phase 1 review?</Text>
          <Text>Does shared run-manifest plus shared dashboards justify a small joint OpenMRS x OpenELIS dev call (already requested 2026-04-28)?</Text>
        </Stack>
      </Grid>

      <Callout tone="success" title="Concrete next step">
        Implement and validate the existing <Code>run_manifest.json</Code> and <Code>events.jsonl</Code> envelope in each emitter,
        keeping project-specific evidence with the project that understands it. Map model metadata to current OpenTelemetry GenAI
        attributes such as <Code>gen_ai.provider.name</Code>, <Code>gen_ai.agent.name</Code>,
        <Code>gen_ai.request.model</Code>, and <Code>gen_ai.tool.name</Code> where available. Catalyst's implementation should emit
        the simple reader packet defined by the current metadata guide rather than a second scoring system.
      </Callout>

      <H2>Sources</H2>
      <Table
        headers={['Source', 'Why it matters', 'How it is used here']}
        rows={sourceLinks}
        striped
      />
    </Stack>
  );
}
