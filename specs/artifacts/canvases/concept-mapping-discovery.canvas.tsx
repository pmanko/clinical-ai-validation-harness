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

// ----- B5 deep dive: obs → typed-table promotion rules ---------------------
//
// The four typed tables (allergy, conditions, orders, drug_order) all have
// 0 rows in legacy_27_raw — every clinical event lives in obs, dispatched
// by concept class. Below: the proposed promotion rules, the obs rows each
// rule would consume, and the rows that must stay in obs.

// Total obs rows by question-side (concept_class × datatype). 476,973 total.
const obsQuestionDistribution = [
  { question_class: 'Question',  question_dt: 'Coded',   n_obs: 246365, distinct_q: 60,  promotion_intent: 'mostly STAYS_IN_OBS; subset → drug_order via value_coded class=Drug; subset → conditions via question 6042 (PROBLEM ADDED)' },
  { question_class: 'Test',      question_dt: 'Numeric', n_obs: 104730, distinct_q: 21,  promotion_intent: 'STAYS_IN_OBS — vitals are observations, not orders. Drives FHIR Observation generation in the read-side, not table promotion.' },
  { question_class: 'Question',  question_dt: 'Boolean', n_obs: 85116,  distinct_q: 29,  promotion_intent: 'STAYS_IN_OBS; subset → allergy (Boolean YES on questions 6011/1083/6012). Booleans use value_coded → YES (1065) / NO (1066) — no value_boolean column in either 2.7 OR 2.8.' },
  { question_class: 'Finding',   question_dt: 'Coded',   n_obs: 19917,  distinct_q: 17,  promotion_intent: 'STAYS_IN_OBS — findings ≠ diagnoses; semantically distinct in CIEL.' },
  { question_class: 'Misc',      question_dt: 'Date',    n_obs: 14214,  distinct_q: 1,   promotion_intent: 'STAYS_IN_OBS (single question: RETURN VISIT DATE 5096). Could feed appointment/visit-planning later.' },
  { question_class: 'Diagnosis', question_dt: 'Coded',   n_obs: 4452,   distinct_q: 2,   promotion_intent: 'MIXED — question 6042 PROBLEM ADDED (3,642 rows) → conditions; the other 810 rows stay in obs.' },
  { question_class: 'Test',      question_dt: 'Coded',   n_obs: 1120,   distinct_q: 5,   promotion_intent: 'NEEDS_REVIEW — lab-order shapes (IMMUNIZATIONS ORDERED, X-RAY, VDRL, HIV PCR). Likely synthesize test_order rows.' },
  { question_class: 'Finding',   question_dt: 'Numeric', n_obs: 655,    distinct_q: 1,   promotion_intent: 'STAYS_IN_OBS' },
  { question_class: 'Question',  question_dt: 'Numeric', n_obs: 299,    distinct_q: 9,   promotion_intent: 'STAYS_IN_OBS' },
  { question_class: 'Question',  question_dt: 'Date',    n_obs: 73,     distinct_q: 2,   promotion_intent: 'STAYS_IN_OBS' },
  { question_class: 'Question',  question_dt: 'Datetime', n_obs: 30,    distinct_q: 1,   promotion_intent: 'STAYS_IN_OBS' },
  { question_class: 'ConvSet',   question_dt: 'N/A',     n_obs: 2,      distinct_q: 2,   promotion_intent: 'GROUPING — obs_group header rows; preserve via obs_group_id linkage on children.' },
];

// Value-side distribution (rows where value_coded is set, grouped by the
// CLASS of the answer concept). This is the primary promotion signal — the
// answer's class tells us what kind of clinical event it is.
const obsValueDistribution = [
  { value_class: 'Misc',            n_obs: 263963, distinct_v: 53,  what_it_is: 'YES/NO/NONE/CONTINUE-style answers',                  promotion: 'STAYS_IN_OBS' },
  { value_class: 'Drug',            n_obs: 43412,  distinct_v: 30,  what_it_is: 'Coded drug answers (ARVs, antibiotics, vaccines)',    promotion: 'PROMOTE → drug_order (1 row per obs)' },
  { value_class: 'Misc Order',      n_obs: 18477,  distinct_v: 6,   what_it_is: 'Treatment-plan status codes (CONTINUE / STOP / START / CHANGE / INPATIENT)', promotion: 'STAYS_IN_OBS — these are plan-status answers, not actionable orders.' },
  { value_class: 'ConvSet',         n_obs: 14476,  distinct_v: 11,  what_it_is: 'Convenience-set group headers',                       promotion: 'GROUPING — keep' },
  { value_class: 'Diagnosis',       n_obs: 4652,   distinct_v: 117, what_it_is: 'Coded diagnoses',                                     promotion: 'MIXED — 3,642 under question 6042 PROBLEM ADDED → conditions; remainder (REASON-STOPPED patterns, CHILDS CURRENT HIV STATUS) STAYS_IN_OBS.' },
  { value_class: 'LabSet',          n_obs: 4068,   distinct_v: 2,   what_it_is: 'Lab-test grouping concepts',                          promotion: 'STAYS_IN_OBS (grouping)' },
  { value_class: 'Test',            n_obs: 4053,   distinct_v: 15,  what_it_is: 'Coded lab-test result categories',                    promotion: 'STAYS_IN_OBS' },
  { value_class: 'Finding',         n_obs: 2902,   distinct_v: 53,  what_it_is: 'Coded clinical findings (non-diagnosis)',             promotion: 'STAYS_IN_OBS' },
  { value_class: 'MedSet',          n_obs: 435,    distinct_v: 4,   what_it_is: 'Medication-set grouping concepts',                    promotion: 'STAYS_IN_OBS' },
  { value_class: 'Symptom/Finding', n_obs: 291,    distinct_v: 13,  what_it_is: '',                                                    promotion: 'STAYS_IN_OBS' },
  { value_class: 'Anatomy',         n_obs: 149,    distinct_v: 1,   what_it_is: 'Body-site references',                                promotion: 'STAYS_IN_OBS' },
  { value_class: 'Symptom',         n_obs: 88,     distinct_v: 13,  what_it_is: '',                                                    promotion: 'STAYS_IN_OBS' },
];

// Concrete proposed promotion rules. Each rule is what would emit one or
// more typed rows for each matching obs row. Ordered most-impactful first.
type PromotionRule = {
  id: string;
  target_table: 'drug_order' | 'conditions' | 'allergy' | 'test_order';
  selector: string;            // human-readable predicate
  selector_sql: string;        // executable SELECT against legacy_27_raw
  rows_promoted: number;       // count of obs that would be consumed
  field_mapping: Array<{ target: string; source: string; note?: string }>;
  open_questions: string[];    // anything that needs a review decision
};

const promotionRules: PromotionRule[] = [
  {
    id: 'P1',
    target_table: 'drug_order',
    selector: 'obs rows where value_coded.class = Drug. Top: question 1088 CURRENT ANTIRETROVIRAL DRUGS USED FOR TREATMENT (30,507 obs); answers like 628 LAMIVUDINE (9,913), 625 STAVUDINE (9,781), 631 NEVIRAPINE (8,810), 916 TRIMETHOPRIM AND SULFAMETHOXAZOLE (4,887), 656 ISONIAZID (1,972), 633 EFAVIRENZ (1,548), vaccines (DTP/Polio/HepB/Hib/Measles).',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS drug_concept_id, o.obs_datetime
FROM legacy_27_raw.obs o
JOIN legacy_27_raw.concept c ON c.concept_id = o.value_coded
JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
WHERE cc.name = 'Drug' AND o.voided = 0`,
    rows_promoted: 43412,
    field_mapping: [
      { target: 'drug_order.patient_id',      source: 'obs.person_id' },
      { target: 'drug_order.encounter_id',    source: 'obs.encounter_id' },
      { target: 'drug_order.concept_id',      source: 'lookup(obs.value_coded → CIEL UUID)',  note: 'rebind per the B1 bridge rule' },
      { target: 'drug_order.drug_inventory_id', source: 'NULL (no drug rows referenced from obs.value_drug in this dump)' },
      { target: 'drug_order.start_date',      source: 'obs.obs_datetime' },
      { target: 'drug_order.orderer',         source: 'obs.creator', note: 'best-available proxy; encounter_provider could refine' },
      { target: 'drug_order.dose / units / frequency / duration', source: 'NULL', note: 'not present in legacy obs — leave null; flag in coverage_sample' },
      { target: 'drug_order.urgency',         source: "'ROUTINE'" },
      { target: 'drug_order.uuid',            source: 'fresh UUID v4' },
    ],
    open_questions: [
      'Vaccines (measles, polio, etc.) — are these correctly drug_order rows, or should they emit an Immunization-shaped resource? In FHIR they are MedicationAdministration / Immunization, not MedicationRequest.',
      'Should we group same-drug repeats per patient into a single drug_order with effective-date span, or keep one row per obs? Per-obs is simpler and traceable.',
      'No dose/frequency present — does this fail any 2.8 NOT NULL constraints? Verify against refapp_28_clean DDL.',
    ],
  },
  {
    id: 'P2',
    target_table: 'conditions',
    selector: 'obs rows whose QUESTION is 6042 PROBLEM ADDED (semantic anchor for "the clinician recorded a new diagnosis on this visit"). 3,642 obs / 114 distinct diagnoses.',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS dx_concept_id, o.obs_datetime
FROM legacy_27_raw.obs o
WHERE o.concept_id = 6042 AND o.value_coded IS NOT NULL AND o.voided = 0`,
    rows_promoted: 3642,
    field_mapping: [
      { target: 'conditions.patient_id',     source: 'obs.person_id' },
      { target: 'conditions.encounter_id',   source: 'obs.encounter_id' },
      { target: 'conditions.condition_coded', source: 'lookup(obs.value_coded → CIEL UUID)' },
      { target: 'conditions.clinical_status', source: "'ACTIVE'", note: 'PROBLEM ADDED implies active at recording time; revisit if a corresponding PROBLEM RESOLVED concept exists.' },
      { target: 'conditions.onset_date',     source: 'obs.obs_datetime' },
      { target: 'conditions.date_created',   source: 'obs.date_created' },
      { target: 'conditions.creator',        source: 'obs.creator' },
      { target: 'conditions.uuid',           source: 'fresh UUID v4' },
    ],
    open_questions: [
      'Does the 2.7 dump ever record "PROBLEM RESOLVED"? If yes, those would close out the condition; if no, every promoted condition stays ACTIVE forever in the new model.',
      'CHILDS CURRENT HIV STATUS (5303, 629 obs) has Diagnosis-class answers (HIV positive/negative) — should this also promote to conditions? Argument FOR: HIV status is a condition. Argument AGAINST: it is repeated screening, not a problem-list entry. Default: STAYS_IN_OBS pending review.',
    ],
  },
  {
    id: 'P3',
    target_table: 'allergy',
    selector: 'obs rows on the three explicit allergy-Boolean questions (6011 ALLERGY TO PENICILLIN, 6012 ALLERGY TO SULFA, 1083 ALLERGY TO OTHER MEDICINE) where value_coded = 1065 (YES). NO rows do NOT promote — absence-of-allergy is not an allergy row.',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS allergen_question, o.obs_datetime
FROM legacy_27_raw.obs o
WHERE o.concept_id IN (6011, 6012, 1083) AND o.value_coded = 1065 AND o.voided = 0`,
    rows_promoted: 7, // 3 + 2 + 2 — extremely sparse in this demo
    field_mapping: [
      { target: 'allergy.patient_id',     source: 'obs.person_id' },
      { target: 'allergy.coded_allergen', source: 'rebind by allergen-question-concept: 6011 → penicillin allergen concept; 6012 → sulfa; 1083 → "other medication" allergen concept' },
      { target: 'allergy.allergen_type',  source: "'DRUG'", note: 'all three legacy questions are drug-allergy flavor' },
      { target: 'allergy.severity_concept_id', source: 'NULL', note: 'not recorded in legacy boolean form' },
      { target: 'allergy.encounter_id',   source: 'obs.encounter_id' },
      { target: 'allergy.date_created',   source: 'obs.date_created' },
      { target: 'allergy.uuid',           source: 'fresh UUID v4' },
    ],
    open_questions: [
      'Map each of the 3 allergen-flavored question concepts to a specific CIEL allergen concept — needs human pick (PENICILLIN as substance, SULFA as substance, etc.).',
      'Should the patient.allergy_status flag flip to See-list when any allergy row is promoted? Or leave as default?',
    ],
  },
  {
    id: 'P4',
    target_table: 'test_order',
    selector: 'obs rows whose QUESTION class is Test and datatype is Coded (lab/imaging orders): question 984 IMMUNIZATIONS ORDERED (891), 12 X-RAY, CHEST (172), 299 VDRL (33), 1030 HIV DNA PCR QUAL (15), 1042 HIV ENZYME IMMUNOASSAY (9).',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS test_concept, o.value_coded AS result_coded, o.obs_datetime
FROM legacy_27_raw.obs o
JOIN legacy_27_raw.concept c ON c.concept_id = o.concept_id
JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd ON cd.concept_datatype_id = c.datatype_id
WHERE cc.name = 'Test' AND cd.name = 'Coded' AND o.voided = 0`,
    rows_promoted: 1120,
    field_mapping: [
      { target: 'orders / test_order.patient_id',  source: 'obs.person_id' },
      { target: 'test_order.concept_id',           source: 'lookup(obs.concept_id → CIEL UUID)', note: 'this is the TEST concept, not the result' },
      { target: 'test_order.encounter_id',         source: 'obs.encounter_id' },
      { target: 'test_order.date_activated',       source: 'obs.obs_datetime', note: 'no order/result split in legacy; assume order-and-result coincident' },
      { target: 'test_order.urgency',              source: "'ROUTINE'" },
      { target: 'test_order.order_action',         source: "'NEW'" },
      { target: 'obs.value_coded (result)',        source: 'preserved as obs row pointing to the new test_order via obs.order_id' },
    ],
    open_questions: [
      'Whether to promote IMMUNIZATIONS ORDERED (891 obs) — these are technically immunization records, not lab tests. Could split off to a different target.',
      'Should we synthesize a paired (test_order + result obs) pattern, or just promote the order and keep the existing obs row as the result with an order_id linkback?',
      'orders.order_type_id — needs mapping per concept class. 2.8 ships a test_order_type by default; verify ID against refapp_28_clean.',
    ],
  },
];

const stayInObsCases = [
  { case: 'Coded YES/NO answers (value_class=Misc)',                          n: 263963, why: 'Free-form answers to boolean/coded questions; semantically observations, not events. Top: 1107 NONE (114,070), 1066 NO (66,679), 1065 YES (39,776).' },
  { case: 'Numeric vital signs (Test+Numeric questions)',                     n: 104730, why: 'TEMPERATURE (5088), WEIGHT (5089), PULSE (5087), BLOOD OXYGEN SATURATION (5092) etc. These are observations by definition; FHIR Observation is the read-side projection.' },
  { case: 'Boolean questions (Q+Boolean) other than the 3 allergy questions', n: 85109,  why: 'YES/NO survey answers (ANTIRETROVIRAL USE, NEW COMPLAINTS, SCHEDULED VISIT). Stay as obs.' },
  { case: 'Treatment-plan status codes (value_class=Misc Order)',             n: 18477,  why: 'CONTINUE / STOP / START / CHANGE — answer values describing plan changes, not actionable orders.' },
  { case: 'ConvSet / LabSet / MedSet grouping rows',                          n: 18979,  why: 'obs_group headers. Preserve via obs_group_id linkage; do not flatten into typed tables.' },
  { case: 'Coded Diagnosis answers NOT under question 6042 PROBLEM ADDED',    n: 1010,   why: 'REASON ARV/TB/PCP/CRYPTOCOCCAL STOPPED patterns and similar — diagnosis-coded values used as reasons, not new conditions.' },
  { case: 'RETURN VISIT DATE (5096)',                                         n: 14214,  why: 'Single Misc+Date question; could feed an Appointment resource later but no 2.8 target table needed.' },
];

const promotionSummaryTotals = {
  total_obs_legacy: 476973,
  promoted_drug_order: 43412,
  promoted_conditions: 3642,
  promoted_allergy: 7,
  promoted_test_order: 1120,
  total_promoted: 48181,
  pct_promoted: '10.1%',
  stays_in_obs: 428792,
  pct_stays: '89.9%',
};

function PromotionRulesPanel() {
  return (
    <Card>
      <CardHeader>
        <H2>Proposed obs → typed-table promotion rules</H2>
        <Text>
          One rule per target table. Each rule consumes a well-bounded slice of obs and emits typed rows; the
          rest of obs (89.9%) stays as obs (vitals, survey answers, plan-status codes, groupings).
        </Text>
      </CardHeader>
      <CardBody>
        <Stack gap={14}>
          <Callout variant="info">
            <Text>
              The four promotion rules together consume <strong>{promotionSummaryTotals.total_promoted.toLocaleString()}</strong> obs rows
              ({promotionSummaryTotals.pct_promoted} of the legacy total of {promotionSummaryTotals.total_obs_legacy.toLocaleString()}).
              The remaining {promotionSummaryTotals.stays_in_obs.toLocaleString()} obs ({promotionSummaryTotals.pct_stays}) stay
              in obs unchanged (after concept-id rebind).
            </Text>
          </Callout>

          {promotionRules.map((r) => (
            <Card key={r.id}>
              <CardHeader>
                <Row gap={8}>
                  <Pill variant={r.target_table === 'drug_order' || r.target_table === 'conditions' ? 'success' : 'warning'}>{r.id}</Pill>
                  <Pill variant="subtle">→ {r.target_table}</Pill>
                  <Pill variant="subtle">{r.rows_promoted.toLocaleString()} rows</Pill>
                </Row>
              </CardHeader>
              <CardBody>
                <Stack gap={10}>
                  <Text><strong>Selector.</strong> {r.selector}</Text>
                  <Code language="sql">{r.selector_sql}</Code>
                  <H3>Field mapping</H3>
                  <Table
                    columns={[
                      { key: 'target', header: 'target column' },
                      { key: 'source', header: 'source' },
                      { key: 'note', header: 'note', optional: true },
                    ]}
                    rows={r.field_mapping}
                  />
                  <H3>Open questions for review</H3>
                  <ul>
                    {r.open_questions.map((q, i) => <li key={i}><Text>{q}</Text></li>)}
                  </ul>
                </Stack>
              </CardBody>
            </Card>
          ))}
        </Stack>
      </CardBody>
    </Card>
  );
}

function ObsQuestionDistributionPanel() {
  return (
    <Card>
      <CardHeader>
        <H3>obs by (question concept class × datatype)</H3>
        <Text>The full 476,973 obs accounted for by the class+datatype of the QUESTION concept. promotion_intent describes whether that slice is consumed by a rule or stays in obs.</Text>
      </CardHeader>
      <CardBody>
        <Table
          columns={[
            { key: 'question_class', header: 'question class' },
            { key: 'question_dt',    header: 'datatype' },
            { key: 'n_obs',          header: 'n obs' },
            { key: 'distinct_q',     header: 'distinct questions' },
            { key: 'promotion_intent', header: 'promotion intent' },
          ]}
          rows={obsQuestionDistribution}
        />
      </CardBody>
    </Card>
  );
}

function ObsValueDistributionPanel() {
  return (
    <Card>
      <CardHeader>
        <H3>obs.value_coded by class of the ANSWER concept</H3>
        <Text>Where the answer concept lives in the class hierarchy. This is the primary signal for promotion: value_class=Drug → drug_order, etc.</Text>
      </CardHeader>
      <CardBody>
        <Table
          columns={[
            { key: 'value_class', header: 'answer class' },
            { key: 'n_obs',       header: 'n obs' },
            { key: 'distinct_v',  header: 'distinct values' },
            { key: 'what_it_is',  header: 'what it represents' },
            { key: 'promotion',   header: 'promotion decision' },
          ]}
          rows={obsValueDistribution}
        />
      </CardBody>
    </Card>
  );
}

function StayInObsPanel() {
  return (
    <Card>
      <CardHeader>
        <H3>What stays in obs (after concept-id rebind)</H3>
        <Text>Rows the promotion rules deliberately do NOT consume. Each gets a one-line justification so the review can accept or contest it.</Text>
      </CardHeader>
      <CardBody>
        <Table
          columns={[
            { key: 'case', header: 'case' },
            { key: 'n',    header: 'n obs' },
            { key: 'why',  header: 'why it stays in obs' },
          ]}
          rows={stayInObsCases}
        />
      </CardBody>
    </Card>
  );
}

function PromotionGlobalQuestionsPanel() {
  return (
    <Card>
      <CardHeader>
        <H2>Cross-cutting decisions for review</H2>
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <Callout variant="warning">
            <Text>
              <strong>Q1 — obs preservation alongside promotion.</strong> When a Drug obs becomes a drug_order row,
              do we DELETE the obs (single source of truth) or KEEP the obs with a link via obs.order_id?
              The 2.8 RefApp UI reads from typed tables; chartsearchai indexes obs. Keeping both costs disk + indexing
              effort; dropping obs loses the "this was originally recorded as an answer to question X" provenance.
              Default proposal: KEEP both, link via obs.order_id (already a column in 2.7).
            </Text>
          </Callout>
          <Callout variant="warning">
            <Text>
              <strong>Q2 — fresh UUIDs vs deterministic UUIDs on promoted rows.</strong> Random UUID v4 breaks
              reproducibility across two transform runs against the same input. Deterministic UUID v5 derived
              from (obs.uuid, target_table) preserves reproducibility. Default proposal: UUID v5 with namespace
              "harness-002-promotion".
            </Text>
          </Callout>
          <Callout variant="warning">
            <Text>
              <strong>Q3 — Vaccines as drug_order vs immunization-shaped resource.</strong> Among the 43,412 Drug-class
              answers, ~2,400 are vaccines (DTP, polio, HepB, Hib, measles). In FHIR R4 these are Immunization, not
              MedicationRequest. The 2.8 OpenMRS schema does not have an immunization table by default; drug_order is
              the canonical home. Default proposal: emit all Drug-class answers as drug_order regardless of vaccine
              status; flag vaccines via an attribute or a class hint so the FHIR layer can re-project them as
              Immunization at read time.
            </Text>
          </Callout>
          <Callout variant="warning">
            <Text>
              <strong>Q4 — orderer field on drug_order / test_order.</strong> Legacy obs has creator (user_id) but
              no provider linkage on the obs itself; encounter_provider holds the encounter-level provider list.
              Best-available orderer for a promoted order is the encounter_provider for the matching encounter.
              Default proposal: prefer encounter_provider (single provider per encounter for this dataset), fall
              back to obs.creator.
            </Text>
          </Callout>
          <Callout variant="warning">
            <Text>
              <strong>Q5 — coverage_sample population.</strong> The promoted rows need entries in the per-bucket
              coverage_sample artifact (per FR-015) so reviewers can spot-check that the round-trip preserves
              clinical meaning. Default proposal: per rule, draw 5 records per concept_class × datatype × value_class
              cohort using a deterministic sampler_seed (recorded in run_manifest).
            </Text>
          </Callout>
        </Stack>
      </CardBody>
    </Card>
  );
}

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

      <H1>B5 deep dive — obs → typed-table promotion</H1>
      <Text>
        Four rules, four target tables. Together they consume <strong>{promotionSummaryTotals.total_promoted.toLocaleString()}</strong> obs
        rows ({promotionSummaryTotals.pct_promoted} of the 476,973 legacy total). The remaining 89.9% stay
        in obs unchanged after concept-id rebind. Every cell below is sourced from a live query against
        legacy_27_raw — tweak the rules in this file, then re-run the corresponding selector_sql to confirm
        the count before accepting.
      </Text>

      <Grid columns={4} gap={12}>
        <Stat label="Total obs (legacy)" value={promotionSummaryTotals.total_obs_legacy.toLocaleString()} />
        <Stat label="Promoted" value={`${promotionSummaryTotals.total_promoted.toLocaleString()} (${promotionSummaryTotals.pct_promoted})`} />
        <Stat label="→ drug_order" value={promotionSummaryTotals.promoted_drug_order.toLocaleString()} />
        <Stat label="→ conditions" value={promotionSummaryTotals.promoted_conditions.toLocaleString()} />
      </Grid>

      <ObsQuestionDistributionPanel />
      <ObsValueDistributionPanel />

      <Divider />

      <PromotionRulesPanel />

      <Divider />

      <StayInObsPanel />

      <Divider />

      <PromotionGlobalQuestionsPanel />

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
