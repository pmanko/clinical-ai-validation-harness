MODEL (
  name refapp_28_demo.stg_privilege,
  kind FULL,
  description 'Staging copy of legacy_27_raw.privilege with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (privilege),
  audits (unique_values(columns := (privilege)))
);

SELECT
  src.privilege,
  src.description,
  src.uuid
FROM legacy_27_raw.privilege src

;
