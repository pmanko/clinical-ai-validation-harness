# Corrected: the complete Spark schema fits — the adapter was inflating it

**Recorded 2026-08-27. The first version of this note was wrong and is
superseded here.**

## What the first version claimed

That a workbench turn failed with `context_window_exceeded` because the
complete readable schema (24 relations / 470 columns, ~336 KB) was too large
for the writer, and that the owner had to choose between raising the context
window, changing snapshot retention, or using a smaller source.

## What is actually true

The schema was never the problem. The Spark dialect adapter synthesized a
description for every column by embedding that column's **native type**:

```python
"description": comment or f"{qualified}.{column_name} (Spark {database_type})"
```

`request_catalog()` sends `description` to the model and strips
`databaseType`, so the FHIR resource tables' deeply nested STRUCT types
reached the writer anyway. One `Encounter.hospitalization` column's type text
is ~5.9 KB on its own.

Measured on the running stack, same 24 relations and 470 columns throughout:

| | model request | approx tokens | ctx-size |
| --- | --- | --- | --- |
| before | 187,652 bytes | ~53,600 | 24,576 |
| after | 24,145 bytes | ~6,900 | 24,576 |

A description is now only a real column comment; the native type stays on
`databaseType`, where the editor already receives it. The query-request
contract required a description on every field — which is why the synthesized
one existed — and that requirement is removed, as the implementation plan's
own table prescribes.

## Outcome

The writer produced Spark SQL against the Spark-discovered schema:

```sql
SELECT count(t1.id) AS count FROM default.patient AS t1
```

Run returned `5384` (BIGINT -> integer), matching the count read directly
through beeline.

## What this cost, and the lesson

No relation allowlist, ranking, selection or truncation was ever added, and
none is needed. Escalating to the owner would have asked for a decision about
a constraint that did not exist. The measurement that settled it — sizing the
actual model request, then finding which field dominated it — took one probe,
and should have come before the escalation was drafted, not after.
