{# The native Time Unit filter supplies time_grain in Superset 6.1. #}
{% set grain = {'P1M': 'month', 'P3M': 'quarter', 'P1Y': 'year'}.get(time_grain, 'month') %}
{% set label_format = {'month': 'Mon YYYY', 'quarter': '"Q"Q YYYY', 'year': 'YYYY'}[grain] %}
WITH bounds AS (
  SELECT
    {% if from_dttm %} TIMESTAMP '{{ from_dttm }}' {% else %} min_month::timestamp {% endif %} AS start_at,
    {% if to_dttm %} TIMESTAMP '{{ to_dttm }}' {% else %} (max_month + INTERVAL '1 month')::timestamp {% endif %} AS end_at
  FROM (SELECT MIN(month_date) AS min_month, MAX(month_date) AS max_month
        FROM public.csim_baseline) source_bounds
), calendar AS (
  SELECT month_start::date AS month_date
  FROM bounds CROSS JOIN LATERAL generate_series(
    date_trunc('month', start_at),
    date_trunc('month', end_at - INTERVAL '1 microsecond'),
    INTERVAL '1 month'
  ) month_start
), series AS (
  -- Keep hospital/state/cohort and location labels on the generated rows.
  -- An outer dashboard filter must not discard a gap because its labels are NULL.
  SELECT DISTINCT hosp_num, hosp_code, state, location_name, location_code
  FROM public.csim_baseline
)
SELECT s.*, c.month_date,
       date_trunc('{{ grain }}', c.month_date)::date AS period_start,
       EXTRACT(EPOCH FROM date_trunc('{{ grain }}', c.month_date)) AS period_sort,
       to_char(c.month_date, '{{ label_format }}') AS time_aggregate,
       b.ucsub, b.txpos, b.asbtreated, b.aspn_treated, b.asbcase,
       b.pos_ua, b.dur_sum, b.dur_count,
       CASE WHEN b.month_date IS NULL THEN 'No submissions'
            WHEN b.txpos = 0 THEN 'No qualifying denominator'
            ELSE 'Reported' END AS reporting_status
FROM series s CROSS JOIN calendar c
LEFT JOIN public.csim_baseline b
  ON b.hosp_code = s.hosp_code AND b.location_code = s.location_code
 AND b.month_date = c.month_date
-- Clear all in this Superset build still submits queries despite required UI
-- filters. With overlapping rollup rows, only a single selected series is valid.
WHERE {{ 'TRUE' if filter_values('hosp_code') | length == 1
                    and filter_values('location_name') | length == 1 else 'FALSE' }}
-- Time range filtering remains on month_date, not the formatted label or
-- period_start. A February-March range can legitimately have a Q1 label.
