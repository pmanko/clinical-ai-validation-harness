AUDIT (
  name audit_no_child_with_adult_weight,
  dialect mysql
);

-- Physiological consistency: no patient under 13 (by corrected DOB) may have a
-- recorded weight >= 45 kg. Catches adults-coded-as-children that the age
-- reconciliation should have raised (the "67 kg toddler" class).

SELECT p.person_id, TIMESTAMPDIFF(YEAR, p.birthdate, DATE('2026-06-01')) AS age
FROM @this_model p
WHERE TIMESTAMPDIFF(YEAR, p.birthdate, DATE('2026-06-01')) < 13
  AND (
    SELECT MAX(o.value_numeric) FROM refapp_28_demo.stg_obs o
    WHERE o.person_id = p.person_id AND o.concept_id = 4168 AND o.value_numeric > 0
  ) >= 45
;
