MODEL (
  name refapp_28_demo.stg_hl7_source,
  kind FULL,
  description 'Staging copy of legacy_27_raw.hl7_source with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (hl7_source_id),
  audits (unique_values(columns := (hl7_source_id)))
);

SELECT
  src.hl7_source_id,
  src.name,
  src.description,
  src.creator,
  src.date_created,
  src.uuid
FROM legacy_27_raw.hl7_source src

;
