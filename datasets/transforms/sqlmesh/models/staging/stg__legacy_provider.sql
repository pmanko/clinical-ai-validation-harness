MODEL (
  name refapp_28_demo.staging.stg__legacy_provider,
  kind FULL,
  description 'Staging copy of legacy_27_raw.provider with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (provider_id),
  audits (unique_values(columns := (provider_id)))
);

SELECT
  src.provider_id,
  src.person_id,
  src.name,
  src.identifier,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid,
  src.role_id,
  src.speciality_id
FROM legacy_27_raw.provider src

;
