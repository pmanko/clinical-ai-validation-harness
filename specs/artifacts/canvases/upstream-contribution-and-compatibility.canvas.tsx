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

// Source of truth: the pmanko `harness-integration` tips vs each repo's
// `upstream/main`, measured 2026-05-31. Commit groupings + the compatibility
// matrix below are derived from the actual commits and from LIVE validation runs
// against the harness backend on both engines (see "Live validation" table) —
// not from inference. Re-measure with: git -C targets/<repo> log upstream/main..harness-integration.

const heroStats = [
  { value: '17', label: 'esm commits ahead of upstream (0 behind — ready)', tone: 'success' as const },
  { value: '17', label: 'module commits ahead (35 behind — rebase first)', tone: 'warning' as const },
  { value: '2', label: 'openmrs repos targeted (esm + module)', tone: 'info' as const },
  { value: 'both', label: 'engines live-verified (remote + local/bundled)', tone: 'success' as const },
  { value: 'n/a', label: 'med-agent-hub — pmanko-only, no openmrs upstream', tone: 'neutral' as const },
];

// ── Section A: contribution map, organized for the two openmrs repos ──────────

// ESM (openmrs/openmrs-esm-chartsearchai). Sits cleanly on current upstream/main
// (0 behind). PR #1 (the picker foundation merge) is already merged on the fork.
const esmPrRows = [
  ['Multi-turn chat history', '2d00a1f', 'Session-threaded chat; client sends only the new turn, server reconstructs history', 'Ready'],
  ['Structured table blocks', '3093e75, dd3516b', 'Render the blocks[] tabular channel below the prose answer (+ tests)', 'Ready'],
  ['Chat controls', '13325a5, a6c3373', 'Refresh clinical context, always-visible New chat, full-screen maximize', 'Ready'],
  ['Sectioned model picker', 'fdfe9f1, ed7c803, 1955226, …', 'Carbon MenuButton picker with one radio group per endpoint; self-hides when N/A', 'Ready'],
  ['Per-request selection + tags', '4f231df', 'Picker writes a per-session override (no global mutation) + faded "(default)" tag, in-thread refresh notice, per-response model tag', 'Ready'],
];
const esmLocalRows = [
  ['yarn.lock chore + merge commits', '0836be4, 1708e2c, 2da6a39', 'Integration bookkeeping — not upstream content'],
];

// Module (openmrs/openmrs-module-chartsearchai). 35 commits behind upstream/main
// → each PR needs a rebase onto current upstream before opening.
const modulePrRows = [
  ['Multi-turn chat redesign', 'dd28cf6, 9e56b3a, 1374669', 'Frozen-session chart in a stable cache-friendly prefix; per-turn log downgrade', 'Rebase first'],
  ['Structured blocks[] channel', 'ff64284', 'Server emits a typed tabular blocks[] channel alongside prose', 'Rebase first'],
  ['Refresh chart snapshot', '8fe7b80', 'Rebuild the chart snapshot mid-session without clearing the transcript', 'Rebase first'],
  ['ModelSwitchService + REST', '3dd0c13, e658b05, df2ce22, 934f073, 2a67d3a', 'Endpoint registry + SSRF-guarded model listing; GET /endpoints, POST /endpoint; LM Studio probe', 'Rebase first'],
  ['Per-request backend override', 'a9878dd, 91101f9, 8cab949', 'Thread-local {endpointUrl,modelName} override per request; engine-aware answered-model field', 'Rebase first'],
  ['Activator privilege provisioning', '72c6a11', 'Provision privileges + role bindings on every startup', 'Rebase first'],
  ['RemoteLlmEngine HTTP/1.1 pin', 'cadb3ae', 'Pin the Java HttpClient to HTTP/1.1 (general remote-engine bug fix)', 'Rebase first'],
];
const moduleLocalRows = [
  ['QueryStoreChartBuilder reflective access', '11e8d25', 'querystore-coupled — upstream only if querystore lands upstream; harness-local today'],
];

// ── Section B: compatibility vs the out-of-the-box / bundled-LLM shape ─────────
// OOTB default = chartsearchai.llm.engine=local → the module's OWN bundled
// llama-server (in-process child process). The contributions are remote-oriented,
// so each row states how it behaves under local + the evidence level.
const compatRows = [
  ['Per-request override (/chat, /chat/stream)', 'Rejected with a clear 4xx: "requires the remote engine; active engine is local"', 'Engine-aware (fixed)', 'live-verified + omod tests'],
  ['`model` response field', 'Reports the bundled model (basename of chartsearchai.llm.modelFilePath), not the remote GP', 'Accurate (fixed)', 'live-verified'],
  ['/endpoints model listing', '503 under engine≠remote → the esm picker self-hides', 'Backend-enforced', 'live-verified + code (controller:333)'],
  ['Model picker (esm)', 'Hidden when /endpoints fails or <2 models', 'Compatible', 'unit-tested + live'],
  ['Chat features (multi-turn, blocks, refresh)', 'Engine-agnostic — LlmProvider routes to the local or remote engine', 'Compatible', 'code-grounded + live'],
  ['Bundled llama-server path', 'Runnable in the harness via `make chartsearch-engine ENGINE=local`', 'Now exercised', 'live-verified'],
];

// The 2026-05-31 live validation matrix — the curl results both engines returned.
const liveRows = [
  ['local', '/chat (no override)', 'answers via bundled llama-server; model = gemma-4-E4B-it-Q4_K_M.gguf', '✓'],
  ['local', '/endpoints', 'HTTP 503 (picker self-hides)', '✓'],
  ['local', '/chat + override', 'HTTP 400 "requires the remote engine"', '✓'],
  ['remote', '/endpoints', 'HTTP 200', '✓'],
  ['remote', '/chat (no override)', 'model = google/gemma-4-e4b', '✓'],
  ['remote', '/chat + override → team', 'model = med-agent-team (KB-grounded answer)', '✓'],
];

export default function UpstreamContributionAndCompatibility() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <Row gap={8} wrap>
          <Pill tone="info" active>harness-integration → openmrs</Pill>
          <Pill tone="success" active>esm: ready</Pill>
          <Pill tone="warning" active>module: rebase first</Pill>
          <Pill tone="success" active>both engines verified</Pill>
          <Pill tone="neutral" active>measured 2026-05-31</Pill>
        </Row>
        <H1>Upstream Contribution Map &amp; Compatibility Validation</H1>
        <Text tone="secondary">
          What the chartsearchai integration burst contributes, organized into reviewable PRs for the two
          openmrs upstream repos, plus a compatibility check that these remote-oriented improvements do not
          break the out-of-the-box (bundled-LLM) shape. Integration lives on the pmanko{' '}
          <Code>harness-integration</Code> branches; this canvas maps it toward{' '}
          <Code>openmrs/openmrs-esm-chartsearchai</Code> and <Code>openmrs/openmrs-module-chartsearchai</Code>.
        </Text>
      </Stack>

      <Grid columns={5} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      <Callout tone="info" title="Topology — which fork is what">
        <Code>harness-integration</Code> is an INTEGRATION branch (17 features + harness pins), not a single
        upstream PR. Real contributions go to <Code>openmrs/*</Code> as focused feature branches cut from
        current <Code>upstream/main</Code>, one coherent PR each. esm sits clean on upstream (0 behind);
        the module is 35 behind, so its PRs need a rebase onto current upstream first. med-agent-hub is
        pmanko&apos;s own service — no openmrs upstream — and is reviewed via harness PR&nbsp;#15.
      </Callout>

      <Divider />
      <H2>A. Contribution map → proposed upstream PRs</H2>

      <H3>ESM — openmrs/openmrs-esm-chartsearchai (clean on upstream)</H3>
      <Table headers={['Proposed PR', 'Commits', 'Scope', 'Upstream']} rows={esmPrRows} striped />
      <Text tone="secondary" size="small">Harness-local (not upstream content):</Text>
      <Table headers={['Item', 'Commits', 'Why harness-local']} rows={esmLocalRows} />

      <H3>Module — openmrs/openmrs-module-chartsearchai (35 behind → rebase first)</H3>
      <Table headers={['Proposed PR', 'Commits', 'Scope', 'Upstream']} rows={modulePrRows} striped />
      <Text tone="secondary" size="small">Harness-local (not upstream content):</Text>
      <Table headers={['Item', 'Commits', 'Why harness-local']} rows={moduleLocalRows} />

      <Divider />
      <H2>B. Compatibility with the out-of-the-box (bundled-LLM) shape</H2>
      <Callout tone="success" title="The remote-oriented features degrade correctly under engine=local">
        OOTB, chartsearchai runs its OWN bundled <Code>llama-server</Code> in-process
        (<Code>chartsearchai.llm.engine=local</Code>). The picker/override/model-tag work is remote-oriented;
        the compatibility analysis surfaced two engine-correctness gaps (the override + the <Code>model</Code>{' '}
        field were remote-centric), both now fixed and live-verified on both engines.
      </Callout>
      <Table headers={['Improvement', 'Under engine=local', 'Result', 'Evidence']} rows={compatRows} striped />

      <H3>Live validation (2026-05-31, against the harness backend)</H3>
      <Table headers={['Engine', 'Request', 'Observed', 'OK']} rows={liveRows} striped />

      <Divider />
      <H2>C. Recommendations &amp; validation plan</H2>
      <Stack gap={8}>
        <Text>
          <strong>Done:</strong> engine-aware override + <Code>model</Code> field (module); a{' '}
          <Code>make chartsearch-engine ENGINE=local|remote</Code> knob so the bundled OOTB path is runnable
          and validatable in the harness.
        </Text>
        <Text>
          <strong>Next (harness-scoped, NOT on the openmrs forks):</strong> a harness CI job that guards both
          engine paths — unit/contract suites + a smoke per engine — so a future change can&apos;t silently
          break either path.
        </Text>
        <Text>
          <strong>Before opening module PRs:</strong> rebase <Code>harness-integration</Code> onto current{' '}
          <Code>upstream/main</Code> (35 behind), then cut the focused feature branches above. esm needs no
          rebase.
        </Text>
      </Stack>
    </Stack>
  );
}
