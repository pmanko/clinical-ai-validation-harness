AUDIT (
  name audit_allergy_not_voided,
  dialect mysql
);

-- Promoted allergies represent active clinical records and MUST have voided = 0.
-- Emits failing rows on fail; zero rows on pass.

SELECT allergy_id_proxy, voided
FROM (
  SELECT source_obs_id AS allergy_id_proxy, voided
  FROM refapp_28_demo.clin__allergy
) t
WHERE voided <> 0
;
