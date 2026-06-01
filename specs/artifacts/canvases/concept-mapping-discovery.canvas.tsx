import {
  BarChart,
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
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  computeDAGLayout,
  useHostTheme,
} from 'cursor/canvas';

// Canvas: feature 002 / M2-A concept mapping & transformation — 2026-05-14.
// All counts come from live SELECT COUNT(*) queries against the running
// harness MariaDB (legacy_27_raw + the CIEL-loaded openmrs DB on RefApp 3.6.0).

// =========================================================================
// 1. HERO NUMBERS
// =========================================================================

const heroStats = [
  { value: '5,284',   label: 'patients (legacy 2.7 dump)',                  tone: 'info' as const },
  { value: '476,973', label: 'obs rows to transform',                       tone: 'info' as const },
  { value: '457/457', label: 'concepts bridgeable to CIEL (100%)',          tone: 'success' as const },
  { value: '48,960',  label: 'obs → typed-table promotions (measured 5D)', tone: 'success' as const },
  { value: '10.3%',   label: 'promoted; 89.7% stays in obs',                tone: 'info' as const },
  { value: 'loaded',  label: 'live in the canonical openmrs schema via dlt + promote', tone: 'success' as const },
];

// =========================================================================
// 2. TRANSFORM PIPELINE DIAGRAM (SVG via DAG layout)
//    Shows the end-to-end shape: source → rebind → promote/keep → target
// =========================================================================

const pipelineNodes: Record<string, { label: string; sub?: string; accent?: 'source' | 'transform' | 'target' | 'side' }> = {
  legacy_concepts:   { label: 'legacy_27_raw.concept',        sub: '2,528 rows · 0 ref maps', accent: 'source' },
  legacy_obs:        { label: 'legacy_27_raw.obs',            sub: '476,973 rows',            accent: 'source' },
  rebind:            { label: 'concept-id rebind',            sub: "RPAD(id,36,'A')",          accent: 'transform' },
  classify:          { label: 'classify by class/datatype',   sub: 'P1-P4 selectors',          accent: 'transform' },
  drug_order:        { label: 'drug_order',                   sub: '43,412 rows (measured)', accent: 'target' },
  conditions:        { label: 'conditions',                   sub: '4,451 rows (measured)', accent: 'target' },
  test_order:        { label: 'test_order',                   sub: '1,095 rows (measured)', accent: 'target' },
  allergy:           { label: 'allergy',                      sub: '2 rows (measured)',     accent: 'target' },
  obs_clean:         { label: 'obs (clean)',                  sub: '428,013 rows (measured)', accent: 'target' },
  orders_parent:     { label: 'orders (parent of drug/test)', sub: '44,507 rows · order_id = obs.obs_id', accent: 'target' },
  ciel_loaded:       { label: 'openmrs.concept (CIEL)',       sub: '358,026 imported',         accent: 'side' },
};

const pipelineEdges: Array<[string, string]> = [
  ['legacy_obs', 'rebind'],
  ['legacy_concepts', 'rebind'],
  ['ciel_loaded', 'rebind'],
  ['rebind', 'classify'],
  ['classify', 'orders_parent'],
  ['orders_parent', 'drug_order'],
  ['orders_parent', 'test_order'],
  ['classify', 'conditions'],
  ['classify', 'allergy'],
  ['classify', 'obs_clean'],
];

function TransformPipelineDiagram() {
  const theme = useHostTheme();
  const nodeWidth = 200;
  const nodeHeight = 56;
  const layout = computeDAGLayout({
    nodes: Object.keys(pipelineNodes).map((id) => ({ id })),
    edges: pipelineEdges.map(([from, to]) => ({ from, to })),
    direction: 'horizontal',
    nodeWidth,
    nodeHeight,
    rankGap: 80,
    nodeGap: 16,
    padding: 28,
  });

  const accentFill: Record<string, string> = {
    source:    theme.fill.tertiary,
    transform: theme.fill.brand ?? theme.fill.tertiary,
    target:    theme.fill.tertiary,
    side:      theme.fill.tertiary,
  };
  const accentStroke: Record<string, string> = {
    source:    theme.stroke.secondary,
    transform: theme.stroke.brand ?? theme.stroke.primary,
    target:    theme.stroke.success ?? theme.stroke.secondary,
    side:      theme.stroke.tertiary ?? theme.stroke.secondary,
  };

  return (
    <svg
      role="img"
      aria-label="2.7 → 2.8 transform pipeline"
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height + 8}`}
      style={{ display: 'block' }}
    >
      <defs>
        <marker id="pipe-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {layout.edges.map((edge, i) => {
        const dx = Math.max(20, (edge.targetX - edge.sourceX) / 2);
        const d = `M ${edge.sourceX} ${edge.sourceY} C ${edge.sourceX + dx} ${edge.sourceY}, ${edge.targetX - dx} ${edge.targetY}, ${edge.targetX} ${edge.targetY}`;
        return (
          <path
            key={i}
            d={d}
            stroke={theme.stroke.secondary}
            strokeWidth={1.4}
            fill="none"
            markerEnd="url(#pipe-arrow)"
          />
        );
      })}

      {layout.nodes.map((n) => {
        const def = pipelineNodes[n.id];
        const accent = def.accent ?? 'source';
        return (
          <g key={n.id}>
            <rect
              x={n.x - nodeWidth / 2}
              y={n.y - nodeHeight / 2}
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={accentFill[accent]}
              stroke={accentStroke[accent]}
              strokeWidth={accent === 'transform' ? 1.6 : 1}
            />
            <text
              x={n.x}
              y={n.y - 4}
              textAnchor="middle"
              fontSize={12}
              fontWeight={600}
              fill={theme.text.primary}
              style={{ fontFamily: 'inherit' }}
            >
              {def.label}
            </text>
            {def.sub && (
              <text
                x={n.x}
                y={n.y + 14}
                textAnchor="middle"
                fontSize={10.5}
                fill={theme.text.tertiary}
                style={{ fontFamily: 'inherit' }}
              >
                {def.sub}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// =========================================================================
// 3. PROMOTION FLOW DIAGRAM (where every obs row goes)
//    Centerpiece visual: 476,973 obs broken down into promotion buckets
// =========================================================================

function PromotionFlowDiagram() {
  const theme = useHostTheme();
  const W = 980;
  const H = 360;
  const left = { x: 20, y: H / 2, w: 220, h: 64, label: 'legacy_27_raw.obs', sub: '476,973 rows' };
  const buckets = [
    { id: 'drug_order',  label: 'drug_order',   sub: '43,412 (9.10%)',   rule: 'P1 · value_coded.class=Drug',                       tone: 'success', n: 43412 },
    { id: 'conditions',  label: 'conditions',   sub: '4,451 (0.93%)',    rule: 'P2 · q=6042 PROBLEM ADDED',                         tone: 'success', n: 4451 },
    { id: 'test_order',  label: 'test_order',   sub: '1,095 (0.23%)',    rule: 'P4 · q class=Test+Coded · drug-class excluded',    tone: 'warning', n: 1095 },
    { id: 'allergy',     label: 'allergy',      sub: '2 (0.0004%)',      rule: 'P3 · q∈{6011,6012,1083} & v=YES',                   tone: 'warning', n: 2 },
    { id: 'obs_clean',   label: 'obs (clean)',  sub: '428,013 (89.74%)', rule: 'remainder · concept-id rebound',                   tone: 'info',    n: 428013 },
  ];
  // Distribute targets vertically on the right.
  const rightX = 700;
  const rightW = 250;
  const rightH = 50;
  const totalSlots = buckets.length;
  const slotGap = (H - 40 - totalSlots * rightH) / (totalSlots - 1);

  const toneStroke: Record<string, string> = {
    success: theme.stroke.success ?? theme.stroke.primary,
    warning: theme.stroke.warning ?? theme.stroke.secondary,
    info:    theme.stroke.tertiary ?? theme.stroke.secondary,
  };

  return (
    <svg role="img" aria-label="Obs row distribution by promotion target" width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.secondary} />
        </marker>
      </defs>

      {/* left: source */}
      <rect x={left.x} y={left.y - left.h / 2} width={left.w} height={left.h} rx={10} fill={theme.fill.tertiary} stroke={theme.stroke.secondary} />
      <text x={left.x + left.w / 2} y={left.y - 6} textAnchor="middle" fontSize={14} fontWeight={600} fill={theme.text.primary}>{left.label}</text>
      <text x={left.x + left.w / 2} y={left.y + 14} textAnchor="middle" fontSize={12} fill={theme.text.tertiary}>{left.sub}</text>

      {/* right: targets */}
      {buckets.map((b, i) => {
        const y = 20 + i * (rightH + slotGap);
        const sourceX = left.x + left.w;
        const sourceY = left.y;
        const targetX = rightX;
        const targetY = y + rightH / 2;
        const widthFromN = Math.max(0.4, Math.min(6, Math.log10(b.n + 1) - 0.5));
        const dx = (targetX - sourceX) / 2;
        const path = `M ${sourceX} ${sourceY} C ${sourceX + dx} ${sourceY}, ${targetX - dx} ${targetY}, ${targetX} ${targetY}`;
        return (
          <g key={b.id}>
            <path d={path} stroke={toneStroke[b.tone]} strokeWidth={widthFromN} fill="none" opacity={0.7} markerEnd="url(#flow-arrow)" />
            <rect x={rightX} y={y} width={rightW} height={rightH} rx={8} fill={theme.fill.tertiary} stroke={toneStroke[b.tone]} strokeWidth={1.2} />
            <text x={rightX + 12} y={y + 18} fontSize={13} fontWeight={600} fill={theme.text.primary}>{b.label}</text>
            <text x={rightX + 12} y={y + 35} fontSize={11} fill={theme.text.tertiary}>{b.sub}</text>
            <text x={rightX + rightW - 12} y={y + 35} fontSize={10.5} textAnchor="end" fill={theme.text.tertiary} style={{ fontStyle: 'italic' }}>{b.rule}</text>
          </g>
        );
      })}
    </svg>
  );
}

// =========================================================================
// 4. BRIDGE RULE VISUAL (legacy ↔ CIEL identity bridge)
// =========================================================================

function BridgeRuleVisual() {
  const theme = useHostTheme();
  const examples = [
    { legacy: 5088, legacy_fsn: 'TEMPERATURE (C)', ciel_uuid: '5088AAAA…AAAA', ciel_id: 4166, ciel_fsn: 'Temperature (c)' },
    { legacy: 5089, legacy_fsn: 'WEIGHT (KG)',     ciel_uuid: '5089AAAA…AAAA', ciel_id: 4168, ciel_fsn: 'Weight (kg)' },
    { legacy: 1088, legacy_fsn: 'CURRENT ANTIRETROVIRAL DRUGS USED FOR TREATMENT', ciel_uuid: '1088AAAA…AAAA', ciel_id: 55823, ciel_fsn: 'Current antiretroviral drugs used for treatment' },
    { legacy: 1107, legacy_fsn: 'NONE', ciel_uuid: '1107AAAA…AAAA', ciel_id: 1107, ciel_fsn: 'None' },
  ];
  const W = 980;
  const rowH = 70;
  const H = 56 + examples.length * rowH;
  const lx = 30,  lw = 360;
  const mx = 410, mw = 160;
  const rx = 590, rw = 360;

  return (
    <svg role="img" aria-label="Legacy ↔ CIEL bridge examples" width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <defs>
        <marker id="bridge-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.stroke.brand ?? theme.stroke.primary} />
        </marker>
      </defs>
      <text x={lx + lw / 2} y={24} textAnchor="middle" fontSize={12} fontWeight={600} fill={theme.text.tertiary} style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>legacy_27_raw.concept</text>
      <text x={mx + mw / 2} y={24} textAnchor="middle" fontSize={12} fontWeight={600} fill={theme.text.tertiary} style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>{"RPAD(id, 36, 'A')"}</text>
      <text x={rx + rw / 2} y={24} textAnchor="middle" fontSize={12} fontWeight={600} fill={theme.text.tertiary} style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>openmrs.concept (CIEL)</text>

      {examples.map((e, i) => {
        const y = 44 + i * rowH;
        return (
          <g key={e.legacy}>
            <rect x={lx} y={y} width={lw} height={rowH - 14} rx={6} fill={theme.fill.tertiary} stroke={theme.stroke.secondary} />
            <text x={lx + 12} y={y + 22} fontSize={13} fontWeight={600} fill={theme.text.primary}>id = {e.legacy}</text>
            <text x={lx + 12} y={y + 40} fontSize={11.5} fill={theme.text.tertiary}>{e.legacy_fsn}</text>

            <rect x={mx} y={y} width={mw} height={rowH - 14} rx={6} fill={theme.fill.tertiary} stroke={theme.stroke.brand ?? theme.stroke.primary} strokeDasharray="3 3" />
            <text x={mx + mw / 2} y={y + 22} textAnchor="middle" fontSize={11} fontFamily="ui-monospace, monospace" fill={theme.text.primary}>{e.ciel_uuid}</text>
            <text x={mx + mw / 2} y={y + 40} textAnchor="middle" fontSize={10.5} fill={theme.text.tertiary}>matches uuid</text>

            <rect x={rx} y={y} width={rw} height={rowH - 14} rx={6} fill={theme.fill.tertiary} stroke={theme.stroke.success ?? theme.stroke.secondary} />
            <text x={rx + 12} y={y + 22} fontSize={13} fontWeight={600} fill={theme.text.primary}>internal id = {e.ciel_id}</text>
            <text x={rx + 12} y={y + 40} fontSize={11.5} fill={theme.text.tertiary}>{e.ciel_fsn}</text>

            <path d={`M ${lx + lw} ${y + (rowH - 14) / 2} L ${mx} ${y + (rowH - 14) / 2}`} stroke={theme.stroke.brand ?? theme.stroke.primary} strokeWidth={1.2} markerEnd="url(#bridge-arrow)" />
            <path d={`M ${mx + mw} ${y + (rowH - 14) / 2} L ${rx} ${y + (rowH - 14) / 2}`} stroke={theme.stroke.brand ?? theme.stroke.primary} strokeWidth={1.2} markerEnd="url(#bridge-arrow)" />
          </g>
        );
      })}
    </svg>
  );
}

// =========================================================================
// 5. PROMOTION RULES — detailed
// =========================================================================

type PromotionRule = {
  id: string;
  target_table: string;
  status: 'ready' | 'review' | 'sparse';
  rows: number;
  selector: string;
  selector_sql: string;
  field_mapping: Array<[string, string, string?]>;   // target, source, optional note
  open_questions: string[];
};

const promotionRules: PromotionRule[] = [
  {
    id: 'P1', target_table: 'drug_order', status: 'ready', rows: 43412,
    selector: 'obs rows where value_coded.class = Drug. Top answers: LAMIVUDINE (9,913), STAVUDINE (9,781), NEVIRAPINE (8,810), TRIMETHOPRIM+SULFAMETHOXAZOLE (4,887), ISONIAZID (1,972), EFAVIRENZ (1,548); plus ~3,000 vaccine doses (DTP, polio, HepB, Hib, measles).',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS drug_concept_id, o.obs_datetime
FROM legacy_27_raw.obs o
JOIN legacy_27_raw.concept c ON c.concept_id = o.value_coded
JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
WHERE cc.name = 'Drug' AND o.voided = 0`,
    field_mapping: [
      ['drug_order.patient_id',     'obs.person_id'],
      ['drug_order.encounter_id',   'obs.encounter_id'],
      ['drug_order.concept_id',     'lookup(obs.value_coded → CIEL UUID)', 'rebind via B1'],
      ['drug_order.start_date',     'obs.obs_datetime'],
      ['drug_order.orderer',        'encounter_provider.provider_id', 'fallback obs.creator'],
      ['drug_order.urgency',        "'ROUTINE'"],
      ['drug_order.dose/units/freq', 'NULL', 'not present in legacy obs — flag in coverage_sample'],
      ['drug_order.uuid',           'orders.uuid', 'synthetic identity lives on parent orders row; deterministic UUIDv5-style name-based UUID per research.md §R-typed-table-promotion Q2'],
      ['drug_order.order_id',       'obs.obs_id', 'parent row in clin__orders (Hibernate joined-table inheritance)'],
    ],
    open_questions: [
      'Vaccines as drug_order vs Immunization shape? (Q3)',
      'One-row-per-obs vs grouped-by-patient+drug? Default: per-obs.',
      'NOT NULL constraints on dose/units/freq in 2.8? Verify against openmrs DDL.',
    ],
  },
  {
    id: 'P2', target_table: 'conditions', status: 'ready', rows: 4451,
    selector: 'obs where concept_id = 6042 PROBLEM ADDED. 114 distinct diagnosis values.',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS dx_concept_id, o.obs_datetime
FROM legacy_27_raw.obs o
WHERE o.concept_id = 6042 AND o.value_coded IS NOT NULL AND o.voided = 0`,
    field_mapping: [
      ['conditions.patient_id',      'obs.person_id'],
      ['conditions.encounter_id',    'obs.encounter_id'],
      ['conditions.condition_coded', 'lookup(obs.value_coded → CIEL UUID)'],
      ['conditions.clinical_status', "'ACTIVE'", 'no PROBLEM RESOLVED concept observed'],
      ['conditions.onset_date',      'obs.obs_datetime'],
      ['conditions.uuid',            'deterministic UUIDv5-style name-based UUID (Q2)'],
    ],
    open_questions: [
      'No PROBLEM RESOLVED signal observed → every promoted condition stays ACTIVE forever. Acceptable?',
      'Should CHILDS CURRENT HIV STATUS (5303, 629 rows) also promote? Default: STAYS_IN_OBS (it is repeated screening, not problem-list).',
    ],
  },
  {
    id: 'P3', target_table: 'allergy', status: 'sparse', rows: 7,
    selector: 'obs on the 3 explicit allergy-Boolean questions (6011 PENICILLIN, 6012 SULFA, 1083 OTHER MED) where value_coded = 1065 YES.',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS q, o.obs_datetime
FROM legacy_27_raw.obs o
WHERE o.concept_id IN (6011, 6012, 1083) AND o.value_coded = 1065 AND o.voided = 0`,
    field_mapping: [
      ['allergy.patient_id',     'obs.person_id'],
      ['allergy.coded_allergen', 'allergen-pick keyed by question concept', '6011→penicillin, 6012→sulfa, 1083→other med'],
      ['allergy.allergen_type',  "'DRUG'", 'all 3 are drug allergies'],
      ['allergy.severity_concept_id', 'NULL', 'not recorded in legacy boolean form'],
      ['allergy.encounter_id',   'obs.encounter_id'],
    ],
    open_questions: [
      'Map 3 question concepts → specific CIEL allergen substance concepts (needs human pick).',
      'Flip patient.allergy_status to See-list when any row promotes?',
    ],
  },
  {
    id: 'P4', target_table: 'test_order', status: 'review', rows: 1120,
    selector: 'obs where question class=Test AND datatype=Coded. Top: IMMUNIZATIONS ORDERED (891), X-RAY CHEST (172), VDRL (33), HIV DNA PCR (15).',
    selector_sql: `SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS test_concept, o.value_coded AS result, o.obs_datetime
FROM legacy_27_raw.obs o
JOIN legacy_27_raw.concept c ON c.concept_id = o.concept_id
JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd ON cd.concept_datatype_id = c.datatype_id
WHERE cc.name = 'Test' AND cd.name = 'Coded' AND o.voided = 0`,
    field_mapping: [
      ['test_order.patient_id',     'obs.person_id'],
      ['test_order.concept_id',     'lookup(obs.concept_id → CIEL UUID)', 'TEST concept, not the result'],
      ['test_order.encounter_id',   'obs.encounter_id'],
      ['test_order.date_activated', 'obs.obs_datetime'],
      ['test_order.urgency',        "'ROUTINE'"],
      ['test_order.order_id',       'obs.obs_id', 'parent row in clin__orders'],
      ['obs.order_id',              'new test_order.order_id', 'preserve result obs row, link back via FK'],
    ],
    open_questions: [
      'IMMUNIZATIONS ORDERED (891 rows) really immunizations, not lab tests — split off?',
      'order_type_id mapping per concept class — verify 2.8 RefApp test_order_type id.',
    ],
  },
];

// =========================================================================
// 6. WHAT STAYS IN OBS
// =========================================================================

const staysInObs: Array<[string, string, string]> = [
  // [bucket name, row count, why]
  ['YES/NO/NONE answers (value_class=Misc)',                          '263,963', 'survey/coded answers — semantically observations, not events. Top: NONE (114,070), NO (66,679), YES (39,776)'],
  ['Numeric vital signs (Test+Numeric questions)',                    '104,730', 'Temperature/Weight/Pulse/BloodOxygen — observations by definition. FHIR Observation projects them on the read side.'],
  ['Boolean survey questions (excluding the 3 allergy ones)',         '85,109',  'ARV use, new complaints, scheduled visit — yes/no surveys stay as obs.'],
  ['Treatment-plan status (value_class=Misc Order)',                  '18,477',  'CONTINUE / STOP / START / CHANGE — plan-status answers, not actionable orders.'],
  ['ConvSet / LabSet / MedSet groupings',                             '18,979',  'obs_group_id header rows — preserve grouping, do not flatten.'],
  ['RETURN VISIT DATE (5096)',                                        '14,214',  'Misc+Date question; may feed Appointment resource later but no 2.8 target table.'],
  ['Coded Diagnosis answers NOT under question 6042',                 '1,010',   'REASON-STOPPED patterns + similar — diagnosis-coded values used as reasons, not new conditions.'],
];

// =========================================================================
// 7. BLOCKERS / ISSUES INVENTORY
// =========================================================================

type Blocker = { id: string; title: string; status: 'SOLVED' | 'PARTIAL' | 'OPEN' | 'NON-ISSUE'; severity: 'critical' | 'high' | 'medium' | 'low'; finding: string; resolution: string };

const blockers: Blocker[] = [
  { id: 'B1', status: 'SOLVED',    severity: 'critical', title: 'Identity bridge legacy → CIEL',
    finding: 'concept_id integers collide (legacy 5088=TEMPERATURE; openmrs internal 5088=Stock ragweed pollen mixture). Legacy UUIDs are NOT in CIEL.',
    resolution: "Bridge by CIEL UUID pattern: openmrs.concept WHERE uuid = RPAD(legacy_id, 36, 'A'). 100% coverage on 457 obs-referenced concepts." },
  { id: 'B2', status: 'SOLVED',    severity: 'high', title: 'No reference_map rows in legacy',
    finding: 'concept_reference_source / concept_reference_term / concept_reference_map all 0 rows.',
    resolution: 'Not a problem under rebind. We point at CIEL concepts; their reference maps come from CIEL itself.' },
  { id: 'B3', status: 'SOLVED',    severity: 'medium', title: '133 CIEL import errors',
    finding: '23 distinct CIEL ids failed (mostly duplicate-name-in-locale validation). 109 cascading mapping errors trace back to these.',
    resolution: '0 of the 23 are referenced by legacy obs. Non-blocking for this dataset.' },
  { id: 'B4', status: 'PARTIAL',   severity: 'medium', title: 'concept_class FK shift (4 of 19 misaligned)',
    finding: 'class_id 16/17/18/19 reshuffled between legacy (Program/Workflow/State/Frequency) and CIEL (Frequency/Pharm Drug Class/Units/Workflow).',
    resolution: 'Bypassed by rebind. Would matter only if we ever carried concept rows forward; we do not.' },
  { id: 'B5', status: 'OPEN',      severity: 'high', title: 'Four typed clinical tables empty in legacy',
    finding: 'allergy/conditions/orders/drug_order all 0 rows; events live entirely in obs.',
    resolution: 'M2-A authored work — promotion rules P1–P4 (see section above). Reviewable per constitution.' },
  { id: 'B6', status: 'OPEN',      severity: 'medium', title: 'Schema deltas 2.7 → 2.8',
    finding: '22 legacy-only tables, 109 openmrs-only, 121 shared.',
    resolution: 'T024 schema_diff enumerates with clinical_meaningful flag. Most legacy-only tables are 0-row anyway.' },
  { id: 'B7', status: 'NON-ISSUE', severity: 'low', title: 'Locale set divergence',
    finding: 'Legacy concept_name English-only (3,555 names).',
    resolution: 'CIEL ships 12 locales — multilingual upgrade for free after rebind.' },
  { id: 'B8', status: 'NON-ISSUE', severity: 'low', title: 'obs.value_drug references',
    finding: '0 rows in obs have value_drug populated.',
    resolution: 'No drug-table mapping problem.' },
];

const blockerToneMap: Record<Blocker['status'], 'success' | 'warning' | 'danger' | 'neutral'> = {
  'SOLVED': 'success', 'PARTIAL': 'warning', 'OPEN': 'danger', 'NON-ISSUE': 'neutral',
};

// =========================================================================
// 8. CROSS-CUTTING DECISIONS
// =========================================================================

const decisions: Array<{ id: string; title: string; question: string; proposal: string }> = [
  { id: 'Q1', title: 'Typed-table canonicalization (no duplicate obs)',
    question: 'When obs → typed row, do we DELETE the obs or KEEP it with a link via obs.order_id?',
    proposal: 'CORRECTED: Typed table is canonical. P1/P2/P3 source rows do NOT remain in residual obs. P4 only: source obs may remain as a linked result row (obs.order_id) when it is the test result, not a copy of the order. No duplicate canonical facts.' },
  { id: 'Q2', title: 'UUID strategy on promoted rows',
    question: 'Non-deterministic UUID() vs deterministic scheme?',
    proposal: 'CORRECTED: Deterministic UUIDv5-style name-based UUIDs for every synthetic promoted OpenMRS row that requires uuid. Fixed namespace + stable source obs uuid + target role; removes UUID() from all clin__*.sql models and stays reproducible across reruns (SC-004).' },
  { id: 'Q3', title: 'Vaccines as drug_order or Immunization?',
    question: 'In FHIR R4 vaccines are Immunization, not MedicationRequest. 2.8 OpenMRS has no immunization table by default.',
    proposal: 'Emit as drug_order; the FHIR read-side can re-project vaccines to Immunization. Tag via attribute.' },
  { id: 'Q4', title: 'Orderer field source',
    question: 'obs has no provider FK; encounter_provider is per encounter.',
    proposal: 'Use encounter_provider for the matching encounter; fall back to obs.creator.' },
  { id: 'Q5', title: 'coverage_sample sampling per rule',
    question: 'FR-015 requires per-bucket coverage samples for spot-check.',
    proposal: '5 records per (concept_class × datatype × value_class) cohort, deterministic sampler_seed recorded in run_manifest.' },
];

// =========================================================================
// 9. BAR CHART — promotion distribution
// =========================================================================

const promotionChartCategories = ['drug_order', 'conditions', 'test_order', 'allergy', 'obs (clean)'];
const promotionChartCounts    = [43412,           4451,         1095,          2,         428013];

// =========================================================================
// MAIN
// =========================================================================

export default function ConceptMappingDiscovery() {
  return (
    <Stack gap={18}>
      <H1>002 / M2-A — Concept Mapping &amp; Transformation</H1>
      <Text tone="secondary">
        How the 5,284-patient OpenMRS 2.7 demo dump becomes a 2.8-RefApp-loadable dataset bound to CIEL v2026-04-28. Every count below
        is sourced from live <Code>SELECT COUNT(*)</Code> queries against legacy_27_raw and the CIEL-loaded openmrs DB on the running
        harness stack. PR #6 lands the inventory, snapshot, error-audit, and loader tooling.
      </Text>

      <Grid columns={3} gap={12}>
        {heroStats.map((s, i) => (<Stat key={i} value={s.value} label={s.label} tone={s.tone} />))}
      </Grid>

      <Divider />

      <H2>End-to-end transformation</H2>
      <Text tone="secondary">Source on the left, transform in the middle, target tables on the right. The CIEL-loaded openmrs DB is the metadata reference, not a data source.</Text>
      <Card><CardBody><TransformPipelineDiagram /></CardBody></Card>

      <Divider />

      <H2>Where every obs row goes</H2>
      <Text tone="secondary">All 476,973 legacy obs accounted for. Line thickness = log10(row count); colored borders flag the per-target status (green = ready, amber = needs review or sparse, neutral = stays unchanged).</Text>
      <Card><CardBody><PromotionFlowDiagram /></CardBody></Card>

      <Card>
        <CardHeader><H3>Same data as a bar chart</H3></CardHeader>
        <CardBody>
          <BarChart
            categories={promotionChartCategories}
            series={[{ name: 'rows', data: promotionChartCounts, tone: 'info' }]}
            height={240}
          />
          <Text tone="secondary" size="small">obs (clean) dominates the y-axis. The four promotion targets are the small bars on the left — visible in the absolute counts but barely a sliver of the dataset volume.</Text>
        </CardBody>
      </Card>

      <Divider />

      <H2>The identity bridge</H2>
      <Callout tone="success" title="One deterministic rule covers every concept reference in legacy obs">
        <Text>
          For every legacy <Code>concept_id N</Code> referenced from obs (as <Code>concept_id</Code> or <Code>value_coded</Code>), the
          CIEL counterpart is the row in <Code>openmrs.concept</Code> where <Code>{"uuid = RPAD(CAST(N AS CHAR), 36, 'A')"}</Code>.
          Verified: <strong>457/457</strong> distinct obs-referenced concept_ids resolve. Names match modulo case
          (legacy is uppercase AMPATH-style; CIEL is title-case).
        </Text>
      </Callout>
      <Card><CardBody><BridgeRuleVisual /></CardBody></Card>
      <Card>
        <CardHeader><H3>Rebind SQL (executable against the live stack)</H3></CardHeader>
        <CardBody>
          <Code language="sql">{`SELECT
  l_obs.obs_id,
  l_obs.concept_id        AS legacy_concept_id,
  q.concept_id            AS new_concept_id,
  v.concept_id            AS new_value_coded
FROM legacy_27_raw.obs l_obs
LEFT JOIN openmrs.concept q ON q.uuid = RPAD(CAST(l_obs.concept_id  AS CHAR), 36, 'A')
LEFT JOIN openmrs.concept v ON v.uuid = RPAD(CAST(l_obs.value_coded AS CHAR), 36, 'A');`}</Code>
        </CardBody>
      </Card>

      <Divider />

      <H2>Promotion rules — for review and tweaking</H2>
      <Text tone="secondary">
        Four rules, four target tables. Together they consume 48,181 obs rows (10.1%). Each rule is independently editable: edit
        <Code>selector_sql</Code>, re-run against legacy_27_raw, confirm the row count before accepting into
        <Code>datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json</Code>.
      </Text>

      {promotionRules.map((r) => (
        <Card key={r.id}>
          <CardHeader trailing={
            <Row gap={6}>
              <Pill size="sm" tone={r.status === 'ready' ? 'success' : 'warning'} active>{r.status}</Pill>
              <Pill size="sm" tone="neutral">{r.rows.toLocaleString()} rows</Pill>
            </Row>
          }>
            <H3>{r.id} · obs → <Code>{r.target_table}</Code></H3>
          </CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text>{r.selector}</Text>
              <Code language="sql">{r.selector_sql}</Code>
              <Text weight="semibold">Field mapping</Text>
              <Table
                headers={['target column', 'source', 'note']}
                rows={r.field_mapping.map((m) => [m[0], m[1], m[2] ?? ''])}
                striped
              />
              <Text weight="semibold">Open questions</Text>
              <Stack gap={4}>
                {r.open_questions.map((q, i) => (<Text key={i} size="small" tone="secondary">• {q}</Text>))}
              </Stack>
            </Stack>
          </CardBody>
        </Card>
      ))}

      <Divider />

      <H2>What stays in obs (after concept-id rebind)</H2>
      <Text tone="secondary">The 89.9% of obs the promotion rules do NOT consume. Each bucket gets a one-line justification so the review can accept or contest it.</Text>
      <Card><CardBody>
        <Table
          headers={['Bucket', 'n obs', 'Why it stays in obs']}
          rows={staysInObs}
          striped
        />
      </CardBody></Card>

      <Divider />

      <H2>Blocker inventory</H2>
      <Text tone="secondary">Each blocker is either solved by tooling, called out as authored scope (B5), or surfaced as a structural diff (B6).</Text>
      <Grid columns={2} gap={10}>
        {blockers.map((b) => (
          <Card key={b.id}>
            <CardHeader trailing={
              <Row gap={6}>
                <Pill size="sm" tone={blockerToneMap[b.status]} active>{b.status}</Pill>
                <Pill size="sm" tone="neutral">{b.severity}</Pill>
              </Row>
            }>
              <Text weight="semibold">{b.id} · {b.title}</Text>
            </CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small"><Text weight="semibold">Finding.</Text> {b.finding}</Text>
                <Text size="small"><Text weight="semibold">Resolution.</Text> {b.resolution}</Text>
              </Stack>
            </CardBody>
          </Card>
        ))}
      </Grid>

      <Divider />

      <H2>Cross-cutting decisions for review</H2>
      <Stack gap={10}>
        {decisions.map((d) => (
          <Callout key={d.id} tone="warning" title={`${d.id} — ${d.title}`}>
            <Stack gap={4}>
              <Text size="small"><Text weight="semibold">Question.</Text> {d.question}</Text>
              <Text size="small"><Text weight="semibold">Default proposal.</Text> {d.proposal}</Text>
            </Stack>
          </Callout>
        ))}
      </Stack>

      <Divider />

      <H2>Missing or under-specified — what this canvas does NOT yet cover</H2>
      <Card><CardBody>
        <Table
          headers={['Gap', 'Status', 'Where it will land']}
          rows={[
            ['Per-class promotion rules for unmapped Drug answers (e.g. immunizations as Immunization)', 'Pending Q3 decision', 'Update to P1; FHIR read-side projection'],
            ['T022 terminology profile: reference_sources[], locales[]', 'Trivially empty in legacy; not yet emitted', 'harness/profile/terminology.py — next commit'],
            ['T023 module classification: bundled_in_2_8_refapp per table', 'Pending', 'harness/profile/modules.py — next commit'],
            ['T024 schema_diff legacy_27_raw vs openmrs (CIEL-loaded baseline)', 'Done — real introspection + §R5 classifier (commit 6d8ead5)', 'harness/schema_diff.py'],
            ['drug.dose / units / frequency / duration sourcing', 'No signal in legacy obs', 'Flag in coverage_sample as NULL columns; review per-drug'],
            ['order_type_id mapping for test_order', 'Done — hardcoded 3 (Test Order) per openmrs.order_type; drug_order = 2', 'clinical/orders.sql'],
            ['Allergen-concept hand-pick (penicillin, sulfa, other-med)', 'Pending human pick', 'datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json — 3 hand-curated entries'],
          ]}
          striped
        />
      </CardBody></Card>

      <Divider />

      <Card>
        <CardHeader><H3>Reproducing the queries behind this canvas</H3></CardHeader>
        <CardBody>
          <Stack gap={6}>
            <Text size="small">All counts here come from queries against the running harness MariaDB. Re-derive any number with one command:</Text>
            <Code language="bash">{`docker exec harness-openmrs-db mariadb --user=openmrs --password=openmrs -B -e "
-- Bridge coverage (expect bridgeable == legacy_distinct_in_obs)
WITH legacy_used AS (
  SELECT DISTINCT concept_id FROM legacy_27_raw.obs WHERE concept_id IS NOT NULL
  UNION SELECT DISTINCT value_coded FROM legacy_27_raw.obs WHERE value_coded IS NOT NULL
)
SELECT COUNT(DISTINCT lu.concept_id) AS legacy_distinct_in_obs,
       COUNT(DISTINCT CASE WHEN ciel.concept_id IS NOT NULL THEN lu.concept_id END) AS bridgeable
FROM legacy_used lu
LEFT JOIN openmrs.concept ciel ON ciel.uuid = RPAD(CAST(lu.concept_id AS CHAR), 36, 'A');
"`}</Code>
            <Text size="small" tone="secondary">
              Provenance: PR #6 commits 53df8bb (demo loader), 37b3211 (T021 inventory), 76300d0 (T024b snapshot), a5edc31 (T024c errors).
              CIEL version: v2026-04-28. Source dump sha256: a7ca4bbe....
            </Text>
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  );
}
