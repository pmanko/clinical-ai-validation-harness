MODEL (
  name refapp_28_demo.clin__visit,
  kind FULL,
  description 'Reconstructed visits. The source (de-identified real data) has 0 visit rows and every encounter.visit_id is NULL; modern OpenMRS auto-creates a visit for every encounter (EmrApiVisitAssignmentHandler). This model rebuilds that container: ONE visit per (patient_id, calendar day) over stg_encounter — the OpenMRS-faithful grouping (allowOverlappingVisits=false → a patient cannot hold two open visits at once). 99.1% of patient-days hold a single encounter, so this is ~1:1 with encounters (~14,248 visits) while correctly collapsing multi-encounter days. Expected ~14,248 rows.',
  tags (policy_bucket:seed_augment),
  grain (visit_id),
  audits (
    unique_values(columns := (visit_id)),
    audit_visit_row_count_min
  )
);

-- Grouping key: (patient_id, DATE(encounter_datetime)). encounter_datetime is
-- already date-transplanted in stg_encounter, so it is passed through unwrapped
-- here (a second @shift_date would double-shift it).
--
-- visit_id: deterministic ROW_NUMBER over the unique (patient_id, day) key —
-- a total order, so re-runs are byte-identical. The wrapped encounter_id(s) of a
-- visit are recoverable by re-joining clin__encounter on (patient_id, day).
--
-- visit_type_id: via the reviewed terminology__visit_type_map; on a mixed-type
-- day the Adult-Visit mapping (OPD, 3) wins over Facility (1) — MAX(target_id).
--
-- date_started / date_stopped: first / last encounter of the day (closed visit,
-- gives OMOP a visit_end_date). location/creator are constant within a patient-day.
--
-- uuid: deterministic UUIDv5-style name-based UUID, fixed namespace
-- 2f56d7b8-8f8f-5d3a-9f52-002002800001, name feature-002:visit:<patient_id>:<day>.
SELECT
  ROW_NUMBER() OVER (ORDER BY g.patient_id, g.visit_day) AS visit_id,
  g.patient_id,
  g.visit_type_id,
  g.date_started,
  g.date_stopped,
  CAST(NULL AS INT)              AS indication_concept_id,
  g.location_id,
  g.creator,
  g.date_created,
  CAST(NULL AS INT)             AS changed_by,
  CAST(NULL AS DATETIME)        AS date_changed,
  0                             AS voided,
  CAST(NULL AS INT)             AS voided_by,
  CAST(NULL AS DATETIME)        AS date_voided,
  CAST(NULL AS VARCHAR)         AS void_reason,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:visit:', CAST(g.patient_id AS CHAR), ':', CAST(g.visit_day AS CHAR)))), 21, 12)
  ))                            AS uuid
FROM (
  SELECT
    e.patient_id,
    DATE(e.encounter_datetime)                              AS visit_day,
    MIN(e.encounter_datetime)                               AS date_started,
    MAX(e.encounter_datetime)                               AS date_stopped,
    MIN(e.location_id)                                      AS location_id,
    MIN(e.creator)                                          AS creator,
    COALESCE(MIN(e.date_created), MIN(e.encounter_datetime)) AS date_created,
    MAX(m.target_id)                                        AS visit_type_id
  FROM refapp_28_demo.stg_encounter e
  JOIN refapp_28_demo.terminology__visit_type_map m
    ON m.source_id = e.encounter_type
  WHERE e.encounter_datetime IS NOT NULL
  GROUP BY e.patient_id, DATE(e.encounter_datetime)
) g
;
