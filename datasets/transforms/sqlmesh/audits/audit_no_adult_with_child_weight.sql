AUDIT (
  name audit_no_adult_with_child_weight,
  dialect mysql
);

-- Physiological consistency: no patient aged >= 15 (by corrected DOB) may have a
-- maximum recorded weight < 25 kg. Catches children-coded-as-adults that the age
-- reconciliation should have lowered.

SELECT p.person_id, TIMESTAMPDIFF(YEAR, p.birthdate, DATE('2026-06-01')) AS age
FROM @this_model p
WHERE TIMESTAMPDIFF(YEAR, p.birthdate, DATE('2026-06-01')) >= 15
  AND (
    SELECT MAX(o.value_numeric) FROM refapp_28_demo.stg_obs o
    WHERE o.person_id = p.person_id AND o.concept_id = 4168 AND o.value_numeric > 0
  ) < 25
;
