MODEL (
  name refapp_28_demo.staging.stg__legacy_tribe,
  kind FULL,
  description 'Staging copy of legacy_27_raw.tribe with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (tribe_id),
  audits (unique_values(columns := (tribe_id)))
);

SELECT
  src.tribe_id,
  src.retired,
  src.name
FROM legacy_27_raw.tribe src

;
