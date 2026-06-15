MODEL (
  name refapp_28_demo.terminology__visit_type_map,
  kind VIEW,
  description 'Reviewed semantic map: encounter_type_id → visit_type_id for visit reconstruction. Adult Visit (2) → OPD Visit (3); every other encounter type → Facility Visit (1). visit_type rows (1=Facility, 3=OPD) are baseline RefApp metadata, not loaded by this pipeline. Mirrors terminology__encounter_type_map.',
  tags (policy_bucket:seed_augment),
  grain (source_id)
);

SELECT
  encounter_type_id                              AS source_id,
  CASE WHEN encounter_type_id = 2 THEN 3 ELSE 1 END AS target_id
FROM refapp_28_demo.stg_encounter_type
;
