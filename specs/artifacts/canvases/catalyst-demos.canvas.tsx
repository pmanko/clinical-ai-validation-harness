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
  Text,
} from 'cursor/canvas';

// Served by the Catalyst demo host, not bundled with the site build. Size was
// never the reason to split these off — permanence was: a recording re-cut on
// every UI change is a new binary, and git keeps every one of them forever.
// The host serves them from a directory the deploy writes, so the repository
// stays text.
const VIDEO_BASE = 'https://catalyst.openelis-global.org/media';

type DemoClip = {
  id: string;
  dataSource: string;
  pill: string;
  question: string;
  followup: string;
  factView: string;
  file: string;
  poster: string;
  sizeLabel: string;
  durationLabel: string;
};

const clips: DemoClip[] = [
  {
    id: 'openelis-lab-demo',
    dataSource: 'OpenELIS Laboratory',
    pill: 'Lab data',
    question: 'Show viral load results since 2026-01-01 with patient, value, and observed date',
    followup: 'Also include the result unit and how many minutes elapsed between specimen receipt and result release',
    factView: 'analytics.lab_result_fact_v1',
    file: 'openelis-lab-demo-20260823.mp4',
    poster: 'openelis-lab-demo-poster.jpg',
    sizeLabel: '~660 KB',
    durationLabel: '~29s',
  },
  {
    id: 'openmrs-hiv-demo',
    dataSource: 'OpenMRS HIV/ART program',
    pill: 'HIV program data',
    question: 'Show CD4 count results since 2026-01-01 with patient, value, and observed date',
    followup: "Also include the patient's gender and birth date",
    factView: 'analytics.hiv_observation_fact_v1',
    file: 'openmrs-hiv-demo-20260823.mp4',
    poster: 'openmrs-hiv-demo-poster.jpg',
    sizeLabel: '~790 KB',
    durationLabel: '~32s',
  },
];

function DemoVideo({ clip }: { clip: DemoClip }) {
  const src = `${VIDEO_BASE}/${clip.file}`;
  const poster = `${VIDEO_BASE}/${clip.poster}`;
  return (
    <Card>
      <CardHeader trailing={<Pill tone="info">{clip.pill}</Pill>}>
        <Text weight="semibold">{clip.dataSource}</Text>
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <video
            controls
            preload="none"
            playsInline
            poster={poster}
            width="100%"
            style={{ borderRadius: 8, background: '#000', maxWidth: 640 }}
          >
            <source src={src} type="video/mp4" />
            Can't play this video — <a href={src}>download it</a> instead.
          </video>
          <Text size="small" tone="tertiary">
            {clip.durationLabel} · {clip.sizeLabel} · synthetic / de-identified demo data, not real patients
          </Text>
          <Divider />
          <Stack gap={4}>
            <Row gap={6} style={{ alignItems: 'flex-start' }}>
              <Pill size="sm" tone="neutral">Turn 1</Pill>
              <Text size="small">{clip.question}</Text>
            </Row>
            <Row gap={6} style={{ alignItems: 'flex-start' }}>
              <Pill size="sm" tone="neutral">Turn 2</Pill>
              <Text size="small">{clip.followup}</Text>
            </Row>
          </Stack>
          <Text size="small" tone="tertiary">
            Generated against <Code>{clip.factView}</Code> — reviewed, executed, and re-refined from the exact
            current query, not restarted from scratch.
          </Text>
        </Stack>
      </CardBody>
    </Card>
  );
}

export default function CatalystDemosCanvas() {
  return (
    <Stack gap={24}>
      <Stack gap={6}>
        <H1>Catalyst — query-to-table for clinical data, on two real data sources</H1>
        <Text tone="secondary">
          Ask a clinical question in plain language; a small writer model drafts SQL against a database-generated
          catalog, a reviewer model checks it, and a deterministic policy — not the model — decides whether the SQL
          is safe to run. Every answer is a typed table you can inspect, not a paragraph you have to trust.
        </Text>
      </Stack>

      <Grid columns={4} gap={16}>
        <Stat value="2" label="Independent data sources" tone="info" />
        <Stat value="2" label="Real turns per demo below" />
        <Stat value="0" label="Hand-written ingestion projections" tone="success" />
        <Stat value="1" label="Read-only SQL policy, enforced deterministically" />
      </Grid>

      <Divider />

      <Stack gap={8}>
        <H2>What makes this different</H2>
        <Grid columns={2} gap={16}>
          {[
            {
              title: 'Governed generation, not a chat window',
              body: 'A writer model drafts the query; a reviewer model checks it against the same catalog. Neither model is trusted to enforce safety — a separate deterministic SQL policy parses the generated statement and rejects anything that is not read-only, regardless of what either model produced.',
            },
            {
              title: 'The catalog is generated, never hand-written',
              body: "Column names, types, and grain come from the database itself (COMMENT ON VIEW / COMMENT ON COLUMN on the curated SQL) plus one small overlay file per source. A canonical value that matches zero live rows fails catalog generation instead of silently producing empty results.",
            },
            {
              title: 'Lossless ingestion, curated in SQL',
              body: 'The ingestion layer keeps every coding on every FHIR resource — nothing is picked or dropped on the way in. Collapsing to one row per resource and choosing a display value happens afterward in SQL, where a mistake costs a view redefinition, not a full re-fetch from the source system.',
            },
            {
              title: 'One session, switchable data source',
              body: 'A workbench session is not locked to the data source it started on: a later turn can target a different registered source, and the session picks up right where the conversation left off.',
            },
          ].map((pillar) => (
            <Card key={pillar.title}>
              <CardBody>
                <Stack gap={4}>
                  <Text weight="semibold">{pillar.title}</Text>
                  <Text size="small" tone="secondary">{pillar.body}</Text>
                </Stack>
              </CardBody>
            </Card>
          ))}
        </Grid>
      </Stack>

      <Divider />

      <Stack gap={12}>
        <H2>Watch it work — one conversation per data source</H2>
        <Text tone="secondary" size="small">
          Each recording is a real run against the live stack: real writer/reviewer models, real PostgreSQL
          execution, no scripted or mocked responses. Turn 2 in each recording refines turn 1's exact query rather
          than starting a new one.
        </Text>
        <Grid columns={2} gap={16}>
          {clips.map((clip) => (
            <DemoVideo key={clip.id} clip={clip} />
          ))}
        </Grid>
      </Stack>

      <Divider />

      <Stack gap={8}>
        <H2>Go deeper</H2>
        <Row gap={16} style={{ flexWrap: 'wrap' }}>
          <Link href="#/spec/README">Project README &amp; setup →</Link>
        </Row>
      </Stack>

      <Callout tone="info">
        <Text size="small">
          <strong>Demo environment, not a live public instance.</strong> These recordings run against a local
          development stack (synthetic/de-identified demo data only — see the honesty note on the homepage). There
          is no publicly hosted Catalyst instance today; the README above covers running it yourself.
        </Text>
      </Callout>
    </Stack>
  );
}
