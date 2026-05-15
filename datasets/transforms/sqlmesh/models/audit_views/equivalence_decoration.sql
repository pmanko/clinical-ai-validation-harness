MODEL (
  name refapp_28_demo.aud__equivalence_decoration,
  kind VIEW,
  description 'Row-level audit view that UNIONs the 4 promoted clinical marts (drug_order, conditions, allergy, test_order) plus the rebound obs mart and decorates each row with the FHIR ConceptMap equivalence label looked up from the concept_translation seed. Consumed by the translation-coverage sampler (FR-015) so per-bucket samples can carry the equivalence label without re-deriving it from the SQLMesh project. Required by contracts/sqlmesh_project.profile.md §Project layout.',
  tags (policy_bucket:passthrough),
  grain (source_table, source_pk, target_table, target_pk)
);

WITH drug_order_dec AS (
  SELECT
    'obs'                          AS source_table,
    d.source_obs_id                AS source_pk,
    'drug_order'                   AS target_table,
    d.uuid                         AS target_pk,
    'seed-augment'                 AS policy_bucket,
    COALESCE(ct.equivalence, 'inexact') AS equivalence_label
  FROM refapp_28_demo.clin__drug_order d
  LEFT JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = d.concept_id
), conditions_dec AS (
  SELECT
    'obs'                          AS source_table,
    c.source_obs_id                AS source_pk,
    'conditions'                   AS target_table,
    c.uuid                         AS target_pk,
    'seed-augment'                 AS policy_bucket,
    COALESCE(ct.equivalence, 'inexact') AS equivalence_label
  FROM refapp_28_demo.clin__conditions c
  LEFT JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = c.condition_coded
), allergy_dec AS (
  SELECT
    'obs'                          AS source_table,
    a.source_obs_id                AS source_pk,
    'allergy'                      AS target_table,
    a.uuid                         AS target_pk,
    'seed-augment'                 AS policy_bucket,
    COALESCE(ct.equivalence, 'inexact') AS equivalence_label
  FROM refapp_28_demo.clin__allergy a
  LEFT JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = a.coded_allergen
), test_order_dec AS (
  SELECT
    'obs'                          AS source_table,
    t.source_obs_id                AS source_pk,
    'test_order'                   AS target_table,
    t.uuid                         AS target_pk,
    'seed-augment'                 AS policy_bucket,
    COALESCE(ct.equivalence, 'inexact') AS equivalence_label
  FROM refapp_28_demo.clin__test_order t
  LEFT JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = t.concept_id
), obs_dec AS (
  SELECT
    'obs'                          AS source_table,
    CAST(o.obs_id AS CHAR(64))     AS source_pk,
    'obs'                          AS target_table,
    o.uuid                         AS target_pk,
    'remap'                        AS policy_bucket,
    COALESCE(ct.equivalence, 'inexact') AS equivalence_label
  FROM refapp_28_demo.clin__obs o
  LEFT JOIN refapp_28_demo.seed__concept_translation ct
    ON ct.target_concept_id = o.concept_id
)
SELECT * FROM drug_order_dec
UNION ALL SELECT * FROM conditions_dec
UNION ALL SELECT * FROM allergy_dec
UNION ALL SELECT * FROM test_order_dec
UNION ALL SELECT * FROM obs_dec
;
