MODEL (
  name refapp_28_demo.stg_obs,
  kind FULL,
  description 'Staging copy of legacy_27_raw.obs with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (obs_id),
  audits (unique_values(columns := (obs_id)))
);

-- source_concept_id and source_value_coded carry the pre-rebind (legacy) concept IDs.
-- Downstream clinical models MUST use these for concept-class classification joins
-- against legacy_27_raw.concept, because concept_id / value_coded are the rebound
-- target local IDs which do not exist in legacy_27_raw.
SELECT
  src.obs_id,
  src.person_id,
  src.concept_id                                          AS source_concept_id,
  COALESCE(ct_0.target_concept_id, src.concept_id)       AS concept_id,
  src.encounter_id,
  src.order_id,
  src.obs_datetime,
  src.location_id,
  src.obs_group_id,
  src.accession_number,
  src.value_group_id,
  src.value_coded                                         AS source_value_coded,
  COALESCE(ct_1.target_concept_id, src.value_coded)      AS value_coded,
  COALESCE(ct_2.target_concept_id, src.value_coded_name_id) AS value_coded_name_id,
  src.value_drug,
  src.value_datetime,
  src.value_numeric,
  src.value_modifier,
  src.value_text,
  src.comments,
  src.creator,
  src.date_created,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.value_complex,
  src.uuid,
  src.previous_version,
  src.form_namespace_and_path,
  src.status,
  src.interpretation
FROM legacy_27_raw.obs src
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_0 ON ct_0.source_concept_id = src.concept_id
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_1 ON ct_1.source_concept_id = src.value_coded
  LEFT JOIN refapp_28_demo.seed__concept_translation ct_2 ON ct_2.source_concept_id = src.value_coded_name_id
;
