# Two sources currently share one Spark namespace

**Recorded 2026-08-27.** The implementation plan left this open deliberately:
"Whether they can share a Spark endpoint is an implementation finding; do not
design a namespace service in advance." This is that finding.

## The answer, as configured: no

Both sources point at the same thriftserver and the same Hive database:

```
targets/catalyst/analytics/config/thriftserver-hive-config.json   databaseName: "default"
catalyst-sources/openmrs-hiv/config/thriftserver-hive-config.json databaseName: "default"
```

FHIR Data Pipes names its registered relations after the resource and the
ViewDefinition, not after the source, so both pipelines register
`patient_flat`, `observation_flat`, `encounter_flat` and their timestamped
twins into the same namespace. The second pipeline to run takes those names.

Only the OpenMRS HIV source has been ingested, which is why nothing has
collided yet. The Gateway's two configured sources therefore resolve to the
same 24 relations today — the source labels differ, the readable schema does
not.

## Do not run `catalyst-mvp.sh seed` or `boot` until this is decided

`scripts/mvp-seed.sh` still triggers the OpenELIS controller's FULL run. With
the three FHIRDATA flags now true, that run registers OpenELIS relations under
the same names into the same `default` database as the HIV views.

## The configuration-level fix

`thriftserver-hive-config.json` already carries a `databaseName` field. Giving
each source its own database, and having the controller create it, separates
the namespaces without a namespace service, a translator, or any change to
Catalyst: a source's configuration keeps naming exactly one connection URI,
whose path selects its database.

That is a deployment decision for the owner, and it is out of scope for the
HIV-only remediation, so it is recorded rather than made here.
