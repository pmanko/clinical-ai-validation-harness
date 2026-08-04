SELECT
  observation_id,
  patient_id,
  test_name,
  result_value,
  result_unit,
  observed_at
FROM analytics.lab_result_fact_v1
WHERE test_name = :test_name
ORDER BY observed_at DESC, observation_id
-- successor refinement
