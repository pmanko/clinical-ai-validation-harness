MODEL (
  name refapp_28_demo.stg_role_privilege,
  kind FULL,
  description 'Staging copy of legacy_27_raw.role_privilege with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (privilege, role),
  audits ()
);

SELECT
  src.role,
  src.privilege
FROM legacy_27_raw.role_privilege src

;
