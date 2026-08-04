SELECT
  observation_id,
  patient_id,
  test_name,
  result_value,
  result_unit,
  observed_at
FROM analytics.lab_result_fact_v1
WHERE observed_at >= :start_date
  AND result_value IS NOT NULL
ORDER BY observed_at, observation_id
