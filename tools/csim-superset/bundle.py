"""Use Superset's native ZIP API with readable, credential-free YAML files.

Run inside the pinned Superset container. Export is explicit; ordinary imports
consume bundle/ and do not need the private development snapshot.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile
import tempfile

import requests
import yaml

ROOT = Path('/repro')
BUNDLE = ROOT / 'bundle'
SLUG = 'csim-full-synthetic'


class ReadableDumper(yaml.SafeDumper):
    pass


def string_value(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value,
                                   style='|' if '\n' in value else None)


ReadableDumper.add_representer(str, string_value)


def connection():
    base = os.environ.get('CSIM_TEST_URL', 'http://localhost:8088')
    if os.environ.get('CSIM_PUBLIC_HTTPS') == '1':
        base = os.environ['CSIM_PUBLIC_URL'].rstrip('/')
    client = requests.Session()
    response = client.post(base+'/api/v1/security/login', json={
        'username':'demo', 'password':os.environ['CSIM_ADMIN_PASSWORD'], 'provider':'db'}, timeout=30)
    response.raise_for_status()
    client.headers['Authorization'] = 'Bearer '+response.json()['access_token']
    response = client.get(base+'/api/v1/security/csrf_token/', timeout=30)
    response.raise_for_status()
    client.headers['X-CSRFToken'] = response.json()['result']
    return base, client


def public_text(value):
    for key in ('CSIM_DB_PASSWORD', 'CSIM_ADMIN_PASSWORD', 'SUPERSET_SECRET_KEY'):
        secret = os.environ.get(key)
        if secret and secret in value:
            raise ValueError('A credential remains in an export')
    return value


def bundle_files(directory=BUNDLE):
    files = sorted(directory.rglob('*.yaml'))
    if not files or not (directory/'metadata.yaml').is_file():
        raise ValueError('Missing native bundle files')
    return files


def packed(directory=BUNDLE):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for file in bundle_files(directory):
            text = public_text(file.read_text())
            if file.parent.name == 'dashboards' and os.environ.get('CSIM_OVERVIEW_URL'):
                text = text.replace('https://catalyst.openelis-global.org/superset/design/',
                                    os.environ['CSIM_OVERVIEW_URL'].rstrip('/')+'/')
            entry=zipfile.ZipInfo('csim/'+file.relative_to(directory).as_posix(), date_time=(1980,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            target.writestr(entry, text)
    return archive.getvalue()


def export_bundle():
    base, client = connection()
    response = client.get(base+'/api/v1/dashboard/', params={'q':'(page_size:100)'}, timeout=30)
    response.raise_for_status()
    dashboard = next(d for d in response.json()['result'] if d['slug']==SLUG)
    response = client.get(base+'/api/v1/dashboard/export/', params={'q':'!('+str(dashboard['id'])+')'}, timeout=60)
    response.raise_for_status()
    destination = Path(tempfile.mkdtemp(prefix='csim-definition-'))
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for file in archive.namelist():
            if not file.endswith('.yaml'):
                continue
            path = Path(file)
            relative = Path(*path.parts[1:])
            data = yaml.safe_load(archive.read(file))
            kind = relative.parts[0]
            if kind == 'metadata.yaml':
                # Superset's export time is not part of dashboard behavior.
                data.pop('timestamp', None)
                output = destination/'metadata.yaml'
            else:
                output = destination/kind/(str(data['uuid'])+'.yaml')
            if kind == 'databases':
                data['sqlalchemy_uri'] = 'postgresql+psycopg2://csim:XXXXXXXXXX@db:5432/csim_synthetic'
                for key in ('password','encrypted_extra','ssh_tunnel'):
                    data.pop(key, None)
            if kind == 'dashboards':
                # Navigation is contextual, not a source installation reference.
                notice=data['position'].get('SYNTHETIC-NOTICE',{}).get('meta',{})
                notice['code']=notice.get('code','').replace('http://127.0.0.1:18769/', 'https://catalyst.openelis-global.org/superset/design/')
            output.parent.mkdir(parents=True, exist_ok=True)
            text = yaml.dump(data, Dumper=ReadableDumper, sort_keys=False, allow_unicode=True, width=100)
            output.write_text(public_text(text))
    receipt = json.loads((ROOT/'output/full-dashboard-receipt.json').read_text())
    from uuid import uuid5, NAMESPACE_URL
    manifest = {
        'format':'superset-native-yaml', 'dashboard_slug':SLUG,
        'source_chart_uuids':{oldid:str(uuid5(NAMESPACE_URL,'https://example.invalid/csim-synthetic/full-chart-'+oldid)) for oldid in receipt['charts']},
        'fixture':'sql/synthetic.sql + sql/baseline.sql + sql/antibiotic-fixture.sql',
        'limits':['Synthetic data only','Clinical definitions need agreement','Production route needs separate verification'],
    }
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'exported_yaml_files':len(bundle_files(destination)), 'path':str(destination)}))


def import_bundle():
    base, client = connection()
    passwords={file.relative_to(BUNDLE).as_posix():os.environ['CSIM_DB_PASSWORD'] for file in (BUNDLE/'databases').glob('*.yaml')}
    response = client.post(base+'/api/v1/dashboard/import/',
        files={'formData':('csim-dashboard.zip', packed(), 'application/zip')},
        data={'passwords':json.dumps(passwords),'overwrite':'true'}, timeout=120)
    response.raise_for_status()
    print(json.dumps({'native_import_status':response.status_code}))


def receipt():
    # Resolve stable UUIDs after import; never reuse the exporter's numeric IDs.
    from superset.app import create_app
    app=create_app()
    with app.app_context():
        from superset import db
        from superset.models.dashboard import Dashboard
        from superset.models.slice import Slice
        manifest=json.loads((BUNDLE/'manifest.json').read_text())
        dashboard=db.session.query(Dashboard).filter_by(slug=SLUG).one()
        charts={oldid:db.session.query(Slice).filter_by(uuid=uuid).one().id for oldid,uuid in manifest['source_chart_uuids'].items()}
        result={'dashboard_id':dashboard.id,'charts':charts,'bundle_sha256':hashlib.sha256(packed()).hexdigest()}
        Path('/tmp/csim-full-dashboard-receipt.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({'dashboard_id':dashboard.id,'resolved_charts':len(charts)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['export','pack','import','receipt'])
    args=parser.parse_args()
    if args.action=='export':export_bundle()
    elif args.action=='import':import_bundle()
    elif args.action=='receipt':receipt()
    else:
        target=Path('/tmp/csim-full-native.zip')
        target.write_bytes(packed())
        print(str(target))
