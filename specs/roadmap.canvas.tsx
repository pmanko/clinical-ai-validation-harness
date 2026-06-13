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

type LaneId = "foundation" | "openmrs" | "safety" | "expansion" | "openelis";

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
  openelis: {
    label: "OpenELIS / Catalyst",
    shortLabel: "Catalyst",
    tone: "info",
    purpose: "FHIR-first lab AI sidecar over OpenELIS Global 2 — resource-grounded answers and report/analytics UI.",
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
    title: "Validation spine + metadata contract (006 MVP)",
    slug: "006-validation-harness-mvp",
    lane: "foundation",
    purpose:
      "Standardize run_manifest.json + events.jsonl across lanes and operationalize them as a scenario x backend comparison with human adjudication. Shipped as the 006 validation-harness MVP (runner/client/report + feedback form, live-run validated). NOTE: judge.jsonl + the clinical-answer-scoring skill, validator confidence, the run-index, and the live dashboard postdate the original spec — lane L3 reconciles 006 to as-built and closes M2-F.1 (SC-015). The phantom slug 003 never existed; this is the real spine.",
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
    unlocks: ["M4", "M5", "M6", "M8", "M9", "F005", "F009"],
  },
  {
    id: "M4",
    num: "M4",
    title: "OpenMRS retrieval evaluation",
    slug: "010-openmrs-retrieval-eval",
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
    slug: "012-answer-citation-abstention-eval",
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
    slug: "013-safety-red-team-eval",
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
    slug: "014-clinician-governance-review",
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
    slug: "015-querystore-parity-testbed",
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
    slug: "016-cross-project-validation-expansion",
    lane: "expansion",
    purpose:
      "Apply the shared validation spine to openmrs_chatbot without inventing a separate harness.",
    scope: [
      "openmrs_chatbot: role-aware chat, multi-turn grounding, and agent handoff traces.",
      "Shared metadata and review records across projects.",
    ],
    evidence: [
      "Expansion cases reuse M2/M3 contracts and can be compared across projects.",
      "Project-specific risks are captured without fragmenting the harness model.",
    ],
    needs: ["M2", "M3", "M6", "M7"],
    unlocks: [],
  },
  {
    id: "M10",
    num: "M10",
    title: "Catalyst FHIR sidecar POC",
    slug: "011-catalyst-fhir-sidecar-poc",
    lane: "openelis",
    purpose:
      "Stand up a Catalyst-owned FHIR-first sidecar over OE2's HAPI FHIR server, answering five canonical lab-data questions with resource-grounded citations and a Scout-style report/analytics UI.",
    scope: [
      "catalyst-mcp FHIR tools (search_patient, get_observations, get_service_requests, get_diagnostic_reports, build_patient_lab_timeline).",
      "HAPI-first answer path; embedded-FHIR parity probe with gap log.",
      "Catalyst sidecar UI: question input, cited answers, evidence cards, lab-result table, lab timeline.",
      "Sidecar response contract (answer + facts[] + citations[] + uiBlocks[]).",
      "Harness adapter smoke: OE2 up → Catalyst up → five canonical questions → emit run_manifest.json + events.jsonl.",
    ],
    evidence: [
      "All five canonical questions answered with FHIR resource IDs cited and resolvable in OE2.",
      "Parity probe records HAPI vs embedded divergences in the OE2 FHIR gap log.",
    ],
    needs: ["M0", "M2", "M3"],
    unlocks: [],
  },
  {
    id: "F005",
    num: "F005",
    title: "med-agent-hub bridge",
    slug: "005-med-agent-hub-bridge",
    lane: "openmrs",
    purpose:
      "Shipped (as-built): integrate pmanko/med-agent-hub as a harness submodule serving chartsearchai over OpenAI-compat via an in-process ReAct loop over typed tools (medical_expert + kb_search). chartsearchai code untouched; two global-property flips switch the backend. Carries the shipped F005 work — chartsearchai P1 model-switch + B4 Carbon picker + WARM model warmup — plus the P3 Tier-1 KB.",
    scope: [
      "Submodule at targets/med-agent-hub/, pinned to med-agent-hub `main` (the harness-integration buffer was retired 2026-06-11 — the hub is our own repo, not a fork; CI gates main directly).",
      "OpenAI-compat POST /v1/chat/completions and GET /v1/models on med-agent-hub.",
      "In-process ReAct loop (orchestrator/synthesizer over typed medical_expert + kb_search tools, MAX_TOOL_ITERATIONS=3) receives full messages[] (system + chart-prefix + priors + current); envelope bound only on the final synthesis call, with a fallback envelope.",
      "Containerized via a single uvicorn Docker image with stdout logs (no honcho/Procfile).",
      "Reaches LM Studio via host.docker.internal:host-gateway; mirrors chartsearchai backend pattern.",
    ],
    evidence: [
      "Three-turn referential chat against Zabella Halambe answers turn 2 referentially against turn 1's content, proving priors flow through the in-process ReAct loop to LM Studio.",
      "Per-turn latency captured for the bridge canvas (prefix-cache loss trade-off documented).",
    ],
    needs: ["M3"],
    unlocks: ["F008"],
  },
  {
    id: "F008",
    num: "F008",
    title: "Chartsearchai model gateway",
    slug: "008-chartsearchai-model-gateway",
    lane: "foundation",
    purpose:
      "New Python FastAPI service that sits between chartsearchai's RemoteLlmEngine and the real LLM providers. Generalizes the model picker to show classes of connections; normalizes per-provider /v1/models; holds provider credentials at the gateway boundary.",
    scope: [
      "Phase 0 (shipped on PR #15 — LM Studio /api/v1/models probe + 'LM Studio' sub-category header + per-entry loaded state + pre-load on select). Proves the wire-shape contract (additive provider + entries[] fields) and forward-compatibility with the picker UX.",
      "OpenAI-compat ingress (chartsearchai sees one URL; preserves response_format / stream / top_k / messages[] verbatim).",
      "Connection registry of providers grouped by class: local-runtime (LM Studio, Ollama, vLLM, llama.cpp), cloud-api (OpenAI, Anthropic, Gemini, Azure), agentic (med-agent-hub from F005).",
      "Provider-specific quirks (Anthropic /v1/messages adapter; claude-opus-4-7 top_k=1; per-provider SSE translation) encoded in gateway, not in chartsearchai.",
      "Picker UX generalized from flat /v1/models list to grouped/two-level view with class metadata.",
      "Backwards compatible: chartsearchai pointing direct at LM Studio (M3 posture) or direct at med-agent-hub (F005 posture) keeps working.",
    ],
    evidence: [
      "Wire-shape preservation verified by byte-identical chartsearchai parser output across providers.",
      "Provider API keys never present in chartsearchai's runtime properties, OpenMRS DB, OpenMRS logs, or chartsearchai → gateway wire traffic.",
    ],
    needs: ["M3", "F005"],
    unlocks: ["F009"],
  },
  {
    id: "F009",
    num: "F009",
    title: "Clinical knowledge base",
    slug: "009-clinical-knowledge-base",
    lane: "foundation",
    purpose:
      "Dedicated host-agnostic Python service (REST + MCP) providing general clinical KB plus a DB-curated contextualized layer for lower-power local models. Orthogonal to chartsearchai's per-patient retrieval; stacks at the prompt.",
    scope: [
      "Hybrid sparse+dense retrieval (BM25 + RRF, cross-encoder rerank, section-aware chunking, explicit abstention) per MedRAG/MIRAGE methodology.",
      "Openly-licensed reference corpus (WHO IMCI/EML/ANC, MSF, RxNorm essentials, immunization schedules).",
      "Separable curation worker that reads deployment OpenMRS DB as aggregates only; LLM-assisted concept-set selection (CUICurate-inspired); YAML curation artifact for mandatory human review.",
      "First consumer: chartsearchai's LlmProvider.search via one optional kbContext parameter.",
      "Second consumer (once F008 lands): gateway-injected KB-augmented provider class.",
    ],
    evidence: [
      "Citation/grounding eval: ≥10 pp accuracy lift over no-KB baseline at unchanged refusal-on-unanswerable rate, on a held-out MIRAGE-style subset.",
      "Curation artifact PHI-free (asserted programmatically); review_status + human_reviewer captured per constitution principle II.",
    ],
    needs: ["M1", "M3"],
    unlocks: [],
  },
  {
    id: "F007",
    num: "F007",
    title: "File-based LLM config overrides",
    slug: "007-llm-config-overrides",
    lane: "foundation",
    purpose:
      "Make chartsearchai's LLM system prompt + request params (temperature, max_tokens, …) overridable via an optional operator-editable file pair (JSON config + prompt .md), read at call-time, layered over today's defaults, no rebuild/restart. Enabler for rapid validation iteration; feeds the 006 MVP (M2).",
    scope: [
      "Optional file pair read at call-time; works unchanged when absent (today: system prompt is a DB-string GP, params are hardcoded in RemoteLlmEngine/LocalLlmEngine.buildRequestBody).",
      "JSON via Jackson (already on the classpath); no new YAML parser.",
      "chartsearchai backend change — ships via the paired-PR fork model (branch on pmanko → PR openmrs:main → consolidate into harness-integration).",
    ],
    evidence: [
      "Override file present → prompt/params change with no restart; absent → byte-identical to current defaults.",
    ],
    needs: ["M3"],
    unlocks: ["M2"],
  },
  {
    id: "F010",
    num: "F010",
    title: "med-agent-hub MCP-ification",
    slug: "017-med-agent-hub-mcp-tools",
    lane: "foundation",
    purpose:
      "Replace the hub's hand-rolled tool dispatch + the homegrown fake-'MCP' layer with one valid FastMCP server mounted at /mcp. kb_search becomes a real MCP tool; medical_expert stays an in-process role; the team consumes the server via an in-memory client. Extensible (FHIR/Spark drop in later) and a product surface other MCP clients can consume. Locked plan: ~/.claude/plans/keen-jingling-muffin.md; executing as lane L1.",
    scope: [
      "FastMCP server (server/mcp/ rebuilt) registering kb_search with @mcp.tool; team-facing in-memory client converts MCP tool schema → OpenAI tool defs.",
      "Delete the homegrown server/mcp/ base + the unwired A2A clinical tools (FHIR/Spark/appointments/medical_search) and dead modules (sdk_agents, agent_configs, llm_clients, explore_a2a.py, launch_a2a_agents.py).",
      "Drop deps that only served deleted code (a2a-sdk, jsonschema, spark/duckdb extras); add fastmcp.",
    ],
    evidence: [
      "tests/test_bridge.py (/v1 OpenAI-compat contract) stays green at every commit while the tool layer underneath is replaced.",
      "Hub-boundary smoke before the harness pin bump: README /v1 curl with real models + a -validated level returns the confidence block + trace.jsonl grows.",
    ],
    needs: ["F005"],
    unlocks: ["F008"],
  },
];

// Active lanes — the in-flight sprint, richer than the milestone cards because
// each is meant to cold-start its own worktree + Claude session. Roadmap drives
// the WHAT/WHY of the program; these drive the HOW of the next three PRs.
type ActiveLane = {
  id: string;
  title: string;
  repo: string;
  branch: string;
  worktree: string;
  relatesTo: string;
  status: string;
  context: string;
  scope: string[];
  gate: string[];
  kickoff: string;
};

const activeLanes: ActiveLane[] = [
  {
    id: "L1",
    title: "med-agent-hub MCP-ification",
    repo: "pmanko/med-agent-hub — our own repo (pins main; the harness-integration buffer was retired 2026-06-11)",
    branch: "feat/real-mcp-tools (off origin/main @ ebdbb43)",
    worktree: "~/code/hub-wt-mcp",
    relatesTo:
      "Extends F005 and realizes the real-MCP tool layer F008 anticipates. Locked plan: ~/.claude/plans/keen-jingling-muffin.md.",
    status: "Ready — worktree created; hub-ci (unit-and-contract + docker-build) green on main.",
    context:
      "Replace the hand-rolled tool dispatch and the homegrown fake-'MCP' layer with one valid FastMCP server mounted in the hub's FastAPI at /mcp. kb_search becomes a real MCP tool; medical_expert stays an in-process role (not a tool); the team consumes the server via an in-memory client (no network hop). Tool surface is hub-global — levels keep choosing only models/prompts/validator.",
    scope: [
      "FastMCP server mounted at /mcp (streamable-HTTP for external clients); team consumes it in-memory.",
      "kb_search → real MCP tool; delete the homegrown server/mcp/ + the unwired A2A clinical tools (FHIR/Spark/appointments/medical_search, all mock).",
      "Delete legacy modules per the locked plan's deletion list: server/sdk_agents/, server/agent_configs/, server/llm_clients.py, explore_a2a.py, launch_a2a_agents.py.",
      "Sweep 5 pre-reboot origin branches (a2a-updates, doc-cleanup-update, feature/agenta, multiagent, rag-augment): quick triage, default delete.",
    ],
    gate: [
      "hub-ci green; tests/test_bridge.py (/v1 OpenAI-compat contract — the surface both chartsearchai and the harness consume) green at EVERY commit.",
      "Pin-bump gate (hub-boundary smoke): rebuild container → README /v1 curl with real local models + a -validated level returns the confidence block + trace.jsonl grows → THEN bump the harness pin (.gitmodules already tracks main).",
    ],
    kickoff:
      "Execute the approved MCP plan at ~/.claude/plans/keen-jingling-muffin.md in this worktree (med-agent-hub, branch feat/real-mcp-tools off origin/main). Red-first tests for the new MCP tool surface; tests/test_bridge.py (/v1 contract) must stay green throughout; delete the legacy A2A/fake-MCP modules per the plan's deletion list. First, sweep the 5 legacy origin branches per the quick-triage-default-delete rule. PR to hub main gated by hub-ci; after merge, rebuild the container and run the hub-boundary smoke (README /v1 curl with real models + -validated confidence block + trace.jsonl growth) before pushing the harness pin bump.",
  },
  {
    id: "L2",
    title: "Reports and human feedback",
    repo: "clinical-ai-validation-harness",
    branch: "feat/report-human-feedback (off main)",
    worktree: "~/code/harness-wt-report",
    relatesTo:
      "Amends feature 006 (validation-harness-mvp) report layer. Driven by reviewer (Ian) feedback; the human-feedback surface is the intake for the parked UCD work.",
    status: "Ready — worktree created and synced.",
    context:
      "The 006 report ships 0-10 rubric scores, a per-cell adjudication form, and a feedback.jsonl export with an optional FEEDBACK_ENDPOINT POST seam. Evolve it for real reviewers: clearer numbers, judgement shown in context, an explainer of what the 'AI team' is, and a split between the machine deep-dive and the human-feedback surface.",
    scope: [
      "Scores as percentages (not 0-10); per-scenario rubric judgement inline with each response (today it's the click-a-cell heatmap note).",
      "An 'AI team' explainer (tiers, roles, system prompts); the Unsafe Answers stat links to the flagged answers.",
      "Two-part report: a Claude-review deep-dive vs. a human-feedback view with answer ranking/annotation.",
      "Redesign the feedback.jsonl export for usability (web + repo research: eval-methodology-brief, Scout rubric); keep the no-backend default.",
      "Parity (decided): extract confidence-inversion rules + score->percentage formatting + labels into ONE shared module under harness/validate/ imported by both report.py and validate-dashboard.py, plus parity tests rendering one fixture through both (extend evals/validate/test_report_confidence.py).",
    ],
    gate: ["harness CI: pytest + diff-cover >=90% on changed lines; squash-only merge."],
    kickoff:
      "/speckit-specify Report evolution for human reviewers: convert scores to percentages, surface per-scenario rubric judgements inline with each response, add an AI-team explainer (tiers, roles, system prompts), link the Unsafe Answers stat to the flagged answers, split the report into a Claude-review deep-dive and a human-feedback view with answer ranking/annotation, and redesign the existing JSON feedback download for usability — grounded in web + repo research on what validation feedback to capture. Static hosting only. Parity is implemented as: a shared rules module under harness/validate/ imported by both report.py and validate-dashboard.py, plus parity tests rendering one fixture through both (extend evals/validate/test_report_confidence.py).",
  },
  {
    id: "L3",
    title: "Validation spine — specs/006 as-built + close M2-F.1",
    repo: "clinical-ai-validation-harness",
    branch: "docs/006-validation-spine-asbuilt (off main)",
    worktree: "~/code/harness-wt-spine",
    relatesTo:
      "Feature 006 IS the validation spine (the canvas's phantom M2/003 never materialized — see audit). Closes M2-F.1 / SC-015 deferred from feature 002.",
    status: "Ready — worktree created and synced.",
    context:
      "specs/006-validation-harness-mvp is 'in progress' since 2026-05-28 and stale: it defers an LLM-as-judge subsystem, but judge.jsonl + the clinical-answer-scoring skill shipped; validator confidence, the run-index, and the live dashboard all postdate it. Bring the spec to as-built and close the one substantive gap.",
    scope: [
      "Update 006 to as-built: reconcile its deferrals against what shipped (judge.jsonl + scoring skill, validator confidence, run-index, live dashboard).",
      "Execute M2-F.1 (SC-015): produce the four artifacts specs/002.../plan.md names — chartsearchai-live/{compose-up.log, indexer-warmup.json, search-response.json, citation-resolution.json} — against the running :8088 stack; every citation must resolve to a translated demo record.",
      "Fix the README slug-numbering note (says 006/007 are 'reserved' while the dirs exist with real content) and sweep stale spec statuses (006, 007).",
    ],
    gate: [
      "The four M2-F.1 artifacts exist under artifacts/<run>/chartsearchai-live/ and the citation-resolution check passes.",
      "POSTs to the live stack on :8088 served from the MAIN checkout — do not bring a second stack up from the worktree.",
    ],
    kickoff:
      "Update specs/006-validation-harness-mvp to as-built: reconcile its deferrals against what shipped (judge.jsonl + scoring skill, validator confidence, run-index, live dashboard); execute M2-F.1 by producing the four artifacts named in specs/002-openmrs-demo-data-2-8-remap/plan.md row M2-F.1 against the running :8088 stack (indexer warmup -> POST /ws/rest/v1/chartsearchai/search -> citation-resolution check, per SC-015); fix the README slug-numbering note; sweep stale spec statuses (006, 007).",
  },
];

const featureById = new Map(features.map((feature) => [feature.id, feature]));

// Single source of truth for delivery status, mirroring the README milestone
// table. Rendered as a pill on each card and a column in the compact reference,
// so status lives in data, not in prose that drifts.
type StatusTone = "info" | "neutral" | "warning" | "success";
const statusById: Record<string, { label: string; tone: StatusTone }> = {
  M0: { label: "Complete", tone: "success" },
  M1: { label: "Complete", tone: "success" },
  M2: { label: "In progress", tone: "warning" },
  M3: { label: "In progress", tone: "warning" },
  M4: { label: "Planned", tone: "neutral" },
  M5: { label: "Planned", tone: "neutral" },
  M6: { label: "Planned", tone: "neutral" },
  M7: { label: "Planned", tone: "neutral" },
  M8: { label: "Planned", tone: "neutral" },
  M9: { label: "Planned", tone: "neutral" },
  M10: { label: "Brief", tone: "info" },
  F005: { label: "Shipped", tone: "success" },
  F007: { label: "Planned", tone: "neutral" },
  F008: { label: "Phase 0 shipped", tone: "info" },
  F009: { label: "Brief", tone: "info" },
  F010: { label: "In progress (lane L1)", tone: "warning" },
};

const dependencyEdges: Array<{ from: string; to: string }> = features.flatMap((feature) =>
  feature.needs.map((need) => ({ from: need, to: feature.id })),
);

const laneFlows: Record<LaneId, string[]> = {
  foundation: ["M0", "M2", "M3", "F007", "F010", "F008", "F009"],
  openmrs: ["M1", "F005", "M4", "M5"],
  safety: ["M6", "M7"],
  expansion: ["M8", "M9"],
  openelis: ["M10"],
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
  ["M2", "M10"],
  ["M3", "M10"],
  ["M3", "F005"],
  ["F005", "F010"],
  ["F005", "F008"],
  ["F008", "M5"],
  ["F008", "F009"],
  ["M1", "F009"],
  ["M3", "F009"],
  ["F009", "M5"],
  ["F009", "M6"],
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
  [
    "M10 is Catalyst-lane, not expansion",
    "The Catalyst FHIR sidecar POC runs in its own openelis lane. It needs M0 (harness foundation), M2 (metadata contract), and M3 (real adapter boundaries) — not full M4/M5/M6. Spec Kit drives Phase 2 (spec/plan/tasks); implementation lands in Phase 3.",
  ],
  [
    "F005 (med-agent-hub bridge) unlocks the gateway slot",
    "Once med-agent-hub serves as a single OpenAI-compat endpoint chartsearchai talks to, F008 (model gateway) generalizes that posture across many provider classes — local-runtime, cloud-api, agentic. Wait for F005 cloud smoke green before starting F008 implementation. F008 absorbs med-agent-hub as one provider class among many.",
  ],
  [
    "F009 (clinical KB) does not block on F008",
    "KB integrates directly with chartsearchai's LlmProvider.search via one optional kbContext parameter; gateway is a likely second consumer. F009 does block on a pre-spec planning brief that resolves hosting + contextualization decisions — see specs/artifacts/planning/clinical-kb-brief.md.",
  ],
  [
    "M5/M6 evolve once F008 + F009 ship",
    "Answer/citation eval (M5) and safety/red-team eval (M6) gain new measurement axes once the gateway exposes per-provider-class metadata and the KB exposes citation/abstention discipline. Reserve room in M5/M6 designs for KB-on/off variants.",
  ],
  [
    "Slug numbering is non-monotonic by design",
    "The phantom slug 003 was never created — the validation spine landed as 006 (validation-harness MVP). Real slugs now: 006 = validation MVP (M2), 007 = llm-config-overrides (F007), 008/009 = the F008/F009 briefs, 017 = F010 (med-agent-hub MCP tools); M4 = 010, M5–M9 = 012–016, M10 = 011 (external refs cemented). Milestone/feature IDs (M0–M10, F005–F010) are the semantic anchor; slugs are filesystem identifiers, not strict order.",
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
    case "openelis":
      return theme.accent.primary;
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
  const laneHeight = 108;
  const leftLabelWidth = 150;
  const nodeWidth = 136;
  const nodeHeight = 44;
  const gap = 48;
  const maxLaneLen = Math.max(...laneIds.map((id) => laneFlows[id].length));
  const width = leftLabelWidth + maxLaneLen * (nodeWidth + gap) + 24;
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
      <CardHeader
        trailing={
          <Row gap={4}>
            <Pill size="sm" tone={statusById[feature.id]?.tone ?? "neutral"} active>
              {statusById[feature.id]?.label ?? "—"}
            </Pill>
            <Pill size="sm" tone={lane.tone} active>
              {lane.shortLabel}
            </Pill>
          </Row>
        }
      >
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

function ActiveLaneCard({ lane }: { lane: ActiveLane }) {
  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" tone="success" active>{lane.id}</Pill>}>
        {`${lane.id} - ${lane.title}`}
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <Text tone="secondary">{lane.context}</Text>
          <Stack gap={3}>
            <Row gap={6} wrap>
              <Text size="small" tone="tertiary">Repo:</Text>
              <Text size="small" tone="secondary">{lane.repo}</Text>
            </Row>
            <Row gap={6} wrap>
              <Text size="small" tone="tertiary">Branch:</Text>
              <Code>{lane.branch}</Code>
            </Row>
            <Row gap={6} wrap>
              <Text size="small" tone="tertiary">Worktree:</Text>
              <Code>{lane.worktree}</Code>
            </Row>
            <Row gap={6} wrap>
              <Text size="small" tone="tertiary">Status:</Text>
              <Text size="small" tone="secondary">{lane.status}</Text>
            </Row>
          </Stack>
          <Divider />
          <Stack gap={4}>
            <Text size="small" weight="semibold">Relates to</Text>
            <Text size="small" tone="secondary">{lane.relatesTo}</Text>
          </Stack>
          <Stack gap={4}>
            <Text size="small" weight="semibold">Scope</Text>
            {lane.scope.map((item) => (
              <Text key={item} size="small" tone="secondary">- {item}</Text>
            ))}
          </Stack>
          <Stack gap={4}>
            <Text size="small" weight="semibold">Gate</Text>
            {lane.gate.map((item) => (
              <Text key={item} size="small" tone="secondary">- {item}</Text>
            ))}
          </Stack>
          <Callout tone="neutral" title="Kickoff prompt">
            <Text size="small">{lane.kickoff}</Text>
          </Callout>
        </Stack>
      </CardBody>
    </Card>
  );
}

const tableRows = features.map((feature) => [
  feature.num,
  feature.title,
  statusById[feature.id]?.label ?? "—",
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
    { foundation: 0, openmrs: 0, safety: 0, expansion: 0, openelis: 0 },
  );

  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>Validation Roadmap</H1>
        <Text tone="secondary">
          Planned validation work for the clinical-ai-validation-harness — organized by dependency, not strict execution order.
          Some milestones can run in parallel once their prerequisites are in place.
        </Text>
      </Stack>

      <Callout tone="info" title="In plain terms — what this project is">
        <Stack gap={8}>
          <Text>
            A test bench for early clinical AI. Clinics are starting to put AI assistants in front of patient data — to
            search a chart, answer a clinician's question, or read lab results. Before anyone relies on those answers we
            have to show they are correct, safe, and traceable back to the real record they came from. This harness runs
            realistic questions through the actual systems and grades the answers with evidence, not impressions.
          </Text>
          <Text size="small" weight="semibold">
            The landscape — what we validate
          </Text>
          <Text size="small" tone="secondary">
            - chartsearchai: the AI inside OpenMRS that searches and answers over one patient's chart.
          </Text>
          <Text size="small" tone="secondary">
            - med-agent-hub: a local "AI team" of small models (orchestrator, medical expert, synthesizer, validator)
            that can stand in for one large model, entirely on your own hardware.
          </Text>
          <Text size="small" tone="secondary">
            - Catalyst: lab-result AI over the OpenELIS lab system.
          </Text>
          <Text size="small" tone="secondary">
            - the harness: the shared bench that drives real questions through these on realistic data (a 5,284-patient
            demo corpus) and records graded, cited evidence.
          </Text>
          <Text size="small" weight="semibold">
            How the work is organized
          </Text>
          <Text size="small" tone="secondary">
            - Milestones (M0-M10, F005-F010, below) are the what and why, ordered by dependency.
          </Text>
          <Text size="small" tone="secondary">
            - Active Lanes (bottom of the page) are the how — the three workstreams in flight right now.
          </Text>
          <Text size="small" tone="secondary">
            - Constitutional gates are the bar every durable claim clears: real systems, reviewed data, and
            record-level evidence with rationale.
          </Text>
          <Text size="small" tone="tertiary">
            Everything below this primer is the detailed, grounded plan.
          </Text>
        </Stack>
      </Callout>

      <Grid columns={6} gap={16}>
        <Stat value={features.length} label="Planned feature specs" />
        <Stat value={laneCounts.foundation} label="Foundation" tone="info" />
        <Stat value={laneCounts.openmrs} label="OpenMRS corpus/eval" />
        <Stat value={laneCounts.safety} label="Safety/governance" tone="warning" />
        <Stat value={laneCounts.expansion} label="Expansion/migration" tone="success" />
        <Stat value={laneCounts.openelis} label="Catalyst/OpenELIS" tone="info" />
      </Grid>

      <Callout tone="info" title="Reading this roadmap">
        <Text>
          Milestone IDs (M0, M1 …) are planning labels for this harness — they are not OpenMRS version numbers or product releases.
          For plain-language names and a cross-reference to feature folders, see the <Code>README.md</Code> milestone table.
          Not building specs? Use the <Code>Validation research</Code> canvas (Start here → Validation research) for the evidence model and evaluation methodology.
        </Text>
      </Callout>

      <Callout tone="neutral" title="Where to start">
        <Text>
          Harness foundation (<Code>001</Code>, M0) and the OpenMRS demo-data remap (<Code>002</Code>, M1) are complete;
          real adapter entrypoints (<Code>004</Code>, M3) remain in progress. The current sprint is the three
          Active Lanes at the bottom of this page — L1 med-agent-hub MCP-ification (F010), L2 reports and human
          feedback (amends <Code>006</Code>), and L3 validation-spine as-built (<Code>006</Code>/M2, closes M2-F.1).
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
        headers={["#", "Title", "Status", "Lane", "Needs", "Unlocks", "Suggested Spec Slug"]}
        rows={tableRows}
        striped
      />

      <Divider />

      <H2>Active Lanes — Current Sprint</H2>
      <Text tone="secondary">
        The three in-flight workstreams, each running in its own git worktree and Claude session. These carry more
        operational detail than the milestone cards above because each is meant to cold-start a lane: repo, branch,
        worktree, scope, the gate that lets it merge, and a verbatim kickoff prompt. Lanes have disjoint file sets and
        merge independently. Source of truth for sequencing: the roadmap plan (squishy-bubbling-spindle).
      </Text>
      <Grid columns={1} gap={14}>
        {activeLanes.map((lane) => (
          <ActiveLaneCard key={lane.id} lane={lane} />
        ))}
      </Grid>
    </Stack>
  );
}
