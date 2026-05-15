MODEL (
  name refapp_28_demo.staging.stg__legacy_logic_token_registration,
  kind FULL,
  description 'Staging copy of legacy_27_raw.logic_token_registration with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (token_registration_id),
  audits (unique_values(columns := (token_registration_id)))
);

SELECT
  src.token_registration_id,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.token,
  src.provider_class_name,
  src.provider_token,
  src.configuration,
  src.uuid
FROM legacy_27_raw.logic_token_registration src

;
