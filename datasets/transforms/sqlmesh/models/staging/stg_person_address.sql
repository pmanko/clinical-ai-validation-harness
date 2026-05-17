MODEL (
  name refapp_28_demo.stg_person_address,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person_address with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (person_address_id),
  audits (unique_values(columns := (person_address_id)))
);

SELECT
  src.person_address_id,
  src.person_id,
  src.preferred,
  src.address1,
  src.address2,
  src.city_village,
  src.state_province,
  src.postal_code,
  src.country,
  src.latitude,
  src.longitude,
  src.creator,
  src.date_created,
  src.voided,
  src.voided_by,
  src.date_voided,
  src.void_reason,
  src.county_district,
  src.address3,
  src.address6,
  src.address5,
  src.address4,
  src.uuid,
  src.date_changed,
  src.changed_by,
  src.start_date,
  src.end_date,
  src.address7,
  src.address8,
  src.address9,
  src.address10,
  src.address11,
  src.address12,
  src.address13,
  src.address14,
  src.address15
FROM legacy_27_raw.person_address src

;
