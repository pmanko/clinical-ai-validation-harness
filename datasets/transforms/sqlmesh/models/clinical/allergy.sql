MODEL (
  name refapp_28_demo.clin__allergy,
  kind FULL,
  description 'P3 — drug-allergy boolean obs answered YES, promoted to allergy. Source questions: 6011 PENICILLIN, 6012 SULFA, 1083 OTHER MEDICINE. coded_allergen per reviewed CIEL mapping: 6011→971 (Penicillin drug class, CIEL 162297), 6012→20 (Sulfonamide drug class, CIEL 162170), 1083→227 (Other, CIEL 5622). Expected ~7 rows.',
  tags (policy_bucket:seed_augment),
  grain (uuid),
  audits (
    unique_values(columns := (uuid)),
    audit_allergy_row_count_min,
    audit_allergy_not_voided
  )
);

-- coded_allergen mapping (reviewed, case-by-case):
--   6011 (ALLERGY TO PENICILLIN) → 971 = CIEL 162297 (Penicillin drug class)
--   6012 (ALLERGY TO SULFA)      → 20  = CIEL 162170 (Sulfonamide drug class)
--   1083 (ALLERGY TO OTHER MED)  → 227 = CIEL 5622   (Other)
--
-- voided = 0: promoted allergies are active records.
-- uuid: deterministic UUIDv5-style name-based UUID with fixed namespace
-- 2f56d7b8-8f8f-5d3a-9f52-002002800001 and name
-- feature-002:allergy:<source obs uuid>.
SELECT
  s.person_id                  AS patient_id,
  CAST(NULL AS INT)            AS severity_concept_id,
  CASE
    WHEN s.source_concept_id = 6011 THEN 971   -- Penicillin drug class (CIEL 162297)
    WHEN s.source_concept_id = 6012 THEN 20    -- Sulfonamide drug class (CIEL 162170)
    ELSE 227                            -- Other (CIEL 5622) for concept_id 1083
  END                          AS coded_allergen,
  CAST(NULL AS VARCHAR)        AS non_coded_allergen,
  'DRUG'                       AS allergen_type,
  CAST(NULL AS VARCHAR)        AS comments,
  s.creator,
  s.obs_datetime               AS date_created,   -- already shifted in stg_obs; pass through
  CAST(NULL AS INT)            AS changed_by,
  CAST(NULL AS DATETIME)       AS date_changed,
  0                            AS voided,
  CAST(NULL AS INT)            AS voided_by,
  CAST(NULL AS DATETIME)       AS date_voided,
  CAST(NULL AS VARCHAR)        AS void_reason,
  LOWER(CONCAT(
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 1, 8), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 9, 4), '-',
    '5', SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 14, 3), '-',
    ELT(CONV(SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 17, 1), 16, 10) % 4 + 1, '8', '9', 'a', 'b'),
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 18, 3), '-',
    SUBSTR(SHA1(CONCAT(UNHEX(REPLACE('2f56d7b8-8f8f-5d3a-9f52-002002800001', '-', '')), CONCAT('feature-002:allergy:', COALESCE(s.uuid, CAST(s.obs_id AS CHAR))))), 21, 12)
  ))                           AS uuid,
  CAST(NULL AS VARCHAR)        AS form_namespace_and_path,
  s.encounter_id,
  s.obs_id                     AS source_obs_id   -- staging lineage; dropped by promote column intersection
FROM refapp_28_demo.stg_obs s
WHERE s.source_concept_id IN (6011, 6012, 1083)
  AND s.source_value_coded = 1065
;
