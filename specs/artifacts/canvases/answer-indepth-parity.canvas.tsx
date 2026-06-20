import type { ReactNode } from 'react';
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
  Pill,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from 'cursor/canvas';

// Architecture dashboard for evolving the Answer and In-Depth sections into two
// TRULY SEPARATE, independently-measured, asynchronous responses — for BOTH the
// vanilla chartsearchai single models AND the med-agent-hub teams. Update the
// Coverage matrix and the Roadmap as phases land. Internal status (PRs, run state)
// lives in specs/artifacts/planning/answer-indepth-parity.md (dev-only).

const heroStats = [
  { value: '2', label: 'axes to measure independently — Answer · In-Depth', tone: 'info' as const },
  { value: '4', label: 'quantities per arm — quality ×2, latency ×2', tone: 'brand' as const },
  { value: 'P0', label: 'shipped: shared single-pass In-Depth (judging parity, 2 hub arms)', tone: 'success' as const },
  { value: '0', label: 'vanilla single models with an In-Depth today', tone: 'warning' as const },
  { value: 'P1–P4', label: 'remaining: separate latency + true async parity', tone: 'info' as const },
];

// ---------- shared SVG architecture diagram (hand-placed nodes + Bezier edges) ----------

type NodeTone = 'accent' | 'success' | 'info' | 'warning' | 'danger';
type ArchNode = { title: string; detail: string; x: number; y: number; tone?: NodeTone };

function ArchDiagram({
  id, nodes, edges, width, height, nodeW = 212, nodeH = 64,
}: {
  id: string;
  nodes: ArchNode[];
  edges: Array<[number, number]>;
  width: number;
  height: number;
  nodeW?: number;
  nodeH?: number;
}) {
  const theme = useHostTheme();
  const strokeFor = (tone?: NodeTone) =>
    tone === 'success' ? theme.stroke.success
      : tone === 'info' ? theme.stroke.brand
        : tone === 'warning' ? theme.stroke.warning
          : tone === 'danger' ? theme.stroke.danger
            : tone === 'accent' ? theme.accent.primary
              : theme.stroke.primary;
  const marker = `aip-arrow-${id}`;
  return (
    <svg role="img" aria-label={id} width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        <marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
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
            markerEnd={`url(#${marker})`}
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
            fill={node.tone ? theme.fill.tertiary : theme.bg.elevated}
            stroke={strokeFor(node.tone)}
            strokeWidth={node.tone ? 1.6 : 1}
          />
          <text x={node.x + 12} y={node.y + 25} fontSize={12.5} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
            {node.title}
          </text>
          <text x={node.x + 12} y={node.y + 45} fontSize={10.5} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
            {node.detail}
          </text>
        </g>
      ))}
    </svg>
  );
}

// ---------- diagrams ----------

// TARGET — two orthogonal calls per (scenario × arm); answer fast, in-depth slow, runnable in parallel.
const targetNodes: ArchNode[] = [
  { title: 'one cell', detail: 'scenario × arm', x: 20, y: 132 },
  { title: 'ANSWER call · fast', detail: 'single → router :8077 · team → hub (answer-only)', x: 300, y: 40, tone: 'success' },
  { title: 'Answer · latency_A', detail: 'judge → Benchmark', x: 640, y: 40, tone: 'success' },
  { title: 'IN-DEPTH call · slow', detail: 'hub in-depth-only — SHARED across all arms', x: 300, y: 224, tone: 'info' },
  { title: 'In-Depth · latency_I', detail: 'judge → Background', x: 640, y: 224, tone: 'info' },
];
const targetEdges: Array<[number, number]> = [[0, 1], [1, 2], [0, 3], [3, 4]];

// CURRENT — med-agent-hub team: answer + in-depth produced and timed as ONE call.
const hubNodes: ArchNode[] = [
  { title: 'harness · ONE call', detail: 'per scenario × arm', x: 20, y: 70 },
  { title: 'chartsearchai', detail: 'assembles chart context', x: 250, y: 70 },
  { title: 'med-agent-hub', detail: 'answer-synth → in-depth-synth (one round)', x: 480, y: 70, tone: 'accent' },
  { title: 'ONE envelope · ONE latency', detail: '"**Answer** … **In Depth** …"', x: 740, y: 70, tone: 'warning' },
  { title: 'judge splits text', detail: '→ Benchmark + Background (latency NOT split)', x: 1000, y: 70 },
];
const hubEdges: Array<[number, number]> = [[0, 1], [1, 2], [2, 3], [3, 4]];

// CURRENT — vanilla chartsearchai single: answer only, no in-depth at all.
const singleNodes: ArchNode[] = [
  { title: 'harness · ONE call', detail: 'per scenario × arm', x: 20, y: 70 },
  { title: 'chartsearchai /chat', detail: 'assembles chart context', x: 250, y: 70 },
  { title: 'router :8077 (GGUF)', detail: 'single LLM, DRY', x: 480, y: 70 },
  { title: 'answer ONLY · ONE latency', detail: 'no **In Depth** section', x: 740, y: 70, tone: 'danger' },
  { title: 'judge → Benchmark', detail: 'no Background axis', x: 1000, y: 70 },
];
const singleEdges: Array<[number, number]> = [[0, 1], [1, 2], [2, 3], [3, 4]];

// ROADMAP — P0 done → P1..P4.
const phaseNodes: ArchNode[] = [
  { title: 'P0 · shared In-Depth', detail: 'judging parity (2 hub arms) — done', x: 20, y: 30, tone: 'success' },
  { title: 'P1 · split hub modes', detail: 'answer-only + in-depth-only', x: 280, y: 30 },
  { title: 'P2 · harness two-call', detail: '2 latencies · 2 artifacts', x: 540, y: 30 },
  { title: 'P3 · judge + report', detail: '2 axes · ALL arms', x: 800, y: 30 },
  { title: 'P4 · parallelize', detail: 'async · answer ∥ in-depth', x: 1060, y: 30 },
];
const phaseEdges: Array<[number, number]> = [[0, 1], [1, 2], [2, 3], [3, 4]];

// ---------- coverage + roadmap data ----------

const yes = <Pill tone="success" size="sm" active>yes</Pill>;
const no = <Pill tone="neutral" size="sm">—</Pill>;
const combined = <Pill tone="warning" size="sm" active>combined</Pill>;

const coverageRows: ReactNode[][] = [
  ['Vanilla single — 12B / Qwen / MedGemma / LFM2', yes, no, no],
  ['Hub validated team (two_call)', yes, combined, no],
  ['Hub single-12b-indepth (new)', yes, combined, no],
  ['Hub parity-indepth (new)', yes, combined, no],
  [<Text weight="semibold">Vision — every arm</Text>, yes, yes, yes],
];

const done = <Pill tone="success" size="sm" active>done</Pill>;
const next = <Pill tone="info" size="sm">next</Pill>;
const planned = <Pill tone="neutral" size="sm">planned</Pill>;

const roadmapRows: ReactNode[][] = [
  ['P0', 'Shared single-pass In-Depth in the hub → separate judging on the 2 hub in-depth arms', done],
  ['P1', 'Split the hub into answer-only + in-depth-only modes (reuses _synthesize_indepth)', next],
  ['P2', 'Harness two-call orchestration: record latency_A + latency_I; results {answer, indepth}. Singles finally get an In-Depth.', planned],
  ['P3', 'Judge + report consume two independent axes for ALL arms (quality + latency per axis)', planned],
  ['P4', 'Parallelize: answer ∥ in-depth → genuinely async, quick answer + slower in-depth', planned],
];

export default function AnswerInDepthParityCanvas() {
  return (
    <Stack gap={22}>
      <Stack gap={6}>
        <H1>Answer / In-Depth parity</H1>
        <Text tone="secondary">
          The architectural evolution to make a question&apos;s <b>Answer</b> and its <b>In-Depth</b> elaboration two
          truly separate, independently-measured, asynchronous responses — for both the vanilla chartsearchai single
          models and the med-agent-hub teams. A quick answer, a slower in-depth, each with its own latency and its own
          judge score.
        </Text>
      </Stack>

      <Grid columns={5} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      {/* ---------- VISION ---------- */}
      <Stack gap={10}>
        <H2>The target — two orthogonal calls</H2>
        <Text tone="secondary">
          Each cell makes two calls. The <b>Answer</b> returns fast; the <b>In-Depth</b> is a separate, slower call routed the
          <i> same way for every arm</i> — so the in-depth axis is a fair comparison just like the answer axis. Team
          scaffolding shapes the Answer; In-Depth is a parity pass for everyone (vanilla singles finally get one). If the
          in-depth doesn&apos;t depend on the answer, the two calls run in parallel — genuinely async.
        </Text>
        <Card>
          <CardBody><ArchDiagram id="target" nodes={targetNodes} edges={targetEdges} width={900} height={320} /></CardBody>
        </Card>
        <Grid columns={4} gap={12}>
          <Stat value="Benchmark" label="answer quality — accuracy · completeness · relevance" tone="success" />
          <Stat value="latency_A" label="answer speed — fast" tone="success" />
          <Stat value="Background" label="in-depth quality — support · added-value · no-harm" tone="info" />
          <Stat value="latency_I" label="in-depth speed — slow" tone="info" />
        </Grid>
      </Stack>

      <Divider />

      {/* ---------- CURRENT ---------- */}
      <Stack gap={10}>
        <H2>Where we are now — both setups</H2>

        <Card>
          <CardHeader trailing={<Pill tone="warning" active>combined · one latency</Pill>}>
            <H3>med-agent-hub (team arms) — produces both, but combined</H3>
          </CardHeader>
          <CardBody>
            <ArchDiagram id="hub-now" nodes={hubNodes} edges={hubEdges} width={1230} height={170} />
            <Text tone="tertiary" size="small">
              The hub already runs answer-synth and in-depth-synth as separate internal calls — they&apos;re just
              concatenated and timed as one. That&apos;s why P1 (splitting them into two modes) is a small move.
            </Text>
          </CardBody>
        </Card>

        <Card>
          <CardHeader trailing={<Pill tone="danger" active>no in-depth</Pill>}>
            <H3>vanilla chartsearchai (single models) — answer only</H3>
          </CardHeader>
          <CardBody>
            <ArchDiagram id="single-now" nodes={singleNodes} edges={singleEdges} width={1230} height={170} />
            <Text tone="tertiary" size="small">
              The multi-class single baselines (12B · Qwen · MedGemma · LFM2) — the whole point of &quot;parity for the
              single models&quot; — emit no In-Depth, so they are only judged on the Answer.
            </Text>
          </CardBody>
        </Card>

        <Card>
          <CardHeader><H3>Coverage today — which axis each arm produces</H3></CardHeader>
          <CardBody>
            <Table
              headers={['Arm', 'Answer', 'In-Depth', 'Separate latency']}
              rows={coverageRows}
            />
          </CardBody>
        </Card>

        <Callout tone="warning" title="The gap (current → vision)">
          1) No <b>separate latency</b> — one round-trip times the pair. &nbsp;2) No In-Depth for vanilla singles. &nbsp;
          3) In-Depth is <b>coupled</b> — generated by elaborating the answer inside one call, not an independent artifact. &nbsp;
          4) Delivery is combined — the fast answer waits for the in-depth.
        </Callout>
      </Stack>

      <Divider />

      {/* ---------- ROADMAP ---------- */}
      <Stack gap={10}>
        <H2>Roadmap — to true parity + independence</H2>
        <Card>
          <CardBody><ArchDiagram id="phases" nodes={phaseNodes} edges={phaseEdges} width={1300} height={130} /></CardBody>
        </Card>
        <Table headers={['Phase', 'Delivers', 'Status']} rows={roadmapRows} striped />

        <Grid columns={2} gap={12}>
          <Callout tone="info" title="Decision 1 — In-Depth ↔ Answer coupling">
            <b>Independent / parallel</b> — in-depth is broad clinical background for the question; the two calls fire
            concurrently → truly async. &nbsp;vs&nbsp; <b>Sequential / elaborate</b> — in-depth elaborates the delivered
            answer (today&apos;s semantics); coupled, can&apos;t parallelize.
          </Callout>
          <Callout tone="info" title="Decision 2 — In-Depth model">
            <b>Per-arm</b> — each arm&apos;s own writer does its in-depth → an in-depth class survey mirroring the answer
            survey. &nbsp;vs&nbsp; <b>Shared-fixed</b> — one model does every in-depth → isolates the in-depth prompt as
            the only variable (pure parity).
          </Callout>
        </Grid>

        <Callout tone="success" title="P0 shipped">
          The shared single-pass In-Depth (hub <code>indepth_shared</code> flag + the single-12b-indepth and
          parity-indepth levels) gives separate <i>judging</i> on the two hub in-depth arms. P1–P2 add the separate
          latency + extend In-Depth to the vanilla singles.
        </Callout>
      </Stack>
    </Stack>
  );
}
