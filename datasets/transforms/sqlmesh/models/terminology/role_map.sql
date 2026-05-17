MODEL (
  name refapp_28_demo.terminology__role_map,
  kind VIEW,
  description 'FK reconciliation map: legacy role ↔ openmrs role (the role NAME is the PK in openmrs.role, not a numeric id). Default policy: identity (legacy verbatim). If an openmrs default role and a legacy role collide on name with different semantics, surface during iteration and decide per-case. See research.md §R-load-pattern.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  role AS source_id,
  role AS target_id
FROM refapp_28_demo.stg_role
;
