"""Configuration for the separate local, synthetic CSiM reproduction."""
import os
import sqlite3

from superset.config import THEME_DARK as BASE_DARK, THEME_DEFAULT as BASE_DEFAULT

SECRET_KEY = os.environ['SUPERSET_SECRET_KEY']
SQLALCHEMY_DATABASE_URI = 'sqlite:////app/superset_home/csim.db'
# Dashboard requests read metadata while Superset records their events.
# WAL lets those reads continue during a write; concurrent writers wait briefly.
SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 30}}
with sqlite3.connect('/app/superset_home/csim.db', timeout=30) as metadata:
    metadata.execute('PRAGMA journal_mode=WAL')
FEATURE_FLAGS = {'ENABLE_TEMPLATE_PROCESSING': True}
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {'x_for': 1, 'x_proto': 1, 'x_host': 1, 'x_port': 1, 'x_prefix': 0}
SESSION_COOKIE_NAME = 'csim_superset_session'
SESSION_COOKIE_SECURE = os.environ.get('CSIM_PUBLIC_HTTPS') == '1'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# In this pinned runtime, both the app factory and frontend prefix relative
# branding URLs. Absolute URLs avoid the observed /superset/superset/static 404.
if os.environ.get('CSIM_PUBLIC_HTTPS') == '1':
    public_url = os.environ['CSIM_PUBLIC_URL'].rstrip('/')
    APP_ICON = public_url + '/static/assets/images/superset-logo-horiz.png'
    branding = {'brandLogoUrl': APP_ICON, 'brandLogoHref': public_url + '/'}
    THEME_DEFAULT = {**BASE_DEFAULT, 'token': {**BASE_DEFAULT['token'], **branding}}
    THEME_DARK = {**BASE_DARK, 'token': {**BASE_DARK['token'], **branding}}
ROW_LIMIT = 5000
SUPERSET_WEBSERVER_TIMEOUT = 120
# This reproduction is a dedicated instance. Production's global grain policy
# must be reviewed separately; this is not a per-dashboard Superset setting.
TIME_GRAIN_DENYLIST = ['PT1S', 'PT5S', 'PT30S', 'PT1M', 'PT5M', 'PT10M',
                       'PT15M', 'PT30M', 'PT1H', 'PT6H', 'P1D', 'P1W',
                       'P1W/1970-01-03T00:00:00Z', 'P1W/1970-01-04T00:00:00Z']
