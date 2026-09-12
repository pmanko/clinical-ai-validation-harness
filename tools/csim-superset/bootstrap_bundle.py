"""Create only the local test account, without dashboard or dataset objects."""
import os
from superset.app import create_app
app=create_app()
with app.app_context():
    from superset import security_manager
    if not security_manager.find_user(username='demo'):
        security_manager.add_user('demo','Synthetic','Demo','demo@example.invalid',
            security_manager.find_role('Admin'),os.environ['CSIM_ADMIN_PASSWORD'])
    print('Synthetic test account ready; dashboard definitions are imported separately.')
