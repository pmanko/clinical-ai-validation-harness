#!/usr/bin/env python3
"""Provision the synthetic OE reporting connection; safe to rerun, no data reset."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote, unquote, urlsplit


def source_document(document, host, port, database, username, password):
    uri = f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(database, safe='')}"
    entry = {"id": "openelis-reporting", "label": "OpenELIS Reporting (PostgreSQL)",
             "connectionUri": uri, "dialect": "postgresql", "supersetSqlalchemyUri": uri}
    sources = document.setdefault("dataSources", [])
    matches = [i for i, old in enumerate(sources) if old.get("id") == entry["id"]]
    if len(matches) > 1:
        raise ValueError("Duplicate reporting source IDs; resolve before setup")
    if matches:
        old = sources[matches[0]]
        prior = urlsplit(old["connectionUri"])
        if (prior.hostname, prior.port or 5432, prior.path) != (host, port, '/' + database):
            raise ValueError("Existing reporting source points elsewhere; refusing to retarget saved work")
        sources[matches[0]] = {**old, **entry}
    else:
        sources.append(entry)
    return document


SQL = r"""
BEGIN;
SELECT format('CREATE ROLE %I LOGIN', :'reader')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'reader') \gexec
SELECT format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', :'reader', :'password') \gexec
SELECT format('ALTER ROLE %I SET default_transaction_read_only = on', :'reader') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'reader') \gexec
SELECT format('GRANT USAGE ON SCHEMA %I TO %I', nspname, :'reader')
FROM pg_namespace WHERE nspname NOT IN ('pg_catalog', 'information_schema') AND nspname !~ '^pg_' \gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', nspname, :'reader')
FROM pg_namespace WHERE nspname NOT IN ('pg_catalog', 'information_schema') AND nspname !~ '^pg_' \gexec
-- Cover each current table/schema owner and the migration login for future tables.
WITH owners AS (
 SELECT n.oid, n.nspname, n.nspowner AS owner FROM pg_namespace n
 UNION SELECT n.oid, n.nspname, c.relowner FROM pg_namespace n JOIN pg_class c ON c.relnamespace=n.oid
 UNION SELECT n.oid, n.nspname, r.oid FROM pg_namespace n CROSS JOIN pg_roles r WHERE r.rolname=current_user
)
SELECT DISTINCT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO %I', r.rolname, o.nspname, :'reader')
FROM owners o JOIN pg_roles r ON r.oid=o.owner
WHERE o.nspname NOT IN ('pg_catalog', 'information_schema') AND o.nspname !~ '^pg_' \gexec
COMMIT;
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database-container', required=True)
    p.add_argument('--host', required=True, help='Address reachable by both Gateway and Superset')
    p.add_argument('--port', type=int, default=5432)
    p.add_argument('--database', default='clinlims')
    p.add_argument('--admin', default='clinlims')
    p.add_argument('--reader', default='catalyst_reporting_reader')
    p.add_argument('--registry', required=True, type=Path)
    args = p.parse_args()
    original = args.registry.read_text() if args.registry.exists() else '{"dataSources": []}\n'
    document = json.loads(original)
    existing = next((s for s in document.get('dataSources', []) if s.get('id') == 'openelis-reporting'), None)
    previous_password = urlsplit(existing['connectionUri']).password if existing else None
    password = os.environ.get('REPORTING_DEMO_PASSWORD') or (unquote(previous_password) if previous_password else 'catalyst-demo')
    document = source_document(document, args.host, args.port, args.database, args.reader, password)
    # psql variables quote identifiers and values; no shell interpolation of credentials.
    cmd = ['docker', 'exec', '-i', args.database_container, 'psql', '-X', '-q',
           '-v', 'ON_ERROR_STOP=1', '-U', args.admin, '-d', args.database,
           '-v', 'reader='+args.reader, '-v', 'password='+password]
    result = subprocess.run(cmd, input=SQL, text=True, capture_output=True)
    if result.returncode:
        p.exit(1, 'Reporting setup failed; no registry change: ' + result.stderr.replace(password, '[redacted]'))
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    backup = args.registry.with_name(args.registry.name+'.before-reporting-setup')
    if args.registry.exists() and not backup.exists():
        backup.write_text(original)
        backup.chmod(0o600)
    temporary = args.registry.with_name(args.registry.name+'.tmp')
    temporary.write_text(json.dumps(document, indent=2)+'\n')
    temporary.chmod(0o644)  # The existing read-only mount must remain readable by the Gateway user.
    temporary.replace(args.registry)
    print(json.dumps({'source': 'openelis-reporting', 'database': args.database,
                      'reader': args.reader, 'registry': str(args.registry),
                      'data_reset': False, 'restart_performed': False}))


if __name__ == '__main__':
    main()
