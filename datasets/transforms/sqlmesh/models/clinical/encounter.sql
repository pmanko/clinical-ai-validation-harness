MODEL (
  name refapp_28_demo.clin__encounter,
  kind FULL,
  description 'Terminal encounter model: stg_encounter passthrough with visit_id resolved to the reconstructed per-day visit (clin__visit). Replaces stg_encounter as the encounter load source so every encounter is linked to a visit (source had all visit_id NULL).',
  tags (policy_bucket:passthrough),
  grain (encounter_id),
  audits (
    unique_values(columns := (encounter_id)),
    audit_encounter_visit_id_not_null
  )
);

-- All stg_encounter columns pass through unchanged (already date-transplanted);
-- only visit_id is set, by joining the per-day visit on (patient_id, day).
-- DATE(v.date_started) = the visit's calendar day = DATE(e.encounter_datetime),
-- and clin__visit holds exactly one row per (patient_id, day), so the join is 1:1.
SELECT
  e.encounter_id,
  e.encounter_type,
  e.patient_id,
  e.location_id,
  e.form_id,
  e.encounter_datetime,
  e.creator,
  e.date_created,
  e.voided,
  e.voided_by,
  e.date_voided,
  e.void_reason,
  e.uuid,
  e.changed_by,
  e.date_changed,
  v.visit_id
FROM refapp_28_demo.stg_encounter e
LEFT JOIN refapp_28_demo.clin__visit v
  ON v.patient_id = e.patient_id
 AND DATE(v.date_started) = DATE(e.encounter_datetime)
;
