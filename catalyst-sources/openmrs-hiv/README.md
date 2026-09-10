# OpenMRS HIV Spark reference source

**Status:** Spark source configuration is integrated in the harness baseline.
Live validation and owner acceptance remain tracked in Feature 008.

This directory owns the OpenMRS HIV source assets used by the selected reference
deployment:

```text
retained OpenMRS demo data
  -> pinned FHIR Data Pipes
  -> Parquet and applicable ViewDefinitions
  -> Spark SQL
  -> Catalyst and Superset as SQL clients
```

The reference deployment uses these assets to:

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

The source is registered in `data-sources.json` with the Spark dialect and the
`openmrs_hiv` catalog. The retained ViewDefinitions are in `config/views/`.
The former PostgreSQL SQL and catalog files are retired; discover the current
readable Spark schema when preparing or validating queries.

Implementation order and acceptance are in the
[Feature 008 plan](../../specs/008-catalyst-query-workbench/plan.md),
[specification](../../specs/008-catalyst-query-workbench/spec.md), and
[quickstart](../../specs/008-catalyst-query-workbench/quickstart.md).
Use the harness `scripts/catalyst-mvp.sh` lifecycle wrapper. Seeding and reset
remain explicit operations.
