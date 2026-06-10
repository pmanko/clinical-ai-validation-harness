AUDIT (
  name audit_person_address_one_preferred,
  dialect mysql
);

-- Every person who has at least one non-voided address MUST have exactly one
-- of them flagged preferred = 1. The legacy 2.7 corpus ships no preferred
-- address at all, so OpenMRS FHIR emits every address with use="old" and the
-- O3 patient header renders no address. stg_person_address derives a single
-- preferred address per person to fix that. This audit guards the invariant.
-- Emits failing rows (person_id + the bad count) on fail; zero rows on pass.

SELECT person_id, SUM(CASE WHEN preferred = 1 THEN 1 ELSE 0 END) AS preferred_count
FROM @this_model
WHERE voided = 0
GROUP BY person_id
HAVING SUM(CASE WHEN preferred = 1 THEN 1 ELSE 0 END) <> 1
;
