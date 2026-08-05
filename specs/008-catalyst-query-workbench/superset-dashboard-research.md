# Superset-backed Dashboard Builder research

**Date:** 2026-08-05  
**Decision status:** Approved architecture; file-export MVP selected

## Decision

Catalyst remains the supervised query, dataset, widget, and dashboard builder.
Apache Superset is the dashboard renderer and runtime. The first integration
uses a deterministic Superset asset ZIP written to a shared outbox and offered
for download rather than Superset's REST API:

`question → governed execution → dataset draft → widget draft → dashboard → outbox ZIP → Superset CLI import`

The isolated stack pins Apache Superset 6.1.0 and exposes it on a localhost-only
port. Catalyst persists draft/library metadata, desired dashboard configuration,
and export provenance in its existing operating-metadata store. For this
one-way MVP, Catalyst is the configuration source of truth and Superset is the
rendering runtime. Superset-only layout edits are not round-tripped and may be
replaced by the next publication; collaborative Superset ownership requires the
deferred API/export-reconciliation phase.

## Why the native ZIP is the MVP boundary

Superset's supported ZIP import/export covers dashboards together with their
charts, datasets, and database definitions. The bundle is versioned YAML with
stable UUIDs, so it is reviewable, portable, and can later be delivered through
the same Superset import API without changing Catalyst's artifact model.

This avoids building a dashboard renderer or canvas in Catalyst and avoids an
early authentication/service-account integration. It also keeps the first
failure boundary inspectable: Catalyst either produces a contract-valid bundle,
or Superset reports an import/render error to the evaluator.

The bundle is configuration, not a clinical-result snapshot. After import,
Superset executes the exported virtual dataset SQL against the configured
read-only analytics database. The local demo bundle may carry its documented
demo-only read credential; non-demo exports must require the receiving Superset
instance to supply its own secret.

## Pinned runtime

- Superset: `6.1.0`, the current official release on 2026-08-05.
- Deployment: one local Superset application with persistent demo metadata;
  Redis, Celery, reports, thumbnails, and production HA are not required.
- Analytics: the existing `catalyst_readonly` PostgreSQL role over the selected
  Catalyst analytics source.
- Import: a one-shot Compose service invokes the pinned Superset CLI. Stack
  bootstrap loads the selected current bundle; an explicit helper imports or
  updates a running instance. Manual UI import remains a diagnostic fallback.

Superset's Docker Compose documentation explicitly describes Compose as an
appropriate local/development setup and not a production deployment. Its
architecture documentation identifies the app and metadata database as the
required components; caching and workers are optional for features outside this
MVP.

## Bundle contract

The generated ZIP contains:

```text
metadata.yaml
databases/<stable-name>.yaml
datasets/<stable-name>.yaml
charts/<stable-name>.yaml
dashboards/<stable-name>.yaml
catalyst/manifest.json
```

`metadata.yaml` uses Superset's versioned asset format. The Catalyst manifest is
additional provenance evidence and is ignored by the Superset importer. It
records the exact session, turn, query version/digest, execution, source/catalog
version, result schema/digest, dashboard version, stable asset UUIDs, bundle
contract version, target Superset version, and a digest of the native asset
members. The host-side `current.json` and export record carry the final ZIP
digest; the manifest does not attempt a self-referential digest of its own ZIP.

Bundle serialization is deterministic: the logical Dashboard draft has a stable
UUID, while Dataset and Widget/chart UUIDs derive from immutable version IDs.
YAML mapping order and ZIP member order are fixed, timestamps and permissions
are normalized, and unchanged inputs produce byte-identical ZIPs.

Named SQL parameters are compiled into typed PostgreSQL literals from the exact
successful execution before export. The original parameterized SQL and typed
values remain in the Catalyst manifest; no free-form string replacement is
allowed. This makes the virtual dataset executable in Superset without a native
filter mapping. Parameter-to-dashboard-filter promotion remains post-MVP.

## Product scope

The supplied design is the UX source of truth:

- one left navigation shell: Ask, Datasets, Widgets, Dashboards;
- one fixed Ask composer and compact chronological thread;
- dataset and widget draft tiles opening one accessible review panel;
- persistent Catalyst libraries for datasets, widgets, and dashboard drafts;
- initial widget suggestion from typed result shape, always user-reviewable;
- table, big-number, time-series line/area, grouped/stacked bar, and proportion
  bar as the target visualization set;
- dashboard action is **Publish to Superset**, which atomically writes the
  outbox bundle and also exposes **Download bundle**;
- **Open Superset** opens the local renderer after the explicit import helper or
  bootstrap importer runs.

Because there is no Superset API call in this slice, Catalyst says `Draft`,
`Bundle ready`, `Imported`, or `Import failed`; only a digest-addressed CLI
receipt can establish the latter two. It never claims `Synced`. Cross-system
Undo and reconciliation remain deferred.

## Alternatives considered

### Local Catalyst dashboard renderer

Rejected. It duplicates mature dashboard technology, contradicts the intended
product architecture, and creates a likely throwaway canvas/configuration model.

### Superset REST API in the first slice

Deferred. It would automate create/update/delete and sync status, but it adds
credentials, CSRF/JWT handling, object reconciliation, partial-failure recovery,
and destructive undo semantics before the bundle contract is proven.

### Superset extension or embedded dashboard

Deferred. Both are useful later, but neither is required to prove that Catalyst
can turn a governed execution into a real dashboard artifact rendered by
Superset.

## Known limitations and nondeterminism

- Superset's YAML schemas and chart `params` are version-coupled; the pin and a
  real import/export round trip are mandatory evidence.
- A generated bundle cannot prove it was imported. Only a receipt from the
  one-shot CLI importer against the exact digest establishes import status.
- Virtual-dataset execution may expose SQL dialect or driver differences even
  when Catalyst previously executed the source query successfully.
- Result ordering is not stable without an explicit SQL/order configuration;
  validation compares keyed values rather than screenshot position alone.
- Superset 6.1.0 overwrites the dashboard but hard-codes `overwrite=False` for
  related database, dataset, and chart assets. The MVP keeps the dashboard UUID
  stable and uses new version-derived child UUIDs on change; orphan cleanup is
  an explicit local reset, not part of publication.
- Re-import overwrites the generated dashboard configuration, so Superset-only
  layout edits are ephemeral in this MVP and the UI must say so.
- The design handoff leaves Undo, non-demo credentials, authorization, unique
  naming, and cache timeout unresolved; none blocks the isolated file-export
  MVP, and none may be represented as solved.

## Primary sources

- [Apache Superset 6.1.0 release](https://github.com/apache/superset/releases/tag/6.1.0)
- [Superset Docker Compose installation](https://superset.apache.org/admin-docs/6.1.0/installation/docker-compose/)
- [Superset architecture](https://superset.apache.org/admin-docs/6.1.0/installation/architecture/)
- [Importing and exporting assets](https://superset.apache.org/docs/configuration/importing-exporting-datasources/)
- [Dashboard import contract](https://superset.apache.org/developer-docs/6.1.0/api/dashboard/)
- [All-assets ZIP export contract](https://superset.apache.org/docs/api/export-all-assets/)
- [Superset 6.1.0 dashboard importer](https://github.com/apache/superset/blob/6.1.0/superset/commands/dashboard/importers/v1/__init__.py)
- [Focused load/reload research and lifecycle decision](superset-load-reload-research.md)
