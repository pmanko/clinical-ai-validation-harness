MODEL (
  name refapp_28_demo.stg_user_property,
  kind FULL,
  description 'Staging copy of legacy_27_raw.user_property with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (user_id, property),
  audits ()
);

SELECT
  src.user_id,
  src.property,
  src.property_value
FROM legacy_27_raw.user_property src

;
