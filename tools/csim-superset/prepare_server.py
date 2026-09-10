"""Initialize credentials/configuration for the dedicated synthetic demo host.

Run once in the uploaded directory. This does not alter the Catalyst application.
"""
import os
import secrets
from pathlib import Path

target = Path('.env.local')
if target.exists():
    raise SystemExit('Existing .env.local retained; initialization is only for a new deployment.')
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    for key in ['DB_PASSWORD', 'SECRET_KEY', 'ADMIN_PASSWORD']:
        stream.write('CSIM_' + key + '=' + secrets.token_hex(24) + '\n')
    stream.write('CSIM_SERVER=1\n')
    stream.write('CSIM_APP_ROOT=/superset\n')
    stream.write('CSIM_PUBLIC_HTTPS=1\n')
    stream.write('CSIM_PUBLIC_URL=https://catalyst.openelis-global.org/superset\n')
print('Created private server settings for the synthetic demo.')
