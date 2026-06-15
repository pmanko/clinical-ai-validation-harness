AUDIT (
  name audit_no_pregnant_male,
  dialect mysql
);

-- After sex reconciliation, no patient with a POSITIVE pregnancy signal
-- (weeks-pregnant / ARV-in-pregnancy / gravida / parity / pregnancy-status=Yes)
-- may be coded male. Any returned row is an uncorrected pregnant-male.

SELECT p.person_id
FROM @this_model p
WHERE p.gender = 'M'
  AND EXISTS (
    SELECT 1 FROM refapp_28_demo.stg_obs o
    WHERE o.person_id = p.person_id
      AND (o.concept_id IN (37155, 52123, 11400, 55898)
           OR (o.concept_id = 3373 AND o.value_coded = 771))
  )
;
