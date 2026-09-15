"""Exercise real Superset chart-data requests over HTTP, with synthetic data."""
import json
import math
import os
import sys
import io
import zipfile
from pathlib import Path
import requests

BASE = os.environ.get('CSIM_TEST_URL', 'http://localhost:8088' + os.environ.get('SUPERSET_APP_ROOT', '/').rstrip('/'))
# The service sees HTTPS through Caddy; use the same forwarded scheme for
# direct-container validation so Flask issues the configured secure cookie.
if os.environ.get('CSIM_PUBLIC_HTTPS') == '1':
    BASE = os.environ['CSIM_PUBLIC_URL'].rstrip('/')
session = requests.Session()
login = session.post(BASE + '/api/v1/security/login', json={
    'username': 'demo', 'password': os.environ['CSIM_ADMIN_PASSWORD'],
    'provider': 'db', 'refresh': True}, timeout=30)
login.raise_for_status()
session.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
csrf = session.get(BASE + '/api/v1/security/csrf_token/', timeout=30)
csrf.raise_for_status()
session.headers['X-CSRFToken'] = csrf.json()['result']
datasets = session.get(BASE + '/api/v1/dataset/', timeout=30).json()['result']
dataset_id = next(d['id'] for d in datasets if d['table_name'] == 'CSiM demo repaired')
RATE = 'Inappropriate diagnosis rate'


def query(grain='P1M', hospital='91', location='Inpatient',
          time_range='2025-11-01 : 2026-06-01'):
    filters = [{'col': column, 'op': 'IN', 'val': [value]}
               for column, value in [('hosp_code', hospital), ('location_name', location)]
               if value is not None]
    form_data = {'datasource': str(dataset_id) + '__table',
        'viz_type': 'echarts_timeseries_line', 'x_axis': 'time_aggregate',
        'time_grain_sqla': grain, 'granularity_sqla': 'month_date',
        'time_range': time_range, 'metrics': [RATE], 'groupby': [],
        'extra_filters': filters}
    payload = {'datasource': {'id': dataset_id, 'type': 'table'},
        'force': True, 'result_format': 'json', 'result_type': 'full',
        'form_data': form_data,
        'queries': [{'columns': ['time_aggregate'], 'metrics': [RATE, 'Submissions', 'Period order'],
            'granularity': 'month_date', 'time_range': time_range, 'filters': filters,
            'extras': {'time_grain_sqla': grain}, 'row_limit': 1000,
            'orderby': [['Period order', True]]}]}
    result = session.post(BASE + '/api/v1/chart/data', json=payload, timeout=60)
    if result.status_code != 200:
        raise AssertionError((result.status_code, result.text[:2000]))
    response = result.json()['result'][0]
    assert response['status'] == 'success', response
    return response['data']


rows = query()
assert [r['time_aggregate'] for r in rows] == ['Nov 2025', 'Dec 2025', 'Jan 2026', 'Feb 2026', 'Mar 2026', 'Apr 2026', 'May 2026'], rows
indexed = {r['time_aggregate']: r for r in rows}
assert indexed['Feb 2026'][RATE] is None and indexed['Feb 2026']['Submissions'] is None
assert indexed['Mar 2026'][RATE] == 0
assert indexed['Apr 2026'][RATE] is None and indexed['Apr 2026']['Submissions'] == 10, indexed['Apr 2026']
quarters = query('P3M')
assert [r['time_aggregate'] for r in quarters] == ['Q4 2025', 'Q1 2026', 'Q2 2026'], quarters
assert math.isclose(quarters[0][RATE], .11) and math.isclose(quarters[1][RATE], .1), quarters
years = query('P1Y')
assert [r['time_aggregate'] for r in years] == ['2025', '2026'], years
assert math.isclose(years[0][RATE], .11) and math.isclose(years[1][RATE], 3 / 18)
other_hospital = query(hospital='92')
assert math.isclose(other_hospital[3][RATE], .1)
other_location = query(location='Emergency Department', time_range='2026-01-01 : 2026-04-01')
assert [r[RATE] for r in other_location] == [.5, None, 2 / 6]
partial_quarter = query('P3M', time_range='2026-02-01 : 2026-04-01')
assert len(partial_quarter) == 1 and partial_quarter[0][RATE] == 0, partial_quarter
extended = query(time_range='2025-10-01 : 2026-07-01')
assert extended[0]['time_aggregate'] == 'Oct 2025' and extended[0][RATE] is None
assert extended[-1]['time_aggregate'] == 'Jun 2026' and extended[-1][RATE] is None
cohort = query('P3M', hospital='Cohort', time_range='2026-01-01 : 2026-04-01')
assert math.isclose(cohort[0][RATE], 12 / 50), cohort
assert query(hospital=None) == []
assert query(location=None) == []
assert query(hospital=None, location=None) == []
report = {'passed': 10, 'path': 'Superset chart-data HTTP API → PostgreSQL',
    'checks': ['month ordering', 'gap versus zero versus no denominator',
               'quarter aggregation and labels', 'year aggregation and labels',
               'hospital filter', 'location filter', 'partial-quarter date range',
               'leading and trailing gaps', 'cohort aggregation',
               'cleared required selections produce no repaired results'],
    'monthly': rows, 'quarterly': quarters, 'annual': years}
Path('/tmp/csim-verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if '--export' in sys.argv:
    dashboards = session.get(BASE + '/api/v1/dashboard/', timeout=30)
    dashboards.raise_for_status()
    dashboard_id = next(d['id'] for d in dashboards.json()['result'] if d['slug'] == 'csim-date-lab')
    exported = session.get(BASE + '/api/v1/dashboard/export/', params={'q': '!(' + str(dashboard_id) + ')'}, timeout=60)
    exported.raise_for_status()
    assert exported.content.startswith(b'PK'), 'Expected a Superset ZIP export'
    # This runtime includes the connection password in its native export.
    # Keep the ZIP structure and definitions, but require destination credentials
    # at import rather than distributing the demo database password.
    sanitized = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(exported.content)) as source, zipfile.ZipFile(sanitized, 'w', zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            contents = source.read(entry).decode('utf-8')
            contents = contents.replace(os.environ['CSIM_DB_PASSWORD'], 'XXXXXXXXXX')
            for key in ['CSIM_DB_PASSWORD', 'CSIM_ADMIN_PASSWORD', 'SUPERSET_SECRET_KEY']:
                assert os.environ[key] not in contents, 'Credential remains in export: ' + entry.filename
            target.writestr(entry.filename, contents)
    Path('/tmp/csim-dashboard-export.zip').write_bytes(sanitized.getvalue())
    print('Native dashboard export saved with the database password removed.')
