"""Create a real Superset dashboard backed only by local synthetic tables."""
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from superset.app import create_app
from superset import db, security_manager
app = create_app()
from superset.models.core import Database
from superset.models.dashboard import Dashboard
from superset.models.slice import Slice
from superset.connectors.sqla.models import SqlaTable, TableColumn, SqlMetric

ROOT = Path('/repro')
TIME_RANGE = '2025-11-01 : 2026-06-01'


def identity(name):
    return uuid5(NAMESPACE_URL, 'https://example.invalid/csim-synthetic/' + name)


def setup():
    user = security_manager.find_user(username='demo')
    if not user:
        user = security_manager.add_user('demo', 'Synthetic', 'Demo',
            'demo@example.invalid', security_manager.find_role('Admin'),
            os.environ['CSIM_ADMIN_PASSWORD'])
    database = db.session.query(Database).filter_by(database_name='CSiM synthetic only').one_or_none()
    if database is None:
        database = Database(database_name='CSiM synthetic only', uuid=identity('database'))
        db.session.add(database)
    database.sqlalchemy_uri = 'postgresql+psycopg2://csim:' + os.environ['CSIM_DB_PASSWORD'] + '@db:5432/csim_synthetic'
    database.expose_in_sqllab = True
    db.session.flush()
    datasets = {}
    for kind in ['baseline', 'repaired']:
        name = 'CSiM demo ' + kind
        dataset = db.session.query(SqlaTable).filter_by(table_name=name, database_id=database.id).one_or_none()
        if dataset is None:
            dataset = SqlaTable(table_name=name, database=database, uuid=identity(kind), schema='public')
            db.session.add(dataset)
        dataset.sql = 'SELECT * FROM public.csim_baseline' if kind == 'baseline' else (ROOT / 'sql/repaired.sql').read_text()
        dataset.main_dttm_col = 'month_date'
        dataset.owners = [user]
        db.session.flush()
        dataset.fetch_metadata()
        for col in dataset.columns:
            if col.column_name in ['month_date', 'period_start']:
                col.is_dttm = True
        definitions = {'Submissions': 'SUM(ucsub)'}
        if kind == 'baseline':
            definitions['Maximum monthly rate'] = 'MAX(inappdx)'
        else:
            definitions['Inappropriate diagnosis rate'] = 'SUM(asbtreated)::float / NULLIF(SUM(txpos), 0)'
            definitions['Period order'] = 'MIN(period_sort)'
        for name, expression in definitions.items():
            metric = next((m for m in dataset.metrics if m.metric_name == name), None)
            if metric is None:
                metric = SqlMetric(metric_name=name, expression=expression)
                dataset.metrics.append(metric)
            metric.expression = expression
        datasets[kind] = dataset
    db.session.flush()
    charts = []
    for kind, title, metric in [
        ('baseline', 'Before: monthly maximum, no calendar', 'Maximum monthly rate'),
        ('repaired', 'After: complete periods and pooled rate', 'Inappropriate diagnosis rate'),
        ('repaired', 'After: submissions by reporting period', 'Submissions'),
    ]:
        chart = db.session.query(Slice).filter_by(uuid=identity(title)).one_or_none()
        if chart is None:
            chart = Slice(uuid=identity(title))
            db.session.add(chart)
        dataset = datasets[kind]
        chart.slice_name = title
        chart.datasource_id = dataset.id
        chart.datasource_type = 'table'
        chart.viz_type = 'echarts_timeseries_line'
        chart.owners = [user]
        params = {
            'datasource': str(dataset.id) + '__table', 'viz_type': chart.viz_type,
            'x_axis': 'month_date' if kind == 'baseline' else 'time_aggregate',
            'granularity_sqla': 'month_date', 'time_grain_sqla': 'P1M',
            'time_range': TIME_RANGE, 'metrics': [metric], 'groupby': [],
            'adhoc_filters': [], 'row_limit': 1000, 'order_desc': False,
            'show_legend': False, 'rich_tooltip': True, 'markerEnabled': True,
            'markerSize': 7, 'seriesType': 'line', 'color_scheme': 'supersetColors',
            'x_axis_title': 'Reporting period', 'x_axis_time_format': 'smart_date',
            'tooltipTimeFormat': 'smart_date', 'x_axis_label_rotation': 0,
            'x_axis_title_margin': 42,
            'y_axis_format': ',d' if metric == 'Submissions' else '.0%',
            'y_axis_bounds': [0, None if metric == 'Submissions' else 1],
            'truncate_metric': True, 'force_max_interval': True,
        }
        if kind == 'repaired':
            params.update({'x_axis_sort': 'Period order', 'x_axis_sort_asc': True,
                'timeseries_limit_metric': 'Period order', 'x_axis_force_categorical': True,
                'x_axis_label_interval': 0, 'x_axis_label_rotation': 30})
        chart.params = json.dumps(params)
        charts.append(chart)
    db.session.flush()
    dashboard = db.session.query(Dashboard).filter_by(slug='csim-date-lab').one_or_none()
    if dashboard is None:
        dashboard = Dashboard(slug='csim-date-lab', uuid=identity('dashboard'))
        db.session.add(dashboard)
    dashboard.dashboard_title = 'CSiM date and filter lab — synthetic data'
    dashboard.published = True
    dashboard.owners = [user]
    dashboard.slices = charts
    positions = {
        'DASHBOARD_VERSION_KEY': 'v2',
        'ROOT_ID': {'id': 'ROOT_ID', 'type': 'ROOT', 'children': ['GRID_ID']},
        'GRID_ID': {'id': 'GRID_ID', 'type': 'GRID', 'parents': ['ROOT_ID'], 'children': ['NOTICE', 'ROW-0', 'ROW-1']},
        'HEADER_ID': {'id': 'HEADER_ID', 'type': 'HEADER', 'meta': {'text': dashboard.dashboard_title}},
        'NOTICE': {'id': 'NOTICE', 'type': 'MARKDOWN', 'parents': ['ROOT_ID', 'GRID_ID'], 'children': [],
            'meta': {'width': 12, 'height': 12, 'code': '**Entirely synthetic demo data.** Select hospital 91 / Inpatient. February is missing; March is a valid 0%; April has no denominator. Switch Month → Quarter → Year. Q1 should be 10%, not the monthly maximum of 100%.'}},
    }
    for i, chart in enumerate(charts):
        row = 'ROW-' + str(0 if i < 2 else 1)
        node = 'CHART-' + str(chart.id)
        if row not in positions:
            positions[row] = {'id': row, 'type': 'ROW', 'parents': ['ROOT_ID', 'GRID_ID'], 'children': [], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}}
        positions[row]['children'].append(node)
        positions[node] = {'id': node, 'type': 'CHART', 'parents': ['ROOT_ID', 'GRID_ID', row], 'children': [],
            'meta': {'chartId': chart.id, 'uuid': str(chart.uuid), 'sliceName': chart.slice_name, 'width': 6 if i < 2 else 12, 'height': 48}}
    dashboard.position_json = json.dumps(positions)
    chart_ids = [chart.id for chart in charts]
    filters = []
    for name, column, default in [('Hospital / cohort', 'hosp_code', '91'), ('Care location', 'location_name', 'Inpatient')]:
        filters.append({'id': 'NATIVE_FILTER-' + column, 'name': name, 'filterType': 'filter_select',
            # The unguarded baseline supplies options even before a selection.
            # Repaired queries require a selected series to avoid rollup overlap.
            'targets': [{'datasetId': datasets['baseline'].id, 'column': {'name': column}}],
            # The source contains overlapping hospital/state/cohort and location
            # totals. An empty selection must not sum those levels together.
            'controlValues': {'multiSelect': False, 'enableEmptyFilter': True, 'defaultToFirstItem': False, 'sortAscending': True},
            'defaultDataMask': {'extraFormData': {'filters': [{'col': column, 'op': 'IN', 'val': [default]}]}, 'filterState': {'value': [default], 'label': default}},
            'cascadeParentIds': [], 'scope': {'rootPath': ['ROOT_ID'], 'excluded': []}, 'chartsInScope': chart_ids, 'type': 'NATIVE_FILTER'})
    for name, key, plugin, value in [('Time Period', 'time_range', 'filter_time', TIME_RANGE), ('Time Unit', 'time_grain_sqla', 'filter_timegrain', 'P1M')]:
        filters.append({'id': 'NATIVE_FILTER-' + key, 'name': name, 'filterType': plugin,
            'targets': [{'datasetId': datasets['repaired'].id}], 'controlValues': {},
            'defaultDataMask': {'extraFormData': {key: value}, 'filterState': {'value': value}},
            'cascadeParentIds': [], 'scope': {'rootPath': ['ROOT_ID'], 'excluded': []}, 'chartsInScope': chart_ids, 'type': 'NATIVE_FILTER'})
    dashboard.json_metadata = json.dumps({'native_filter_configuration': filters, 'cross_filters_enabled': False,
        'color_scheme': 'supersetColors', 'refresh_frequency': 0, 'label_colors': {}})
    db.session.commit()
    print(json.dumps({'dashboard': os.environ.get('CSIM_PUBLIC_URL', 'http://127.0.0.1:18089').rstrip('/') + '/superset/dashboard/csim-date-lab/',
        'dataset_ids': {k: v.id for k, v in datasets.items()}, 'chart_ids': chart_ids, 'synthetic_only': True}))


if __name__ == '__main__':
    with app.app_context():
        setup()
