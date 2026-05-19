AUDIT (
  name audit_concept_uuid_agreement,
  dialect mysql
);

-- Every row in seed__concept_translation MUST satisfy:
--   concept.concept_id = target_concept_id
--   WHERE concept.uuid  = target_uuid
--
-- Emits failing translation rows on fail; zero rows on pass.
-- This directly verifies the FK resolution that seed_emit.py now performs:
-- target_concept_id is the UUID-resolved local concept.concept_id, not the
-- legacy source integer.

SELECT
  ct.source_concept_id,
  ct.target_uuid,
  ct.target_concept_id        AS seed_target_concept_id,
  c.concept_id                AS actual_concept_id_for_uuid,
  c.uuid                      AS actual_uuid
FROM refapp_28_demo.seed__concept_translation ct
LEFT JOIN openmrs.concept c ON c.uuid = ct.target_uuid
WHERE c.concept_id IS NULL                           -- UUID not found in target
   OR c.concept_id <> ct.target_concept_id           -- UUID found but local ID differs
;
