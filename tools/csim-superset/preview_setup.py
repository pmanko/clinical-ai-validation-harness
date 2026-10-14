"""Configure native Time Unit choices and an independent hourly comparison."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from superset.app import create_app

app = create_app()


def identity(name):
    return uuid5(NAMESPACE_URL, 'https://example.invalid/csim-preview/' + name)


with app.app_context():
    from superset import db, security_manager
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.connectors.sqla.models import SqlaTable, SqlMetric

    pin = json.loads(Path('/repro/preview.json').read_text())
    assert app.config['TIME_GRAIN_DENYLIST'] == []
    user = security_manager.find_user(username='demo')
    full = db.session.query(Dashboard).filter_by(slug='csim-full-synthetic').one()
    metadata = json.loads(full.json_metadata)
    grains = [f for f in metadata['native_filter_configuration'] if f.get('filterType') == 'filter_timegrain']
    assert len(grains) == 1
    grains[0]['time_grains'] = pin['csimTimeGrains']
    assert grains[0]['defaultDataMask']['filterState']['value'] == 'P1M'
    # The snapshot blocks Apply for empty required controls, leaving the old
    # chart values visible. Allow clearing to reach the dataset's existing
    # no-selection guards, which return empty results instead of mixed totals.
    for f in metadata['native_filter_configuration']:
        if f.get('type') == 'NATIVE_FILTER':
            f.setdefault('controlValues', {})['enableEmptyFilter'] = False
    full.json_metadata = json.dumps(metadata)
    full.dashboard_title = 'CSiM full dashboard — upstream snapshot'

    database = db.session.query(Database).filter_by(database_name='CSiM synthetic only').one()
    date_context = Path('/repro/sql/preview-date-context.sql').read_text()
    adapted = 0
    for saved in db.session.query(SqlaTable).filter_by(database_id=database.id):
        if saved.main_dttm_col == 'filter_anchor' and not saved.sql.startswith(date_context):
            saved.sql = date_context + saved.sql
            adapted += 1
        if saved.main_dttm_col == 'filter_anchor':
            # PostgreSQL accepts "3 months", not "1 quarter". Use a valid
            # interval literal directly in the dataset SQL.
            saved.sql = saved.sql.replace("INTERVAL '1 {{ grain }}'",
                "INTERVAL '{{ 3 if grain == \"quarter\" else 1 }} {{ \"months\" if grain == \"quarter\" else grain }}'")
    dataset = db.session.query(SqlaTable).filter_by(uuid=identity('hourly-dataset')).one_or_none()
    if dataset is None:
        dataset = SqlaTable(uuid=identity('hourly-dataset'), database=database, schema='public', table_name='Hourly reporting example')
        db.session.add(dataset)
    # Forty-eight hourly observations: alternating 2 and 4 specimens. Each day
    # totals 72, so changing Hour to Day must preserve a total of 144.
    dataset.sql = """SELECT TIMESTAMP '2026-01-05' + n * INTERVAL '1 hour' AS collected_at,
       CASE WHEN n % 2 = 0 THEN 2 ELSE 4 END AS specimens
FROM generate_series(0, 47) AS n"""
    dataset.main_dttm_col = 'collected_at'
    dataset.owners = [user]
    db.session.flush()
    dataset.fetch_metadata()
    for column in dataset.columns:
        if column.column_name == 'collected_at': column.is_dttm = True
    if not any(m.metric_name == 'Specimens' for m in dataset.metrics):
        dataset.metrics.append(SqlMetric(metric_name='Specimens', expression='SUM(specimens)'))
    db.session.flush()

    chart = db.session.query(Slice).filter_by(uuid=identity('hourly-chart')).one_or_none()
    if chart is None:
        chart = Slice(uuid=identity('hourly-chart'))
        db.session.add(chart)
    chart.slice_name = 'Specimens by collection time'
    chart.datasource_id, chart.datasource_type = dataset.id, 'table'
    chart.viz_type, chart.owners = 'echarts_timeseries_bar', [user]
    chart.params = json.dumps({
        'datasource': str(dataset.id)+'__table', 'viz_type':chart.viz_type,
        'x_axis':'collected_at', 'granularity_sqla':'collected_at', 'time_grain_sqla':'PT1H',
        'time_range':'2026-01-05 : 2026-01-07', 'metrics':['Specimens'], 'groupby':[],
        'adhoc_filters':[], 'row_limit':1000, 'order_desc':False, 'show_legend':False,
        'x_axis_title':'Collection time', 'x_axis_time_format':'smart_date', 'y_axis_format':',d',
        'rich_tooltip':True, 'color_scheme':'supersetColors', 'truncate_metric':True,
    })
    db.session.flush()
    dashboard = db.session.query(Dashboard).filter_by(slug='hourly-reporting-preview').one_or_none()
    if dashboard is None:
        dashboard = Dashboard(slug='hourly-reporting-preview', uuid=identity('hourly-dashboard'))
        db.session.add(dashboard)
    dashboard.dashboard_title = 'Hourly reporting — independent Time Unit choices'
    dashboard.published, dashboard.owners, dashboard.slices = True, [user], [chart]
    dashboard.position_json = json.dumps({
        'DASHBOARD_VERSION_KEY':'v2',
        'ROOT_ID':{'id':'ROOT_ID','type':'ROOT','children':['GRID_ID']},
        'GRID_ID':{'id':'GRID_ID','type':'GRID','parents':['ROOT_ID'],'children':['NOTICE','ROW']},
        'HEADER_ID':{'id':'HEADER_ID','type':'HEADER','meta':{'text':dashboard.dashboard_title}},
        'NOTICE':{'id':'NOTICE','type':'MARKDOWN','parents':['ROOT_ID','GRID_ID'],'children':[],
            'meta':{'width':12,'height':12,'code':'This dashboard offers **Hour, Day and Week**. The CSiM dashboard in this same Superset offers **Month, Quarter and Year**. Choose Day: both days should show 72 specimens.'}},
        'ROW':{'id':'ROW','type':'ROW','parents':['ROOT_ID','GRID_ID'],'children':['CHART'],'meta':{'background':'BACKGROUND_TRANSPARENT'}},
        'CHART':{'id':'CHART','type':'CHART','parents':['ROOT_ID','GRID_ID','ROW'],'children':[],
            'meta':{'chartId':chart.id,'uuid':str(chart.uuid),'sliceName':chart.slice_name,'width':12,'height':70}},
    })
    dashboard.json_metadata = json.dumps({'native_filter_configuration':[{
        'id':'NATIVE_FILTER-preview-hourly','name':'Time Unit','filterType':'filter_timegrain','type':'NATIVE_FILTER',
        'targets':[{'datasetId':dataset.id}], 'scope':{'rootPath':['ROOT_ID'],'excluded':[]},
        'cascadeParentIds':[], 'controlValues':{'enableEmptyFilter':False},
        'time_grains':pin['comparisonTimeGrains'],
        'defaultDataMask':{'extraFormData':{'time_grain_sqla':'PT1H'},'filterState':{'value':'PT1H','label':'Hour'}},
    }], 'color_scheme':'supersetColors'})
    db.session.commit()
    print(json.dumps({'snapshot':pin['commit'],'csimDashboard':full.id,'hourlyDashboard':dashboard.id,'hourlyChart':chart.id,'instanceDenylist':app.config['TIME_GRAIN_DENYLIST']}))
