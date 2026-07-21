SELECT observation_id, patient_id, test_name, result_value, observed_at
FROM analytics.lab_result_fact_v1
WHERE observed_at >= :start_date
ORDER BY observed_at DESC, observation_id
