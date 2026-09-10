"""Check native import relationships against the files, using stable UUIDs."""
import json
from pathlib import Path
import yaml
from superset.app import create_app

app=create_app()
with app.app_context():
    from superset import db
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.connectors.sqla.models import SqlaTable
    root=Path('/repro/bundle')
    definition=yaml.safe_load(next((root/'dashboards').glob('*.yaml')).read_text())
    dashboard=db.session.query(Dashboard).filter_by(uuid=definition['uuid']).one()
    expected={node['meta']['chartId']:node['meta']['uuid'] for node in definition['position'].values() if isinstance(node,dict) and node.get('type')=='CHART'}
    charts={str(c.uuid):c for c in dashboard.slices}
    assert set(charts)==set(expected.values()) and len(charts)==21
    remap={old:charts[uuid].id for old,uuid in expected.items()}
    assert any(old!=new for old,new in remap.items()),'Use an independent instance with different chart IDs'
    actual_metadata=json.loads(dashboard.json_metadata)
    actual_filters={f['id']:f for f in actual_metadata['native_filter_configuration'] if f.get('type')=='NATIVE_FILTER'}
    expected_filters=[f for f in definition['metadata']['native_filter_configuration'] if f.get('type')=='NATIVE_FILTER']
    assert len(actual_filters)==len(expected_filters)==6
    cached_scopes=[]
    for f in expected_filters:
        actual=actual_filters[f['id']]
        assert actual['scope']['rootPath']==f['scope']['rootPath']
        assert set(actual['scope']['excluded'])=={remap[cid] for cid in f['scope']['excluded']},f['name']
        assert actual['defaultDataMask']==f['defaultDataMask'],f['name']
        expected_cache={remap[cid] for cid in f.get('chartsInScope',[])}
        actual_cache=set(actual.get('chartsInScope',[]))
        cached_scopes.append({'filter':f['name'],'matches':actual_cache==expected_cache,
                              'expected':sorted(expected_cache),'actual':sorted(actual_cache)})
        for original,target in zip(f.get('targets',[]),actual.get('targets',[]),strict=True):
            if original.get('datasetUuid'):
                dataset=db.session.get(SqlaTable,target['datasetId'])
                assert str(dataset.uuid)==original['datasetUuid'],f['name']
    for file in (root/'datasets').glob('*.yaml'):
        data=yaml.safe_load(file.read_text())
        dataset=db.session.query(SqlaTable).filter_by(uuid=data['uuid']).one()
        assert dataset.sql==data.get('sql'),data['table_name']
    for file in (root/'charts').glob('*.yaml'):
        data=yaml.safe_load(file.read_text())
        chart=charts[data['uuid']]
        dataset=db.session.get(SqlaTable,chart.datasource_id)
        assert str(dataset.uuid)==data['dataset_uuid'],chart.slice_name
    result={'charts':21,'datasets':8,'filters':6,'changed_chart_identifiers':sum(old!=new for old,new in remap.items()),'checks':['Chart and dataset UUID relationships','Exact virtual-dataset SQL','Native filter defaults and exclusions','Filter dataset UUID relationships']}
    expected_global={remap[cid] for cid in definition['metadata'].get('global_chart_configuration',{}).get('chartsInScope',[])}
    actual_global=set(actual_metadata.get('global_chart_configuration',{}).get('chartsInScope',[]))
    # Released 6.1.0 leaves these caches stale even when the tested interactions
    # work. Report that known import gap separately from the successful checks.
    result['cached_scope_references']={'all_match':all(f['matches'] for f in cached_scopes) and actual_global==expected_global,
                                      'filters':cached_scopes,'global_matches':actual_global==expected_global}
    Path('/tmp/csim-bundle-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
