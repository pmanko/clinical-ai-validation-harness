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
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from 'cursor/canvas';

// Profile of the OpenMRS demo corpus loaded in this harness, measured 2026-05-29
// by direct queries against the live clinical DB (container harness-openmrs-db,
// schema `openmrs`). Source corpus: feature 002 transform of OpenMRS
// large-demo-data-2-7-0 -> Platform 2.8 / RefApp 3.6.0
// (artifacts/share/openmrs-2.8-refapp-demo-5284-patients.provenance.json).
//
// The load-bearing finding: program NAMES are misleading remap artifacts, so
// every cohort below is labeled by its actual clinical content (drugs / obs /
// conditions), with the program name kept only as provenance. Two checks proved
// this matters — see the "Phenotype cohorts" backing column.

const fmt = (n: number) => n.toLocaleString('en-US');

const heroStats = [
  { value: '5,284', label: 'patients (all active, none deceased)', tone: 'info' as const },
  { value: '427.9K', label: 'observations', tone: 'info' as const },
  { value: '14.3K', label: 'encounters · 44.5K orders', tone: 'info' as const },
  { value: '88%', label: 'in HIV care (WHO-staged) — the real phenotype', tone: 'success' as const },
  { value: '2006', label: 'single clinical time-slice (frozen snapshot)', tone: 'warning' as const },
];

// ── Phenotype cohorts. "Backing" = is there clinical content to actually test
// retrieval/reasoning on, or is the label cosmetic? Counts are from live queries;
// drug cohorts use case-insensitive name matching (heuristic, slight undercount
// on rare combo pills); pediatric is birthdate-derived age at the 2006 care era.
const cohortRows = [
  ['HIV — in care (WHO HIV-stage obs)', '4,670 (88%)', 'Strong', 'ARV plans, WHO staging, adherence, TB/PCP prophylaxis obs across the chart'],
  ['HIV — on ART (≥1 ARV drug)', '3,634 (69%)', 'Strong', 'Lamivudine / Stavudine / Nevirapine / Efavirenz / Lopinavir-r + combos'],
  ['Cotrimoxazole prophylaxis', '2,087 (40%)', 'Strong', 'Trimethoprim-sulfamethoxazole orders (OI prophylaxis)'],
  ['TB treatment / prophylaxis', '1,253 (24%)', 'Strong', 'Isoniazid / Ethambutol / RIPE orders + TB plan obs'],
  ['Pediatric (age < 15 at 2006)', '800 (15%)', 'Strong', '360 under-5; EPI vaccine series + cotrimoxazole (HIV-exposed infants)'],
  ['Malaria (coded condition)', '461 (9%)', 'Strong', 'Second most common condition after acute coryza'],
  ['Childhood vaccine recipient', '486 (9%)', 'Strong', 'DPT / Polio / HepB / Hib / Measles drug orders'],
  ['Peripheral neuropathy (ARV toxicity)', '185 (4%)', 'Strong', 'Classic d4T/ddI adverse effect — drug→side-effect linkage target'],
  ['Multi-morbid (≥6 active conditions)', '45', 'Strong', 'Dense problem lists for multi-condition reasoning'],
  ['Structured encounter-diagnoses (any)', '50', 'Thin', 'Only 50 patients carry coded diagnoses; 914 dx total dataset-wide'],
  ['HIV program enrollment ("PEP/PrEP")', '3,100 (59%)', 'Mislabeled', 'Program NAME says prevention; population is HIV-positive on treatment'],
  ['"Diabetes Education" program', '821 (16%)', 'None', '0 antidiabetic orders, 0 glucose/HbA1c obs, 0 diabetes conditions — label only'],
];

// ── Curated validation patients. uuid is the chart URL key (…/spa/patient/<uuid>/chart).
// Counts are non-voided. age is at the 2006 care era. "good for" ties each to a
// concrete retrieval/reasoning test the harness can run.
type Patient = {
  name: string;
  uuid: string;
  sex: string;
  age: number;
  obs: number;
  enc: number;
  cond: number;
  dx: number;
  orders: number;
  tags: string[];
  conditions: string;
  drugs: string;
  programs: string;
  goodFor: string;
  flagship?: boolean;
};

const curatedPatients: Patient[] = [
  {
    name: 'Zabella Halambe', uuid: 'dd75c020-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 27, obs: 303, enc: 11, cond: 0, dx: 0, orders: 39,
    tags: ['HIV on 1st-line ART', 'densest obs', 'no problem list'],
    conditions: '— (none coded)',
    drugs: 'Efavirenz, Lamivudine, Nevirapine, Stavudine',
    programs: 'HIV care',
    goodFor: 'Retrieval-recall baseline — the densest chart and the patient already indexed in querystore-ES. Multi-turn med questions ("what is she on?" → "how many?").',
    flagship: true,
  },
  {
    name: 'Aloice Mukangu', uuid: 'dd5558ed-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 41, obs: 271, enc: 11, cond: 6, dx: 36, orders: 20,
    tags: ['HIV on ART', 'TB co-treatment', 'AIDS-defining OI', 'dx-rich'],
    conditions: 'Human immunodeficiency virus, Candidiasis (oral), Fever, Vomiting',
    drugs: 'Efavirenz, Lamivudine/zidovudine, RIPE (TB), Cotrimoxazole',
    programs: 'HIV care + Diabetes (label only)',
    goodFor: 'Cross-source synthesis — uniquely combines a coded problem list, 36 structured diagnoses, ART + TB regimens. Does retrieval pull all three surfaces?',
  },
  {
    name: 'Timoty Kenduiwo', uuid: 'dd79194e-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 35, obs: 206, enc: 7, cond: 9, dx: 0, orders: 27,
    tags: ['treatment-experienced HIV', '2nd-line ART', 'regimen failure'],
    conditions: 'Regimen failure, Pneumocystis carinii pneumonia, Malaria, Otitis media, Dermatitis (+4)',
    drugs: 'Abacavir, Didanosine, Lopinavir/ritonavir, Lamivudine/zidovudine, Nevirapine, Stavudine',
    programs: 'HIV care + Diabetes (label only)',
    goodFor: 'Temporal / causal reasoning — 2nd-line salvage regimen with a documented "regimen failure". "Why was the therapy changed?"',
  },
  {
    name: 'Sharolyne Lenye', uuid: 'dd556a73-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 21, obs: 271, enc: 9, cond: 1, dx: 0, orders: 25,
    tags: ['HIV / TB co-infection'],
    conditions: 'Pneumonia, tuberculous',
    drugs: 'Efavirenz, RIPE, Lamivudine/zidovudine, Stavudine, Cotrimoxazole',
    programs: 'HIV care',
    goodFor: 'Co-infection retrieval — concurrent HIV ART + full TB regimen. Tests regimen disambiguation (which drugs treat which disease).',
  },
  {
    name: 'Rahima Kobilo', uuid: 'dd9a0cf1-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 32, obs: 260, enc: 9, cond: 10, dx: 0, orders: 34,
    tags: ['multi-morbid HIV', 'ARV toxicity', 'comorbid HTN', 'no program'],
    conditions: 'Hypertension, Peripheral neuropathy, Allergy, Dyspepsia, Polymenorrhea, Vaginitis',
    drugs: 'Lamivudine, Stavudine, Nevirapine, Isoniazid, Cotrimoxazole',
    programs: '— (enrolled in none)',
    goodFor: 'Problem-list breadth + adverse-effect linkage (Stavudine → peripheral neuropathy). Edge case: real HIV care with zero program enrollment.',
  },
  {
    name: 'Zacharia Monari', uuid: 'dd77da1d-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 19, obs: 258, enc: 10, cond: 10, dx: 0, orders: 0,
    tags: ['rich problem list', 'ZERO medications'],
    conditions: 'Appendicitis, Malaria, UTI, Back pain, Helminthiasis, Myalgia, RTI, Rhinitis, Acute coryza',
    drugs: '— (no orders)',
    programs: 'HIV care',
    goodFor: 'Hallucination guard / negative case — 10 conditions but no drug orders at all. A faithful "what medications?" answer must say none.',
  },
  {
    name: 'Constatina Buigut', uuid: 'dd55457a-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 22, obs: 113, enc: 4, cond: 1, dx: 42, orders: 12,
    tags: ['HIV on ART', 'structured-diagnosis specialist'],
    conditions: 'Urinary tract infection (1 coded condition)',
    drugs: 'Lamivudine, Nevirapine, Stavudine',
    programs: 'HIV care',
    goodFor: 'The rare structured encounter-diagnosis surface — 42 coded diagnoses (the most in the corpus). Tests whether retrieval reaches the diagnosis table at all.',
  },
  {
    name: 'Sospeta Wandanga', uuid: 'dd881a72-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 3, obs: 125, enc: 3, cond: 1, dx: 0, orders: 19,
    tags: ['pediatric', 'HIV-exposed infant', 'full EPI series'],
    conditions: 'Respiratory tract infection, NOS',
    drugs: 'DPT, Hib, HepB, Measles, Oral polio, Cotrimoxazole',
    programs: 'HIV care',
    goodFor: 'Pediatric + immunization reasoning — complete childhood vaccine schedule plus infant cotrimoxazole prophylaxis.',
  },
  {
    name: 'Lelphas Wanjiru', uuid: 'dd88a67e-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 27, obs: 171, enc: 4, cond: 10, dx: 0, orders: 30,
    tags: ['advanced HIV/AIDS', 'multiple OIs'],
    conditions: 'Pneumocystis carinii pneumonia, Failure to thrive, Bronchopneumonia, Anemia, Diarrhea, Gastroenteritis, Malaria',
    drugs: 'RIPE (TB), full vaccine series, Cotrimoxazole, Ethambutol',
    programs: 'HIV care',
    goodFor: 'AIDS opportunistic-infection reasoning — dense OI comorbidity (PCP, failure to thrive, bronchopneumonia) in one chart.',
  },
  {
    name: 'Humprey Siromba', uuid: 'dd557008-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 49, obs: 294, enc: 10, cond: 4, dx: 0, orders: 29,
    tags: ['HIV on ART', 'acute infections', '2nd-densest obs'],
    conditions: 'Malaria, Pneumonia',
    drugs: 'Lamivudine, Lamivudine/nevirapine/stavudine, Nevirapine, Stavudine',
    programs: 'HIV care + Diabetes (label only)',
    goodFor: 'High-volume obs retrieval (294 obs) with intercurrent acute illness layered over chronic HIV care.',
  },
  {
    name: 'Lovich Atingo', uuid: 'dd74d1cd-1691-11df-97a5-7038c432aabf',
    sex: 'F', age: 39, obs: 240, enc: 10, cond: 0, dx: 0, orders: 41,
    tags: ['pharmacy-heavy', 'no problem list'],
    conditions: '— (none coded)',
    drugs: 'Lamivudine, Nevirapine, Stavudine, Isoniazid, Cotrimoxazole',
    programs: 'HIV care + Diabetes (label only)',
    goodFor: 'Contrast case — the most drug orders (41) with no coded conditions. Medication-list retrieval without a problem-list anchor.',
  },
  {
    name: 'Heldart Mbae', uuid: 'dd759516-1691-11df-97a5-7038c432aabf',
    sex: 'M', age: 7, obs: 260, enc: 9, cond: 7, dx: 0, orders: 27,
    tags: ['pediatric HIV', 'multi-condition'],
    conditions: 'Acute coryza, Dermatitis, Diarrhea, Dyspepsia, Malaria, Rash',
    drugs: 'Lamivudine, Nevirapine, Stavudine',
    programs: 'HIV care',
    goodFor: 'Pediatric multi-condition breadth — school-age child on ART with a stack of acute conditions.',
  },
];

// ── Landscape (below the fold). All non-voided.
const volumeRows = [
  ['Patients', '5,284', 'All active; none deceased; 100% have birthdate + gender'],
  ['Encounters', '14,317', '14,316 dated 2006; 1 synthetic 2026 row'],
  ['Observations', '427,874', '308K coded · 106K numeric · 14K datetime · 0 free-text'],
  ['Orders (all)', '44,508', '43,413 drug orders · 1,095 test orders'],
  ['Conditions (problem list)', '4,451', 'All clinical_status = ACTIVE; covers 47% of patients'],
  ['Encounter diagnoses', '914', 'Sparse — only 50 patients (0.9%)'],
  ['Program enrollments', '3,921', 'Two programs only (HIV, Diabetes)'],
  ['Visits', '306', 'Sparse — 51 patients (1%); most encounters are unwrapped'],
];

const coverageRows = [
  ['Observations', '100%', 'Every patient has obs (median band 50–149)'],
  ['Encounters', '100%', 'Median band 1–5 encounters'],
  ['Any order', '86.5%', 'Mostly drug orders'],
  ['Drug orders', '86.0%', 'ARVs dominate'],
  ['Programs', '66.2%', 'HIV and/or Diabetes enrollment'],
  ['Conditions', '47.4%', 'Coded problem list present for ~half'],
  ['Test orders', '14.4%', 'Mostly immunizations + chest X-ray'],
  ['Visits', '1.0%', 'Near-absent — encounters are not visit-wrapped'],
  ['Structured diagnoses', '0.9%', 'Near-absent — use conditions for problem lists'],
];

const obsHistogram = [
  { label: '0', value: 1 },
  { label: '1–9', value: 2 },
  { label: '10–49', value: 940 },
  { label: '50–149', value: 4158 },
  { label: '150–399', value: 183 },
];

const encHistogram = [
  { label: '1–2', value: 2541 },
  { label: '3–5', value: 2635 },
  { label: '6–10', value: 106 },
  { label: '11+', value: 2 },
];

const ageHistogram = [
  { label: '1–4', value: 360 },
  { label: '5–14', value: 440 },
  { label: '15–24', value: 479 },
  { label: '25–44', value: 3303 },
  { label: '45–64', value: 701 },
  { label: '65+', value: 1 },
];

const topObsRows = [
  ['Antiretroviral plan', '14,259'],
  ['Tuberculosis prophylaxis plan', '14,250'],
  ['Tuberculosis treatment plan', '14,244'],
  ['PCP prophylaxis plan', '14,240'],
  ['Temperature (C)', '14,220'],
  ['Weight (kg)', '14,173'],
  ['Pulse', '14,167'],
  ['Arterial O₂ saturation', '14,144'],
  ['Antiretroviral use', '13,960'],
  ['Overall drug adherence (last month)', '13,346'],
  ['Systolic / diastolic BP', '13,275 / 13,269'],
  ['Current WHO HIV stage', '13,004'],
];

const topConditionRows = [
  ['Acute coryza', '710'],
  ['Malaria', '509'],
  ['Peripheral neuropathy', '225'],
  ['Myalgia', '154'],
  ['Pneumonia', '141'],
  ['Dermatitis', '136'],
  ['Gastroenteritis', '132'],
  ['Respiratory tract infection, NOS', '119'],
  ['Urinary tract infection', '96'],
  ['Anemia / Peptic ulcer', '63 / 63'],
];

const topDrugRows = [
  ['Lamivudine', '9,913'],
  ['Stavudine', '9,781'],
  ['Nevirapine', '8,810'],
  ['Trimethoprim-sulfamethoxazole', '4,887'],
  ['Isoniazid', '1,972'],
  ['Efavirenz', '1,548'],
  ['DPT / Polio / HepB vaccines', '664 / 639 / 600'],
  ['Lopinavir/ritonavir (2nd-line)', '474'],
];

function Histogram({ title, data, unit }: { title: string; data: Array<{ label: string; value: number }>; unit?: string }) {
  const theme = useHostTheme();
  const max = Math.max(...data.map((d) => d.value), 1);
  const rowH = 28;
  const labelW = 74;
  const valueW = 64;
  const width = 520;
  const barMax = width - labelW - valueW;
  const height = data.length * rowH + 6;
  return (
    <svg role="img" aria-label={title} width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {data.map((d, i) => {
        const y = i * rowH + 3;
        const w = Math.max(2, (d.value / max) * barMax);
        return (
          <g key={d.label}>
            <text x={labelW - 8} y={y + 16} textAnchor="end" fontSize={11.5} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
              {d.label}
            </text>
            <rect x={labelW} y={y + 4} width={barMax} height={15} rx={3} fill={theme.fill.secondary} opacity={0.35} />
            <rect x={labelW} y={y + 4} width={w} height={15} rx={3} fill={theme.accent.primary} />
            <text x={labelW + barMax + 6} y={y + 16} textAnchor="end" fontSize={11.5} fill={theme.text.primary} style={{ fontFamily: 'inherit', fontWeight: 600 }}>
              {fmt(d.value)}
            </text>
          </g>
        );
      })}
      {unit ? (
        <text x={labelW} y={height - 1} fontSize={10} fill={theme.text.secondary} style={{ fontFamily: 'inherit' }}>
          {unit}
        </text>
      ) : null}
    </svg>
  );
}

function PatientCard({ p }: { p: Patient }) {
  const theme = useHostTheme();
  return (
    <Card>
      <CardHeader>
        <Row gap={8} wrap>
          <Text weight="semibold">{p.name}</Text>
          {p.flagship ? <Pill tone="success" active>flagship</Pill> : null}
          <Text size="small" tone="secondary">
            {p.sex} · {p.age}y (2006) · {fmt(p.obs)} obs / {p.enc} enc / {p.cond} cond / {p.dx} dx / {p.orders} orders
          </Text>
        </Row>
      </CardHeader>
      <CardBody>
        <Stack gap={6}>
          <Row gap={6} wrap>
            {p.tags.map((t) => (
              <Pill key={t} tone="info" active>{t}</Pill>
            ))}
          </Row>
          <Text size="small"><Text weight="semibold">Conditions:</Text> {p.conditions}</Text>
          <Text size="small"><Text weight="semibold">Drugs:</Text> {p.drugs}</Text>
          <Text size="small"><Text weight="semibold">Programs:</Text> {p.programs}</Text>
          <Text size="small" style={{ color: theme.text.secondary }}>
            <Text weight="semibold">Good for:</Text> {p.goodFor}
          </Text>
          <Code>{p.uuid}</Code>
        </Stack>
      </CardBody>
    </Card>
  );
}

export default function OpenMrsDemoDataProfile() {
  return (
    <Stack gap={20}>
      <Stack gap={8}>
        <Row gap={8} wrap>
          <Pill tone="info" active>Demo corpus profile</Pill>
          <Pill tone="info" active>OpenMRS 2.8 / RefApp 3.6.0</Pill>
          <Pill tone="success" active>5,284 patients</Pill>
          <Pill tone="success" active>HIV/TB care</Pill>
          <Pill tone="info" active>Measured 2026-05-29 (live DB)</Pill>
        </Row>
        <H1>OpenMRS Demo Data — Profile &amp; Validation Cohorts</H1>
        <Text tone="secondary">
          A grounded profile of the corpus loaded in this harness (the chartsearchai + querystore deployment runs against it). Every number comes from a live query against schema <Code>openmrs</Code>. The goal: landscape metrics, a candid richness/completeness read, and a curated set of data-rich patients spanning real clinical phenotypes for retrieval and reasoning validation.
        </Text>
      </Stack>

      <Grid columns={5} gap={12}>
        {heroStats.map((s) => (
          <Stat key={s.label} value={s.value} label={s.label} tone={s.tone} />
        ))}
      </Grid>

      <Callout tone="info" title="One-sentence framing">
        This is the classic OpenMRS / AMPATH <Text weight="semibold">HIV + TB care</Text> demo: <Text weight="semibold">wide but shallow and highly uniform</Text> — 5,284 patients, but most carry a near-identical battery of ~50–149 obs across 1–5 encounters, all frozen at a single 2006 time-slice. Clinical signal lives in <Code>obs</Code> + <Code>conditions</Code> + <Code>drug_orders</Code> + <Code>programs</Code>; visits and structured diagnoses are nearly absent.
      </Callout>

      <Callout tone="warning" title="Read the cohort labels before you trust them">
        Program <Text weight="semibold">names are misleading remap artifacts</Text>. The <Code>HIV Preventative Services (PEP/PrEP)</Code> program (3,100) is actually a population of HIV-<Text weight="semibold">positive</Text> patients on antiretroviral <Text weight="semibold">treatment</Text> — PEP/PrEP is prevention for HIV-negative people, so the name is clinically wrong. Worse, the <Code>Outpatient Diabetes Education Program</Code> (821) has <Text weight="semibold">zero</Text> diabetes-specific clinical data: 0 antidiabetic orders, 0 glucose/HbA1c observations, and 0 diabetes conditions exist anywhere in the corpus. Do not build a "diabetes" validation on it. Every cohort below is therefore labeled by <Text weight="semibold">clinical content</Text>, not program name.
      </Callout>

      <Divider />

      <H2>Phenotype Cohorts</H2>
      <Text tone="secondary">
        Cohorts you can actually test on, ordered by size. <Text weight="semibold">Backing</Text> = whether the label is supported by clinical content (<Code>Strong</Code>), present but thin (<Code>Thin</Code>), a misleading program name over real HIV-treatment data (<Code>Mislabeled</Code>), or a cosmetic enrollment label with no clinical footprint (<Code>None</Code>). Drug cohorts use case-insensitive name matching (heuristic; minor undercount on rare combination pills).
      </Text>
      <Table headers={['Cohort (by clinical content)', 'Patients', 'Backing', 'Evidence in the data']} rows={cohortRows} striped />
      <Row gap={8} wrap>
        <Pill tone="success" active>Strong — testable</Pill>
        <Pill tone="info" active>Thin — limited</Pill>
        <Pill tone="warning" active>Mislabeled / None — do not trust the name</Pill>
      </Row>

      <Divider />

      <H2>Curated Validation Patients</H2>
      <Text tone="secondary">
        Twelve data-rich patients chosen to span phenotypes and test-shapes — flagship retrieval baseline, multi-domain synthesis, treatment-experienced HIV, HIV/TB co-infection, multi-morbidity, ARV toxicity, pediatrics, and deliberate negative/contrast cases. Each <Code>uuid</Code> is the chart URL key. Open at <Code>/openmrs/spa/patient/&lt;uuid&gt;/chart</Code>.
      </Text>
      <Grid columns={2} gap={12}>
        {curatedPatients.map((p) => (
          <PatientCard key={p.uuid} p={p} />
        ))}
      </Grid>

      <Callout tone="success" title="How to use these for validation">
        <Stack gap={4}>
          <Text size="small"><Text weight="semibold">Retrieval recall:</Text> Zabella / Humprey (densest obs) — does the chart-builder surface the right slice for a focused question?</Text>
          <Text size="small"><Text weight="semibold">Cross-source synthesis:</Text> Aloice (conditions + 36 diagnoses + ART + TB) — does retrieval reach problem list, diagnoses, and meds together?</Text>
          <Text size="small"><Text weight="semibold">Multi-condition reasoning:</Text> Rahima / Zacharia / Lelphas — dense problem lists, including drug→adverse-effect (Stavudine → neuropathy).</Text>
          <Text size="small"><Text weight="semibold">Negative / hallucination guard:</Text> Zacharia (10 conditions, 0 drugs) — a faithful "what meds?" must answer none.</Text>
          <Text size="small"><Text weight="semibold">Temporal / causal:</Text> Timoty (2nd-line ART after documented regimen failure) — "why was therapy changed?"</Text>
          <Text size="small"><Text weight="semibold">Pediatrics:</Text> Sospeta / Heldart — infant EPI series and school-age ART.</Text>
        </Stack>
      </Callout>

      <Divider />

      <H2>Shape &amp; Completeness</H2>
      <Text tone="secondary">
        The corpus is broad but uniform: the breadth that makes it useful for validation is across <Text weight="semibold">cohort membership</Text>, not per-patient depth. Age is derived from real birthdates at the 2006 care era (the encounters' actual year); the patients are predominantly working-age adults with a meaningful pediatric tail.
      </Text>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Observations per patient</CardHeader>
          <CardBody><Histogram title="Observations per patient" data={obsHistogram} unit="patients (4,158 cluster at 50–149 — templated)" /></CardBody>
        </Card>
        <Card>
          <CardHeader>Encounters per patient</CardHeader>
          <CardBody><Histogram title="Encounters per patient" data={encHistogram} unit="patients (1–5 is the norm)" /></CardBody>
        </Card>
        <Card>
          <CardHeader>Age distribution (at 2006)</CardHeader>
          <CardBody><Histogram title="Age bands at 2006" data={ageHistogram} unit="patients · 66% F / 34% M" /></CardBody>
        </Card>
        <Card>
          <CardHeader>Entity coverage (% of 5,284 patients)</CardHeader>
          <CardBody>
            <Table headers={['Entity', 'Coverage', 'Note']} rows={coverageRows} striped />
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="warning" title="Data caveats that affect validation design">
        <Stack gap={4}>
          <Text size="small"><Text weight="semibold">Single time-slice:</Text> all clinical events are 2006 (one synthetic 2026 encounter aside). No longitudinal trends — vitals/labs are point-in-time, not series.</Text>
          <Text size="small"><Text weight="semibold">Multilingual concepts (CIEL):</Text> the dictionary carries French/Spanish/Russian/Khmer/Haitian-Creole names; the locale-preferred name is often not English. Retrieval and display must tolerate non-English concept names.</Text>
          <Text size="small"><Text weight="semibold">Shallow per-patient depth:</Text> ~50–149 obs, 1–5 encounters each. Good for breadth/coverage tests; weak for deep longitudinal-history tests.</Text>
          <Text size="small"><Text weight="semibold">Near-zero diagnoses &amp; visits:</Text> use <Code>conditions</Code> (47% coverage) for problem lists; encounter-diagnoses (0.9%) and visits (1%) are too sparse to test broadly.</Text>
          <Text size="small"><Text weight="semibold">Obs values:</Text> 72% coded, 25% numeric, 0 free-text; dates are clean (427,869 / 427,874 within 1990–2020; 5 stray sentinels).</Text>
        </Stack>
      </Callout>

      <Divider />

      <H2>Clinical Content</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Top observations (by frequency)</CardHeader>
          <CardBody><Table headers={['Concept', 'Obs']} rows={topObsRows} striped /></CardBody>
        </Card>
        <Card>
          <CardHeader>Top conditions (coded problem list)</CardHeader>
          <CardBody><Table headers={['Condition', 'Patients']} rows={topConditionRows} striped /></CardBody>
        </Card>
        <Card>
          <CardHeader>Top drugs ordered</CardHeader>
          <CardBody><Table headers={['Drug', 'Orders']} rows={topDrugRows} striped /></CardBody>
        </Card>
        <Card>
          <CardHeader>Programs · tests · encounters</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small"><Text weight="semibold">Programs:</Text> HIV "PEP/PrEP" (3,100; really HIV treatment) · Diabetes Education (821; label only).</Text>
              <Text size="small"><Text weight="semibold">Tests:</Text> Immunizations 866 · Chest X-ray 172 · VDRL 33 · HIV DNA PCR 15 · HIV EIA 9.</Text>
              <Text size="small"><Text weight="semibold">Encounter types:</Text> Adult Visit 13,369 · Check In 941 · (Attachment Upload 6).</Text>
              <Text size="small"><Text weight="semibold">Visit types (only 306):</Text> Facility 84 · OPD 79 · Group Session 72 · Home 71.</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Landscape — entity volume</H2>
      <Table headers={['Entity', 'Count (non-voided)', 'Notes']} rows={volumeRows} striped />

      <Callout tone="info" title="Provenance & how to refresh">
        Source: feature 002 transform of <Code>large-demo-data-2-7-0</Code> → Platform 2.8 / RefApp 3.6.0 (<Code>artifacts/share/openmrs-2.8-refapp-demo-5284-patients.provenance.json</Code>). Measured 2026-05-29 by direct SQL against container <Code>harness-openmrs-db</Code>, schema <Code>openmrs</Code>. To refresh, re-run the profiling queries (volume / coverage / cohort-backing / per-patient stats) and update the arrays above. Re-verify the two backing checks — antidiabetic orders and glucose obs among the Diabetes cohort, ART + WHO-stage signals among the HIV cohort — if the corpus is ever re-transformed.
      </Callout>
    </Stack>
  );
}
