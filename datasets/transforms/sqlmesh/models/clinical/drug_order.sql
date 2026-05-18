MODEL (
  name refapp_28_demo.clin__drug_order,
  kind FULL,
  description 'P1 — obs whose value_coded is a Drug-class concept, promoted to the drug_order child table. order_id FK links to the matching clin__orders parent row. drug_inventory_id is populated only when a drug catalog row matches the UUID-resolved concept; all dose/route/frequency fields are null unless a source signal is present. Expected row count ~43,412.',
  tags (policy_bucket:seed_augment),
  grain (order_id),
  audits (
    unique_values(columns := (order_id)),
    audit_drug_order_row_count_min
  )
);

-- drug_order is the Hibernate child table of orders.  Its schema contains
-- only child-specific columns; all parent fields (patient_id, encounter_id,
-- concept_id, creator, uuid, etc.) live in the parent orders row.
--
-- Triage policy per plan §Step 3:
--   drug_inventory_id: populated only when openmrs.drug has a row whose
--     concept_id = ct.target_concept_id (UUID-resolved local FK). NULL otherwise.
--   drug_non_coded: NULL; no reviewed non-coded display strings in source.
--   dose/route/frequency/etc.: NULL; no dose signal in legacy obs.
--
-- Source selector: Drug class filter uses legacy_27_raw (source IDs) so
-- classification is stable before and after the seed FK fix.
SELECT
  s.obs_id                        AS order_id,           -- PK; matches parent clin__orders.order_id
  drg.drug_id                     AS drug_inventory_id,  -- NULL when no catalog match
  CAST(NULL AS DOUBLE)            AS dose,
  0                               AS as_needed,
  CAST(NULL AS VARCHAR)           AS dosing_type,
  CAST(NULL AS DOUBLE)            AS quantity,
  CAST(NULL AS VARCHAR)           AS as_needed_condition,
  CAST(NULL AS INT)               AS num_refills,
  CAST(NULL AS TEXT)              AS dosing_instructions,
  CAST(NULL AS INT)               AS duration,
  CAST(NULL AS INT)               AS duration_units,
  CAST(NULL AS INT)               AS quantity_units,
  CAST(NULL AS INT)               AS route,
  CAST(NULL AS INT)               AS dose_units,
  CAST(NULL AS INT)               AS frequency,
  CAST(NULL AS VARCHAR)           AS brand_name,
  0                               AS dispense_as_written,
  CAST(NULL AS VARCHAR)           AS drug_non_coded,
  s.obs_id                        AS source_obs_id       -- staging lineage; dropped by promote column intersection
FROM refapp_28_demo.stg_obs s
JOIN legacy_27_raw.concept c
  ON c.concept_id = s.source_value_coded
JOIN legacy_27_raw.concept_class cc
  ON cc.concept_class_id = c.class_id
JOIN refapp_28_demo.seed__concept_translation ct
  ON ct.source_concept_id = s.source_value_coded
LEFT JOIN openmrs.drug drg
  ON drg.concept_id = ct.target_concept_id
WHERE cc.name = 'Drug'
;
