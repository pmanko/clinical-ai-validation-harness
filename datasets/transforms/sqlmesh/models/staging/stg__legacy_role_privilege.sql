MODEL (
  name refapp_28_demo.staging.stg__legacy_role_privilege,
  kind FULL,
  description 'Staging copy of legacy_27_raw.role_privilege with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (privilege, role),
  audits (unique_values(columns := (privilege, role)))
);

SELECT
  src.role,
  src.privilege
FROM legacy_27_raw.role_privilege src

;
