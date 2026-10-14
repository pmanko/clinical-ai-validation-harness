"""Use the CSiM development layout with synthetic data only.

The source snapshot contains definitions, never connection credentials or rows.
Bucket raw records before the original calculations so their cohort weighting
survives a change of period. Apply the range to original dates. A separate
filter anchor keeps Superset's outer predicate from discarding a partial period.
"""
import copy
import json
import os
import re
from pathlib import Path

from setup_dashboard import app, db, security_manager, Database, Dashboard, Slice
from setup_dashboard import SqlaTable, SqlMetric, identity, ROOT, TIME_RANGE

SOURCE = ROOT / 'output/source-dashboard-20260910.json'
SLUG = 'csim-full-synthetic'


def filter_anchor(sql):
    # Raw dates are filtered inside the query before calculation. Superset also
    # emits an outer predicate. Its helper column must remain inside that range,
    # even when a quarter starts before it, or an overall chart has no date axis.
    return '''SELECT p.*,
{% if from_dttm %} TIMESTAMP '{{ from_dttm }}'
{% elif to_dttm %} TIMESTAMP '{{ to_dttm }}' - INTERVAL '1 microsecond'
{% else %} TIMESTAMP '1970-01-01' {% endif %} AS filter_anchor
FROM (\n''' + sql + '\n) p'


def category_calendar(sql, antibiotic):
    keys=['hosp_num','hosp_code','state','location_name','location_code']
    if antibiotic:keys.append('antibiotic_name')
    values='b.prescription_count,b.rnk' if antibiotic else 'b.n_submissions'
    join=' AND '.join('b.'+k+'=s.'+k for k in ['hosp_code','location_code']+(['antibiotic_name'] if antibiotic else []))
    prelude_end=sql.index('%}',sql.index('{% set tf'))+2
    prelude=sql[:prelude_end];body=sql[prelude_end:]
    return prelude+'''WITH observed AS (
'''+body+'''
), bounds AS (
SELECT {% if from_dttm %} TIMESTAMP '{{ from_dttm }}' {% else %} MIN(month_date) {% endif %} AS start_at,
       {% if to_dttm %} TIMESTAMP '{{ to_dttm }}' {% else %} MAX(month_date)+INTERVAL '1 {{ grain }}' {% endif %} AS end_at
FROM observed HAVING COUNT(*) >= 0
), calendar AS (
SELECT d::date AS month_date FROM bounds CROSS JOIN LATERAL generate_series(
date_trunc('{{ grain }}',start_at),date_trunc('{{ grain }}',end_at-INTERVAL '1 microsecond'),INTERVAL '1 {{ grain }}') d
), dimensions AS (SELECT DISTINCT '''+','.join(keys)+''' FROM observed)
SELECT s.*,c.month_date,EXTRACT(EPOCH FROM c.month_date) AS period_sort,
       to_char(c.month_date,'{{ label_format }}') AS time_aggregate,'''+values+'''
FROM dimensions s CROSS JOIN calendar c LEFT JOIN observed b ON '''+join+' AND b.month_date=c.month_date'


def period_sql(source, calendar=False, bucket=True, location_required=False):
    source = source.replace('\r\n', '\n').strip().rstrip(';')
    match = re.match(r'WITH raw_data AS \((.*?)\),\s*(\w+) AS', source, re.S)
    if not match:
        raise ValueError('Unrecognized source SQL; inspect before adapting')
    raw = match.group(1)
    fields = [s.strip() for s in re.search(r'SELECT(.*?)FROM', raw, re.S).group(1).split(',')]
    assert all(re.fullmatch(r'[a-z0-9_]+', f) for f in fields)
    expressions = []
    for field in fields:
        if bucket and field in ('month', 'year'):
            expressions.append("EXTRACT(" + field + " FROM date_trunc('{{ grain }}', make_date(year::int, month::int, 1)))::int AS " + field)
        else:
            expressions.append(field)
    filtered = '''), raw_data AS (
SELECT ''' + ', '.join(expressions) + ''' FROM source_raw
WHERE TRUE
{% if tf.from_expr %} AND make_date(year::int, month::int, 1) >= {{ tf.from_expr }} {% endif %}
{% if tf.to_expr %} AND make_date(year::int, month::int, 1) < {{ tf.to_expr }} {% endif %}
), ''' + match.group(2) + ' AS'
    adapted = 'WITH source_raw AS (' + raw + filtered + source[match.end():]
    if bucket:
        adapted = adapted.replace("TO_CHAR(h.month_date, 'Mon YYYY')", "TO_CHAR(h.month_date, '{{ label_format }}')")
    header = '''{% set grain = {'P1M':'month','P3M':'quarter','P1Y':'year'}.get(time_grain, 'month') %}
{% set label_format = {'month':'YYYY-MM','quarter':'YYYY "Q"Q','year':'YYYY'}[grain] %}
{% set tf = {'from_expr': "TIMESTAMP '" ~ from_dttm ~ "'" if from_dttm else none,
             'to_expr': "TIMESTAMP '" ~ to_dttm ~ "'" if to_dttm else none} %}
'''
    guard = "{{ 'TRUE' if filter_values('hosp_code') | length > 0"
    if location_required:
        guard += " and filter_values('location_name') | length == 1"
    guard += " else 'FALSE' }}"
    if not calendar:
        return header + 'SELECT * FROM (\n' + adapted + '\n) selected WHERE ' + guard
    return header + '''WITH observed AS (
''' + adapted + '''
), bounds AS (
 SELECT {% if tf.from_expr %} {{ tf.from_expr }} {% else %} MIN(month_date) {% endif %} AS start_at,
        {% if tf.to_expr %} {{ tf.to_expr }} {% else %} MAX(month_date) + INTERVAL '1 {{ grain }}' {% endif %} AS end_at
 FROM observed HAVING COUNT(*) >= 0
), calendar AS (
 SELECT d::date AS month_date FROM bounds CROSS JOIN LATERAL generate_series(
 date_trunc('{{ grain }}', start_at), date_trunc('{{ grain }}', end_at - INTERVAL '1 microsecond'),
 INTERVAL '1 {{ grain }}') d
), dimensions AS (
 SELECT DISTINCT hosp_num,hosp_code,state,location_name,location_code FROM public.csim_baseline
)
SELECT s.*, c.month_date, EXTRACT(EPOCH FROM c.month_date) AS period_sort,
       to_char(c.month_date, '{{ label_format }}') AS time_aggregate,
       b.ucsub,b.txpos,b.asbtreated,b.aspn_treated,b.asbcase,b.pos_ua,b.dur_sum,b.dur_count,
       b.dur_cat_1,b.dur_cat_2,b.dur_cat_3,b.dur_cat_4,
       b.inappdx,b.inappdx_aspn,b.prev,b.txrate,b.pos_ua_rate,b.medabxdur
FROM dimensions s CROSS JOIN calendar c LEFT JOIN observed b
 ON b.hosp_code=s.hosp_code AND b.location_code=s.location_code AND b.month_date=c.month_date
WHERE ''' + guard


def setup():
    source = json.loads(SOURCE.read_text())
    assert len(source['charts']) == 21
    user = security_manager.find_user(username='demo')
    database = db.session.query(Database).filter_by(database_name='CSiM synthetic only').one()
    # This is the sole allowed execution connection for the restored definitions.
    assert database.sqlalchemy_uri.endswith('@db:5432/csim_synthetic')
    datasets = {}
    for original in source['datasets']:
        sid = original['id']
        if sid not in [35,36,37,38,40,41]:
            continue
        d = db.session.query(SqlaTable).filter_by(uuid=identity('full-dataset-' + str(sid))).one_or_none()
        if d is None:
            d = SqlaTable(uuid=identity('full-dataset-' + str(sid)), database=database, schema='v1')
            db.session.add(d)
        d.table_name = 'CSiM synthetic full — ' + original['table_name']
        d.sql = period_sql(original['sql'], calendar=sid==40, bucket=sid!=41, location_required=sid in [37,40,41])
        if sid in [37,38]:
            d.sql = category_calendar(d.sql,sid==37)
        if sid in [35,36,41]:
            d.sql = 'SELECT p.*, NULL::date AS month_date FROM (\n' + d.sql + '\n) p'
        d.sql = filter_anchor(d.sql)
        d.main_dttm_col = 'filter_anchor'
        d.owners = [user]
        db.session.flush(); d.fetch_metadata()
        for col in d.columns:
            if col.column_name in ['month_date','filter_anchor']: col.is_dttm = True
        if sid in [37,38,40] and not any(m.metric_name=='Period order' for m in d.metrics):
            d.metrics.append(SqlMetric(metric_name='Period order',expression='MIN(period_sort)'))
        datasets[sid] = d
    # Latest-data indicator must use actual observations, never generated dates.
    latest = db.session.query(SqlaTable).filter_by(uuid=identity('full-latest')).one_or_none()
    if latest is None:
        latest = SqlaTable(uuid=identity('full-latest'),database=database,schema='public',table_name='CSiM synthetic full — actual observation dates')
        db.session.add(latest)
    original40 = next(t for t in source['datasets'] if t['id']==40)
    latest.sql = filter_anchor(period_sql(original40['sql'], bucket=False, location_required=True))
    latest.main_dttm_col='filter_anchor'; latest.owners=[user]
    db.session.flush();latest.fetch_metadata()
    charts = {}
    for original in source['charts']:
        oldid = original['id']; d = latest if oldid==107 else datasets[original['datasource_id']]
        c = db.session.query(Slice).filter_by(uuid=identity('full-chart-'+str(oldid))).one_or_none()
        if c is None:
            c=Slice(uuid=identity('full-chart-'+str(oldid)));db.session.add(c)
        c.slice_name=original['slice_name'];c.viz_type=original['viz_type'];c.owners=[user]
        c.datasource_id=d.id;c.datasource_type='table'
        p=json.loads(original['params']);p['datasource']=str(d.id)+'__table'
        p.pop('slice_id',None);p.pop('dashboards',None);p['time_range']=TIME_RANGE;p['time_grain_sqla']='P1M'
        p['granularity_sqla']='filter_anchor'
        p['adhoc_filters']=[f for f in p.get('adhoc_filters',[]) if f.get('subject')!='hosp_code']
        for f in p['adhoc_filters']:
            if f.get('operator')=='TEMPORAL_RANGE':f['subject']='filter_anchor'
        if oldid==107:p.update(time_format='%b %Y',force_timestamp_formatting=True)
        if oldid==100:
            p['adhoc_filters'].append({'clause':'WHERE','expressionType':'SIMPLE','subject':'hosp_code','operator':'IN','comparator':['Cohort']})
            p['time_range']='No filter'
        if oldid==106:p['time_range']='No filter'
        if p.get('x_axis')=='month_date':
            p.update(x_axis='time_aggregate',x_axis_sort='name',x_axis_sort_asc=True,
                     timeseries_limit_metric='Period order',x_axis_force_categorical=True,
                     x_axis_label_interval=0,x_axis_label_rotation=30,x_axis_title_margin=45,
                     order_desc=False,row_limit=1000,show_empty_columns=True)
        c.params=json.dumps(p); charts[oldid]=c
    db.session.flush()
    dashboard=db.session.query(Dashboard).filter_by(slug=SLUG).one_or_none()
    if dashboard is None:
        dashboard=Dashboard(slug=SLUG,uuid=identity('full-dashboard'));db.session.add(dashboard)
    dashboard.dashboard_title='CSiM full dashboard — synthetic review'
    dashboard.published=True;dashboard.owners=[user];dashboard.slices=list(charts.values())
    positions=json.loads(source['dashboard']['position_json'])
    for node in positions.values():
        if not isinstance(node,dict):continue
        meta=node.get('meta',{})
        if node.get('type')=='CHART':
            c=charts[meta['chartId']];meta.update(chartId=c.id,uuid=str(c.uuid),sliceName=c.slice_name)
        if node.get('type')=='MARKDOWN':
            code=meta.get('code','')
            if '<img ' in code:code='**CSiM · Synthetic review copy**'
            if 'Most recent data import' in code:code='*Invented records only · November 2025–May 2026*'
            if 'Data source:' in code:code='Data source: generated demonstration records; no patient data.'
            if 'ASB Prevalence Rate' in code:
                code+='\n\n**Definition discrepancy:** The existing SQL divides both ASB measures by all submissions. The displayed definitions name positive urine cultures and ASB cases instead. The treatment numerator also includes all treated submissions, rather than only treated ASB cases. This synthetic version retains the existing SQL; the intended denominators need clinical agreement.'
            if 'Table of Contents' in code:
                code='### Table of contents\n'+'\n'.join('- ['+positions[k]['meta']['text']+'](#'+k+')' for k in positions['GRID_ID']['children'] if positions[k].get('type')=='HEADER')
            meta['code']=code
    positions['HEADER_ID']['meta']['text']=dashboard.dashboard_title
    notice='SYNTHETIC-NOTICE'
    public_url=os.environ.get('CSIM_PUBLIC_URL','http://127.0.0.1:18089').rstrip('/')
    overview_url=(public_url+'/design/' if public_url.startswith('https://') else 'http://127.0.0.1:18769/')
    positions[notice]={'id':notice,'type':'MARKDOWN','parents':['ROOT_ID','GRID_ID'],'children':[],
                      'meta':{'width':12,'height':23,'code':'[Dashboard overview]('+overview_url+') · [Workflow evidence]('+overview_url+'evidence/)\n\n**21-chart CSiM dashboard · Synthetic data only.** Month / Quarter / Year group selected records before calculating measures. Hospital 91 has no February submissions. Existing cohort weighting is retained. Production may differ; measure definitions still need clinical review.'}}
    positions['GRID_ID']['children'].insert(0,notice)
    dashboard.position_json=json.dumps(positions);dashboard.css=source['dashboard']['css']
    metadata=json.loads(source['dashboard']['json_metadata'])
    metadata['chart_configuration']={};metadata['global_chart_configuration']={'scope':{'rootPath':['ROOT_ID'],'excluded':[]},'chartsInScope':[c.id for c in charts.values()]}
    filters=metadata['native_filter_configuration']
    baseline=db.session.query(SqlaTable).filter_by(uuid=identity('baseline')).one()
    for f in filters:
        f['chartsInScope']=[charts[i].id for i in f.get('chartsInScope',[]) if i in charts]
        f['scope']['excluded']=[charts[i].id for i in f['scope'].get('excluded',[]) if i in charts]
        f.pop('requiredFirst',None)
        if f.get('type')!='NATIVE_FILTER':continue
        f['targets']=[{'datasetId':baseline.id,**({'column':{'name':f['targets'][0]['column']['name']}} if f.get('targets') and f['targets'][0].get('column') else {})}]
        name=f['name'];f['controlValues']['enableEmptyFilter']=True
        if name in ['Hospital and state','Your hospital','Cohort/State','Location of Urine Culture Collection']:
            column=f['targets'][0]['column']['name'];values={'Hospital and state':['91','Cohort'],'Your hospital':['91'],'Cohort/State':['Cohort'],'Location of Urine Culture Collection':['Inpatient']}[name]
            f['defaultDataMask']={'extraFormData':{'filters':[{'col':column,'op':'IN','val':values}]},'filterState':{'value':values,'label':', '.join(values)}}
            if name in ['Your hospital','Cohort/State']:
                f['adhoc_filters']=[{'expressionType':'SQL','clause':'WHERE','sqlExpression':'hosp_num IS '+('NOT NULL' if name=='Your hospital' else 'NULL')}]
                # The newest-data indicator follows the main hospital selection.
                f['chartsInScope']=[i for i in f['chartsInScope'] if i!=charts[107].id]
                f['scope']['excluded']=sorted(set(f['scope']['excluded']+[charts[107].id]))
        elif name=='Time Period':
            f['defaultDataMask']={'extraFormData':{'time_range':TIME_RANGE},'filterState':{'value':TIME_RANGE}}
            f['description']='Choose the reporting date range. The selected Time Unit groups records within this range.'
        elif name=='Time Unit':
            f['defaultDataMask']={'extraFormData':{'time_grain_sqla':'P1M'},'filterState':{'value':'P1M','label':'Month'}}
            f['description']='Group the selected reporting dates by Month, Quarter, or Year.'
    metadata['cross_filters_enabled']=False
    dashboard.json_metadata=json.dumps(metadata);db.session.commit()
    receipt={'slug':SLUG,'dashboard_id':dashboard.id,'source_changed_on':source['dashboard']['changed_on'],
             'charts':{str(k):v.id for k,v in charts.items()},'datasets':{str(k):v.id for k,v in datasets.items()},'latest_dataset':latest.id}
    Path('/tmp/csim-full-dashboard-receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':
    with app.app_context():setup()
