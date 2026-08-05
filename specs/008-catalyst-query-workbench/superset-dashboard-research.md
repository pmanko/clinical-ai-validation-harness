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

- Superset: `6.1.0`, the current official release on 2026-08-05. D1b records an
  immutable multi-architecture image digest rather than relying on the tag.
- Deployment: one local Superset application with persistent demo metadata;
  Redis, Celery, reports, thumbnails, and production HA are not required.
- Analytics: the existing `catalyst_readonly` PostgreSQL role over the selected
  Catalyst analytics source.
- Import: a one-shot Compose service invokes the pinned Superset CLI.
  `current.json` is the global desired-publication pointer, not import truth or
  the recovery target. Bootstrap imports it only when no terminal
  `import_failed` projection for that desired digest suppresses automatic work;
  a failed desired bundle changes only through an explicit retry or a new
  publication. An explicit helper imports or updates a running instance. Manual
  UI import remains a diagnostic fallback.
- Runtime ownership: Catalyst owns and gitignores `runtime/superset/`. Importer/
  state code is standalone Python 3.10 under `targets/catalyst/scripts/`, imports
  no Catalyst package, and uses only standard-library and pinned-image built-ins.
  Gateway CI proves its constrained canonical JSON against `rfc8785` and smoke-
  executes it inside the pinned Superset container.

Superset's Docker Compose documentation explicitly describes Compose as an
appropriate local/development setup and not a production deployment. Its
architecture documentation identifies the app and metadata database as the
required components; caching and workers are optional for features outside this
MVP.

## Bundle contract

Superset 6.1.0 strips the first path component from every ZIP member, so the
generated ZIP contains one required enclosing root:

```text
catalyst_dashboard_<stable-dashboard-uuid>/
  metadata.yaml
  databases/<stable-name>.yaml
  datasets/<stable-name>.yaml
  charts/<stable-name>.yaml
  dashboards/<stable-name>.yaml
  catalyst/manifest.json
```

`metadata.yaml` uses Superset's versioned asset format. The Catalyst manifest is
additional provenance evidence. Pinned 6.1.0 bundle loading accepts only YAML
members, so the JSON member is ignored by Superset while remaining available to
Catalyst; a clean import still verifies this behavior. It records the original
parameterized SQL and ordered typed parameter values plus exact session, turn,
query version/digest, execution, source/catalog version, bounded-result schema/
digest/truncation, immutable Dataset/Widget/Dashboard versions and authors/times,
stable asset UUIDs, bundle contract version, target Superset version, and a
digest of the native asset members. The host-side current pointer and publication
record carry the final ZIP digest; the manifest does not attempt a self-
referential digest of its own ZIP. Its `bundleId` is deterministically derived
from immutable configuration inputs, while dynamic attempt IDs/times remain
outside the archive. The pointer identifies desired content only. Per-digest
`receipts/latest/<bundleDigest>.json` records the latest attempt, while verified
success atomically advances
`receipts/last-verified/<logicalDashboardId>.json` under
`catalyst.superset.last-verified.v1`; neither is inferred from `current.json`.

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
- **Open Superset** is enabled only when the exact desired digest has a validated
  `imported` receipt/latest projection; merely running bootstrap/import is not
  success.

Because there is no Superset API call in this slice, Catalyst says `Draft`,
`Bundle ready`, `Imported`, or `Import failed`; status requires the immutable
digest-addressed receipt plus its validated atomic latest projection. Preflight
and confirmed transaction-rollback failures preserve prior verified state;
`post_import_verification` with `committed_unverified` does not. It never claims
`Synced`. Cross-system Undo and reconciliation remain deferred.

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
- A generated bundle cannot prove it was imported. Only a validated immutable
  receipt/latest projection for the exact digest establishes status; successful
  verification also advances the per-Dashboard last-verified projection.
- Virtual-dataset execution may expose SQL dialect or driver differences even
  when Catalyst previously executed the source query successfully.
- Result ordering is not stable without an explicit SQL/order configuration;
  validation compares keyed values rather than screenshot position alone.
- Superset 6.1.0 overwrites the dashboard but hard-codes `overwrite=False` for
  related database, dataset, and chart assets. The MVP keeps the dashboard UUID
  stable and uses new version-derived child UUIDs on change; orphan cleanup is
  an explicit full reset of Superset-local metadata database/home volumes, not
  part of publication. The MVP never performs asset-selective deletion or direct
  Superset ORM/REST recovery mutations.
- Re-import overwrites the generated dashboard configuration, so Superset-only
  layout edits are ephemeral in this MVP and the UI must say so.
- The design handoff leaves Undo, non-demo credentials, authorization, unique
  naming, and cache timeout unresolved; none blocks the isolated file-export
  MVP, and none may be represented as solved.
- The lean `apache/superset:6.1.0` image does not bundle PostgreSQL drivers.
  D1b first proves and digest-pins `6.1.0-dev` plus its driver identity on arm64
  and amd64; if unavailable or inconsistent, it builds a lean-derived image with
  a hash-pinned driver instead of installing packages at runtime.

## Primary sources

- [Apache Superset 6.1.0 release](https://github.com/apache/superset/releases/tag/6.1.0)
- [Superset Docker Compose installation](https://superset.apache.org/admin-docs/6.1.0/installation/docker-compose/)
- [Superset architecture](https://superset.apache.org/admin-docs/6.1.0/installation/architecture/)
- [Importing and exporting assets](https://superset.apache.org/docs/configuration/importing-exporting-datasources/)
- [Dashboard import contract](https://superset.apache.org/developer-docs/6.1.0/api/dashboard/)
- [All-assets ZIP export contract](https://superset.apache.org/docs/api/export-all-assets/)
- [Superset 6.1.0 dashboard importer](https://github.com/apache/superset/blob/6.1.0/superset/commands/dashboard/importers/v1/__init__.py)
- [Superset 6.1.0 bundle loader](https://github.com/apache/superset/blob/6.1.0/superset/commands/importers/v1/utils.py#L228-L234)
- [Focused load/reload research and lifecycle decision](superset-load-reload-research.md)
