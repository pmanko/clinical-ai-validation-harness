import {
  Callout,
  Card,
  CardBody,
  CardHeader,
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

type StageIndex = 0 | 1 | 2 | 3 | 4;

type MaturityProject = {
  id: string;
  name: string;
  current: number;
  target: number;
  note: string;
};

const maturityStages = ['POC', 'MVP', 'Pilot', 'Production-ready', 'Deployed'];

const maturityProjects: MaturityProject[] = [
  {
    id: 'csai',
    name: 'chartsearchai',
    current: 1.6,
    target: 2.5,
    note: 'Live demo + 485-case eval; not deployed in production',
  },
  {
    id: 'cbot',
    name: 'openmrs_chatbot',
    current: 0.3,
    target: 1.5,
    note: 'Setup + workflow trace docs only; no public eval',
  },
  {
    id: 'cat',
    name: 'Catalyst (OpenELIS)',
    current: 0.8,
    target: 1.7,
    note: 'M0.0 foundation in 3.2.1.3 release; smoke E2E scripts',
  },
];

function MaturitySpectrumDiagram() {
  const theme = useHostTheme();
  const padX = 24;
  const padY = 16;
  const headerHeight = 30;
  const labelColWidth = 170;
  const noteColWidth = 240;
  const trackHeight = 52;
  const trackGap = 12;
  const viewWidth = 1000;
  const trackStartX = padX + labelColWidth;
  const trackEndX = viewWidth - padX - noteColWidth;
  const trackWidth = trackEndX - trackStartX;
  const stageGap = trackWidth / (maturityStages.length - 1);
  const viewHeight = padY * 2 + headerHeight + maturityProjects.length * (trackHeight + trackGap);

  return (
    <svg
      role="img"
      aria-label="Maturity spectrum across the three prototype projects"
      width="100%"
      viewBox={`0 0 ${viewWidth} ${viewHeight}`}
      style={{ display: 'block' }}
    >
      {maturityStages.map((stage, idx) => (
        <g key={stage}>
          <line
            x1={trackStartX + idx * stageGap}
            y1={padY + headerHeight - 4}
            x2={trackStartX + idx * stageGap}
            y2={viewHeight - padY}
            stroke={theme.stroke.tertiary}
            strokeWidth={0.5}
          />
          <text
            x={trackStartX + idx * stageGap}
            y={padY + 18}
            fontSize={11}
            textAnchor="middle"
            fill={theme.text.tertiary}
            style={{ fontFamily: 'inherit', letterSpacing: '0.06em', textTransform: 'uppercase' }}
          >
            {stage}
          </text>
        </g>
      ))}

      {maturityProjects.map((p, pidx) => {
        const y = padY + headerHeight + pidx * (trackHeight + trackGap) + trackHeight / 2;
        const cx = trackStartX + p.current * stageGap;
        const tx = trackStartX + p.target * stageGap;
        return (
          <g key={p.id}>
            <text
              x={padX + labelColWidth - 16}
              y={y + 4}
              fontSize={13}
              textAnchor="end"
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit', fontWeight: 600 }}
            >
              {p.name}
            </text>

            <line
              x1={trackStartX}
              y1={y}
              x2={trackEndX}
              y2={y}
              stroke={theme.stroke.secondary}
              strokeWidth={2}
            />

            {maturityStages.map((_, idx) => (
              <circle
                key={idx}
                cx={trackStartX + idx * stageGap}
                cy={y}
                r={3}
                fill={theme.stroke.secondary}
              />
            ))}

            {p.target > p.current && (
              <line
                x1={cx + 11}
                y1={y}
                x2={tx - 8}
                y2={y}
                stroke={theme.accent.primary}
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}

            <circle
              cx={cx}
              cy={y}
              r={9}
              fill={theme.fill.secondary}
              stroke={theme.accent.primary}
              strokeWidth={2}
            />
            <circle
              cx={tx}
              cy={y}
              r={6}
              fill="none"
              stroke={theme.accent.primary}
              strokeWidth={1.5}
              strokeDasharray="2 2"
            />

            <text
              x={trackEndX + 14}
              y={y + 4}
              fontSize={12}
              fill={theme.text.secondary}
              style={{ fontFamily: 'inherit' }}
            >
              {p.note}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const vectorOverviewRows = [
  ['V1. Clinical RAG architecture', 'Naive RAG can hurt; structured artifacts + provenance dramatically reduce hallucination.', 'STRONG', 'chartsearchai (primary), Catalyst (FHIR resource retrieval + citation, M10), openmrs_chatbot (if any retrieval)'],
  ['V2. Multi-agent clinical AI', 'Helps under workload; not universally better than single LLMs; component metrics deceive.', 'EMERGING', 'openmrs_chatbot, Catalyst (catalyst-gateway → catalyst-agents → catalyst-mcp trace)'],
  ['V3. NL-to-SQL clinical', 'SOTA models drop on hard queries; consistency (Pass^N) is the safety metric.', 'ACTIVE', 'Catalyst (future Phase 3 SQL path; FHIR-first POC is M10)'],
  ['V4. Evaluation evolution', 'Static benchmarks contaminate; live + execution-grounded benchmarks emerging; provider switching causes silent drift.', 'EMERGING', 'All three'],
  ['V5. Indirect prompt injection', 'Architectural problem; defense-in-depth is the standard.', 'STRONG', 'All three (most acute for chartsearchai)'],
  ['V6. Healthcare AI governance', 'FDA PCCP becoming change-control standard; over 1,400 AI medical devices authorized.', 'REGULATORY', 'All three (forward-looking)'],
  ['V7. Agent operating principles', 'Principles and explanations generalize better than rule-stuffing in agentic settings.', 'STRONG', 'All three'],
  ['V8. Agent observability & metadata', 'OTel GenAI conventions are emerging as the cross-tool trace vocabulary for agents.', 'ACTIVE', 'All three'],
];

const openQuestionsRows = [
  ['Will OpenMRS adopt PCCP-shaped change records even outside SaMD?', 'chartsearchai, Catalyst', 'Decision needed'],
  ['Can the validation spine schema be ratified across all three projects?', 'All', 'Cross-project conversation'],
  ['Should LiveClin-style benchmark refresh be coordinated across OpenMRS AI initiatives?', 'All', 'Future practice'],
  ['Where is the boundary between exploratory POC and pilot per project?', 'All', 'Stakeholder definition'],
  ['Who reviews indirect-injection corpora when they include synthetic chart text?', 'chartsearchai, openmrs_chatbot', 'Process design'],
  ['How does role-aware abstention generalize from chartsearchai to patient/doctor UIs?', 'openmrs_chatbot', 'Specification'],
  ['Does Catalyst\'s Rule of Two pattern apply to chartsearchai\'s record-level access?', 'chartsearchai', 'Architecture review'],
  ['Should the 18/20 OpenMRS clinical questions be benchmarked against all three with role-aware variants?', 'All', 'Eval design'],
];

const readingListRows = [
  ['Clinical RAG', <Link href="https://medrxiv.org/cgi/content/short/2026.02.13.26346256v1">Representation Before Retrieval (medRxiv 2026)</Link>, 'Structured patient artifacts cut unsupported claims 43.6% → 8.4%; provenance discipline matters more than retrieval algorithm.'],
  ['Clinical RAG', <Link href="https://arxiv.org/abs/2511.06738">Rethinking RAG for Medicine (arXiv 2025)</Link>, 'Stage-aware expert eval: only 22% top-16 medical RAG passages relevant; evidence selection P=41-43%, R=27-49%.'],
  ['Clinical RAG', <Link href="https://arxiv.org/html/2603.03541v1">RAG-X (arXiv 2026)</Link>, 'Diagnostic framework for medical RAG; 14% gap between perceived success and actual evidence-based grounding ("Accuracy Fallacy").'],
  ['Clinical RAG', <Link href="https://www.medrxiv.org/content/10.64898/2026.01.26.26344757v1.full">Retrospective Quality Analysis of a Clinical RAG Chatbot (medRxiv 2026)</Link>, 'Observable signals when full retrieval traces are unavailable: intent analysis, message-level scores, explicit user feedback.'],
  ['Multi-agent', <Link href="https://arxiv.org/abs/2506.06574">The Optimization Paradox (arXiv 2026)</Link>, 'Best-of-breed components (85.5% info accuracy) → 67.7% diagnostic accuracy on 2,400 cases; integrated multi-agent: 77.4%.'],
  ['Multi-agent', <Link href="http://www.nature.com/articles/s44401-026-00077-0">Orchestrated multi-agents under workload (npj Health Systems 2026)</Link>, 'Multi-agent: 90.6%→65.3% at 80 tasks vs single-agent 73.1%→16.6% collapse; up to 65× fewer tokens.'],
  ['Multi-agent', <Link href="http://www.nature.com/articles/s44387-026-00076-4">AI agents in healthcare: applications, evaluations, future directions (npj AI 2026)</Link>, 'Task-specific results: multi-agent does not universally beat single LLMs or specialized methods.'],
  ['Multi-agent', <Link href="https://arxiv.org/html/2603.26182v1">ClinicalAgents: Dual-Memory + MCTS (arXiv 2026)</Link>, 'Dynamic orchestration with Working Memory + Experience Memory; emerging SOTA for diagnostic reasoning.'],
  ['NL-to-SQL', <Link href="https://arxiv.org/abs/2601.09876">CLINSQL (arXiv 2026)</Link>, '633 expert-annotated tasks on MIMIC-IV v3.1; GPT-5-mini 74.7% execution; Gemini-2.5-Pro drops 85.5%→67.2% on hard queries.'],
  ['NL-to-SQL', <Link href="https://arxiv.org/abs/2509.23415v2">EHR-ChatQA (arXiv 2025)</Link>, 'Pass@5 over 90% but Pass^5 drops by up to 60 percentage points; consistency is the safety metric.'],
  ['NL-to-SQL', <Link href="https://arxiv.org/abs/2604.15646">FD-NL2SQL (arXiv 2026)</Link>, 'Feedback-driven schema-aware decomposition with exemplar bank growth via clinician feedback.'],
  ['NL-to-SQL', <Link href="https://www.mdpi.com/1999-4893/18/3/124">Recent LMs in SQL Query Automation (MDPI 2026)</Link>, 'Survey of clinical NL-to-SQL challenges: heterogeneous tables, temporal reasoning, terminology.'],
  ['Evaluation', <Link href="https://arxiv.org/html/2605.02240v1">PhysicianBench (arXiv 2026)</Link>, '100 long-horizon EHR tasks, 670 checkpoints, 21 specialties; best LLM agent only 46% success.'],
  ['Evaluation', <Link href="https://arxiv.org/abs/2602.16747v1">LiveClin (arXiv 2026)</Link>, 'Live clinical benchmark refreshed biannually; 1,407 cases / 6,605 questions; top model only 35.7% case accuracy.'],
  ['Evaluation', <Link href="https://arxiv.org/html/2601.04195v1">MedPI (arXiv 2026)</Link>, '105 dimensions in patient-clinician conversations; mapped to ACGME competencies.'],
  ['Evaluation', <Link href="https://www.flexpa.com/blog/benchmarking-llms-on-fhir">LLM FHIR Eval (Flexpa 2026)</Link>, 'Standardized eval across 14 models for FHIR-specific tasks; tool-assisted dramatically beats zero-shot.'],
  ['Indirect injection', <Link href="https://learn.microsoft.com/en-us/security/zero-trust/sfi/defend-indirect-prompt-injection">Microsoft: Defend against indirect prompt injection</Link>, 'Spotlighting reduces ASR over 50% → under 2%; defense-in-depth pattern (shields, IFC, plan drift, critic agents).'],
  ['Indirect injection', <Link href="https://zylos.ai/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content">Indirect Prompt Injection: 2026 SOTA (Zylos)</Link>, 'Architectural framing; Meta\'s Rule of Two; assume some attacks succeed.'],
  ['Indirect injection', <Link href="https://www.aptible.com/hipaa-ai-security/prompt-injection">Prompt injection in healthcare AI (Aptible)</Link>, 'HIPAA-aware framing of clinical-harm risks: dosing, triage, downplaying symptoms.'],
  ['Governance', <Link href="https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence">FDA PCCP guidance (final 2024 / impl 2025)</Link>, 'Modification Description + Modification Protocol + Impact Assessment for AI device changes.'],
  ['Governance', <Link href="https://reg-intel.com/fda-ai-medical-devices-2026-guidance-pccp-and-eu-ai-act-comparison/">FDA AI Medical Devices: 2026 Guidance, PCCP, EU AI Act Comparison</Link>, '1,451 AI-enabled medical devices authorized as of Dec 2025; 26 PCCPs authorized as of May 2025.'],
  ['Governance', <Link href="https://www.medrxiv.org/content/10.64898/2026.04.09.26350519v1">HAARF: Healthcare AI Agents Regulatory Framework (medRxiv 2026)</Link>, '279 requirements across risk-based levels for autonomous clinical AI, including tool-use security and clinical decision traceability.'],
  ['Governance', <Link href="https://chai.org/workgroup/responsible-ai/responsible-ai-checklists-raic">CHAI RAIC (Responsible AI Checklists)</Link>, 'Healthcare AI self-review across usefulness, fairness, safety, transparency, privacy/security.'],
  ['Governance', <Link href="https://pmc.ncbi.nlm.nih.gov/articles/PMC12104976/">TRIPOD-LLM (PMC 2025)</Link>, 'Healthcare LLM reporting checklist with data, metrics, annotation, prompting, compute, and intended-use items.'],
  ['Governance', <Link href="https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence">NIST GenAI Profile</Link>, 'Risk-management lifecycle for design, development, use, and evaluation of GenAI systems.'],
  ['Agent operating principles', <Link href="https://www.anthropic.com/research/teaching-claude-why">Teaching Claude why (Anthropic)</Link>, 'Targeted rule training helps narrowly; principle-driven reasoning and constitutional documents generalize better in agentic settings.'],
  ['Agent operating principles', <Link href="https://www.anthropic.com/research/agentic-misalignment">Agentic Misalignment (Anthropic)</Link>, 'Chat alignment does not automatically transfer to autonomous tool-use settings.'],
  ['Agent operating principles', <Link href="https://www.anthropic.com/constitution">Claude Constitution (Anthropic)</Link>, 'Constitutional principles provide a transferable reasoning frame instead of a flat checklist.'],
  ['Agent operating principles', <Link href="https://www.corti.ai/agents/clinical-guidelines-agent">Clinical Guidelines Agent (Corti)</Link>, 'Example of strict source control, explicit citation, and transparent reasoning for guideline assessment.'],
  ['Agent observability', <Link href="https://opentelemetry.io/docs/specs/semconv/gen-ai">OpenTelemetry GenAI semantic conventions</Link>, 'Development-stage standard for GenAI model, agent, tool, event, exception, and metrics spans.'],
  ['Agent observability', <Link href="http://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/">OpenTelemetry GenAI agent spans</Link>, 'Agent operations cover create/invoke agent, workflow invocation, and tool execution spans.'],
  ['Agent observability', <Link href="https://docs.arize.com/phoenix/tracing/llm-traces">Phoenix tracing</Link>, 'Open-source LLM tracing with OTel/OpenInference support for prompt and agent debugging.'],
  ['Agent observability', <Link href="https://docs.langchain.com/oss/python/langchain/observability">LangSmith Observability</Link>, 'LangChain-first agent tracing capturing tool calls, prompts, and decisions.'],
];

type Vector = {
  id: string;
  number: string;
  title: string;
  evidence: 'STRONG' | 'EMERGING' | 'ACTIVE' | 'REGULATORY';
  evidenceTone: 'success' | 'info' | 'warning' | 'neutral';
  primary: string[];
  lead: string;
  findings: string[];
  doList: string[];
  dontList: string[];
  csai: string;
  cbot: string;
  cat: string;
  limitation: string;
};

const vectors: Vector[] = [
  {
    id: 'rag',
    number: 'V1',
    title: 'Clinical RAG architecture',
    evidence: 'STRONG',
    evidenceTone: 'success',
    primary: ['chartsearchai (primary)', 'Catalyst (FHIR resource retrieval; resource-level citations per Observation/DiagnosticReport/ServiceRequest)', 'openmrs_chatbot (if retrieval)'],
    lead: 'Eighteen months of evidence has changed the prior. Naive RAG often hurts more than it helps in clinical contexts. Quality depends on representation choices and provenance discipline more than retrieval algorithm choices.',
    findings: [
      'Baseline clinical RAG produced 43.6% unsupported claims; structured patient artifacts with provenance reduced this to 8.4% (40% relative reduction).',
      'Large medical RAG eval found only 22% of top-16 passages relevant; evidence-selection precision 41-43%, recall 27-49%.',
      'RAG-X "Accuracy Fallacy": 14% gap between perceived success and evidence-based grounding.',
      'Multi-step verification consistently outperforms single-pass RAG for safety-relevant outputs.',
    ],
    doList: [
      'Stage-aware metrics (retrieval / selection / answer / abstention).',
      'Structured serialization with first-class provenance per claim.',
      'Multi-step verification before display.',
    ],
    dontList: [
      'Trust end-to-end accuracy; it hides where the failure lives.',
      'Rely on naive top-k embedding retrieval as the only retriever.',
      'Assume "more retrieval = safer answers".',
    ],
    csai: 'Validates the labeled-prose + structured-metadata pattern; adds urgency to per-citation provenance preservation in eval traces.',
    cbot: 'Any retrieval needs the same discipline; observable-signals eval is the practical floor.',
    cat: 'FHIR resource queries (Patient, Observation, ServiceRequest, DiagnosticReport) are the structured retrieval layer for M10. Schema RAG / allowlist remains the model for the future SQL path (Phase 3). Resource-level citations are the provenance artifact.',
    limitation: 'Most studies use English-language EMRs (MIMIC-IV class). Generalization to OpenMRS in resource-constrained settings is not yet established.',
  },
  {
    id: 'mas',
    number: 'V2',
    title: 'Multi-agent clinical AI',
    evidence: 'EMERGING',
    evidenceTone: 'info',
    primary: ['openmrs_chatbot', 'Catalyst (multi-agent FHIR retrieval: gateway → agents → mcp trace; events.jsonl per M2 spine)'],
    lead: 'Orchestrated multi-agent helps in workload-heavy or mixed-task scenarios but is not universally better than a strong single LLM. The Optimization Paradox shows component-level metrics consistently deceive when used alone.',
    findings: [
      'Multi-agent sustained 90.6% accuracy at 5 tasks → 65.3% at 80 tasks vs single-agent 73.1% → 16.6% collapse.',
      'Multi-agent used up to 65-fold fewer tokens with limited latency growth in workload-heavy scenarios.',
      'Optimization Paradox: 85.5% component info accuracy yielded only 67.7% diagnostic accuracy; an integrated multi-agent system hit 77.4%.',
      'Multi-agent does not universally beat single LLMs in textual MQA, EHR-prediction, or medical visual QA.',
      'ClinicalAgents (MCTS + Dual-Memory) emerging as SOTA for diagnostic reasoning with explainability.',
    ],
    doList: [
      'Validate end-to-end on real cases, not just per-component metrics.',
      'Measure token efficiency and latency under realistic workload variability.',
      'Run ablations: does multi-agent actually beat a strong single LLM on this task?',
    ],
    dontList: [
      'Assume multi-agent always wins.',
      'Optimize components in isolation and assume the system improves.',
      'Skip end-to-end evaluation when adopting a new agent role.',
    ],
    csai: 'Not multi-agent today. If added later, justify per task type and avoid optimizing components without end-to-end validation.',
    cbot: 'Agent-team scaffolding present; needs empirical justification per task type before committing.',
    cat: 'catalyst-agents is multi-agent by design; FHIR tool orchestration (search_patient → get_observations → build_timeline) is the natural multi-agent test bed; end-to-end trace via events.jsonl + MCP tool spans.',
    limitation: 'Most studies focus on diagnostic/triage tasks. Chart-search and conversational EMR tasks not yet well-evaluated in the MAS literature.',
  },
  {
    id: 'nlsql',
    number: 'V3',
    title: 'NL-to-SQL clinical',
    evidence: 'ACTIVE',
    evidenceTone: 'info',
    primary: ['Catalyst (future Phase 3 SQL path; FHIR-first retrieval is the active M10 POC lane)'],
    lead: 'Benchmarks are emerging fast (CLINSQL, EHR-ChatQA). Even SOTA models drop accuracy substantially on hard queries; consistency (Pass^N) is a much stricter bar than Pass@N and is the right safety metric for clinical use. For Catalyst, the FHIR-first POC (M10) precedes the SQL path; V3 findings apply to Phase 3 planning.',
    findings: [
      'CLINSQL: GPT-5-mini 74.7% execution score; DeepSeek-R1 69.2% (best open-source); Gemini-2.5-Pro 85.5% on easy → 67.2% on hard.',
      'EHR-ChatQA: best agents reach Pass@5 over 90% but Pass^5 drops by up to 60 percentage points.',
      'Schema-aware decomposition (FD-NL2SQL) plus post-validation outperforms direct generation.',
      'Exemplar-bank growth via clinician feedback is a practical evolution path.',
    ],
    doList: [
      'Pass^N consistency, not just Pass@N.',
      'Schema-aware decomposition into predicate-level sub-questions.',
      'Post-processing validity checks before returning SQL to user.',
      'Exemplar bank that grows with clinician feedback.',
    ],
    dontList: [
      'Trust single-trial Pass@N as a release gate.',
      'Ignore temporal reasoning over time-series clinical data.',
      'Assume schema stability; allowlist + drift detection are required.',
    ],
    csai: 'Not NL-to-SQL today. Relevant only if querystore-grounded SQL paths emerge.',
    cbot: 'Not NL-to-SQL today.',
    cat: 'Future Phase 3 lane (SQL execution). M10 FHIR POC is the active path. Pass^N + schema-aware decomposition apply when the SQL path resumes in Phase 3 (post-OGC-070 Java backend integration).',
    limitation: 'MIMIC-IV-centric benchmarks. OpenELIS schema not yet benchmarked. Non-English clinical contexts under-studied.',
  },
  {
    id: 'eval',
    number: 'V4',
    title: 'Evaluation evolution',
    evidence: 'EMERGING',
    evidenceTone: 'info',
    primary: ['All three'],
    lead: 'Static benchmarks risk training-data contamination as models improve. Live + execution-grounded benchmarks are emerging. Provider switching introduces silent drift that is invisible if you do not test for it.',
    findings: [
      'PhysicianBench: 100 long-horizon EHR tasks, 670 checkpoints; best LLM agent only 46% success.',
      'LiveClin: biannual refresh of contemporary case reports; top models hit only 35.7% case accuracy.',
      'MedPI: 105 dimensions in patient-clinician conversations, mapped to ACGME competencies.',
      'Silent provider-switch drift: -8 to +13 percentage points on a single handoff; ~70% explained by per-model prefix-influence + suffix-susceptibility.',
      'Tool-assisted approaches dramatically beat zero-shot generation for FHIR-specific tasks.',
    ],
    doList: [
      'Plan benchmark refresh cadence (e.g. quarterly clinical-question regeneration).',
      'Capture per-provider performance per case so handoff drift is detectable.',
      'Pin model id, file hash, prompt version, dataset version per run.',
      'Use execution-grounded scoring where possible (real DB / real API responses).',
    ],
    dontList: [
      'Rely on a one-time golden baseline.',
      'Assume benchmark generalization across populations or care settings.',
      'Skip handoff drift testing when introducing a new provider.',
    ],
    csai: 'Golden 485-case set will need a refresh cadence. Per-provider metric capture matters once LM Studio model changes are routine.',
    cbot: 'No public eval contract. Observable signals (intent, message-level quality, explicit feedback) are the practical floor.',
    cat: 'Provider portability needs explicit handoff drift testing; today\'s smoke E2E does not capture it.',
    limitation: 'Benchmark pluralism is causing fragmentation. No consensus on which to track for resource-poor settings yet.',
  },
  {
    id: 'ipi',
    number: 'V5',
    title: 'Indirect prompt injection',
    evidence: 'STRONG',
    evidenceTone: 'success',
    primary: ['All three (most acute for chartsearchai)'],
    lead: 'The vulnerability is architectural: LLMs cannot reliably distinguish instructions from data on the same token stream. Industry SOTA in 2026 is layered defense, not a single fix. Healthcare-specific benchmarks now separate clinical harm from instruction compliance.',
    findings: [
      'Spotlighting (mark + isolate untrusted content) reduces attack success rate from over 50% to under 2% with minimal task degradation.',
      'Meta\'s Rule of Two: an agent should hold at most two of {process untrusted inputs, access sensitive systems, change state externally}.',
      'Microsoft defense-in-depth: spotlighting + prompt shields + IFC + plan drift detection + critic agents + least privilege.',
      'MPIB introduces Clinical Harm Event Rate (CHER) alongside ASR; harm depends on whether injection lives in user query vs retrieved context.',
      'Practical stance: assume some indirect injections will succeed; design with human-in-the-loop on risky clinical actions.',
    ],
    doList: [
      'Build an indirect-injection corpus where attacks ride in chart text, lab notes, or MCP responses.',
      'Adopt spotlighting + Rule of Two as the baseline architecture.',
      'Track CHER alongside ASR; not all "successful" attacks cause clinical harm.',
      'Require human-in-the-loop confirmation for state-changing or high-risk actions.',
    ],
    dontList: [
      'Cover only direct injection (user-provided malicious prompts).',
      'Rely on a single defense layer.',
      'Assume the model can self-defend through prompt instruction.',
    ],
    csai: 'Chart text is the primary indirect-injection vector. Expand the existing PromptInjectionEvalTest from direct only to indirect via observation/note text.',
    cbot: 'Needs explicit injection eval. Declare Rule of Two boundary explicitly given multi-UI and agent-team surface.',
    cat: 'Allowlist + RBAC + read-only DB user honors Rule of Two by design. Add spotlighting between schema context and user input inside MCP responses.',
    limitation: 'Defenses partially reduce but never eliminate. Plan for residual risk; no architecture is injection-immune.',
  },
  {
    id: 'gov',
    number: 'V6',
    title: 'Healthcare AI governance',
    evidence: 'REGULATORY',
    evidenceTone: 'warning',
    primary: ['All three (forward-looking)'],
    lead: 'FDA finalized PCCP guidance December 2024; over 1,400 AI-enabled medical devices authorized as of December 2025. PCCP shape is becoming the industry change-control standard, useful even outside SaMD scope.',
    findings: [
      'PCCP triple: Modification Description + Modification Protocol + Impact Assessment.',
      '1,451 AI-enabled medical devices authorized as of December 2025 (record year 2025: 295 new).',
      '26 PCCPs authorized as of May 2025; 510(k) pathway dominant.',
      'EU AI Act conformity assessment is comparable in shape to PCCP; international convergence is plausible.',
      'NIST GenAI Profile, CHAI RAIC, and TRIPOD-LLM provide complementary self-review frameworks.',
      'HAARF adds a healthcare-agent-specific view: 279 requirements across risk-based levels, including tool-use security, continuous equity monitoring, and clinical decision traceability.',
    ],
    doList: [
      'Encode change records in PCCP shape now: Modification Description + Protocol + Impact Assessment.',
      'Maintain intended-use docs and monitoring plans even outside SaMD scope.',
      'Pin every model/prompt/retrieval change to a reviewable change record.',
    ],
    dontList: [
      'Treat governance as an afterthought to be bolted on at deployment.',
      'Skip change-control formality for "minor" prompt or retrieval tweaks.',
      'Assume open-source clinical AI is exempt from emerging regulatory expectations.',
    ],
    csai: 'Validation roadmap should encode PCCP-shaped change records; existing 485-case eval is well-positioned to serve as the Impact Assessment substrate.',
    cbot: 'Governance currently undeclared. Needs at minimum: intended-use statement, change log, basic monitoring plan.',
    cat: 'Provider abstraction (LM Studio + Gemini) is itself a change vector; PCCP framing useful for handoff change control.',
    limitation: 'International regulatory landscape evolving fast; LMIC-specific frameworks under-developed; OpenMRS deployment contexts may need bespoke governance shape.',
  },
  {
    id: 'principles',
    number: 'V7',
    title: 'Agent operating principles',
    evidence: 'STRONG',
    evidenceTone: 'success',
    primary: ['All three'],
    lead: 'Anthropic’s agentic-alignment work is directly relevant to our agent instructions. The lesson is not to stuff more rules into system prompts; it is to teach the operating principles, the reasons behind them, and the context in which they apply.',
    findings: [
      'Direct training on honeypot-like failures reduced misalignment only narrowly; targeted fixes did not generalize well out of distribution.',
      'Adding reasoning about why aligned actions were better reduced misalignment far more than demonstrations alone.',
      'A much smaller “difficult advice” dataset generalized better than a much larger targeted honeypot dataset, suggesting principled reasoning transfers.',
      'Constitutional documents and positive stories about aligned behavior reduce agentic misalignment by shifting the model’s persona distribution.',
      'Diverse context, including tool definitions and system prompts even when tools are unused, improves generalization in agentic settings.',
    ],
    doList: [
      'Write project guidance as principles with because-clauses, not just do/don’t rules.',
      'Keep a short project constitution above operational rules.',
      'Give agents README, ADRs, eval docs, failure history, and examples of good changes.',
      'When an agent fails, ask which principle was missing before adding another specific prohibition.',
    ],
    dontList: [
      'Patch every failure with a new isolated rule.',
      'Treat chat behavior as evidence of agent behavior under tool-use pressure.',
      'Hide domain context and expect the model to infer why a rule matters.',
    ],
    csai: 'Rewrite top-level guidance around clinical evidence, evals-as-contract, scoped changes, and provenance; specific API rules can remain underneath.',
    cbot: 'Each agent role needs a short constitution: role, evidence limits, escalation behavior, and role-aware abstention.',
    cat: 'The allowlist/RBAC design is strong and preserved for the SQL path. For FHIR M10: agent instructions should explain FHIR read-only access boundaries, resource scope limits, and citation obligations in clinical-safety terms.',
    limitation: 'The Anthropic work is not healthcare-specific and is based on model-training interventions, not just prompt files. Treat it as strong guidance for prompt/guideline design, not a guarantee.',
  },
  {
    id: 'observability',
    number: 'V8',
    title: 'Agent observability & metadata',
    evidence: 'ACTIVE',
    evidenceTone: 'info',
    primary: ['All three'],
    lead: 'The emerging standard path is not a bespoke pile of logs. OpenTelemetry GenAI semantic conventions now define common vocabulary for model, agent, workflow, and tool spans. Our metadata store should align to those conventions while preserving clinical eval fields.',
    findings: [
      'OpenTelemetry GenAI conventions cover LLM client spans, model operations, agent operations, tool spans, events, exceptions, and metrics.',
      'Agent spans include creating agents, invoking agents, invoking workflows, and executing tools, with attributes such as gen_ai.system, gen_ai.agent.name, gen_ai.request.model, and gen_ai.tool.name.',
      'Major observability vendors and frameworks are adopting OTel/OpenInference-style traces; LangSmith and Phoenix provide complementary trace/debug workflows.',
      'Clinical AI needs more than tracing: run manifests, retrieval records, answer records, evaluator outputs, and reviewer notes must be queryable as operating metadata.',
    ],
    doList: [
      'Define an append-only operating metadata store: run, query, retrieval, model, response, evaluation, review, and change-record events.',
      'Map shared fields to OTel GenAI attributes where possible.',
      'Keep clinical eval fields (citations, claims, abstention, CHER, reviewer label) even if OTel does not standardize them.',
      'Make dashboards, baseline diffs, and PCCP-style change records read from the same metadata store.',
    ],
    dontList: [
      'Treat console logs or free-form workflow traces as sufficient for validation.',
      'Force all clinical concepts into OTel attributes; use OTel for interoperability and project fields for clinical semantics.',
      'Let model/provider changes happen without preserving run-level provenance.',
    ],
    csai: 'P2 validation spine should emit run manifests and JSONL traces aligned to OTel GenAI conventions while keeping citation/eval-specific fields.',
    cbot: 'Workflow trace docs should evolve into agent/tool/model spans plus per-turn evaluation records.',
    cat: 'A2A router, catalyst-agents, MCP FHIR tool calls (search_patient, get_observations, etc.), and answer/citation generation are natural OTel GenAI span boundaries. SQL preview + RBAC spans deferred to Phase 3.',
    limitation: 'OpenTelemetry GenAI conventions are still in development. Use them as a vocabulary target, but keep the schema versioned and locally owned.',
  },
];

function VectorSection({ vector }: { vector: Vector }) {
  return (
    <Stack gap={10}>
      <H3>{`${vector.number}. ${vector.title}`}</H3>
      <Row gap={8} wrap>
        <Pill tone={vector.evidenceTone} active>{vector.evidence} evidence</Pill>
        {vector.primary.map((p) => (
          <Pill key={p} size="sm" tone="neutral">{p}</Pill>
        ))}
      </Row>
      <Text tone="secondary">{vector.lead}</Text>
      <Card>
        <CardBody>
          <Grid columns="1fr 1fr" gap={16}>
            <Stack gap={10}>
              <Text weight="semibold">Findings</Text>
              {vector.findings.map((f, i) => (
                <Text key={i} tone="secondary">• {f}</Text>
              ))}
            </Stack>
            <Stack gap={10}>
              <Text weight="semibold">For our prototypes</Text>
              <Stack gap={6}>
                <Text><Text weight="semibold">chartsearchai:</Text> {vector.csai}</Text>
                <Text><Text weight="semibold">openmrs_chatbot:</Text> {vector.cbot}</Text>
                <Text><Text weight="semibold">Catalyst:</Text> {vector.cat}</Text>
              </Stack>
            </Stack>
          </Grid>
        </CardBody>
      </Card>
      <Grid columns="1fr 1fr" gap={12}>
        <Card>
          <CardHeader>Do</CardHeader>
          <CardBody>
            <Stack gap={6}>
              {vector.doList.map((d, i) => (
                <Text key={i}>• {d}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Avoid</CardHeader>
          <CardBody>
            <Stack gap={6}>
              {vector.dontList.map((d, i) => (
                <Text key={i}>• {d}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
      </Grid>
      <Callout tone="neutral" title="What the research does not (yet) show">
        {vector.limitation}
      </Callout>
    </Stack>
  );
}

const evolutionPaths = {
  csai: {
    now: 'MVP-tier prototype with strong eval discipline (485-case enriched retrieval, citation, absent-data, prompt-injection); live demo at chartsearchai.openmrs.org; embedded llama-server + LM Studio remote.',
    near: [
      'Structured-artifact provenance preserved per cited record in eval traces.',
      'Indirect-injection corpus through chart text (notes, observations).',
      'PCCP-shaped change records on every retrieval/prompt change.',
      'Constitution-style project guidance: principles with reasons before API-level rules.',
      'Run-manifest and JSONL traces aligned to OpenTelemetry GenAI conventions.',
      'Demo-data 2.8 remap so validation runs against a realistic patient corpus.',
    ],
    far: [
      'querystore parity once retrieval is delegated.',
      'Contamination-resistant baseline refresh cadence.',
      'Clinician adjudication SOP for baseline updates.',
      'Observable-signals fallback for limited-trace deployments.',
    ],
  },
  cbot: {
    now: 'Early POC: patient/doctor UIs, agent-team scaffolding, workflow-trace docs in repo; no public eval contract; provider/model unspecified.',
    near: [
      'Declare provider/model contract publicly.',
      'Define eval primitives (citation, abstention, role-aware grounding).',
      'Commit to Rule of Two boundary explicitly.',
      'Write per-agent operating principles before expanding agent roles.',
      'Convert workflow traces into agent/tool/model spans plus per-turn evaluation records.',
    ],
    far: [
      'Empirical multi-agent justification per task type.',
      'Observable-signals eval as the floor.',
      'Role-aware abstention contract per UI (patient vs doctor).',
      'Adopt the shared validation spine schema.',
    ],
  },
  cat: {
    now: 'M10 (Planning) — FHIR-first sidecar POC. OGC-070 spec defines prior NL-to-SQL milestone plan; allowlist + RBAC by design; provider abstraction (LM Studio + Gemini). Active pivot: catalyst-mcp moves from schema mock to FHIR resource tools over OE2 HAPI FHIR (:8444).',
    near: [
      'Five canonical FHIR questions answered with resource-level citations (M10 POC).',
      'Scout-style sidecar UI: evidence cards per FHIR resource type, lab-result table, lab timeline.',
      'HAPI-first answer path + embedded-FHIR parity probe with gap log (M10-F).',
      'Pass^N consistency over canonical question set; OTel GenAI spans for MCP FHIR tool calls.',
      'run_manifest.json + events.jsonl per M2 metadata spine.',
    ],
    far: [
      'NL-to-SQL Phase 3 (post-OGC-070 Java backend integration): CLINSQL-shaped scoring on OpenELIS schema.',
      'CHER tracking alongside ASR for safety-eval rigor once SQL path active.',
      'Federated cross-project benchmarks (sharing spine schema with chartsearchai).',
      'PCCP-shaped change records for provider abstraction transitions and FHIR surface changes.',
    ],
  },
};

export default function ClinicalAIResearchGuidance() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <H1>Clinical AI Research → Prototype Guidance</H1>
        <Text tone="secondary">
          Positions chartsearchai, openmrs_chatbot, and OpenELIS Catalyst as early-prototype explorations against the current
          state of clinical AI development (mid-2026). Recent peer-reviewed and arXiv work calibrates realistic expectations,
          identifies near-term evolution moves, and protects against treating the prototypes as feature-complete products.
        </Text>
        <Row gap={8} wrap>
          <Pill tone="info" active>Research grounding</Pill>
          <Pill tone="info" active>Prototype guidance</Pill>
          <Pill tone="info" active>Maturity assessment</Pill>
          <Pill tone="info" active>Evolution paths</Pill>
          <Pill tone="warning" active>Mid-2026 SOTA</Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="8" label="Research vectors covered" tone="info" />
        <Stat value="3" label="Early-prototype projects assessed" tone="info" />
        <Stat value="Curated" label="Recent papers and standards" tone="success" />
        <Stat value="2 of 3" label="Projects below MVP tier" tone="warning" />
      </Grid>

      <Callout tone="warning" title="What these projects actually are">
        chartsearchai, openmrs_chatbot, and Catalyst are <Text weight="semibold">early-prototype explorations</Text>, not
        feature-complete products. Each one occupies a different point on the maturity spectrum and asks a different research
        question; the research below calibrates expectations and sets near-term moves.
      </Callout>

      <Divider />

      <H2>Maturity Snapshot</H2>
      <Text tone="secondary">
        Filled circle = current position; dashed open circle = realistic 12-month target if the recommended evolution moves
        are taken. Movement is not a goal in itself — staying at POC for the right reasons (e.g. waiting on clinician input
        or governance clarity) is acceptable.
      </Text>
      <Card>
        <CardBody>
          <MaturitySpectrumDiagram />
        </CardBody>
      </Card>

      <Divider />

      <H2>Eight Research Vectors</H2>
      <Text tone="secondary">
        Eight dimensions where the field has moved meaningfully in the last 12-18 months. Evidence-strength tags
        (STRONG / EMERGING / ACTIVE / REGULATORY) signal how much weight to put on each finding when designing prototypes.
      </Text>
      <Table
        headers={['Vector', 'One-line state of research', 'Evidence', 'Most relevant to']}
        rows={vectorOverviewRows}
        striped
      />

      <Divider />

      <H2>Vector Deep Dives</H2>
      <Text tone="secondary">
        Each section: state-of-research lead, key findings (with numbers and citations from the reading list below), how it
        applies to each prototype, do-list and avoid-list, plus what the research does not yet show.
      </Text>

      {vectors.map((v) => (
        <VectorSection key={v.id} vector={v} />
      ))}

      <Divider />

      <H2>Per-Project Evolution Path</H2>
      <Text tone="secondary">
        Concrete next-move recommendations grounded in the vectors above. "Now" reflects mid-2026 state; "Next 3 months" and
        "Next 12 months" sketch a realistic evolution given a single-contributor pace per project.
      </Text>
      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>MVP-tier</Pill>}>
            chartsearchai
          </CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text><Text weight="semibold">Now:</Text> {evolutionPaths.csai.now}</Text>
              <Stack gap={6}>
                <Text weight="semibold">Next 3 months</Text>
                {evolutionPaths.csai.near.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
              <Stack gap={6}>
                <Text weight="semibold">Next 12 months</Text>
                {evolutionPaths.csai.far.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="warning" active>POC-tier</Pill>}>
            openmrs_chatbot
          </CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text><Text weight="semibold">Now:</Text> {evolutionPaths.cbot.now}</Text>
              <Stack gap={6}>
                <Text weight="semibold">Next 3 months</Text>
                {evolutionPaths.cbot.near.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
              <Stack gap={6}>
                <Text weight="semibold">Next 12 months</Text>
                {evolutionPaths.cbot.far.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>POC → MVP</Pill>}>
            Catalyst
          </CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text><Text weight="semibold">Now:</Text> {evolutionPaths.cat.now}</Text>
              <Stack gap={6}>
                <Text weight="semibold">Next 3 months</Text>
                {evolutionPaths.cat.near.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
              <Stack gap={6}>
                <Text weight="semibold">Next 12 months</Text>
                {evolutionPaths.cat.far.map((n, i) => (
                  <Text key={i} tone="secondary">• {n}</Text>
                ))}
              </Stack>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Open Questions Worth Tracking</H2>
      <Text tone="secondary">
        Questions where the answer is genuinely unknown or requires stakeholder decision rather than more research. Worth
        tracking explicitly so they do not become silent assumptions.
      </Text>
      <Table
        headers={['Open question', 'Affects', 'Type of resolution']}
        rows={openQuestionsRows}
        striped
      />

      <Divider />

      <H2>Reading List</H2>
      <Text tone="secondary">
        Curated bibliography organized by vector. Use as the bibliography for any cross-project working group or external
        write-up. Most sources are 2025-2026 publications or current standards; older work is included only when it remains a
        load-bearing reference.
      </Text>
      <Table
        headers={['Vector', 'Paper / source', 'One-line takeaway']}
        rows={readingListRows}
        striped
      />

      <Callout tone="info" title="Posture summary">
        Read these prototypes as <Text weight="semibold">live experiments</Text> rather than products. The research does not
        give us a single architecture to converge on; it gives us a set of disciplined moves: stage-aware retrieval metrics,
        Pass^N consistency, indirect-injection coverage, per-provider drift capture, PCCP-shaped change control, and a refresh
        cadence on benchmarks. The agentic-alignment research adds two more: principle-driven operating guidance and traceable
        operating metadata. Each project should pick the moves that match its current tier and explicitly defer the rest.
      </Callout>
    </Stack>
  );
}
