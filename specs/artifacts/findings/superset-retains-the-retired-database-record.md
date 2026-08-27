# Fixed: Superset kept the retired PostgreSQL database record on import

**Recorded and resolved 2026-08-27.** An earlier version of this note reported
this as an open owner decision. It was fixed instead; the note is kept because
the failure mode is worth remembering.

## The defect

Catalyst published a bundle naming the Spark source
(`hive://catalyst@spark-thriftserver:10000/default`), the importer reported
`{"status": "imported"}` — and the dashboard still resolved to PostgreSQL.

Superset matches assets by UUID, and the bundle derives its database UUID
deterministically, so a database first imported during the PostgreSQL era kept
that connection permanently. Superset 6.1's `superset import-dashboards` CLI
offers only `-p` and `-u`; there is no overwrite flag to force reconciliation.

The failure was silent, which is what made it serious: a successful-looking
import pointing at an engine that had been deleted is the same
substitution-hidden-behind-a-green-signal shape this whole remediation exists
to remove.

## The fix

`scripts/superset-import.py` now reconciles the database before importing: if
a database with the bundle's UUID exists and its URI differs, the importer
reconnects it and records what changed in the receipt, so an engine change is
visible rather than indistinguishable from an ordinary import. The receipt
contract requires that field.

## Verified end to end on the running stack

| Step | Evidence |
| --- | --- |
| Catalyst executed the writer's Spark SQL | `SELECT count(t1.id) AS count FROM default.patient AS t1` -> **5384** |
| Saved as Dataset -> Widget -> Dashboard, published | `status: bundle_ready` |
| Imported | `status: imported` |
| Superset's database after reconciliation | `backend: hive` |
| Superset dataset SQL | `SELECT count(t1.id) AS count FROM default.patient AS t1` |
| Executed through Superset | `{"count": 5384}` |

The displayed value matches the originating Catalyst result, read through
Superset's own connection to the same Spark source — no second database.
