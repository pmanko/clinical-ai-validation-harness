MODEL (
  name refapp_28_demo.terminology__user_map,
  kind VIEW,
  description 'FK reconciliation map: legacy user_id ↔ openmrs user_id. Default policy: identity (legacy verbatim). Used by the dlt loader to harmonize legacy user references against openmrs CIEL-baseline. If a future iteration surfaces an ID collision, replace this body with an explicit renumber. See datasets/load/openmrs-loadback.review.md for the rationale + research.md §R-load-pattern.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  user_id AS source_id,
  user_id AS target_id
FROM refapp_28_demo.stg_users
;
