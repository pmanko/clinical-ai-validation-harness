MODEL (
  name refapp_28_demo.clin__test_order,
  kind FULL,
  description 'P4 — obs whose question concept is Test-class with Coded datatype, promoted to the test_order child table. order_id FK links to the matching clin__orders parent row. The source obs may remain as a linked result obs via obs.order_id when it is the result of the test (not a duplicate of the order fact). Expected ~1,120 rows.',
  tags (policy_bucket:seed_augment),
  grain (order_id),
  audits (
    unique_values(columns := (order_id)),
    audit_test_order_row_count_min
  )
);

-- test_order is the Hibernate child table of orders. Its schema contains only
-- child-specific columns; all parent fields (patient_id, encounter_id, concept_id,
-- creator, uuid, etc.) live in the parent orders row.
--
-- Child fields: specimen_source, laterality, clinical_history, frequency,
-- number_of_repeats, location — all null; no signal in legacy obs.
--
-- Source selector: Test-class / Coded-datatype filter uses legacy_27_raw
-- (source IDs), same as clin__orders P4 branch, to keep classification stable.
SELECT
  s.obs_id                   AS order_id,         -- PK; matches parent clin__orders.order_id
  CAST(NULL AS INT)          AS specimen_source,
  CAST(NULL AS VARCHAR)      AS laterality,
  CAST(NULL AS TEXT)         AS clinical_history,
  CAST(NULL AS INT)          AS frequency,
  CAST(NULL AS INT)          AS number_of_repeats,
  CAST(NULL AS INT)          AS location,
  s.obs_id                   AS source_obs_id     -- staging lineage; dropped by promote column intersection
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.source_concept_id
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN legacy_27_raw.concept_datatype cd
  ON cd.concept_datatype_id = c.datatype_id
WHERE cc.name = 'Test'
  AND cd.name = 'Coded'
  -- Drug_order wins when an obs has a Test-class question AND a Drug-class
  -- answer. Prevents duplicate orders rows for the same obs_id.
  AND NOT EXISTS (
    SELECT 1
    FROM legacy_27_raw.concept dc
    JOIN legacy_27_raw.concept_class dcc ON dcc.concept_class_id = dc.class_id
    WHERE dc.concept_id = s.source_value_coded AND dcc.name = 'Drug'
  )
;
