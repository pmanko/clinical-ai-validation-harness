MODEL (
  name refapp_28_demo.stg_person_address,
  kind FULL,
  description 'Staging copy of legacy_27_raw.person_address. All columns pass through 1:1 EXCEPT preferred: the legacy 2.7 corpus marks no preferred address (all 0), so OpenMRS FHIR emits every address with use="old" and the O3 patient header shows no address. We deterministically flag the single non-voided address per person as preferred so the chart renders it. This is a demo-display normalization, NOT source-faithful for the preferred column.',
  tags (policy_bucket:passthrough),
  grain (person_address_id),
  audits (
    unique_values(columns := (person_address_id)),
    audit_person_address_one_preferred
  )
);

SELECT
  src.person_address_id,
  src.person_id,
  -- Derived (see model description): mark the single current non-voided address
  -- per person preferred. ORDER BY voided ASC ensures a non-voided row wins rank
  -- 1 when one exists; date_created DESC picks the most recently entered as
  -- "current"; person_address_id DESC is the deterministic tie-break (SC-004).
  CASE
    WHEN src.voided = 0
     AND ROW_NUMBER() OVER (
           PARTITION BY src.person_id
           ORDER BY src.voided ASC, src.date_created DESC, src.person_address_id DESC
         ) = 1
    THEN 1
    ELSE 0
  END AS preferred,
  src.address1,
  src.address2,
  src.city_village,
  src.state_province,
  src.postal_code,
  src.country,
  src.latitude,
  src.longitude,
  src.creator,
  @shift_date(src.date_created) AS date_created,
  src.voided,
  src.voided_by,
  @shift_date(src.date_voided) AS date_voided,
  src.void_reason,
  src.county_district,
  src.address3,
  src.address6,
  src.address5,
  src.address4,
  src.uuid,
  @shift_date(src.date_changed) AS date_changed,
  src.changed_by,
  @shift_date(src.start_date) AS start_date,
  @shift_date(src.end_date) AS end_date,
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
