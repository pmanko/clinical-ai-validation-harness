MODEL (
  name refapp_28_demo.terminology__location_map,
  kind VIEW,
  description 'FK reconciliation map: legacy location_id ↔ openmrs location_id. Default policy: identity (legacy verbatim). See research.md §R-load-pattern + datasets/load/openmrs-loadback.review.md.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  location_id AS source_id,
  location_id AS target_id
FROM refapp_28_demo.stg_location
;
