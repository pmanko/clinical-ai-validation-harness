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
      <H2>Prompt flow — what we ask, how we validate, what we return</H2>
      <Stack gap={8}>
        <Text tone="secondary">
          End-to-end trace of one team turn, grounded in <Code>team.py::run_team</Code> and the prompt files.
          The synthesizer is asked for a two-section <Code>answer</Code>; the validator judges those two
          sections separately; the hub always returns the <em>same</em> one-envelope shape.
        </Text>
        <Code>{`INPUT  chartsearchai message array
  [ system = DEFAULT_SYSTEM_PROMPT  (chart-only, "cite EVERY record") ]
  [ user = PATIENT CHART ]  [ ...prior turns ]  [ user = QUESTION ]
        |
        v
ORCHESTRATOR LOOP        prompt orchestrator.txt   model = tier orchestrator (LOW gemma-e2b-q2 ... HIGH gemma-31b)
  ReAct tool loop on its OWN message list, repeat until no tool call:
    - kb_search       -> KB reference snippets   (NOT chart data)
    - medical_expert  -> MedGemma interprets the CHART against KB (free text)
        |  kb_context + expert_notes
        v  _gathered_evidence()
GATHERED EVIDENCE  (one block: KB snippets + expert notes)
        |
        v
SYNTHESIS                prompt synthesis(-low).txt  model = tier synth (LOW qwen3-4b ... HIGH qwen3.6-35b)
  call = ORIGINAL prefix messages + user( synthesis_instruction + gathered )
  bound to chartsearchai response_format -> ONE JSON envelope:
     { "answer": "<two markdown sections in ONE string>", "citations":[N...], "blocks":[...] }
        the answer string =
          **Answer**     1-2 sentences, direct, cite chart records inline [N]
          **In Depth**   reasoning: KB guidance (named in prose) + expert reading of THIS chart
        |
        v  _normalize_envelope()   repair mangled \\n  -  fold inline [N] -> citations
   validator set on this level? ---- no ----> RETURN envelope unchanged
        | yes   _audit_and_revise()  (max_loops, default 1)
        v
VALIDATOR                prompt validation.txt  model = tier validator (gemma; cross-family vs the qwen synth)
  sees  CHART (ground truth) + GATHERED + the Answer string
  judges the TWO sections SEPARATELY, returns
     { answer_ok, answer_issues, indepth_ok, indepth_issues }   (FAIL-OPEN -> ok on any parse error)
        |
        v  GRANULAR decision
   answer_ok &  indepth_ok  ->  SHIP full draft (both sections)
   answer_ok & !indepth_ok  ->  _drop_indepth(): keep **Answer**, In Depth -> "(elaboration withheld...)"  -> SHIP
  !answer_ok                ->  re-synthesize( draft + _validator_feedback ) -> re-audit:
                                  Answer now ok    -> adopt (drop In Depth if still bad)
                                  Answer still bad -> ABSTAIN -> _fallback_envelope(_VALIDATOR_ABSTAIN_MSG)
        |
        v
RETURN   ALWAYS the same shape ->  { answer, citations, blocks }
         (the two sections live INSIDE the one answer string; the verdict does NOT leave the hub)`}</Code>
        <Callout tone="warning" title="Why the low-validated run still reads as one confident answer">
          The return contract is fixed: one <Code>{`{ answer, citations, blocks }`}</Code> envelope.
          <Code>**Answer**</Code> and <Code>**In Depth**</Code> are markdown headers <em>inside</em> the single
          <Code>answer</Code> string — not separate fields — and the validator verdict
          (<Code>answer_ok</Code> / <Code>indepth_ok</Code> + issues) never leaves the hub. It only steers
          ship / drop-In-Depth / abstain and goes to the hub logs. So downstream (chartsearchai &rarr; report / ESM)
          receives one prose blob with no machine-readable confidence and no per-section status. Consequences:
          (a) plain LOW (no validator) ships a confident <Code>**Answer**</Code> even when fabricated — nothing
          gates it; (b) when the validator drops In Depth or abstains, the consumer still sees only one string
          (the inline italic notice is the sole signal); (c) the dashboard drilldown and any confidence UI have
          nothing to render yet. <strong>Candidate fix</strong> (ties to the dashboard-flow item + goal-framing):
          emit the per-section verdict + issues into the returned artifact / run trace, so the answer carries an
          explicit grounded confidence instead of one uniform-confidence blob.
        </Callout>
      </Stack>

      <Divider />
      <H2>Answer vs In Depth — different scope, different validation (research-grounded)</H2>
      <Text tone="secondary">
        The two sections have different epistemic scope, so they need different criteria, different
        thresholds, and different fallbacks. Full write-up + citations:
        <Code>specs/artifacts/planning/answer-indepth-structure-research-brief.md</Code>.
      </Text>
      <Table headers={['Aspect', 'Answer (direct)', 'In Depth (elaboration)']} rows={[
        ['Content', 'patient facts from THIS chart', 'interpretation + external KB / guideline guidance'],
        ['Truth test', 'faithful to the chart (groundedness)', 'chart-claims grounded; guideline-claims correct + attributed (NOT in chart); + does the KB actually INFORM the answer'],
        ['Rubric axis', 'accuracy + faithfulness + abstention', 'completeness + relevance + KB-utilization + attribution'],
        ['Threshold', 'STRICT — error cost is high', 'LOWER / advisory — error cost is bounded (it can be dropped)'],
        ['On failure', 'ABSTAIN (never ship a wrong fact)', 'soften / drop the claim — NEVER abstain the turn for an In-Depth-only miss'],
      ]} striped />
      <Callout tone="danger" title="The mis-scoping bug — we judge the In Depth against the chart it is meant to go beyond">
        Our validator prompt tells it the In Depth must be &quot;grounded only in the patient chart.&quot; But the
        In Depth&apos;s job is to bring in KB / guideline guidance that is <em>not</em> in the chart. That is a
        category error: in this run&apos;s verdict logs the e4b validator flagged an In Depth because it
        &quot;introduces external knowledge (OpenMRS guidelines)&quot; — the exact content the synthesis prompt
        <em> asks for</em>. Fix = <strong>route the In Depth audit by claim type</strong> (chart-claims grounded
        vs chart; guideline-claims judged for not-fabricated + correctly-attributed + medically-plausible), and
        add the real In-Depth test: <strong>does the retrieved KB relevantly and correctly inform the answer</strong>
        (context-utilization), at an <strong>advisory threshold</strong> — not the Answer&apos;s strict abstain-or-die bar.
      </Callout>
      <Callout tone="info" title="What the literature says (validated)">
        <strong>Validate the two separately</strong> — answer correctness and explanation/attribution faithfulness
        are independent; passing one does not imply the other (Wallat et al. 2025, <em>Correctness is not
        Faithfulness in RAG Attributions</em>). <strong>An explanation can be plausible yet unfaithful</strong>, so
        a clean In Depth must not vouch for the Answer or vice-versa — keep the gates independent (Turpin et al.
        2023, arXiv:2305.04388). <strong>Completeness is a distinct axis from accuracy</strong> (~90% accurate yet
        omits key info in ~47% of summaries, npj Digit. Med. 2025) — so the In Depth matters, but bound it by the
        question. <strong>For weak models, elaboration can HURT</strong>: reasoning does not uniformly help and can
        reduce small-model accuracy (<em>Selective CoT in Medical QA</em>, arXiv:2602.20130); models elaborate on
        planted errors in up to 83% of cases (Comm. Medicine 2025) — the In Depth is the fabrication surface, so its
        richness should <strong>scale with tier</strong>. <strong>Partial abstention is research-backed</strong> but
        the principled unit is the <em>claim</em>, not the section (selective generation does not scale to long-form;
        I-CALM 2604.03904, AbstentionBench 2506.09038) — section-drop is our pragmatic interim, claim-level is the target.
      </Callout>
      <Callout tone="warning" title="Open decisions (discuss before building)">
        <strong>D1 granularity</strong> — section-level drop (now) vs claim-level keep/drop (research ideal).
        <strong> D2 tier-scaled elaboration</strong> — should weak tiers emit a rich In Depth at all, or Answer +
        the <Code>blocks</Code> evidence table only? (needs a measured A/B). <strong> D3 validator scope fix</strong> —
        route the In Depth audit by claim type + add the KB-informs / advisory-threshold check (looks unambiguously
        correct). <strong> D4 fix mechanism</strong> — one full re-synth + keep-best vs a targeted In-Depth-only
        regeneration that freezes the validated Answer.
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

      <H3>Granular split + validator floor — e4b vs 12b, SAME synth (live run, only the validator differs)</H3>
      <Table headers={['Scenario / turn', 'e4b validator', '12b validator']} rows={[
        ['am-weight-trend t1', 'ABSTAIN (correct)', 'ABSTAIN (correct)'],
        ['am-cd4-history t1', 'FULL', 'FULL'],
        ['am-convo-azt-anemia t1', 'FULL', 'Answer-only (In Depth dropped)'],
        ['am-convo-azt-anemia t2', 'ABSTAIN', 'Answer-only (In Depth dropped)'],
        ['am-convo-azt-anemia t3', 'ABSTAIN', 'FULL'],
        ['am-convo-azt-anemia t4', 'Answer-only (In Depth dropped)', 'Answer-only (In Depth dropped)'],
        ['shipped / 6', '3/6', '5/6'],
      ]} striped />
      <Callout tone="success" title="The granular split works — and 12b is at the validator floor, e4b below it">
        Same orchestrator + synth on both arms; the ONLY difference is the validator model. The granular
        Answer/In-Depth split fires on both (drop-In-Depth keeps the grounded Answer instead of abstaining the
        whole turn). But the e4b validator over-flags the <em>Answer</em> — in the verdict logs it returns
        <Code>answer_ok=False</Code> even for In-Depth-localized issues and citation-index near-misses — so it
        over-abstains (azt t2/t3). The 12b discriminates: <Code>answer_ok=True, indepth_ok=False</Code> for
        In-Depth-only problems (9.2 vs chart 9.1; an unsupported &quot;normal range&quot; / &quot;improved due to ART&quot; claim),
        keeping the Answer and dropping only the elaboration, and passes the one fully-clean turn. Net:
        <strong> 12b ships 5/6 with only the one CORRECT abstain (weight-trend); e4b ships 3/6, over-abstaining two
        turns the 12b correctly ships.</strong> Both correctly abstain the genuine weight-trend fabrication.
      </Callout>
      <Callout tone="warning" title="Two grounded residuals from the verdict logs">
        <strong>1. Citation-index near-miss still trips <Code>answer_ok=False</Code></strong> — even 12b flagged an
        Answer for citing <Code>[168]</Code> (diastolic BP) where <Code>[186]</Code> is the Hgb record, though the
        clinical value + date were right. The prompt says an index near-miss is NOT an Answer failure; the rule
        isn&apos;t fully obeyed → tighten it, or resolve indices deterministically before the audit.
        <strong> 2. Re-synthesis by the weak LOW synth makes things WORSE</strong> — the 12b weight re-synth produced
        NEW hallucinations (&quot;year 2016&quot;, &quot;52.3 kg&quot;). Detection is solved; correction by the same weak synth is the
        bottleneck — which is exactly why the abstain (never ship a wrong Answer) is load-bearing, and why the
        corrector belongs to a separate, more capable role.
      </Callout>

      <Callout tone="info" title="Feasibility — a strong corrector is only viable if it fires rarely">
        The strong corrector is the expensive top rung (a 31B model that evicts the tier models on the
        <Code>--models-max</Code> stack — a thrash cycle per call). It runs <strong>per-flag, never per-query</strong>
        (cost ≈ flag-rate × corrector-cost) — so it&apos;s only affordable if the <strong>flag rate is low</strong>. But
        the weak tiers that need correction most fabricate most, so they&apos;d flag most, and the corrector would fire on
        a large fraction (a per-turn tax exactly where it&apos;s least affordable). Resolution,
        ordered by cost: <strong>prevent (deterministic computed evidence → fewer fabrications → fewer flags; cheap,
        always-on) → gate + abstain (free) → selective strong correction (expensive, rare).</strong> Prevention is what
        earns the right to use a powerful corrector at all; correction is the last resort, not the workhorse.
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
      <H2>G. Iteration log + refined design</H2>
      <Callout tone="danger" title="Iteration 1 (abstain-terminal): correct, but exposed the real blocker">
        Shipped abstain-terminal (never return a flagged answer). Live re-run of the worst scenarios →
        <strong> 100% abstention.</strong> Cause: the validator is <strong>barrier-framed</strong> ("hunt every
        violation → ok=false → abstain"), and the 2-bit gemma-e2b-q2 over-flags (it even false-flagged a correct
        answer for &quot;not auditing separately&quot; — a prompt misread). A reject-everything machine only knows how to
        reject.
      </Callout>
      <Grid columns={2} gap={12}>
        <div><H3>Goal-framing, not barrier-framing</H3><Text size="small">Guide the validator + corrector by GOALS — (1) an accurate Answer, (2) a valid, useful In Depth — not by hunting violations. The validator asks &quot;is it good enough / what would make it so&quot;; abstain is the rare fallback when the goal truly can&apos;t be met, not the default. This is the root fix for the all-abstain.</Text></div>
        <div><H3>Granular abstain (Answer vs In Depth)</H3><Text size="small">The envelope is <Code>**Answer**</Code> (direct) + <Code>**In Depth**</Code> (elaboration). Validate them separately; return the grounded Answer and fix/drop only the flagged In Depth — not all-or-nothing. Smaller focused audits also help the tiny validator over-flag less.</Text></div>
        <div><H3>Validator floor — compare, don&apos;t assume</H3><Text size="small">The 2-bit model over-flags. Find the MINIMUM competent validator: compare <Code>gemma-e4b</Code> vs <Code>gemma-4-12b</Code> (cross-family) on the worst scenarios — pick the smallest that flags real fabrications without false-flagging correct answers.</Text></div>
        <div><H3>Visibility — LLM flow in the dashboard drilldown</H3><Text size="small">The live dashboard (<Code>:8099</Code>) should surface the full per-turn LLM flow (orchestrator → expert → synth → validator verdict → corrector) inside the drilldown modal of each scenario×backend cell, to dig into why a turn passed / abstained. Needs the hub to emit a per-turn trace into the run artifacts.</Text></div>
      </Grid>

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
