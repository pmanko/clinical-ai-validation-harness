"""Exercise each restored chart through the real chart-data HTTP endpoint."""
import copy
import json
import math
import os
from pathlib import Path
import requests

BASE = os.environ.get('CSIM_TEST_URL','http://localhost:8088'+os.environ.get('SUPERSET_APP_ROOT','/').rstrip('/'))
if os.environ.get('CSIM_PUBLIC_HTTPS')=='1':BASE=os.environ['CSIM_PUBLIC_URL'].rstrip('/')
s=requests.Session()
r=s.post(BASE+'/api/v1/security/login',json={'username':'demo','password':os.environ['CSIM_ADMIN_PASSWORD'],'provider':'db'},timeout=30);r.raise_for_status()
s.headers['Authorization']='Bearer '+r.json()['access_token']
r=s.get(BASE+'/api/v1/security/csrf_token/',timeout=30);r.raise_for_status();s.headers['X-CSRFToken']=r.json()['result']
receipt=json.loads(Path(os.environ.get('CSIM_RECEIPT_PATH','/repro/output/full-dashboard-receipt.json')).read_text())
d=s.get(BASE+'/api/v1/dashboard/'+str(receipt['dashboard_id']),timeout=30).json()['result']
filters=json.loads(d['json_metadata'])['native_filter_configuration']
chart_ids=set(receipt['charts'].values())


def charts_in_scope(f):
 # Superset derives native-filter coverage from the layout root and exclusions.
 # chartsInScope is cached editor state and is not remapped by native import.
 assert f['scope']['rootPath']==['ROOT_ID'],('Unexpected scope root',f['name'])
 return chart_ids-set(f['scope'].get('excluded',[]))


chart_params={}
request_count=0
for oldid,cid in receipt['charts'].items():
 r=s.get(BASE+'/api/v1/chart/'+str(cid),timeout=30);r.raise_for_status();chart_params[oldid]=json.loads(r.json()['result']['params'])


def query(oldid,grain='P1M',date_range='2025-11-01 : 2026-06-01',hospital='91',location='Inpatient',clear_all=False):
 global request_count
 request_count+=1
 cid=receipt['charts'][str(oldid)];p=copy.deepcopy(chart_params[str(oldid)])
 selected=[];scoped_range='No filter';scoped_grain='P1M'
 for f in filters:
  if f.get('type')!='NATIVE_FILTER' or cid not in charts_in_scope(f):continue
  if f['filterType']=='filter_time':scoped_range=date_range
  elif f['filterType']=='filter_timegrain':scoped_grain=grain
  else:
   name=f['name'];column=f['targets'][0]['column']['name']
   values={'Hospital and state':[hospital,'Cohort'] if hospital else [],'Your hospital':[hospital] if hospital else [],'Cohort/State':['Cohort'],'Location of Urine Culture Collection':[location] if location else []}[name]
   if clear_all:values=[]
   if values:selected.append({'col':column,'op':'IN','val':values})
 for f in p.get('adhoc_filters',[]):
  if f.get('expressionType')=='SIMPLE' and f.get('operator')!='TEMPORAL_RANGE':
   selected.append({'col':f['subject'],'op':f['operator'],'val':f['comparator']})
 p.update(time_range=scoped_range,time_grain_sqla=scoped_grain,extra_filters=selected)
 columns=[]
 if p.get('x_axis'):columns.append(p['x_axis'])
 columns+=p.get('groupby') or []
 metrics=p.get('metrics') or ([p['metric']] if p.get('metric') else [])
 q={'columns':list(dict.fromkeys(columns)),'metrics':metrics,'granularity':'filter_anchor','time_range':scoped_range,'filters':selected,'extras':{'time_grain_sqla':scoped_grain},'row_limit':1000}
 if p.get('x_axis')=='time_aggregate':q['metrics']=metrics+['Period order'];q['orderby']=[['Period order',True]]
 payload={'datasource':{'id':int(p['datasource'].split('__')[0]),'type':'table'},'force':True,'result_format':'json','result_type':'full','form_data':p,'queries':[q]}
 r=s.post(BASE+'/api/v1/chart/data',json=payload,timeout=90)
 if r.status_code!=200:raise AssertionError((oldid,r.status_code,r.text[:1500]))
 result=r.json()['result'][0]
 if result['status']!='success':raise AssertionError((oldid,result))
 return result


if __name__=='__main__':
 results=[]
 for grain in ['P1M','P3M','P1Y']:
  for oldid in receipt['charts']:
   r=query(oldid,grain)
   assert r['data'],('Unexpected empty chart',oldid,grain)
   results.append({'source_chart':int(oldid),'grain':grain,'rows':len(r['data']),'data':r['data']})
   print(json.dumps({'source_chart':oldid,'grain':grain,'rows':len(r['data'])}),flush=True)
 def selected(oldid,grain,hospital='91'):
  return [v for v in next(r for r in results if r['source_chart']==oldid and r['grain']==grain)['data'] if v.get('hosp_code',hospital)==hospital]
 monthly=selected(73,'P1M')
 assert [v['time_aggregate'] for v in monthly]==['2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05']
 assert [v['MAX(inappdx)'] for v in monthly]==[.2,.1,1,None,0,None,.25]
 assert [v['SUM(ucsub)'] for v in selected(99,'P1M')]==[10,90,1,None,9,10,8], 'Calendar must not multiply submission counts'
 assert sum(v['SUM(prescription_count)'] for v in selected(82,'P1M') if v['time_aggregate']=='2025-11')==10, 'Calendar must not multiply antibiotic counts'
 for oldid,metric in [(82,'SUM(prescription_count)'),(85,'SUM(n_submissions)')]:
  rows=selected(oldid,'P1M');feb=[r for r in rows if r['time_aggregate']=='2026-02']
  assert feb and all(r[metric] is None for r in feb),('Category chart omitted the missing month',oldid)
 quarterly=selected(73,'P3M')
 assert [v['time_aggregate'] for v in quarterly]==['2025 Q4','2026 Q1','2026 Q2']
 assert [v['MAX(inappdx)'] for v in quarterly]==[.11,.1,.25]
 annual=selected(73,'P1Y');assert [v['time_aggregate'] for v in annual]==['2025','2026']
 assert math.isclose(annual[1]['MAX(inappdx)'],3/18)
 # This deliberately differs from pooling denominators across hospitals.
 cohort_q2=selected(73,'P3M','Cohort')[-1]['MAX(inappdx)']
 assert math.isclose(cohort_q2,(.25*18+.125*40)/58)
 partial=query(73,'P3M','2026-02-01 : 2026-04-01')['data']
 own=[r for r in partial if r['hosp_code']=='91'];assert len(own)==1 and own[0]['time_aggregate']=='2026 Q1' and own[0]['MAX(inappdx)']==0
 overall=query(74,date_range='2026-02-01 : 2026-04-01')['data']
 assert next(r for r in overall if r['hosp_code']=='91')['% inappropriate UTI diagnosis']==0
 other=query(73,hospital='92')['data'];assert next(r for r in other if r['hosp_code']=='92' and r['time_aggregate']=='2026-02')['MAX(inappdx)']==.1
 care=query(73,date_range='2026-01-01 : 2026-04-01',location='Emergency Department')['data']
 assert [r['MAX(inappdx)'] for r in care if r['hosp_code']=='91']==[.5,None,2/6]
 latest=query(107,date_range='2025-10-01 : 2026-07-01')['data'][0]['MAX(month_date)']
 assert latest==1777593600000.0
 for oldid,count in [(100,248),(106,128)]:
  rows=query(oldid,date_range='2026-02-01 : 2026-04-01')['data'];assert rows[0]['SUM(ucsub)']==count
 for oldid in receipt['charts']:
  rows=query(oldid,clear_all=True)['data']
  assert not rows or all(all(v is None for v in row.values()) for row in rows),('Cleared filters leaked a total',oldid,rows)
 positions=json.loads(d['position_json'])
 assert {v['meta']['chartId'] for v in positions.values() if isinstance(v,dict) and v.get('type')=='CHART'}==chart_ids
 for f in filters:
  if f.get('type')=='NATIVE_FILTER':
   assert set(f['scope']['excluded'])<=chart_ids,(f['name'],'exclusion references a missing chart')
 report={'source_charts':21,'chart_requests':request_count,'checks':['Every chart returns results for Month, Quarter, Year','Chronology and missing/zero/undefined rates','Category charts retain missing months','Partial first and last periods retained','Original cohort weighting preserved','Overall measures respect date range','Hospital and care-location selections','Latest date uses observations, not calendar','All-time count exclusions retained','Cleared selections do not combine overlapping totals','All chart/filter references mapped'],'results':results}
 Path('/tmp/csim-full-verification.json').write_text(json.dumps(report,indent=2))
