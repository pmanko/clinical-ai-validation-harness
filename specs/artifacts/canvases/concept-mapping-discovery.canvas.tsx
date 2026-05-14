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
} from 'cursor/canvas';

// Canvas: feature 002 / M2-A concept mapping discovery — 2026-05-14.
//
// Source signals: queries against the live harness MariaDB containing
//   legacy_27_raw (the 5,284-patient 2.7 demo dump)
//   openmrs        (the live RefApp 3.6.0 with CIEL v2026-04-28 imported)
// All counts are from `SELECT COUNT(*)` queries — not the approximate
// information_schema.table_rows — to avoid the drift documented in PR #6.

const headlineFacts = [
  { label: 'Distinct concepts referenced by obs', value: '457', sub: '150 as concept_id + 318 as value_coded (with overlap)' },
  { label: 'Bridgeable to CIEL via UUID rule', value: '457 / 457', sub: '100% — zero unmapped' },
  { label: 'Legacy concept_reference_map rows', value: '0', sub: 'No prior terminology cross-references at all' },
  { label: 'CIEL import errors hitting legacy data', value: '0 / 23', sub: 'All failed concepts are in CIEL\'s long tail, untouched by this dataset' },
];

const bridgeExamples = [
  { legacy: 5088, legacy_fsn: 'TEMPERATURE (C)', ciel_uuid: '5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', ciel_internal: 4166, ciel_fsn: 'Temperature (c)' },
  { legacy: 5089, legacy_fsn: 'WEIGHT (KG)',     ciel_uuid: '5089AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', ciel_internal: 4168, ciel_fsn: 'Weight (kg)' },
  { legacy: 1088, legacy_fsn: 'CURRENT ANTIRETROVIRAL DRUGS USED FOR TREATMENT', ciel_uuid: '1088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', ciel_internal: 55823, ciel_fsn: 'Current antiretroviral drugs used for treatment' },
  { legacy: 1111, legacy_fsn: 'PATIENT REPORTED CURRENT TUBERCULOSIS TREATMENT', ciel_uuid: '1111AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', ciel_internal: 55043, ciel_fsn: 'Patient reported current tuberculosis treatment' },
  { legacy: 1107, legacy_fsn: 'NONE', ciel_uuid: '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', ciel_internal: 0, ciel_fsn: 'None' },
];

const blockers = [
  {
    id: 'B1',
    status: 'SOLVED',
    severity: 'critical',
    title: 'Identity bridge legacy → CIEL',
    finding:
      'concept_id numbers collide (legacy 5088 = TEMPERATURE; CIEL canonical 5088 = also TEMPERATURE — but openmrs.concept.concept_id is the internal OCL-import row id, which DIFFERS). Legacy concept UUIDs do not exist in CIEL.',
    resolution:
      'Bridge by CIEL UUID pattern: legacy.concept_id N ↔ openmrs.concept WHERE uuid = RPAD(N, 36, \'A\'). 100% coverage on the 457 distinct concepts actually used in obs.',
    artifact: 'preliminary mapping rule (this canvas, §Bridge Rule)',
  },
  {
    id: 'B2',
    status: 'SOLVED',
    severity: 'high',
    title: 'No reference_map rows in legacy',
    finding:
      'concept_reference_source, concept_reference_term, concept_reference_map all have ZERO rows in the 2.7 dump. The dump shipped without any external-terminology cross-references.',
    resolution:
      'Not a problem under the rebind strategy. We are not translating concept rows; we are pointing obs.concept_id / obs.value_coded at the CIEL-imported concept (different internal id, same canonical identity). Reference maps come from CIEL itself, already loaded.',
    artifact: '—',
  },
  {
    id: 'B3',
    status: 'SOLVED',
    severity: 'medium',
    title: 'CIEL import had 133 errors',
    finding:
      '23 distinct CIEL canonical IDs failed import (cascade: 109 mapping errors trace back to these 23). The errors are duplicate-name-in-locale validation failures (e.g. \'exantema súbito\' es, \'Quinine sulfate\' en).',
    resolution:
      'Cross-check: 0 of the 23 failed CIEL IDs are referenced by legacy obs. The errors are entirely in CIEL\'s long tail. Non-blocking for this dataset; we can revisit if/when other datasets land.',
    artifact: 'artifacts/dev-20260514-212318/profile/ciel-import-errors.json',
  },
  {
    id: 'B4',
    status: 'PARTIAL',
    severity: 'medium',
    title: 'concept_class FK shift (4 of 19 misaligned)',
    finding:
      'class_id=16 means \'Program\' in legacy but \'Frequency\' in CIEL-loaded openmrs. class_id 16/17/18/19 are all reshuffled. Naively migrating concept rows would semantically corrupt class assignment.',
    resolution:
      'Bypassed by rebind strategy — we don\'t carry forward legacy concept rows. concept_class on the target side is whatever CIEL says. The 4 misaligned IDs are a non-issue for obs migration; would be a real problem for a schema-level concept merge.',
    artifact: '—',
  },
  {
    id: 'B5',
    status: 'OPEN',
    severity: 'high',
    title: 'Four typed clinical tables are empty',
    finding:
      'allergy, conditions, orders, drug_order all have 0 rows in legacy_27_raw. Clinical events live entirely in obs, keyed by concept (e.g. answer-class Drug, answer-class Diagnosis).',
    resolution:
      'M2-A scope: synthesize typed rows by reading obs with concept-class hints (Drug → drug_order; Diagnosis → conditions; etc.). Not an identity problem; a SEMANTIC promotion problem. Needs a per-class promotion rule set, reviewable per constitution.',
    artifact: 'TODO: harness/transform/promote_obs.py (T049–T055 territory)',
  },
  {
    id: 'B6',
    status: 'OPEN',
    severity: 'medium',
    title: 'Schema deltas 2.7 → 2.8',
    finding:
      '22 tables exist in legacy_27_raw but NOT in the RefApp 3.6.0 openmrs DB (likely modules removed/refactored). 109 tables exist in openmrs but NOT in legacy (RefApp 3 additions: openconceptlab, fhir2, addresshierarchy, formentryapp, …). 121 tables are shared.',
    resolution:
      'T024 schema_diff.py will enumerate each delta with clinical_meaningful flag per the §R5 rule. The 22 legacy-only tables likely need bucket decisions (drop / migrate / preserve). Most are 0-row in this dump (only 52 of 143 legacy tables are populated).',
    artifact: 'TODO: artifacts/<run>/schema-diff/diff.json from T024',
  },
  {
    id: 'B7',
    status: 'NON-ISSUE',
    severity: 'low',
    title: 'Locale set divergence',
    finding:
      'Legacy concept_name has English only (3,555 names). Legacy global_property says locale.allowed.list = en,es,fr,it,pt — multilingual aspiration but English-only authoring.',
    resolution:
      'Under the rebind strategy, the target obs rows reference CIEL concepts which already carry 12 locales (en/es/fr/nl/pt_BR/pt/vi/ru/ht/sw/bn/km). Multilingual upgrade comes for free.',
    artifact: '—',
  },
  {
    id: 'B8',
    status: 'NON-ISSUE',
    severity: 'low',
    title: 'obs.value_drug references',
    finding:
      '0 rows in obs have value_drug populated. drug table has 6 rows, all unreferenced from obs.',
    resolution:
      'No drug-table mapping problem in this dataset. drug_order promotion (B5) will need to fabricate drug rows from obs answer-coded drug references, but no orphan value_drug references to resolve.',
    artifact: '—',
  },
];

const obsUsageByClass = [
  { class: 'Diagnosis',         distinct: 119, notes: 'Question + Diagnosis answer-coded → conditions promotion target' },
  { class: 'Question',          distinct: 101, notes: 'Obs question concepts (the keys of the obs grid)' },
  { class: 'Finding',           distinct: 69 },
  { class: 'Misc',              distinct: 54,  notes: 'Date / free-text outcomes (return-visit-date, etc.)' },
  { class: 'Test',              distinct: 34,  notes: 'Numeric vitals: temp, weight, pulse, O2sat → could feed FHIR Observation' },
  { class: 'Drug',              distinct: 30,  notes: 'Drug-coded answers → drug_order promotion target' },
  { class: 'Symptom',           distinct: 13 },
  { class: 'Symptom/Finding',   distinct: 13 },
  { class: 'ConvSet',           distinct: 11 },
  { class: 'Misc Order',        distinct: 6 },
  { class: 'MedSet',            distinct: 4 },
  { class: 'LabSet',            distinct: 2 },
  { class: 'Anatomy',           distinct: 1 },
];

function BridgeRulePanel() {
  return (
    <Card>
      <CardHeader>
        <H2>The bridge rule (preliminary mapping)</H2>
        <Text>One deterministic SQL expression covers 100% of the obs-referenced concepts. No hand curation needed for identity.</Text>
      </CardHeader>
      <CardBody>
        <Stack gap={12}>
          <Callout variant="success">
            <Text>
              For every legacy concept_id <Code>N</Code> referenced from obs, the CIEL counterpart is
              the row in <Code>openmrs.concept</Code> where <Code>uuid = RPAD(N, 36, &#39;A&#39;)</Code>.
            </Text>
          </Callout>
          <Code language="sql">{`-- Identity rule: legacy.concept_id  →  openmrs.concept (CIEL-loaded)
SELECT
  l_obs.obs_id,
  l_obs.concept_id           AS legacy_concept_id,
  ciel_q.concept_id          AS new_concept_id,
  ciel_v.concept_id          AS new_value_coded
FROM legacy_27_raw.obs l_obs
LEFT JOIN openmrs.concept ciel_q ON ciel_q.uuid = RPAD(CAST(l_obs.concept_id  AS CHAR), 36, 'A')
LEFT JOIN openmrs.concept ciel_v ON ciel_v.uuid = RPAD(CAST(l_obs.value_coded AS CHAR), 36, 'A');`}</Code>
          <Text variant="subtle">
            Coverage verified: 457 / 457 distinct concept_ids actually used in obs map to a non-null row.
            FSN names match modulo case (legacy is uppercase AMPATH-style; CIEL is title-case).
          </Text>
        </Stack>
      </CardBody>
    </Card>
  );
}

function BridgeExamplesPanel() {
  return (
    <Card>
      <CardHeader>
        <H3>Bridge examples — top 5 by obs usage</H3>
      </CardHeader>
      <CardBody>
        <Table
          columns={[
            { key: 'legacy', header: 'legacy id' },
            { key: 'legacy_fsn', header: 'legacy FSN (en)' },
            { key: 'ciel_uuid', header: 'CIEL UUID' },
            { key: 'ciel_internal', header: 'openmrs internal id' },
            { key: 'ciel_fsn', header: 'CIEL FSN (en)' },
          ]}
          rows={bridgeExamples}
        />
      </CardBody>
    </Card>
  );
}

function BlockersPanel() {
  const ordered = [...blockers].sort((a, b) => {
    const rank = (s: string) => ({ critical: 0, high: 1, medium: 2, low: 3 }[s as 'critical' | 'high' | 'medium' | 'low'] ?? 4);
    if (rank(a.severity) !== rank(b.severity)) return rank(a.severity) - rank(b.severity);
    return a.id.localeCompare(b.id);
  });

  return (
    <Card>
      <CardHeader>
        <H2>Blocker inventory</H2>
        <Text>Each row is a concrete blocker we can either close or call out as scope.</Text>
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          {ordered.map((b) => (
            <Card key={b.id}>
              <CardHeader>
                <Row gap={8}>
                  <Pill variant={b.status === 'SOLVED' ? 'success' : b.status === 'PARTIAL' ? 'warning' : b.status === 'NON-ISSUE' ? 'subtle' : 'danger'}>{b.status}</Pill>
                  <Pill variant="subtle">{b.severity}</Pill>
                  <Text style={{ fontWeight: 600 }}>{b.id} · {b.title}</Text>
                </Row>
              </CardHeader>
              <CardBody>
                <Stack gap={6}>
                  <Text><strong>Finding.</strong> {b.finding}</Text>
                  <Text><strong>Resolution.</strong> {b.resolution}</Text>
                  {b.artifact !== '—' && <Text variant="subtle">Artifact: <Code>{b.artifact}</Code></Text>}
                </Stack>
              </CardBody>
            </Card>
          ))}
        </Stack>
      </CardBody>
    </Card>
  );
}

function ObsUsagePanel() {
  return (
    <Card>
      <CardHeader>
        <H3>Distinct concepts in obs, by class</H3>
        <Text>The 457 concepts that need bridging, grouped by concept_class. Drug + Diagnosis classes feed the promotion-from-obs work (B5).</Text>
      </CardHeader>
      <CardBody>
        <Table
          columns={[
            { key: 'class', header: 'class' },
            { key: 'distinct', header: 'distinct concepts used' },
            { key: 'notes', header: 'notes', optional: true },
          ]}
          rows={obsUsageByClass}
        />
      </CardBody>
    </Card>
  );
}

function NextActionsPanel() {
  return (
    <Card>
      <CardHeader>
        <H2>What this changes about M2-A</H2>
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <Callout variant="info">
            <Text>
              The big M2-A concern — "how do we authorially map 2,528 source concepts to CIEL" — collapses.
              We don't curate per-concept; we apply the UUID rule and rebind. ConceptMap authoring is reserved for
              the structural promotions (obs → conditions/drug_order/allergy/orders), which is fewer rules and more
              clearly clinical-judgment territory.
            </Text>
          </Callout>
          <Text><strong>Newly unblocked:</strong></Text>
          <ul>
            <li>T024 schema_diff can run against the two side-by-side DBs immediately (legacy_27_raw + openmrs).</li>
            <li>The 002 ConceptMap artifact (datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json) becomes <em>thin</em> — a single rule statement plus the obs-promotion class-to-table rules. Hand-curated entries reduce from "thousands" to "tens".</li>
            <li>T022 (terminology profile) can finish quickly — there's nothing to enumerate in legacy reference_map; just emit the empty-array case with a flag.</li>
          </ul>
          <Text><strong>Still required:</strong></Text>
          <ul>
            <li>B5 — obs → typed-table promotion rules per concept class. Real semantic work; reviewable.</li>
            <li>B6 — T024 schema diff; the 22 legacy-only tables need bucket decisions.</li>
            <li>Verification that the rebind preserves answer-set membership (concept_answer rows in legacy reference concept_ids; under rebind, the answer set still resolves correctly because both endpoints share the UUID space). To be confirmed by a spot-check.</li>
          </ul>
        </Stack>
      </CardBody>
    </Card>
  );
}

export default function Canvas() {
  return (
    <Stack gap={18}>
      <H1>002 / M2-A — Concept Mapping Discovery</H1>
      <Text>
        Probing legacy_27_raw vs the CIEL-loaded openmrs DB to answer: what blocks mapping the 2.7 demo
        concepts to CIEL + the OpenMRS 2.8 data model? Findings recorded 2026-05-14 from the live stack;
        see PR #6 for the inventory tooling.
      </Text>

      <Grid columns={2} gap={12}>
        {headlineFacts.map((f) => (
          <Stat key={f.label} label={f.label} value={f.value} subtext={f.sub} />
        ))}
      </Grid>

      <BridgeRulePanel />
      <BridgeExamplesPanel />

      <Divider />

      <BlockersPanel />

      <Divider />

      <ObsUsagePanel />

      <Divider />

      <NextActionsPanel />

      <Divider />

      <Card>
        <CardHeader>
          <H3>Reproducing the queries behind this canvas</H3>
        </CardHeader>
        <CardBody>
          <Stack gap={8}>
            <Text>All counts and examples here come from queries against the running harness MariaDB. To re-derive:</Text>
            <Code language="bash">{`# Bridge coverage (expects "legacy_distinct_in_obs = bridgeable_via_ciel_uuid")
docker exec harness-openmrs-db mariadb --user=openmrs --password=openmrs -B -e "
WITH legacy_used AS (
  SELECT DISTINCT concept_id FROM legacy_27_raw.obs WHERE concept_id IS NOT NULL
  UNION
  SELECT DISTINCT value_coded FROM legacy_27_raw.obs WHERE value_coded IS NOT NULL
)
SELECT
  COUNT(DISTINCT lu.concept_id) AS legacy_distinct_in_obs,
  COUNT(DISTINCT CASE WHEN ciel.concept_id IS NOT NULL THEN lu.concept_id END) AS bridgeable
FROM legacy_used lu
LEFT JOIN openmrs.concept ciel ON ciel.uuid = RPAD(CAST(lu.concept_id AS CHAR), 36, 'A');
"`}</Code>
            <Text variant="subtle">
              Provenance: PR #6 commit a5edc31 (T024c errors), 37b3211 (T021 inventory), 76300d0 (T024b
              snapshot). CIEL version: v2026-04-28.
            </Text>
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  );
}
