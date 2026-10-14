"""Provision a shareable account limited to the invented CSiM datasets."""
import json
import secrets
from pathlib import Path
from superset.app import create_app

app=create_app()
with app.app_context():
    from superset import db, security_manager as sm
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.core import Database
    access_file=Path('/app/superset_home/csim-viewer.json')
    if access_file.exists():
        access=json.loads(access_file.read_text())
    else:
        generated = secrets.token_urlsafe(18)
        access={'username':'csim-viewer','password':generated}
        access_file.write_text(json.dumps(access))
        access_file.chmod(0o600)
    role=sm.find_role('CSiM demo datasets') or sm.add_role('CSiM demo datasets')
    database=db.session.query(Database).filter_by(database_name='CSiM synthetic only').one()
    for dataset in db.session.query(SqlaTable).filter_by(database_id=database.id):
        permission=sm.find_permission_view_menu('datasource_access',dataset.get_perm())
        if permission:sm.add_permission_role(role,permission)
    user=sm.find_user(username=access['username'])
    if not user:
        user=sm.add_user(access['username'],'CSiM','Viewer','csim-viewer@example.invalid',
            [sm.find_role('Gamma'),role],access['password'])
    db.session.commit()
    Path('/tmp/csim-viewer.env').write_text('CSIM_ADMIN_PASSWORD='+access['password']+'\n')
    Path('/tmp/csim-viewer.env').chmod(0o600)
    print('Demo viewer account ready.')
