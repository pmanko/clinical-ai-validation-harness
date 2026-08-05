# Superset dashboard load/reload research

> Research conducted 2026-08-05 | Depth: quick, focused | Sources: 8 |
> Tone: technical analyst | Audience: Catalyst implementers | Mode: unassisted

## Decision summary

Catalyst should use Superset's native versioned ZIP importer through a one-shot
Compose service, not a filesystem watcher and not direct writes to Superset's
metadata database. The publish action atomically writes a content-addressed ZIP
and `current.json` pointer to a host-visible outbox. A separate importer reads
that outbox, invokes the pinned Superset 6.1.0 CLI, verifies the exact digest,
and writes a receipt that Catalyst can display.

The important version-specific constraint is that Superset 6.1.0's
`import-dashboards` CLI passes `overwrite=True` for the dashboard, but its v1
importer hard-codes `overwrite=False` for related databases, datasets and charts.
This means a changed bundle must not reuse a child asset UUID and expect its
configuration to update. The reliable MVP strategy is:

- stable UUID for the logical Dashboard draft;
- immutable, version-derived UUIDs for Dataset and Widget/chart versions;
- stable database UUID and connection configuration for one local stack;
- dashboard overwrite on import, pointing it to newly created versioned child
  assets;
- periodic explicit reset of the disposable local Superset metadata database to
  remove orphaned historical children, not as part of normal publication.

This makes repeated publication reliable without private Superset internals.
The tradeoff is that old Dataset/chart versions accumulate and Superset-only
layout edits are overwritten by the next Catalyst publication. Therefore, for
this file-export MVP, Catalyst is the source of desired dashboard configuration
and Superset is the rendering runtime. Making Superset the collaborative source
of truth requires the deferred API/export-reconciliation phase.

## What the official behavior supports

Superset stores dashboards, charts, datasets, database connections and users in
its metadata database; Docker Compose persists that database in a volume. The
official guidance treats that metadata database as durable state and recommends
backups before upgrades. Ordinary application restart should therefore retain
the metadata volume and should not blindly re-import every bundle.

Superset's supported versioned asset ZIP contains database, dataset, chart and
dashboard YAML. The CLI command `superset import-dashboards -p <zip> -u admin`
is an appropriate local automation boundary. It provides a process exit code
and log evidence without adding authentication, CSRF handling or a Superset REST
client to Catalyst.

The moving documentation is less precise than the pinned implementation about
overwrite behavior. Current general docs describe overwrite support for related
assets, but the 6.1.0 CLI and importer source show that only the dashboard is
overwritten. The plan must follow the pinned source until a real round-trip test
proves otherwise.

## Recommended lifecycle

### First load

1. Start the Superset metadata PostgreSQL service and wait for health.
2. Run a one-shot initialization service: `superset db upgrade`, create the
   deterministic local admin if absent, then `superset init`.
3. Start the Superset application against the persistent metadata volume.
4. If the outbox contains a valid `current.json`, run the one-shot importer.
5. Verify the dashboard UUID and its chart/dataset relationships in Superset,
   then write a receipt containing bundle digest, command revision, start/end
   times, exit status and bounded diagnostic.

Initialization and import should be separate services. A malformed dashboard
must not prevent Superset itself from booting; the stack health report should
show `Superset ready / import failed` and retain the failed bundle for review.

### Ordinary restart

Keep the metadata database and the Superset secret key stable. If the receipt
digest equals `current.json`, do nothing. This preserves imported state and
avoids unnecessary, partially overwriting imports.

### Publish/update while running

1. Catalyst validates the complete bundle and manifest in memory.
2. It writes `<digest>.zip.tmp`, fsyncs, renames it to `<digest>.zip`, then
   atomically replaces `current.json`. Superset mounts the outbox read-only.
3. The explicit `catalyst-superset-import` command starts the one-shot importer,
   which acquires an import lock and copies/opens the exact digest named by the
   pointer.
4. Re-importing the identical digest is a no-op. A changed bundle uses the same
   Dashboard UUID and new immutable Dataset/Widget version UUIDs; Superset 6.1.0
   creates the children and overwrites the logical dashboard and relationships.
5. Only verified CLI success writes an `Imported` receipt. Failure leaves the
   prior Superset dashboard usable and Catalyst shows `Import failed` for the
   attempted digest.

Do not add a background directory watcher in the MVP. Watchers complicate
partial-write detection, retries, ordering and attribution. The explicit command
is deterministic and observable; a future API integration can make publication
immediate without changing the bundle model.

### Reset/rebuild

Provide a clearly destructive local-only `catalyst-superset-reset` command that
backs up or exports current metadata, removes only the Catalyst Superset metadata
volume, reruns initialization, and imports `current.json`. Use it to prune old
immutable child assets, recover from schema/version drift, or validate a clean
installation. Never make reset the normal `up` or `import` behavior.

## Bundle and state rules

The outbox is runtime state and must be gitignored. Use a fixed layout such as:

```text
runtime/superset/
  outbox/<sha256>.zip
  outbox/current.json
  receipts/<sha256>.json
  backups/
```

The Gateway is the only outbox writer. Superset and the importer read it
read-only; only the importer writes receipts. `current.json` contains the
dashboard identity, exact bundle digest, filename, target Superset version and
actual generation time. Dynamic export/import times stay outside the ZIP; its
manifest records the immutable source-version creation time so identical inputs
remain byte-identical. The in-bundle manifest hashes its native asset members
rather than self-referentially hashing the final ZIP. Receipts are append-only
by bundle digest.

UI states should be `Draft`, `Bundle ready`, `Imported`, and `Import failed`.
`Importing` is only justified while an importer process with the exact digest is
known to be active. `Synced` is not supportable because Catalyst does not read
back Superset edits.

## Validation matrix

| Scenario | Required result |
| --- | --- |
| Clean metadata DB + valid bundle | One dashboard with all expected children; rendered values match PostgreSQL |
| Restart, same digest | No import; same Superset IDs and metadata state |
| Import, same digest | No-op receipt or idempotent success; no duplicate children |
| Changed Widget/Dataset versions | New immutable child UUIDs; same dashboard UUID points to new children |
| Malformed ZIP/YAML | Superset remains healthy; failed receipt and full bounded diagnostic |
| Missing/changed database connection | Import or render fails explicitly; no credential guessing |
| Concurrent import commands | One lock winner; later command re-checks receipt/current digest |
| Clean reset + current bundle | Same logical dashboard/asset UUIDs and rendered values |
| Superset version mismatch | Fail before import unless the bundle target matches the pinned runtime |

## Risks and deferred decisions

- Orphaned versioned charts/datasets accumulate in the persistent demo metadata
  database. This is bounded for the MVP and handled by explicit reset; selective
  cleanup belongs with an API/reconciliation phase.
- A user can edit layout in Superset, but the next Catalyst publication replaces
  the dashboard configuration. The UI and docs must warn about this one-way
  ownership boundary.
- Database connections are not overwritten by 6.1.0 dashboard import. Treat the
  local connection as stack configuration; a connection change requires reset
  or a separately tested datasource-import operation.
- Import is not transactionally coupled to Catalyst draft save. The content
  digest, receipt and retained prior dashboard provide honest recovery evidence.
- Asset schemas and chart `params` are release-coupled. Pin the image and validate
  every supported visualization with an export-from-Superset fixture and a real
  clean import before claiming compatibility.

## References

| # | Confidence | Source | Type | Relevance |
| --- | --- | --- | --- | --- |
| 1 | 🟢 High | [Apache Superset 6.1.0 release](https://github.com/apache/superset/releases/tag/6.1.0) | Official release | Runtime pin |
| 2 | 🟢 High | [Docker Compose installation](https://superset.apache.org/admin-docs/6.1.0/installation/docker-compose/) | Official docs | Local stack, persistent metadata, image/driver guidance |
| 3 | 🟢 High | [Importing and exporting assets](https://superset.apache.org/admin-docs/6.1.0/configuration/importing-exporting-datasources/) | Official docs | Native ZIP and CLI contract |
| 4 | 🟢 High | [Superset 6.1.0 import/export CLI source](https://github.com/apache/superset/blob/6.1.0/superset/cli/importexport.py) | Pinned primary source | CLI calls dashboard importer with overwrite enabled |
| 5 | 🟢 High | [Superset 6.1.0 dashboard importer source](https://github.com/apache/superset/blob/6.1.0/superset/commands/dashboard/importers/v1/__init__.py) | Pinned primary source | Related database/dataset/chart overwrite is disabled |
| 6 | 🟢 High | [Superset architecture](https://superset.apache.org/admin-docs/6.1.0/installation/architecture/) | Official docs | Metadata database role and minimal services |
| 7 | 🟢 High | [Upgrading Superset](https://superset.apache.org/admin-docs/6.1.0/installation/upgrading-superset/) | Official docs | Migrations, initialization and backup guidance |
| 8 | 🟡 Medium | [Reported related-asset overwrite behavior](https://github.com/apache/superset/issues/34879) | Upstream issue | Corroborates the pinned-source constraint; not itself normative |
