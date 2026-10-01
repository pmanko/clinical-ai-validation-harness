# Quickstart: Reviewed OpenMRS Demo Corpus (002)

This feature maintains the reviewed corpus/mapping and clinical-preservation
protocol. Reusable migration/terminology tooling ownership is an open
[umbrella decision](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#7-outstanding-decisions).
The data functionality remains in place pending that decision; standalone validation
does not require reconstructing the data-build environment.

## Prepare inputs and targets outside the runner

Use the [OpenClinAI setup documentation](https://github.com/pmanko/openclinai.org)
or your target's native preparation workflow. Supply:

- `large-demo-data-2-7-0.sql` and its origin/version/checksum;
- reviewed ConceptMap and SQLMesh inputs plus versioned CIEL/LOINC snapshots;
- a caller-prepared Core 2.8.x/O3 RefApp-compatible CIEL baseline and disposable
  database build schemas if rebuilding the corpus;
- configured database and OpenMRS REST/FHIR access for selected checks;
- supplied/observed target identity, image digests when available, and output location.

No harness target-registry, submodule initialization, pin check or service-start
command is part of this protocol. Product preparation, restoration, source builds,
service shutdown and credential hygiene belong to the deploying owner. For a
live chat claim consult [ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai).
OpenELIS feasibility uses an explicitly supplied schema artifact, not a required
sibling source tree, and does not execute a live load.

## Install and inspect actual entry points

From the harness repository with Python 3.11+ and `uv`:

```sh
uv sync --extra dev
uv run harness-cli --help
uv run python -m harness.profile --help
uv run python -m harness.load --help
uv run harness-cli transform run --help
```

Use the module help and your supplied connection settings for corpus operations.
Some top-level data CLI verbs (`conceptmap`, `sample`, `ocl refresh`, `manifest
finalize`) still return "not yet implemented"; they are not a working end-to-end
quickstart. The `import-smoke` CLI currently invokes a stub and does not prove a
real import. [Tasks](tasks.md) and [plan](plan.md) define remaining obligations.
Java is needed for the HL7 Validator operation, not every experiment.

## Rebuild/review the corpus when needed

1. Profile the source and supplied baseline. Review table/reference-source/locale/
   module coverage and schema differences before accepting transform decisions.
2. Validate the reviewed FHIR R4 ConceptMap with the HL7 Validator and the
   [ConceptMap profile](contracts/conceptmap.profile.md). Every referenced source
   concept needs a target/equivalence/action decision and reviewer rationale.
3. Emit deterministic translation seeds; review SQLMesh models and run standards
   conformance and audits against the supplied database. See the
   [SQLMesh profile](contracts/sqlmesh_project.profile.md).
4. Use the [direct load profile](contracts/load.profile.md) against a disposable
   build schema. Compare materialized row/content identities across clean replays,
   and inspect FK/completeness findings; a successful copy is not clinical acceptance.
5. Hand the module-clean portable dump and provenance sidecar to the deploying
   owner for restoration into a fresh OpenMRS instance. OpenMRS owns Liquibase.
6. On the prepared target, inspect real REST/FHIR import-smoke and terminology
   binding evidence, then sample all declared nonempty translation policy buckets
   with a recorded seed. Preserve per-record clinical fields and failure rationale.
7. For SC-015, run a configured clinical comparison through real ChartSearchAI chat
   and resolve final citations to translated records. See
   [harness quickstart](../../README.md#run-an-experiment).
8. For OpenELIS analysis, retain entity classifications, gaps, source columns and
   proposed shared identifiers in the [feasibility](contracts/openelis_feasibility.schema.yaml)
   and [skeleton](contracts/openelis_skeleton.profile.md) artifacts. Analysis is not parity evidence.

## Review the packet

Validate manifest/event meanings against [Spec 001](../001-harness-control-plane-foundation/contracts/run-manifest.schema.yaml)
and [002 extensions](contracts/run_manifest_002_extensions.schema.yaml). Include
mapping/snapshot checksums, source identity, actual exercised target provenance
with nullable revisions, record-level findings and reviewer/change rationale.
Capture inputs needed for offline reports; copy the whole packet. Counts, source
links and default image labels do not prove clinical meaning or deployed identity.

Keep credentials/private reasoning outside artifacts. Although this source is a
public demo corpus, newly captured evidence and deployment details still need
review before sharing. The umbrella owns publication and environment cleanup;
there is no harness Compose cleanup step.
