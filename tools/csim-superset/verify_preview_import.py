"""Exercise native export/import of both dashboards' saved time choices."""
import io
import json
import os
from pathlib import Path
import zipfile

import yaml
from bundle import connection
from superset.app import create_app

app = create_app()
with app.app_context():
    from superset import db
    from superset.models.dashboard import Dashboard
    dashboards = db.session.query(Dashboard).filter(Dashboard.slug.in_(['csim-full-synthetic','hourly-reporting-preview'])).all()
    assert len(dashboards) == 2
    expected = {}
    for dashboard in dashboards:
        f = next(f for f in json.loads(dashboard.json_metadata)['native_filter_configuration'] if f.get('filterType') == 'filter_timegrain')
        expected[dashboard.slug] = {'choices':f['time_grains'],'default':f['defaultDataMask']}
    base, client = connection()
    response = client.get(base+'/api/v1/dashboard/export/', params={'q':'!('+','.join(str(d.id) for d in dashboards)+')'}, timeout=60)
    response.raise_for_status()
    archive = response.content
    passwords = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as files:
        exported = {}
        for name in files.namelist():
            if not name.endswith('.yaml'): continue
            data = yaml.safe_load(files.read(name))
            if '/databases/' in name:
                passwords['/'.join(name.split('/')[1:])] = os.environ['CSIM_DB_PASSWORD']
            if '/dashboards/' in name:
                f = next(f for f in data['metadata']['native_filter_configuration'] if f.get('filterType') == 'filter_timegrain')
                exported[data['slug']] = {'choices':f['time_grains'],'default':f['defaultDataMask']}
        assert exported == expected
    # Change the stored menus before import. Reading an unchanged dashboard
    # afterward would not prove that the native importer restores these fields.
    for dashboard in dashboards:
        metadata = json.loads(dashboard.json_metadata)
        for f in metadata['native_filter_configuration']:
            if f.get('filterType') == 'filter_timegrain': f['time_grains'] = ['P1Y']
        dashboard.json_metadata = json.dumps(metadata)
    db.session.commit()
    try:
        response = client.post(base+'/api/v1/dashboard/import/',
            files={'formData':('snapshot.zip',archive,'application/zip')},
            data={'passwords':json.dumps(passwords),'overwrite':'true'},timeout=120,allow_redirects=False)
        response.raise_for_status()
        assert response.status_code == 200 and response.json()['message'] == 'OK'
        db.session.expire_all()
        actual = {}
        for dashboard in dashboards:
            f = next(f for f in json.loads(dashboard.json_metadata)['native_filter_configuration'] if f.get('filterType') == 'filter_timegrain')
            actual[dashboard.slug] = {'choices':f['time_grains'],'default':f['defaultDataMask']}
        assert actual == expected
    finally:
        # Keep a failed diagnostic from leaving the public example misconfigured.
        db.session.rollback()
        for dashboard in dashboards:
            metadata = json.loads(dashboard.json_metadata)
            for f in metadata['native_filter_configuration']:
                if f.get('filterType') == 'filter_timegrain':
                    f['time_grains'] = expected[dashboard.slug]['choices']
                    f['defaultDataMask'] = expected[dashboard.slug]['default']
            dashboard.json_metadata = json.dumps(metadata)
        db.session.commit()
    Path('/tmp/csim-preview-native.zip').write_bytes(archive)
    result = {'passed':True,'dashboards':actual,'instanceDenylist':app.config['TIME_GRAIN_DENYLIST']}
    Path('/tmp/csim-preview-import-check.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
