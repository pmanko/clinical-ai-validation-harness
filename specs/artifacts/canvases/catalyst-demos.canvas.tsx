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
    id: 'catalyst-openelis-local',
    dataSource: 'OpenELIS Laboratory',
    pill: 'Local · writer and reviewer',
    question: 'How many patients are there?',
    followup: 'Break down that patient count by gender, including patients with missing gender. Return gender and patient_count.',
    file: 'catalyst-openelis-local-light-20260911-d070fe7.mp4',
    poster: 'catalyst-openelis-local-light-20260911-d070fe7-poster.jpg',
    sizeLabel: '~4 MB',
    durationLabel: '3:08',
  },
  {
    id: 'catalyst-openmrs-hiv-local',
    dataSource: 'OpenMRS HIV/ART program',
    pill: 'Local · writer and reviewer',
    question: 'How many patients are there?',
    followup: 'Break down that patient count by gender, including patients with missing gender. Return gender and patient_count.',
    file: 'catalyst-openmrs-hiv-local-light-20260911-d070fe7.mp4',
    poster: 'catalyst-openmrs-hiv-local-light-20260911-d070fe7-poster.jpg',
    sizeLabel: '~4 MB',
    durationLabel: '3:06',
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
            aria-label={`${clip.dataSource}: local query-to-dashboard demonstration`}
            style={{ aspectRatio: '16 / 10', borderRadius: 8, background: '#000', maxWidth: 640 }}
          >
            <source src={src} type="video/mp4" />
            Can't play this video — <a href={src}>download it</a> instead.
          </video>
          <Text size="small" tone="tertiary">
            {clip.durationLabel} · {clip.sizeLabel} · recorded locally · aggregate results
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
          and a Dashboard published to Superset.
        </Text>
      </Stack>

      <Callout tone="warning">
        <Text size="small">
          <strong>Recorded locally with a writer and reviewer.</strong> Gemma 4 12B drafts and Qwen 2.5 14B reviews
          each query. Both demonstrations use the current Spark deployment and show actual Superset rendering.
          These local recordings do not establish final server or owner acceptance.
        </Text>
      </Callout>

      <Grid columns={4} gap={16}>
        <Stat value="2" label="Local product-flow recordings" tone="info" />
        <Stat value="2" label="Conversation turns" />
        <Stat value="2" label="Model roles per turn" tone="success" />
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
          Both walkthroughs show drafting alongside schema browsing, explicit execution, refinement, saved-SQL reuse,
          charts and Dashboard arrangement, followed by actual import and rendering in Superset. The pipeline
          introduction is 13 seconds; only labelled waiting periods are accelerated.
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
          <strong>Try the public application.</strong> <a href="https://catalyst.openelis-global.org/">Open Catalyst</a>
          {' '}to explore the deployed Workbench. The videos above were recorded in the local acceptance stack;
          server verification and owner acceptance are tracked in Feature 008 tasks.
        </Text>
      </Callout>
    </Stack>
  );
}
