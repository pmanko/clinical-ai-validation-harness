SELECT patient_id
FROM analytics.lab_result_fact_v1
WHERE observed_at >= :start_date
ORDER BY patient_id
