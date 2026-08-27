# OpenMRS HIV Spark reference source

**Status:** Not implemented.

This directory owns the OpenMRS HIV source assets used by the selected reference
deployment:

```text
retained OpenMRS demo data
  -> pinned FHIR Data Pipes
  -> Parquet and applicable ViewDefinitions
  -> Spark SQL
  -> Catalyst and Superset as SQL clients
```

The implementation must:

- enable the pinned FHIR Data Pipes Parquet path;
- review and retain the applicable files under `config/views/`;
- expose the resulting data through Spark SQL;
- register Spark as a Catalyst source with an explicit dialect;
- expose every Spark-readable table, view, column, and type to the model,
  editor, and Available data view;
- connect Superset to the same Spark source; and
- reuse retained demo data during ordinary development.

Optional descriptions may enrich the discovered schema. They do not approve,
rank, or hide relations.

The current runtime uses the PostgreSQL sink, SQL, catalog, registry, and
ingestion files in this directory. The selected Spark deployment contains none
of those components.

Implementation order and acceptance are in the
[Catalyst implementation plan](../../specs/catalyst-implementation-plan.md)
and [Feature 008 quickstart](../../specs/008-catalyst-query-workbench/quickstart.md).
There is no supported source-local Spark command until that work lands. Seeding
and reset remain explicit operations.
