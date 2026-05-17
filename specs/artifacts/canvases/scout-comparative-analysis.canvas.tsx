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

const projects = ['scout', 'chartsearchai', 'chatbot', 'catalyst'] as const;
type ProjectKey = (typeof projects)[number];

const projectStages: Record<
  ProjectKey,
  {
    name: string;
    badge: string;
    user: string;
    entry: string;
    context: string;
    retrieve: string;
    generate: string;
    execute: string;
    output: string;
  }
> = {
  scout: {
    name: 'Scout (Duke DIHI)',
    badge: 'Closed institutional · MVP++',
    user: 'Clinician (mostly faculty), trainees, nurses, pharmacists',
    entry: 'Web app; user enters MRN, sets context (time, encounters, notes), free-text question',
    context: 'FHIR resources pre-fetched per patient; uploaded PDFs; user-set filters',
    retrieve: 'LLM orchestrator plans → subagents per domain (notes, labs, meds, vitals, allergies, imaging) → returns spans + structured fields',
    generate: 'OpenAI GPT family via Azure ZDR (PHI-permitted); fast-path/slow-path routed by complexity',
    execute: 'In-process orchestration; guardrails + safety checks at answer time; full interaction logging per internal policy',
    output: 'Free-text or templated answer, every claim cited; evidence cards expose source spans',
  },
  chartsearchai: {
    name: 'chartsearchai',
    badge: 'Java / OpenMRS · MVP-tier',
    user: 'Clinician at point of care (O3)',
    entry: 'O3 floating button or workspace dock',
    context: 'Serialized chart records (text + dense embedding + structured metadata)',
    retrieve: 'ONNX (MiniLM L6 / MedCPT) + Lucene + RRF; per-resource serializers; AOP indexing today',
    generate: 'Embedded llama-server (default Gemma 4 E4B) or remote OpenAI-compat (LM Studio: MedGemma 1.5 4B / Gemma 4 26B MoE)',
    execute: 'In-process Java; rate-limited; prompt-injection eval; audit log',
    output: 'Structured JSON answer with chart-record citations',
  },
  chatbot: {
    name: 'openmrs_chatbot',
    badge: 'Python / Multi-UI · POC',
    user: 'Patient or doctor (separate UIs)',
    entry: 'Patient chat UI / doctor chat UI',
    context: 'OpenMRS data + dialogue state + role context',
    retrieve: 'Conversational orchestration; agent-team scaffolding',
    generate: 'LLM via agent team (provider unspecified in public docs)',
    execute: 'In-process Python; setup + workflow trace docs',
    output: 'Multi-turn role-conditioned message',
  },
  catalyst: {
    name: 'Catalyst (OpenELIS)',
    badge: 'Python FHIR sidecar · M10 Planning',
    user: 'Lab tech or reviewer (sidecar report portal)',
    entry: 'catalyst-gateway (A2A router) + sidecar UI',
    context: 'catalyst-mcp queries OE2 HAPI FHIR (:8444); embedded FHIR parity probe',
    retrieve: 'FHIR resource tools: search_patient, get_observations, get_diagnostic_reports, build_patient_lab_timeline',
    generate: 'catalyst-agents (LM Studio / Gemini); FHIR-grounded answer with inline citation markers',
    execute: 'Read-only FHIR queries; no SQL execution in POC; Scout-style evidence cards + lab timeline',
    output: 'answer + facts[] + citations[resourceType, id, url] + uiBlocks[lab_result_table, lab_timeline]',
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
    if (lines.length >= 3) break;
  }
  if (lines.length < 4 && current) lines.push(current);
  if (lines.length === 4 && (current.length > maxChars || words.length > lines.join(' ').split(' ').length)) {
    lines[3] = lines[3].slice(0, maxChars - 1) + '…';
  }
  return lines.slice(0, 4);
}

function ArchitectureMatrixDiagram() {
  const theme = useHostTheme();
  const colWidth = 230;
  const colGap = 14;
  const labelColWidth = 130;
  const padX = 18;
  const headerHeight = 38;
  const rowHeight = 78;
  const rowGap = 8;
  const totalWidth = padX * 2 + labelColWidth + projects.length * (colWidth + colGap) - colGap;
  const totalHeight = headerHeight + 12 + stageRows.length * (rowHeight + rowGap);

  return (
    <svg
      role="img"
      aria-label="Per-project architecture matrix including Scout"
      width="100%"
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      style={{ display: 'block' }}
    >
      {projects.map((p, idx) => {
        const x = padX + labelColWidth + idx * (colWidth + colGap);
        const isScout = p === 'scout';
        return (
          <g key={`hdr-${p}`}>
            <rect
              x={x}
              y={4}
              width={colWidth}
              height={headerHeight - 4}
              rx={6}
              fill={isScout ? theme.fill.secondary : theme.fill.tertiary}
              stroke={isScout ? theme.accent.primary : theme.stroke.secondary}
              strokeWidth={isScout ? 1.5 : 1}
            />
            <text
              x={x + 12}
              y={headerHeight - 18}
              fontSize={12.5}
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit', fontWeight: 600 }}
            >
              {projectStages[p].name}
            </text>
            <text
              x={x + 12}
              y={headerHeight - 5}
              fontSize={10}
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
              const isScout = p === 'scout';
              const accent = stage.key === 'retrieve' || stage.key === 'execute' || stage.key === 'context';
              const lines = wrapToLines(text, 36);
              return (
                <g key={`cell-${p}-${stage.key}`}>
                  <rect
                    x={x}
                    y={y}
                    width={colWidth}
                    height={rowHeight}
                    rx={6}
                    fill={isScout ? theme.fill.secondary : theme.bg.elevated}
                    stroke={accent ? theme.accent.primary : theme.stroke.primary}
                    strokeWidth={accent ? 1.25 : 1}
                  />
                  {lines.map((line, lidx) => (
                    <text
                      key={lidx}
                      x={x + 10}
                      y={y + 18 + lidx * 14}
                      fontSize={11}
                      fill={theme.text.primary}
                      style={{ fontFamily: 'inherit' }}
                    >
                      {line}
                    </text>
                  ))}
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

const scoutArchPillars = [
  {
    title: 'Data Retrieval',
    body: 'All data via FHIR. Notes, diagnostic reports, pathology, labs, vitals, ordered meds, vaccinations, demographics, encounter history, allergies. Pre-fetched per patient to reduce time-to-first-token.',
  },
  {
    title: 'Orchestration & Tool Calling',
    body: 'LLM orchestrator plans task and routes via fast-path (note-only) or slow-path (multi-tool). Subagents per data domain handle retrieval; each one preserves the unique IDs of accessed records.',
  },
  {
    title: 'Answer + Evidence Cards',
    body: 'Final answer composed with citations on every claim. Evidence cards display the source span used for each citation. Guardrails + safety checks applied at answer time. All interactions logged per internal policy.',
  },
];

const evidenceTable = [
  ['Time to completion', '37.6% reduction', 'Geometric-mean ratio 0.624 (95% CI 0.565–0.689), p<0.001; mixed-effects model'],
  ['NASA-TLX raw', '−8.74 points', '95% CI −12.0 to −5.46, adjusted p<0.001 (largest drops in mental demand, effort, temporal demand)'],
  ['Accuracy (0–10)', '+0.20 (NI met, not superior)', 'Lower-bound CI exceeds −0.5 NI margin, p=0.325; rubric scored by domain-expert physicians'],
  ['Completeness (0–10)', '+0.84 (NI + superior)', '95% CI 0.44 to 1.24, p<0.001; only domain that exceeded zero by prespecified test'],
  ['Relevance (0–10)', '+0.05 (NI met, not superior)', 'CI −0.33 to 0.43, p=0.879'],
  ['Pilot scale', '6,641 queries / 3 mo', '200+ users, 20+ specialties; 70 weekly active users by end of pilot'],
  ['Auto-monitoring', '0.38 hallucinations + 0.34 inaccuracies / output', 'Modified VeriFact + GPT-4.1 judge; 67% of outputs had neither; none classified as moderate-or-worse harm'],
  [
    'LLM-as-judge fidelity',
    '11 of 17 "errors" actually supported (5-patient sample)',
    'Manual adjudication on 187 claims confirmed all 170 "supported" labels but reversed 11 of 17 "unsupported" labels — high false-positive rate from the judge',
  ],
];

const alignDivergeRows = [
  [
    'Citation-first design',
    'Foundational; every claim has cited source span',
    'Foundational; structured JSON output with chart-record citations',
    'Implementation-defined',
    'Implicit (SQL preview shows the executed query, not source rows)',
  ],
  [
    'Agentic multi-step orchestration',
    'Yes; orchestrator + per-domain subagents; fast/slow-path routing',
    'Single retrieval pipeline (config-selectable: embedding / lucene / hybrid / ES)',
    'Agent-team scaffolding (multi-agent orchestration in scope)',
    'A2A router → agents → MCP; multi-agent E2E smoke',
  ],
  [
    'PHI in LLM context',
    'Yes — OpenAI GPT via Azure ZDR with BAA',
    'Yes — but local-first (embedded llama-server) keeps prompts on box; remote endpoint optional',
    'Implementation-defined',
    'No PHI sent to LLM in FHIR POC path; FHIR resources are read-only; LocalPHI mode (full record in context) deferred',
  ],
  [
    'Provider strategy',
    'Single provider family (OpenAI GPT via Azure)',
    'Embedded LLM by default; remote OpenAI-compat optional',
    'Provider unspecified in public docs',
    'Provider-portable by design (LM Studio + Gemini abstraction)',
  ],
  [
    'Retrieval substrate',
    'FHIR resources + uploaded PDFs',
    'Serialized text + dense embeddings + Lucene/RRF over OpenMRS data',
    'OpenMRS data via dialogue orchestration',
    'Allowlisted relational schema (read-only DB user)',
  ],
  [
    'Conversational vs single-shot',
    'Single-shot per task; richer "set context" controls',
    'Single-shot per query; structured answer',
    'Multi-turn dialogue, role-conditioned',
    'Single-shot SQL generation w/ user review',
  ],
  [
    'Resource-constrained operability',
    'No — designed for cloud LLM + Azure tenancy',
    'Yes — embedded LLM is a design baseline; resource-poor sites are explicit target',
    'Unknown',
    'Possible — depends on provider config',
  ],
  [
    'Open vs closed source',
    'Closed institutional product; preprint + arXiv code repo for power-sim only',
    'Open source (MPL 2.0)',
    'Open source',
    'Open source',
  ],
];

const principleMappingRows = [
  [
    'I. Real Production Paths',
    'Scout deployed in real Duke Health workflows; RCT used real patient charts (de-identified during eval); pilot used live tool with real clinical staff',
    'Validates the constitution\'s premise: trial-grade evidence emerges only from real-path validation, not synthetic harnesses. Apply Scout\'s evaluator-blinded crossover pattern to chartsearchai when 2.8 demo-data path is ready.',
  ],
  [
    'II. Deterministic Reviewed Transforms',
    'Scout\'s pillar-2 "gold-standard dataset" is a curated, versioned, expert-adjudicated regression corpus — exactly the deterministic review surface the harness mandates',
    'Treat the gold-standard dataset as the eval-side analog of "accepted mappings live in code". Promotion path: clinician adjudication → curated case → version-pinned regression set.',
  ],
  [
    'III. Record-Level Evidence',
    'Scout\'s evidence cards expose the cited span; manual review found false-positive judge labels precisely because the cited spans were inspectable',
    'The harness already requires "rationale-bearing evidence". Scout shows what record-level evidence looks like in production. chartsearchai\'s structured-JSON citations and querystore document IDs are the corresponding pattern.',
  ],
  [
    'IV. Metadata, Provenance, and Traceability',
    'Scout logs every interaction per internal policy; preserves unique data-element IDs through subagent calls into final answer',
    'Adopt the same shape: agent invocation → tool/subagent span → cited record IDs → response event. The cross-project run-manifest already targets this; Scout confirms it works at production scale.',
  ],
  [
    'V. Tests Define Behavior',
    'Scout\'s RCT used 7 specialties / 200 cases / 1 evaluator per use case (limitation); pilot covered 18 task categories across 6,641 queries',
    'Diversity is built into the RCT design. The harness should require ≥2 evaluators per use case and span the OpenMRS 18-question set + at least one analog of each Scout pilot category that maps to OpenMRS scope.',
  ],
];

const threePillarRows = [
  [
    'Pillar 1 — Clinical Expert Review',
    'Domain-expert physicians manually adjudicate outputs for new use cases or sampled production data; 11-pt rubrics for accuracy, completeness, relevance with explicit qualitative tier definitions',
    'Maps to the harness\'s "human review" surface. chartsearchai already has clinician adjudication planned (P6). Adopt Scout\'s 11-pt rubric verbatim as a starting point.',
  ],
  [
    'Pillar 2 — Gold-Standard Dataset',
    'Curated, versioned corpus of adjudicated cases used for regression testing across system changes (model, prompt, retrieval)',
    'This is the deterministic-eval analog of the constitution\'s mapping policy. Promote adjudicated cases into a versioned dataset under datasets/eval/ instead of treating them as ephemeral runs.',
  ],
  [
    'Pillar 3 — LLM-as-Judge',
    'Modified VeriFact + GPT-4.1 judge for periodic and as-needed monitoring (post model upgrade, prompt change). Found 0.38 hallucinations + 0.34 inaccuracies per output across 70 RCT outputs',
    'CRITICAL: 11 of 17 "errors" the judge flagged were actually supported by the chart on manual review. Use LLM-as-judge as a screening signal calibrated against the gold-standard set, never as a sole gate.',
  ],
];

const chartsearchaiActions = [
  'Adopt Scout\'s 11-point accuracy/completeness/relevance rubric as the human-adjudication surface for the 485 enriched retrieval cases. The qualitative tier definitions ("Very Good = 8" etc.) give reviewers a concrete shared vocabulary.',
  'Plan a randomized evaluator-blinded crossover trial as the M2 milestone for chartsearchai once 2.8 demo-data is wired through. Borrow Scout\'s power-simulation methodology (link in Appendix F of the preprint).',
  'Carry the LLM-as-judge false-positive lesson into PromptInjectionEvalTest and AbsentDataEvalTest design — periodic human spot-checks on a sampled subset of "judge-flagged" cases.',
  'Map the OpenMRS 18-question set against Scout\'s 18 pilot task categories (Clinical Summary, Point-of-Care, Temporal Pattern, etc.) to test category coverage. ~54% of Scout queries are clinical summaries — confirm OpenMRS questions span beyond that single category.',
  'Add NASA-TLX (raw + subscales, excluding physical demand) to clinician-evaluation runbooks. The instrument is open and validated; Scout shows the effect size to expect (~−9 points raw).',
];

const chatbotActions = [
  'Use Scout\'s task-categorization prompt (Appendix K) to classify any logged conversational queries into the same 18-category taxonomy; this gives the chatbot a defensible eval scope without inventing primitives.',
  'Adapt Scout\'s 3-pillar framework to a multi-turn world: gold-standard cases become annotated dialogue traces (with role tags) instead of single Q→A pairs.',
  'Define a role-aware abstention contract — Scout doesn\'t need this (single role) but the patient/doctor split makes it the chatbot\'s most distinctive risk surface.',
  'Treat Scout\'s "performance subscale slightly worse despite quality non-inferior" finding as a warning: dialog interfaces are even more susceptible to perceived-trust gaps. Plan a longitudinal study, not a one-shot evaluation.',
];

const catalystActions = [
  'The sidecar report/analytics portal (M10) directly mirrors Scout\'s evidence-card presentation: FHIR-resource citations serve the same verification role as Scout\'s span-level citations. Design evidence cards per resource type (Observation, DiagnosticReport, ServiceRequest) with resource ID, display text, and date.',
  'Scout\'s fast/slow-path orchestrator pattern still applies: single-resource lookups (one Observation) route to a one-shot path; multi-resource "trend" queries (all Observations for a patient over 90 days) route through the multi-agent MCP path. Add routing decision to the events.jsonl trace.',
  'Add NASA-TLX to lab-tech evaluation of the sidecar UI once five canonical questions are answered end-to-end. Scout demonstrates workload reduction is independently measurable; the lab-timeline and evidence-card layout directly address the charting burden Scout measured.',
  'Adopt LLM-as-judge calibration discipline: any automated FHIR-grounded answer scorer (resource ID present, flag correct, date matches) must be benchmarked against a human-adjudicated gold subset before being trusted for regression gating.',
];

const usageCategoryRows = [
  ['Clinical Summary and Multi-Chart Review', '3,564', '54%', 'Highest demand by far — comprehensive summaries dominate'],
  ['Point-of-Care Information Retrieval', '2,043', '31%', 'Quick lookups; fast-path orchestration justified by volume'],
  ['Temporal Pattern Analysis', '1,375', '21%', 'Trend reasoning over time; benefits most from multi-step orchestration'],
  ['Registries and Forms', '1,110', '17%', 'Templated outputs — the use case Scout calls out as 10× more time-saving than the trial showed'],
  ['Clinical Reasoning and Decision Support', '567', '9%', 'Lower volume but high stakes; needs strongest provenance'],
  ['Long-tail task-focus categories', '32–182 each', '<3% each', 'Consults/handoffs, quality/safety, admissions, discharge, trials, preventive care'],
];

const privacyContrastRows = [
  [
    'Scout',
    'OpenAI GPT family via Microsoft Azure with Zero Data Retention + BAA',
    'PHI flows to LLM by design',
    'Requires enterprise Azure tenancy + signed BAA; closed institutional control plane',
    'Aspirational evidence anchor, not a transferrable architecture for OpenMRS deployments',
  ],
  [
    'chartsearchai',
    'Embedded llama-server (default) or remote OpenAI-compat endpoint',
    'PHI stays inside OpenMRS module boundary by default; local LLM keeps prompts on box',
    'Resource-poor sites are the explicit design baseline',
    'Architecturally appropriate for OpenMRS distribution; the local-first stance is a differentiator',
  ],
  [
    'openmrs_chatbot',
    'Provider unspecified in public docs',
    'Implementation-defined',
    'Unknown — need explicit declaration before deployment review',
    'Privacy stance is the most important undeclared contract',
  ],
  [
    'Catalyst',
    'LM Studio or Gemini via provider abstraction',
    'No PHI in LLM context — allowlist excludes PHI tables; only schema is sent',
    'Provider-portable by design; works in cloud or local',
    'Strongest structural privacy stance of the four',
  ],
];

const limitationsRows = [
  [
    'Single academic health system',
    'Scout RCT ran at Duke only; the team explicitly flags external validation as future work',
    'OpenMRS deployments span many resource, connectivity, workflow, and governance contexts — assume Scout\'s effect sizes are upper bounds, not transferable estimates',
  ],
  [
    'Single evaluator per use case',
    'Each use-case author also evaluated their own use case — chosen for domain familiarity but acknowledged as a limitation',
    'The harness should require ≥2 evaluators per use case and report inter-rater agreement on at least the accuracy domain',
  ],
  [
    'LLM-as-judge sensitivity',
    'Modified VeriFact + GPT-4.1 had a notable false-positive rate (11/17 in a 5-patient sample); flagged supported claims as unsupported',
    'Never sign off purely on automated eval. The harness\'s "tests define behavior" principle covers this; Scout provides the empirical data point.',
  ],
  [
    'Sustained-use trust gap',
    'Participants rated their perceived performance slightly lower with Scout despite non-inferior quality — verification trust takes time',
    'Plan longitudinal evaluation when chartsearchai or chatbot reach pilot scale; one-shot evals miss the trust-evolution curve',
  ],
  [
    'Closed source + closed eval data',
    'Only the power-simulation R code is public; production code, prompts, and gold-standard set are not',
    'OpenMRS-side projects can publish what Scout cannot — turn open-source eval datasets into a community contribution',
  ],
];

const sourceRows = [
  [
    <Link href="https://dihi.org/scout/">DIHI Scout product page</Link>,
    'Product framing: 4-step UX (MRN → context → question → results in 1–3 min), use cases, roadmap',
    'Use as the externally-visible claim baseline; cross-check against the preprint for what is actually measured',
  ],
  [
    <Link href="https://dihi.org/project/scout/">Scout RCT and pilot in brief (DIHI)</Link>,
    'Project background: information-overload framing, "pajama time" stat (4.23 hrs/wk avg, 13% report 10+ hrs/wk), study design overview',
    'Reference for the problem-side framing that should anchor the harness\'s OpenMRS-side narrative',
  ],
  [
    <Link href="https://dihi.org/wp-content/uploads/2026/03/scout_preprint.pdf">Scout preprint (PDF, March 2026)</Link>,
    'Full RCT methodology + appendices (technical details, use cases, NASA-TLX form, rubrics, power simulation, hallucination prompts, sensitivity analysis)',
    'Primary reference for evaluation methodology; copy rubrics + LLM-as-judge prompts directly into the harness eval surface',
  ],
  [
    <Link href="https://scirate.com/arxiv/2604.26953">arXiv listing 2604.26953</Link>,
    'Citable abstract; author list; submission and publication metadata',
    'Use for citations in PCCP records, plan.md, and any harness publication',
  ],
  [
    'Scout power-simulation code availability statement',
    'Appendix F says power-simulation code is provided, but the public GitHub URL was not resolvable from available web results during this review',
    'Do not depend on that repository link until verified; the preprint text still contains enough model specification to reproduce the power-simulation design',
  ],
  [
    <Link href="https://arxiv.org/abs/2501.16672">VeriFact (arXiv 2501.16672)</Link>,
    'LLM-as-judge framework Scout adapted for automated quality monitoring',
    'Pre-validated baseline for the harness\'s automated-eval pillar; upgrade path beyond ad-hoc judge prompts',
  ],
  [
    <Link href="https://hl7.org/fhir/">FHIR R5</Link>,
    'Scout\'s exclusive retrieval substrate; defines the resource shapes Scout consumes',
    'Cross-walk for chartsearchai\'s per-resource serializers and querystore\'s document shape',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-chartsearchai">openmrs-module-chartsearchai</Link>,
    'OpenMRS-side comparator; embedded chart-QA architecture',
    'Direct apply: 11-pt rubric, NASA-TLX, randomized crossover design when 2.8 demo-data is wired through',
  ],
  [
    <Link href="https://github.com/openmrs/openmrs-module-querystore">openmrs-module-querystore</Link>,
    'CQRS read-store extracted from chartsearchai; document shape = text + embedding + structured metadata',
    'Reference: querystore\'s per-type indices and labeled-prose serialization are the OpenMRS-native analog of Scout\'s FHIR-then-spans pattern',
  ],
  [
    <Link href="https://uwdigi.atlassian.net/wiki/spaces/OMRSAI/pages/1302790145">OpenMRS AI Clinical Questions (18-question set)</Link>,
    'Canonical eval scope for chartsearchai answers',
    'Map against Scout\'s 18 pilot task categories; report category coverage explicitly',
  ],
];

export default function ScoutComparativeAnalysis() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <Row gap={8} align="center">
          <Pill tone="info" active size="sm">External tool</Pill>
          <Pill tone="warning" active size="sm">Closed institutional · MVP++</Pill>
          <Pill tone="success" active size="sm">RCT-grade evidence</Pill>
        </Row>
        <H1>Scout (Duke DIHI) vs. the harness's three projects</H1>
        <Text tone="secondary">
          Deep analysis of <Link href="https://dihi.org/scout/">Scout</Link>, an LLM-based EHR search and synthesis platform
          built at Duke Institute for Health Innovation, and how it aligns with, diverges from, and informs the three
          early-prototype projects this harness validates: <Code>chartsearchai</Code>, <Code>openmrs_chatbot</Code>, and
          <Code> Catalyst (OpenELIS)</Code>. Comparative synthesis, not a buying guide.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="37.6%" label="Task-completion time reduction (Scout RCT, n=200 cases, 7 specialties)" tone="success" />
        <Stat value="−8.74" label="NASA-TLX raw points (lower = less workload), p<0.001" tone="success" />
        <Stat value="6,641" label="Pilot queries in 3 months (200+ users, 20+ specialties)" tone="info" />
        <Stat value="11/17" label={'LLM-judge "errors" actually supported on manual review — the load-bearing caveat'} tone="warning" />
      </Grid>

      <Callout tone="info" title="Working hypothesis">
        Scout is the closest published analog to <Code>chartsearchai</Code>'s exploration question, with structurally
        different choices on PHI handling, provider strategy, and openness. Treat Scout as <Text weight="semibold">
        an aspirational evidence anchor for evaluation methodology</Text>, not a transferrable architecture. The biggest
        yields for this harness are: (1) Scout's 3-pillar evaluation framework, (2) the 11-point clinical-rubric +
        NASA-TLX + non-inferiority pattern, and (3) the empirical LLM-as-judge fragility data that justifies the
        constitution's "LLM advisory only" stance.
      </Callout>

      <Divider />

      <H2>What Scout actually is</H2>
      <Text tone="secondary">
        Three architectural pillars per <Link href="https://dihi.org/wp-content/uploads/2026/03/scout_preprint.pdf">Appendix A of the preprint</Link>.
        All retrieval is via FHIR; all generation is OpenAI GPT family via Microsoft Azure with Zero Data Retention and
        a Business Associate Agreement, so PHI flows through the LLM by design.
      </Text>
      <Grid columns={3} gap={12}>
        {scoutArchPillars.map((p) => (
          <Card key={p.title}>
            <CardHeader>{p.title}</CardHeader>
            <CardBody>
              <Text>{p.body}</Text>
            </CardBody>
          </Card>
        ))}
      </Grid>

      <H3>Trial + pilot evidence</H3>
      <Table
        headers={['Outcome', 'Effect', 'Detail']}
        rows={evidenceTable}
        striped
      />
      <Text tone="secondary" size="small">
        Source: <Link href="https://scirate.com/arxiv/2604.26953">Gao et al., arXiv:2604.26953</Link>
        {' '}(prospective, randomized, evaluator-blinded, two-period crossover, IRB Pro00118622). Quality differences computed via mixed-effects model with patient case fixed effect and participant random intercept; non-inferiority margin = −0.5 on 11-pt scale.
      </Text>

      <Divider />

      <H2>Architecture matrix: Scout next to the three projects</H2>
      <Text tone="secondary">
        Same seven-stage frame used in <Code>cross-project-comparison.canvas.tsx</Code>, with Scout added as the
        external comparator. Accent borders mark the load-bearing stages where divergence is sharpest:
        context layer, retrieval, and execution boundary.
      </Text>
      <Card>
        <CardBody>
          <ArchitectureMatrixDiagram />
        </CardBody>
      </Card>

      <H2>Where Scout aligns and diverges per dimension</H2>
      <Table
        headers={['Dimension', 'Scout', 'chartsearchai', 'openmrs_chatbot', 'Catalyst']}
        rows={alignDivergeRows}
        striped
      />

      <Divider />

      <H2>Per-project alignment, divergence, and what to take</H2>
      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>chartsearchai</Pill>}>
            Closest structural sibling
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Aligns on:</Text> citation-first design philosophy, agentic orchestration with per-domain subagents, point-of-care chart QA as the primary use case, structured-output discipline.</Text>
              <Text><Text weight="semibold">Diverges on:</Text> retrieval substrate (FHIR vs serialized text + ONNX/Lucene), provider strategy (single Azure-GPT vs embedded/local-first), distribution model (closed institutional vs open OpenMRS module), PHI handling (Azure ZDR vs local-by-default).</Text>
              <Text><Text weight="semibold">Take from Scout:</Text> the 11-pt rubric verbatim, the randomized crossover design, NASA-TLX as a measured outcome, the gold-standard regression dataset pattern, the fast/slow-path orchestrator concept.</Text>
              <Text tone="secondary"><Text weight="semibold">Don't take:</Text> Azure-GPT-only provider stance — chartsearchai's resource-poor-sites baseline forecloses it; the closed-source eval dataset model.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="warning" active>openmrs_chatbot</Pill>}>
            Different shape, useful template
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Aligns on:</Text> free-text input, multi-step LLM orchestration over EHR data, agent-team scaffolding.</Text>
              <Text><Text weight="semibold">Diverges on:</Text> single-shot task vs multi-turn dialogue, single user role vs patient + doctor split, declared safety surface (Scout has guardrails + interaction logging; chatbot has neither documented).</Text>
              <Text><Text weight="semibold">Take from Scout:</Text> the 18-category task taxonomy (Appendix K) as eval-scope template, the 3-pillar framework adapted to dialogue traces, the "perceived performance gap" finding as motivation for longitudinal study design.</Text>
              <Text tone="secondary"><Text weight="semibold">Distinctive risk:</Text> role-aware abstention is the chatbot's signature challenge — Scout doesn't need it, so this work is novel.</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>Catalyst</Pill>}>
            Different primitive, shared discipline
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text><Text weight="semibold">Aligns on:</Text> agentic multi-step orchestration, tool-call discipline, verification-first design (evidence cards over FHIR resources vs Scout's span-level citations), separation of retrieval and generation.</Text>
              <Text><Text weight="semibold">Diverges on:</Text> FHIR resource retrieval vs Scout's free-text synthesis over notes; read-only FHIR vs PHI-via-Azure; dedicated report/analytics sidecar UI vs embedded modal.</Text>
              <Text><Text weight="semibold">Take from Scout:</Text> fast/slow-path routing for single vs multi-resource queries; LLM-as-judge calibration discipline; NASA-TLX for lab-tech workload on the sidecar UI; non-inferiority margins for RCT readiness.</Text>
              <Text tone="secondary"><Text weight="semibold">Catalyst's structural strength:</Text> FHIR-read-only + no-PHI-in-LLM-context is structurally stronger than Scout's Azure-hosted PHI pipeline. The harness should not erode this under "Scout does it differently" pressure.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>The 3-pillar evaluation framework: Scout's most portable contribution</H2>
      <Text tone="secondary">
        From <Text weight="semibold">Figure 8 of the preprint</Text>. Each pillar feeds the next: clinical experts adjudicate
        new cases → adjudicated cases enter the gold-standard dataset → the LLM-as-judge is calibrated against that dataset for
        ongoing monitoring. The harness's constitution describes the same shape in different language; Scout supplies the
        operational vocabulary.
      </Text>
      <Table
        headers={['Pillar', 'How Scout uses it', 'Implication for the harness']}
        rows={threePillarRows}
        striped
      />

      <Callout tone="warning" title="The load-bearing caveat: LLM-as-judge fragility">
        On a 5-patient sample of 187 claims, the GPT-4.1-based judge was perfect on supported claims (170/170) but
        false-positive on 11 of 17 unsupported claims. Multiple failure modes: judge missed evidence Scout had correctly
        cited; judge re-interpreted Scout's synthesized phrasing as inaccurate; judge flagged irrelevant omissions. This is
        the empirical data point that justifies the harness's <Text weight="semibold">"LLM analysis is advisory, accepted
        behavior lives in reviewed code"</Text> stance, extended to evaluators, not just mappers.
      </Callout>

      <H2>Constitution alignment: what Scout validates and what it pressures</H2>
      <Table
        headers={['Constitution principle', 'Scout evidence', 'Implication']}
        rows={principleMappingRows}
        striped
      />

      <Divider />

      <H2>Scout's pilot usage map: real demand signals for OpenMRS-side eval scoping</H2>
      <Text tone="secondary">
        Scout categorized 6,641 pilot queries into 18 paper-reported categories; Appendix K also shows a 20-category
        classification prompt structure (11 primary + 9 subgroups). The distribution exposes which
        clinical workflows actually drive LLM-EHR demand at a major academic center. <Text weight="semibold">Use this
        distribution to test eval-scope coverage</Text> for the OpenMRS 18-question set: if the OpenMRS set is concentrated in
        the same buckets, both projects are exploring the same demand surface; gaps point to under-covered categories.
      </Text>
      <Table
        headers={['Category', 'Queries (n)', '% of total*', 'Implication']}
        rows={usageCategoryRows}
        striped
      />
      <Text tone="secondary" size="small">
        * Categories are not mutually exclusive (each query may carry up to 3 labels), so percentages sum to more than 100%.
        Source: Table 4, Scout preprint.
      </Text>

      <Divider />

      <H2>Privacy stance contrast — the structural difference that matters most</H2>
      <Text tone="secondary">
        Scout's choice to send PHI to OpenAI GPT via Azure ZDR + BAA is enabled by Duke Health's enterprise tenancy. That
        choice is <Text weight="semibold">not available</Text> to most OpenMRS deployments. Reading Scout's results without
        this context invites a category error: Scout's effect sizes are not transferable on the back of a different privacy
        architecture.
      </Text>
      <Table
        headers={['Project', 'Provider stance', 'PHI in LLM context', 'Operational requirement', 'Strategic position']}
        rows={privacyContrastRows}
        striped
      />

      <Divider />

      <H2>Concrete actions per project</H2>
      <Grid columns="1fr 1fr 1fr" gap={14}>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>chartsearchai</Pill>}>
            Embedded chart QA
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {chartsearchaiActions.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="warning" active>openmrs_chatbot</Pill>}>
            Conversational chat
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {chatbotActions.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill size="sm" tone="info" active>Catalyst</Pill>}>
            FHIR sidecar lab
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              {catalystActions.map((a, i) => (
                <Text key={i}>• {a}</Text>
              ))}
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H2>Limitations of Scout to internalize before importing patterns</H2>
      <Text tone="secondary">
        Scout's authors flag these themselves; the harness should preserve them when borrowing methodology so we don't import
        Scout's effect-size claims along with the techniques.
      </Text>
      <Table
        headers={['Limitation', 'What Scout reports', 'What the harness should do']}
        rows={limitationsRows}
        striped
      />

      <Divider />

      <H2>Synthesis</H2>
      <Grid columns="1.2fr 1fr" gap={16}>
        <Stack gap={8}>
          <H3>What Scout adds to the harness's evidence base</H3>
          <Text>
            Until Scout, the harness was anchored against research-grade benchmarks (CLINSQL, EHR-ChatQA, PhysicianBench,
            LiveClin) and on the OpenMRS-side comparator set. Scout adds a <Text weight="semibold">published
            randomized crossover RCT</Text> of an LLM-EHR search-and-synthesis tool with non-inferior accuracy/completeness/relevance
            and a ~40% time saving. That is now the production-side reference effect size for what an MVP-level chart-QA
            tool can deliver against blinded expert adjudication.
          </Text>
          <Text>
            For chartsearchai specifically, Scout demonstrates that the embedded-EMR chart-QA exploration is well-aligned
            with proven clinical demand: more than half of Scout's pilot queries are clinical summaries — exactly
            chartsearchai's primary use case. The harness can stop hedging on whether the use case is real.
          </Text>
          <Text>
            For openmrs_chatbot and Catalyst, Scout supplies validated <Text weight="semibold">evaluation primitives</Text>
            (rubrics, NASA-TLX, non-inferiority margins, 3-pillar monitoring) that don't need to be re-invented. The
            architectures stay project-specific; the eval surface converges.
          </Text>
        </Stack>
        <Stack gap={8}>
          <H3>What Scout does <em>not</em> change</H3>
          <Text>The OpenMRS projects remain open-source and resource-poor-site-aware; Scout is closed and cloud-native.</Text>
          <Text>The constitution's PHI-in-context concerns are unaffected; Scout's permissive stance is institutional, not architectural.</Text>
          <Text>chartsearchai's embedded-llama-server design and Catalyst's no-PHI-in-context allowlist remain the structurally appropriate stances.</Text>
          <Text>External validation across OpenMRS deployment contexts is still required regardless of how strong Scout's Duke-only RCT is.</Text>
        </Stack>
      </Grid>

      <Callout tone="success" title="One concrete next step">
        Open a new PCCP-style change record proposing the harness adopt Scout's 3-pillar framework with the
        following named surfaces under <Code>evals/</Code>: <Code>evals/clinical_review/</Code> for adjudicated cases,
        <Code> datasets/eval/gold/</Code> for the versioned regression corpus, and <Code>evals/llm_judge/</Code>
        for calibrated automated monitoring. Cite Scout's preprint and the 11/17 false-positive finding as the
        rationale for never gating on Pillar 3 alone.
      </Callout>

      <H2>Open questions worth pursuing</H2>
      <Stack gap={6}>
        <Text>• Will Scout's 11-point rubric tier definitions transfer to a chartsearchai context where the answer is JSON-structured rather than free-text? Likely yes, but worth piloting on a sample.</Text>
        <Text>• Can the OpenMRS 18-question set be scored against the same 3-domain rubric Scout uses, so chartsearchai and Scout become directly comparable on quality?</Text>
        <Text>• Does the Scout team publish their gold-standard dataset shape (even abstracted)? If yes, the harness can adopt the same record schema. If no, the harness has an opportunity to publish a community-friendly version.</Text>
        <Text>• What is the right OpenMRS analog of "pajama time" — i.e., what burden metric beyond NASA-TLX captures the clinical-staff cost in the LMIC contexts where OpenMRS lives?</Text>
        <Text>• Is there appetite at DIHI for a joint Scout × OpenMRS chart-search eval session? The 18-category taxonomy + the OpenMRS 18-question set is a natural shared artifact.</Text>
      </Stack>

      <H2>Sources</H2>
      <Table
        headers={['Source', 'What it contains', 'How it is used here']}
        rows={sourceRows}
        striped
      />
    </Stack>
  );
}
