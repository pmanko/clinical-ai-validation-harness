MODEL (
  name refapp_28_demo.stg_role,
  kind FULL,
  description 'Staging copy of legacy_27_raw.role with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (role),
  audits (unique_values(columns := (role)))
);

SELECT
  src.role,
  src.description,
  src.uuid
FROM legacy_27_raw.role src

;
