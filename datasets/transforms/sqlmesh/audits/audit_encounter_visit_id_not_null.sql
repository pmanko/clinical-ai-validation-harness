AUDIT (
  name audit_encounter_visit_id_not_null,
  dialect mysql
);

-- Every encounter must be linked to a reconstructed visit. The source had all
-- visit_id NULL; after clin__encounter resolves them, any remaining NULL means a
-- visit was not built for that (patient, day) — a real defect. Returned rows fail.

SELECT encounter_id
FROM @this_model
WHERE visit_id IS NULL
;
