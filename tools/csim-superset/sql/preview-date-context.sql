{# Upstream no longer supplies from_dttm/to_dttm. Read the native date filter
   explicitly, retaining the existing calendar, partial-period and anchor SQL. #}
{% set selected_window = get_time_filter('filter_anchor', strftime='%Y-%m-%d %H:%M:%S') %}
{% set from_dttm = selected_window.from_expr %}
{% set to_dttm = selected_window.to_expr %}
