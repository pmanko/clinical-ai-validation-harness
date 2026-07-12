import {
  Callout,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  Pill,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from 'cursor/canvas';

// Source of truth: targets/med-agent-hub/server/team.py (the live answer pipeline) as of run
// 65609a25-264d-4c79-8579-a0e5d167ba38, plus targets/med-agent-hub/server/temporal.py (the gate)
// and server/prompts/validation-answer.txt. Every layer below cites its team.py symbol + line.
// Purpose: see the WHOLE answer flow at once so we can decide what to SIMPLIFY — the quality
// machinery has grown into several overlapping LLM-judge layers, yet the one failure that shipped
// (a non-substantive "." answer) slipped through ALL of them. This canvas is the map for that cut.

const heroStats = [
  { value: '5', label: 'top-level run_team branches (indepth_only · answer_only · two_call · parity · solo)', tone: 'warning' as const },
  { value: '2', label: 'answer-validator IMPLEMENTATIONS — regenerate vs rewrite (same gate, two code paths)', tone: 'warning' as const },
  { value: '4', label: 'distinct answer-quality layers stacked on one answer (gate · validate · merge-conf · in-depth)', tone: 'warning' as const },
  { value: '1', label: 'gap none of them cover: "is this a real answer?" — "." shipped GREEN', tone: 'danger' as const },
];

// The answer-quality layers, in call order (team.py::_synthesize_and_validate 1165-1202).
const layerRows = [
  ['1 · Synthesize answer', '_synthesize_answer :657', 'writer (synth model)', 'produce {answer, citations, blocks}', '—'],
  ['2 · Temporal gate', '_apply_temporal_gate :602 → temporal.run_temporal_gate', 'deterministic + facts', 'patch/flag temporal claims vs temporal_facts (off/warn/enforce)', 'overlaps the validator’s temporal check'],
  ['3 · Validate + refine', '_validate_and_refine_answer :983', 'validator LLM (cross-family)', 'flag factual/temporal contradiction → regenerate OR rewrite', 'two impls; temporal overlaps layer 2'],
  ['4 · Merge confidence', '_merge_temporal_gate_conf :571', 'deterministic', 'combine gate + validator → green/yellow/red', 'reconciles two overlapping signals'],
  ['5 · In-Depth synth + validate', '_gen_indepth :897 → _validate_indepth_verdict :810', 'writer + validator LLM', 'elaborate → drop/keep claims → re-synth → strip', 'separate validation subsystem'],
];

// The two validator implementations — selected by the prompt NAME, not a clean flag.
const validatorImpls = [
  ['regenerate', '_validate_answer :723 + _answer_feedback :644', '{answer_ok, answer_issues}', 'flag → re-synthesize the WHOLE answer (re-touches correct parts)', 'degraded the strong writer in the A/B'],
  ['rewrite', '_validate_answer_rewrite :765', '{answer_ok, errors[], corrected_answer}', 'adopt the validator’s surgical fix; keep-best, never-regress', 'won the A/B — the one to keep'],
];

// The gap the run-65609a25 failure exposed — a non-substantive answer passes every layer.
const gapRows = [
  ['Writer emits "."', 'qwen3.6-35b-q6 returns a schema-valid but empty answer', 'envelope is valid → no transport/schema error'],
  ['Temporal gate', 'status = not_applicable ("." has no temporal claim to check)', 'PASS'],
  ['Validate + refine', 'no false claim to name; validation-answer.txt:16 says "if you cannot name a concrete error, pass"', 'answer_ok = true → PASS'],
  ['Merge confidence', 'gate n/a + validator ok', 'GREEN'],
  ['Ship', 'green confidence → shipped as a clean answer', 'BAD answer shipped'],
];

// What can collapse. The thesis: many overlapping LLM-judge layers, one missing cheap deterministic gate.
const simplifyRows = [
  ['Collapse the 2 validator impls → 1', 'regenerate + rewrite are two code paths for the same gate, chosen by prompt-name string match (_is_rewrite_validator :979)', 'Keep rewrite (won the A/B); delete the regenerate path + _answer_feedback. One validator.'],
  ['Fold temporal into the validator (or vice-versa)', 'layer 2 (gate) and layer 3 (validator) both check temporal correctness; merge-conf (layer 4) exists only to reconcile them', 'Pick one home for temporal. If the gate owns dates, the validator stops scoring them (and merge-conf shrinks).'],
  ['ADD one deterministic substance gate', 'no layer asks "is this a real answer?" — empty/"."/refusal/missing-required-shape ships green', 'A pre-validator check: non-empty + has refs/blocks when the task requires them → fail fast (cheap, catches the real failure).'],
  ['Unify the 5 branches', 'indepth_only / answer_only / two_call / parity / solo are forked paths through run_team with duplicated synth+gate+validate+assemble', 'One linear pipeline with feature flags (has_validator, emit_indepth, retrieve_chart) instead of 5 branches.'],
  ['Don’t build the route-by-field layer yet', 'validator-audit-framework.canvas proposes routing context_issues vs answer_issues to orchestrator vs corrector — a 3rd validation layer', 'The data says the bottleneck is the corrector + the missing substance gate, not richer routing. Defer.'],
];

function AnswerFlow() {
  const theme = useHostTheme();
  // Linear spine; quality layers (gate / validate / in-depth) are accented. "." would pass 4→5→6.
  const nodes = [
    { title: 'Request', detail: '/v1/chat/completions', kind: 'io' },
    { title: 'Chart source', detail: 'retrieve(querystore) | messages', kind: 'io' },
    { title: 'Context spec', detail: 'temporal · kb · expert', kind: 'io' },
    { title: 'Gather', detail: 'orchestrator ReAct + tools (solo: skip)', kind: 'io' },
    { title: 'Synthesize answer', detail: 'writer → {answer,citations,blocks}', kind: 'write' },
    { title: 'Temporal gate', detail: 'off / warn / enforce', kind: 'qual' },
    { title: 'Validate + refine', detail: 'regenerate | rewrite', kind: 'qual' },
    { title: 'Merge confidence', detail: 'green / yellow / red', kind: 'io' },
    { title: 'In-Depth', detail: 'synth → validate → strip', kind: 'qual' },
    { title: 'Assemble + ship', detail: 'envelope to caller', kind: 'io' },
  ];
  const nodeW = 158;
  const nodeH = 62;
  const gapX = 16;
  const width = nodes.length * (nodeW + gapX);
  const height = 200;
  const y = 40;
  const xs = nodes.map((_, i) => 10 + i * (nodeW + gapX));
  const fillFor = (kind: string) =>
    kind === 'qual' ? theme.fill.secondary : theme.bg.elevated;
  const strokeFor = (kind: string) =>
    kind === 'qual' ? theme.accent.primary : kind === 'write' ? theme.stroke.primary : theme.stroke.secondary;

  return (
    <svg role="img" aria-label="med-agent-hub answer flow" width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        <marker id="aflow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>
      {nodes.slice(0, -1).map((_, i) => {
        const x1 = xs[i] + nodeW;
        const x2 = xs[i + 1];
        const yc = y + nodeH / 2;
        return (
          <path
            key={`e-${i}`}
            d={`M ${x1} ${yc} L ${x2 - 6} ${yc}`}
            fill="none"
            stroke={theme.stroke.secondary}
            strokeWidth={1.3}
            markerEnd="url(#aflow-arrow)"
          />
        );
      })}
      {/* the gap: a "." answer passes synth → gate → validate untouched */}
      <path
        d={`M ${xs[4] + nodeW / 2} ${y + nodeH + 10} L ${xs[6] + nodeW / 2} ${y + nodeH + 10}`}
        fill="none"
        stroke={theme.text.tertiary}
        strokeWidth={1}
        strokeDasharray="4 3"
      />
      <text x={xs[5] + nodeW / 2} y={y + nodeH + 30} fontSize={11} textAnchor="middle" fill={theme.text.tertiary} style={{ fontFamily: 'inherit' }}>
        a "." answer passes every gate → ships GREEN (no substance check)
      </text>
      {nodes.map((n, i) => (
        <g key={n.title}>
          <rect
            x={xs[i]}
            y={y}
            width={nodeW}
            height={nodeH}
            rx={8}
            fill={fillFor(n.kind)}
            stroke={strokeFor(n.kind)}
            strokeWidth={n.kind === 'qual' ? 1.6 : 1}
          />
          <text x={xs[i] + 12} y={y + 25} fontSize={13} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
            {n.title}
          </text>
          <text x={xs[i] + 12} y={y + 45} fontSize={10.5} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
            {n.detail}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function AnswerFlowCanvas() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <Pill tone="warning">simplification map</Pill>
        <H1>med-agent-hub answer flow — what to simplify</H1>
        <Text tone="secondary">
          The whole answer pipeline on one page, grounded in <Code>team.py</Code> at run{' '}
          <Code>65609a25</Code>. The quality machinery has grown into several overlapping LLM-judge
          layers; the one bad answer that shipped (<Code>.</Code>) passed through every one of them.
          The cut: collapse the overlapping layers, add the one cheap deterministic gate they’re missing.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      <Divider />

      <H2>The flow</H2>
      <Text tone="secondary">
        Linear spine; the <b>accented</b> boxes are the answer-quality layers. Branch/solo variants
        reuse these same stages. Source: <Code>_synthesize_and_validate</Code> (team.py:1165–1202).
      </Text>
      <AnswerFlow />

      <H2>The quality layers (call order)</H2>
      <Table
        headers={['Layer', 'team.py symbol', 'Who', 'Checks', 'Overlap / smell']}
        rows={layerRows}
        striped
      />

      <H2>Two validator implementations — same gate, two paths</H2>
      <Text tone="secondary">
        Selected by a prompt-name string match (<Code>_is_rewrite_validator</Code>, team.py:979), not a
        clean flag. The A/B already picked a winner.
      </Text>
      <Table
        headers={['Mode', 'symbol', 'verdict shape', 'behaviour', 'verdict']}
        rows={validatorImpls}
        striped
      />

      <Divider />

      <H2>The gap: a non-answer ships green</H2>
      <Callout tone="danger" title="run 65609a25 · wide-team-high · date-zabella-weight-endpoints">
        The writer returned <Code>.</Code> — schema-valid, semantically empty. It passed every quality
        layer because each only checks for a <i>wrong</i> claim, never for the <i>absence of a real
        answer</i>. This is the resilience hole: the system is robust at the transport/schema level,
        not at the answer-substance level.
      </Callout>
      <Table
        headers={['Stage', 'What happened', 'Result']}
        rows={gapRows}
        striped
      />

      <Divider />

      <H2>Simplification candidates</H2>
      <Text tone="secondary">
        The pattern is over-engineered where the layers overlap and under-engineered on the actual
        failure. Net: remove overlapping LLM layers, add one deterministic substance gate.
      </Text>
      <Table
        headers={['Move', 'Why (grounded)', 'Cut']}
        rows={simplifyRows}
        striped
      />

      <Callout tone="success" title="The one-line thesis">
        Keep ONE validator (rewrite), give temporal ONE home, ADD a cheap deterministic substance gate
        before the LLM validator, and unify the 5 branches into one flagged pipeline. That removes more
        code than it adds and closes the only failure that actually shipped.
      </Callout>

      <Text tone="tertiary">
        Related: <Code>validator-audit-framework.canvas.tsx</Code> (the route-by-audit-field proposal —
        deferred here) and <Code>answer-indepth-parity.canvas.tsx</Code> (the two-call split).
      </Text>
    </Stack>
  );
}
