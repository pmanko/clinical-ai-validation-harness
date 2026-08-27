# Superset keeps the retired PostgreSQL database record on import

**Recorded 2026-08-27, on the running stack.** This is the one acceptance step
in the Spark remediation that is not finished, and it needs an owner decision
because the fix touches Superset state that predates this work.

## What works

- Catalyst publishes a bundle whose database names the Spark source:
  `hive://catalyst@spark-thriftserver:10000/default`.
- `scripts/catalyst-mvp.sh superset-import` reports
  `{"status": "imported", ...}` with a dashboard URL.
- Superset's own driver reaches Spark: from inside the running container,
  `SELECT COUNT(*) FROM patient_flat` returns **10669**, matching Catalyst and
  beeline.

## What does not

Superset still serves the dashboard from a **PostgreSQL** database record.
Executing the saved query through Superset returns
`SYNTAX_ERROR ... "engine_name": "PostgreSQL"`, and the two Catalyst databases
list as `postgresql`:

```
1 | Catalyst openelis analytics     | uuid 09daed55-c9d2-58ac-8b74-960e7e69729b
2 | Catalyst OpenMRS HIV analytics  | uuid 4bbbd7a3-7e8f-44c4-8884-b3958bd33b52
```

Both were created by imports from the retired PostgreSQL era and point at
`analytics-db`, a service that no longer exists.

## Why it persists

The bundle derives its database UUID deterministically (uuid5), so a re-import
carries the same UUID as the retired-era record. Superset matches assets by
UUID and keeps the existing database rather than replacing its connection.
Superset 6.1's `superset import-dashboards` CLI offers only `-p` and `-u` —
there is no `--overwrite`, so the importer cannot force reconciliation.

The failure is silent: the import reports success while the dashboard still
points at an engine that was removed.

## Owner decision

1. **Remove the two stale Catalyst database records from Superset**, then
   re-import. Cheapest, and they reference a deleted service — but it discards
   the charts and datasets from earlier demos along with them.
2. **Teach the importer to reconcile a database whose URI has changed** before
   invoking the CLI, using Superset's REST API. Durable, and it closes the
   silent-success gap for every future redeploy.

Option 2 is the one that prevents recurrence; option 1 unblocks the smoke
today. They compose.

## Reproduce

```
./scripts/catalyst-mvp.sh superset-import      # reports "imported"
# then, authenticated against :18088
GET /api/v1/database/1                          # backend: postgresql
POST /api/v1/sqllab/execute/ {database_id: 1, sql: "SELECT count(t1.id) ..."}
#   -> SYNTAX_ERROR, engine_name: PostgreSQL
```
