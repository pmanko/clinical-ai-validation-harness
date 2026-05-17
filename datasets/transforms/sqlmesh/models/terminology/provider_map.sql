MODEL (
  name refapp_28_demo.terminology__provider_map,
  kind VIEW,
  description 'FK reconciliation map: legacy provider_id ↔ openmrs provider_id. Default policy: identity (legacy verbatim). See research.md §R-load-pattern.',
  tags (policy_bucket:passthrough),
  grain (source_id)
);

SELECT
  provider_id AS source_id,
  provider_id AS target_id
FROM refapp_28_demo.stg_provider
;
