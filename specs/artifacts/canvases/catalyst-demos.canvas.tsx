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
  file: string;
  poster: string;
  sizeLabel: string;
  durationLabel: string;
};

const clips: DemoClip[] = [
  {
    id: 'catalyst-full-scenario-demo',
    dataSource: 'OpenELIS Laboratory',
    pill: 'Full scenario',
    question: 'Show viral load results since 2026-01-01 with patient, value, and observed date',
    followup: 'Now count the results by test name instead, highest count first',
    file: 'catalyst-full-scenario-demo-20260825b.mp4',
    poster: 'catalyst-full-scenario-demo-20260825b-poster.jpg',
    sizeLabel: '~3.1 MB',
    durationLabel: '1:48',
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
            The second turn refines the exact current query rather than starting over.
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
        <H1>Catalyst — from a question to a dashboard</H1>
        <Text tone="secondary">
          The selected Catalyst contract uses a configured SQL source, its declared dialect, and every table and column
          the connection can read. A writer drafts SQL, a selected profile may add a reviewer, advisory findings remain
          visible, and the person chooses the exact query to run. Successful results can become Datasets, Widgets,
          and a Dashboard published to Superset. The generic connection is not yet implemented.
        </Text>
      </Stack>

      <Callout tone="warning">
        <Text size="small">
          <strong>The Spark reference deployment is not yet implemented.</strong> The recording demonstrates the accepted
          Workbench-to-Superset interaction. Phase 1 acceptance waits for the FHIR Data Pipes → Parquet → Spark
          connection and a fresh model-team comparison.
        </Text>
      </Callout>

      <Grid columns={4} gap={16}>
        <Stat value="1" label="Full product-flow recording" tone="info" />
        <Stat value="2" label="Conversation turns" />
        <Stat value="0" label="Sensitive patient records" tone="success" />
        <Stat value="1" label="Configured source per session" />
      </Grid>

      <Divider />

      <Stack gap={8}>
        <H2>Selected product contract</H2>
        <Grid columns={2} gap={16}>
          {[
            {
              title: 'One source per session',
              body: 'A session keeps one source identity, dialect, and readable schema. Choosing another source starts another session instead of mixing data or query context.',
            },
            {
              title: 'Complete readable schema',
              body: 'The model, Available data view, and editor receive every readable table, view, column, and type. Optional descriptions may explain the data but cannot hide it.',
            },
            {
              title: 'Exact, person-controlled execution',
              body: 'Formatting and validation are advisory. The person can edit the query, inspect findings, and run the exact selected SQL once to receive typed rows or the database error.',
            },
            {
              title: 'Product and deployment stay separate',
              body: 'Catalyst is a SQL client. FHIR Data Pipes, Parquet, and Spark define the selected reference deployment without becoming a requirement for every Catalyst connection.',
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
        <H2>Watch the full product flow</H2>
        <Text tone="secondary" size="small">
          This is a real writer/reviewer run through conversation, typed results, saved Datasets and Widgets, and a
          Dashboard imported into Superset. It demonstrates the existing Workbench-to-Superset interaction on the current runtime.
        </Text>
        <Grid columns={1} gap={16}>
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
