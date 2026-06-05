import {
  Callout,
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
} from 'cursor/canvas';

// Source of truth: this session's validator debugging (runs 9af1192f Aloice baseline,
// 4b760af1 interrupted validator A/B, 2a20e51d smoke), the live hub verdict logs,
// offline catch tests against the recorded answers, and four research strands
// (orchestration-flow + role-decomposition/model-matching, ~20 primary sources).
// Roles + tiers live in targets/med-agent-hub/server/levels.yaml; the loop is
// team.py::_audit_and_revise. Findings are grounded in those signals, not inference.

const heroStats = [
  { value: '10/10', label: 'failures the validator CATCHES (even gemma-e2b-q2, offline)', tone: 'success' as const },
  { value: '0', label: 'answers changed in the live A/B — the validator was a no-op', tone: 'danger' as const },
  { value: 'corrector', label: 'the real bottleneck — NOT the auditor', tone: 'warning' as const },
  { value: 'cross-family', label: 'validator (gemma) vs synth (qwen) — already correct', tone: 'success' as const },
  { value: 'keep-best', label: 'gate is sound — but it shipped the flagged original', tone: 'warning' as const },
];

// The per-tier role/model map (levels.yaml) — orchestrator and synthesizer are
// COMPARABLE size within a tier (at MED the synth is bigger), not strong/weak.
const tierRows = [
  ['LOW', 'gemma-e2b-q2 (~2B, 2-bit)', 'medgemma-1.5-4b', 'qwen3-4b (~4B)', 'gemma-e2b-q2'],
  ['MED', 'gemma-e4b-q8 (~4B)', 'medgemma-1.5-4b-q8', 'qwen2.5-14b (14B)', 'gemma-e4b-q8'],
  ['12B', 'gemma-4-12b (12B)', 'medgemma-1.5-4b-q8', 'qwen2.5-14b (14B)', '—'],
  ['HIGH', 'gemma-31b (31B)', 'medgemma-27b', 'qwen3.6-35b (35B MoE)', 'gemma-31b'],
];

// Route the correction by WHICH audit field fired — the validator already emits both.
const routeRows = [
  ['context_issues', 'gathered evidence wrong / missing / insufficient', 'ORCHESTRATOR re-gathers (re-plan)', 'Plan-and-Execute replan · ReWOO · CRITIC · LATS'],
  ['answer_issues (evidence correct)', 'composition wrong: fabricated trend, date↔value, window over-claim', 'CORRECTOR re-composes (escalating)', 'Self-Refine · Reflexion actor · CriticGPT'],
  ['neither clears after escalation', 'no clean answer can be produced', 'ABSTAIN — "not documented / cannot determine"', 'R-Tuning · clinical safety'],
];

// Capability × stakes per role — match the model to the role, not the tier.
const rubricRows = [
  ['Routing / extraction / formatting', 'low', 'low (recoverable)', 'small / cheap'],
  ['Orchestrator (plan + tools)', 'medium (planning)', 'medium (missed evidence → wrong answer)', 'mid → strong; scale per tier'],
  ['Expert (domain reasoning)', 'high', 'high (clinical)', 'domain-tuned; fit > raw size'],
  ['Synthesizer (compose)', 'medium-high', 'medium-high (the returned surface)', 'strong; scale per tier'],
  ['Validator (verify)', 'high', 'HIGH (last line of defense)', 'strong + cross-family; HIGH FLOOR'],
  ['Corrector (constrained rewrite)', 'HIGHEST', 'HIGHEST (edits flagged content)', 'strong + cross-family; HIGH FLOOR, not tier-scaled'],
];

// Empirical: offline catch (does the audit flag the known-bad answers?).
const catchRows = [
  ['gemma-e2b-q2 (LOW validator)', '10 / 10', '0', 'tiny 2-bit model still catches every fabrication'],
  ['gemma-e4b-q8 (MED validator)', '10 / 10', '0', 'catches all'],
  ['gemma-4-12b', '9 / 10', '0', 'missed one borderline "fluctuated" weight case'],
];

// Empirical: corrector comparison — does a flagged answer get FIXED? (re-validated by
// gemma-4-12b on a stripped chart, so the auto-count under-reports; eyeball in the note).
const correctorRows = [
  ['qwen3-4b (LOW synth, control)', '0 / 9', 'weak same-tier synth still fabricates ("weight increased") — genuine fail'],
  ['qwen2.5-14b (MED synth, control)', '2 / 9', 'fixes single-CD4 + most-recent-Hgb'],
  ['gemma-26b (strong x-family, treatment)', '1 / 9 (≈3 real)', 'cd4 ✓, weight-decline ✓, Hgb-most-recent ✓ — but re-validator FALSE-FLAGGED 2 correct rewrites'],
];

export default function ValidatorAuditFramework() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <Row gap={8} wrap>
          <Pill tone="info" active>validator audit framework</Pill>
          <Pill tone="success" active>detection works</Pill>
          <Pill tone="warning" active>correction is the bottleneck</Pill>
          <Pill tone="danger" active>don't ship a flagged answer</Pill>
          <Pill tone="neutral" active>grounded 2026-06-05</Pill>
        </Row>
        <H1>Validator / Audit-Framework — Findings &amp; Design</H1>
        <Text tone="secondary">
          What we learned wiring a per-tier validator into the med-agent team, why it changed nothing in the
          live A/B despite catching every fabrication, and the research-grounded flow + role/model design that
          fixes it. The validator is <Code>team.py::_audit_and_revise</Code>; tiers are in <Code>levels.yaml</Code>.
        </Text>
      </Stack>

      <Grid columns={5} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      <Callout tone="warning" title="The one-line finding">
        The validator <strong>catches reliably</strong> (even the 2-bit LOW model: 10/10 offline) and the
        <strong> keep-best gate is sound</strong> — but in the live A/B every answer was byte-identical to baseline.
        Root cause: the audit flagged the fabrication, the <em>same weak tier synthesizer</em> couldn&apos;t fix it on
        re-synthesis, so keep-best kept the original — which the validator had just flagged. <strong>Detection works;
        correction (by the wrong role) failed; and we shipped a known-flagged answer.</strong> The fix is the
        <em> router</em> and the <em>corrector role</em>, not the auditor.
      </Callout>

      <Divider />
      <H2>A. What the live run actually did</H2>
      <Stack gap={8}>
        <Text>Verdict logging (added this session) on a live LOW-validated turn, <Code>am-weight-trend</Code>:</Text>
        <Code>{`validator[gemma-e2b-q2] ok=False answer_issues="TREND fabrication: draft claims weight increased 42->52; chart shows decline 41/42/48..."  (chart=20347ch gathered=1731ch)
validator flagged the draft -> re-synthesizing with feedback
validator[gemma-e2b-q2] ok=False answer_issues="...dates and values are incorrect or misalign"
validator: revision still flagged -> kept the original draft`}</Code>
        <Text tone="secondary" size="small">
          The audit saw the full chart (20k chars) + the gathered evidence (1.7k, which already had the correct
          declining weights) and correctly flagged the fabrication. The re-synthesis by the weak qwen3-4b synth was
          still flagged; keep-best (correctly) refused the worse rewrite — and returned the original fabrication.
        </Text>
      </Stack>

      <Divider />
      <H2>B. The orchestration flow — route, escalate, abstain</H2>
      <Text tone="secondary">
        Established patterns converge: the loop isn&apos;t the problem, the <strong>router</strong> is. The validator
        already emits <Code>answer_issues</Code> vs <Code>context_issues</Code> — use that to route who re-does the work.
        Never re-run a role with no new signal (Huang); never ship a flagged answer.
      </Text>
      <Table headers={['Validator signal', 'Meaning', 'Loops back to', 'Pattern']} rows={routeRows} striped />
      <Callout tone="info" title="Escalation ladder for answer_issues (evidence correct)">
        1. re-compose, constrained critique (cite each claim; no trend &lt; 2 points) → 2. re-compose with a
        <strong> stronger / distinct corrector</strong> → 3. re-orchestrate (maybe a disguised evidence gap) →
        4. <strong>ABSTAIN</strong>. One round per rung (keep-best gate throughout); escalate, never repeat.
        Today&apos;s code routes <em>both</em> fields to the same weak synth and, on persistent flag, keeps the
        original — the two defects to fix.
      </Callout>

      <Divider />
      <H2>C. Roles — compose ≠ validate ≠ correct</H2>
      <Text tone="secondary">
        Split a capability into its own agent when it has a distinct <strong>cognitive task + failure mode + success
        criterion</strong> (Anthropic, Building Effective Agents). All three differ across compose / verify / correct,
        so they are distinct roles — and <strong>correcting is the hardest</strong>: a constrained rewrite that must
        satisfy the critique AND not regress what was right.
      </Text>
      <Grid columns={3} gap={12}>
        <div><H3>Compose (synth)</H3><Text size="small">Turn gathered evidence into a fluent grounded answer. Open-ended generation.</Text></div>
        <div><H3>Validate (audit)</H3><Text size="small">Judge an answer vs ground truth, per claim. Discrimination; needs cross-family independence.</Text></div>
        <div><H3>Correct (rewrite)</H3><Text size="small">Apply a specific critique faithfully without re-introducing errors. Hardest + highest-stakes.</Text></div>
      </Grid>
      <Callout tone="success" title="Already right in our system">
        Cross-family validator (gemma audits qwen at every tier) directly counters self-preference bias
        [2404.13076]; the keep-best re-audit gate is the textbook defense against revision-degradation [Huang
        2310.01798] — and Huang is <em>for</em> this architecture (external feedback + keep-best), not against it.
      </Callout>

      <Divider />
      <H2>D. Model-role matching — capability × stakes, not tier</H2>
      <Text tone="secondary">
        Task-matched model selection preserves quality at lower cost (FrugalGPT 2305.05176; RouteLLM 2406.18665).
        Spend capability where errors are unrecoverable or expensive to detect: planning, verification, correction.
      </Text>
      <Table headers={['Role', 'Difficulty', 'Stakes', 'Model class']} rows={rubricRows} striped />
      <H3>Per-tier role/model map (levels.yaml) — orch ≈ synth within a tier</H3>
      <Table headers={['Tier', 'Orchestrator', 'Expert', 'Synthesizer', 'Validator (today)']} rows={tierRows} striped />

      <Divider />
      <H2>E. Empirical — the validator catches; the corrector is the question</H2>
      <H3>Offline catch (does the audit flag the known-bad answers, given the chart?)</H3>
      <Table headers={['Validator model', 'caught (of 10 bad)', 'false-flag*', 'note']} rows={catchRows} striped />
      <Text tone="secondary" size="small">
        * offline false-flags were artifacts of a stripped (observations-only) chart; the live audit sees the full
        chart + gathered context. Catch is the real signal: even a 2-bit 2B model flags ~every fabrication.
      </Text>
      <H3>Control vs treatment — does a flagged answer get FIXED?</H3>
      <Table headers={['Corrector', 'auto-fixed / 9', 'eyeball']} rows={correctorRows} striped />
      <Callout tone="warning" title="Three takeaways (the corrector helps, but isn't a silver bullet)">
        <strong>1. A capable corrector beats the weak synth</strong> (0 → ~3 real fixes) — the corrector-as-a-role
        has merit; re-prompting the same weak synth is the dead end (qwen3-4b: 0/9).
        <strong> 2. No corrector reliably fixed the hard multi-turn chronology</strong> — even gemma-26b still
        garbled the AZT-anemia Hgb inversion (&quot;9.1… higher than the earlier 3.9&quot;) and a weight ordering.
        That points back to <strong>deterministic computed temporal evidence (prevention) + abstain</strong> for
        the residual, not correction alone.
        <strong> 3. Offline auto-scoring is unreliable</strong> — the re-validator over-flagged correct rewrites
        (stripped-chart noise), so the auto-count under-reports real fixes. A clean measure needs the full chart +
        human calibration.
      </Callout>

      <Divider />
      <H2>F. Recommendations</H2>
      <Stack gap={8}>
        <Text><strong>1. Route by error type.</strong> <Code>context_issues</Code> → re-orchestrate; <Code>answer_issues</Code> → re-compose. Today both go to the same synth.</Text>
        <Text><strong>2. Promote the corrector to a separate role</strong> at a high capability floor (≥ synth, cross-family), <em>not</em> tier-scaled — a constant safety net (the &quot;advisor&quot;). Don&apos;t re-prompt the synth that just failed.</Text>
        <Text><strong>3. Abstain, never ship a flagged answer.</strong> If escalation can&apos;t produce a clean answer, return &quot;not documented / cannot determine&quot; — fixes the shipped-the-fabrication bug.</Text>
        <Text><strong>4. Keep cross-family validator + keep-best gate</strong> — both are correct and load-bearing.</Text>
        <Text><strong>5. Reconsider the 2-bit-2B validator at LOW as a production default</strong> — fine as a labeled floor-probe, but a weak last-line-of-defense for a clinical check; give the validator a floor too.</Text>
      </Stack>

      <Divider />
      <Text tone="secondary" size="small">
        Sources — orchestration: Reflexion 2303.11366 · Self-Refine 2303.17651 · CRITIC 2305.11738 · LATS 2310.04406 ·
        Plan-and-Solve 2305.04091 · ReWOO 2305.18323 · AutoGen 2308.08155 · Huang &quot;cannot self-correct yet&quot; 2310.01798.
        Roles/matching: Anthropic Building Effective Agents · FrugalGPT 2305.05176 · RouteLLM 2406.18665 · CriticGPT
        2407.00215 · GenRM 2408.15240 · self-preference 2404.13076. (Mixture-of-Agents 2406.04692 is an ensemble, NOT
        evidence for one-model-per-role.) Living doc — updated as runs accumulate.
      </Text>
    </Stack>
  );
}
