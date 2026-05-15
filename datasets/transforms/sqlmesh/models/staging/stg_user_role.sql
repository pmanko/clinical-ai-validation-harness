MODEL (
  name refapp_28_demo.stg_user_role,
  kind FULL,
  description 'Staging copy of legacy_27_raw.user_role with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (role, user_id),
  audits ()
);

SELECT
  src.user_id,
  src.role
FROM legacy_27_raw.user_role src

;
