# Cross-project metadata guide

This guide defines the stable metadata envelope shared by validation work in
this repository. It supports the provenance and traceability rules in the
[project constitution](../../../.specify/memory/constitution.md) without making
one feature's evidence model mandatory for another.

Catalyst delivery uses this shared envelope. Its integration and evidence
requirements are tracked in the [Feature 008 specification](../../008-catalyst-query-workbench/spec.md)
and [tasks](../../008-catalyst-query-workbench/tasks.md); only the fields below
are current requirements.

## Stable run envelope

Every run emits:

- `run_manifest.json` — frozen run identity and provenance; and
- `events.jsonl` — chronological operating events, one JSON object per line.

Feature-specific evidence files may sit beside them. The manifest and event
stream reference those files; they do not copy large clinical payloads into the
shared metadata layer.

### Minimum manifest identity

The common manifest retains:

- `run_id`;
- `project` and `component`;
- `git_sha` — supplied harness revision, nullable when unavailable; no Git lookup;
- `generated_at`;
- `dataset_id` and `dataset_version` when a dataset is used;
- `schema_mapping_version` when a mapping is used;
- `target_provenance`;
- `dataset_provenance` when source artifacts or fixtures are part of the run;
- `otel.gen_ai.provider.name` when a model is invoked; and
- `otel.gen_ai.operation.name` when a model/agent operation is involved.

Unknown model/provider/operation metadata is explicitly disclosed by the feature;
these fields must not be fabricated merely to fill the envelope.

Feature schemas may add configuration and evidence references. They must not
change the meaning of these common fields.

### Target provenance

`target_provenance` records identity supplied by the caller or observed through the
configured target's interface. Record each exercised target separately, with
`target_id`, assertion origin (`target_source`: `supplied`, `observed_api` or
`unavailable`) and nullable `target_actual_sha`. Adapter-specific image/deployment,
endpoint, profile/model/prompt or configuration identities may extend that entry.
A reference-only repository is not an exercised target.

A caller-supplied revision is an assertion, not proof of the code running at an
endpoint. Preserve supplied and observed identities separately, including conflicts;
never overwrite one with the other. Unknown revisions remain null and other missing
metadata is disclosed explicitly. Model/provider/prompt fields are recorded only
when supplied or observed, never inferred by scanning local product/model sources.

The runner does not enforce pins or require Git, submodules, target paths, checkout
state, reviewed revisions, override/promotion status or a workspace catalog.
Missing revision metadata does not itself block a capable configured target.
`evidence_status` labels the evidence and its limits, not workspace compliance or
harness-granted release approval. Release acceptance remains an external decision.
See the [foundation manifest contract](../../001-harness-control-plane-foundation/contracts/run-manifest.schema.yaml)
for common shapes; feature emitters own executable schemas and wire-format versions.

### Dataset provenance

`dataset_provenance` identifies the data accepted for the run. Depending on the
feature, it may include source files, fixture or corpus versions, mapping
versions, receipts, and content digests. It records missing expected inputs
explicitly. Counts alone are not evidence that the intended records or clinical
meaning were present.

Existing chart/corpus comparison runs keep their current dataset identity:

- the selected comparison-set file and digest;
- each selected scenario file and digest;
- each patient fixture's file and canonical-record digest;
- any missing expected fixtures;
- the restored corpus receipt and source-dump digest when available; and
- one combined digest over the complete accepted input set.

Their corpus receipt is created only after the portable dump and provenance
sidecar pass the existing verification path. Fixture-to-live-record equality is
checked before the run where required by the selected clinical protocol. Target
preparation/restoration is caller-owned, not a runner deployment operation.

Capture the selected configuration, comparison/suite, scenario and required fixture
bytes with their digests in the run directory. Missing expected inputs are explicit.
Reports consume that frozen packet, not live services, original authored dataset
directories or product sources. A copied run must retain enough evidence to
regenerate reports offline; a missing input cannot silently fall back to a local file.

## Event stream

The shared event vocabulary remains:

- `run`;
- `query`;
- `retrieval`;
- `model`;
- `response`;
- `evaluation`;
- `profile_discovery_failed`;
- `runtime_identity`;
- `runtime_identity_failed`; and
- `reviewer_change_record`.

Each event uses the versioned schema owned by the emitting feature and retains
enough run, time, case, component, and trace identity to resolve its referenced
evidence. Evidence paths are relative to the run directory and must not escape
it. Events are appended; a later observation does not rewrite an earlier one.

## Data boundaries

The shared metadata files contain operating evidence, not a second clinical
data store.

- Credentials, connection strings containing secrets, tokens, private keys,
  and infrastructure access rules are excluded.
- Clinical result rows are stored only in the bounded feature evidence that
  needs them. The manifest and event stream contain a safe reference and
  identity for that evidence, not the rows themselves.
- Raw private model reasoning is excluded. The actual messages and structured
  context supplied to a model may be retained when required for review.
- Absolute workstation paths and private deployment details are excluded from
  publishable evidence.

## Executable schema ownership

This Markdown file is guidance, not a machine contract. Each emitter owns its
versioned JSON schemas, writing code, and validators. Feature 008's harness
evidence schemas live in
[`specs/008-catalyst-query-workbench/contracts/`](../../008-catalyst-query-workbench/contracts/).
Catalyst Gateway API schemas live beside the Gateway in the Catalyst repository
under [Catalyst `docs/contracts/`](https://github.com/DIGI-UW/openelis-catalyst/tree/main/docs/contracts).
Spec 002's [corpus/mapping extensions](../../002-openmrs-demo-data-2-8-remap/contracts/run_manifest_002_extensions.schema.yaml)
retain data identity and deterministic transform evidence without workspace gates. A
wire-format change updates and tests the actual emitter and every retained copy
together. It does not silently add requirements to another project.

## Catalyst Phase 1 reader packet

The selected Catalyst Phase 1 comparison will reuse the shared run envelope and
be reader-led: automated checks will establish collection, identity, and
contract facts, while the reader interprets the complete case against one shared
rubric.

### Run identity and configuration

The Catalyst manifest and public configuration identify:

- the scenario suite and its content identity;
- the selected model team and its resolved profiles, models, prompts, and
  settings;
- supplied/observed Harness, Catalyst and Med Agent Hub identity, with revisions
  nullable when unavailable and each assertion's origin retained;
- the configured source identity and safe connection reference;
- the source's explicit SQL dialect and readable-schema snapshot identity;
- the dataset and reference-deployment identity; and
- whether collection is complete or unfinished.

Service or machine interruptions are recorded separately from model behavior.
An unfinished suite remains unfinished; it is not converted into a model result
by a numeric allowance.

### Case evidence

Each case supplied to the reader contains:

- the full conversation;
- the actual model context for each invocation;
- the resolved model-team configuration and model outputs;
- the exact selected SQL, typed parameters, query-version identity, and digest
  for a ready turn;
- the bounded typed rows or database error returned by that one Catalyst
  execution;
- the static design-time reference or reviewed expected response;
- the shared human-readable rubric; and
- the relevant source, dialect, schema, timing, and component provenance.

A ready scenario's reference is authored, run, and reviewed when the scenario is
designed or deliberately changed. The comparison does not execute that
reference again. Clarification and unsupported cases retain their reviewed
expected response and show that no SQL ran.

Wrong SQL, a wrong answer, and a database error remain valid observations when
their evidence is complete. The harness does not compute factual equivalence,
a score threshold, a rank, a disqualification, a winner, or an automatic
verdict.

### Reader rationale

One full-context reader pass is the default. Its rationale is stored separately
from the collected case evidence with:

- reader identity and, when applicable, provider, model, and model version;
- review time;
- the content identity of the exact reader input; and
- the complete written rationale against the shared rubric.

Another perspective is a separate deliberate review over the same input. Reader
rationales are not averaged or collapsed into a synthetic result.

The Catalyst event schema will reference scenario, turn, query version,
execution, and reader review. It will not emit automated judge outcomes. The
machine schema and runtime writer are implementation work under the Catalyst
implementation plan.

## Catalyst Dashboard lineage

Dashboard metadata extends the same run identity with a direct lineage:

```text
source -> query version -> execution -> Dataset version
       -> Widget version -> Dashboard version -> bundle -> import receipt
```

The lineage retains:

- source identity, dialect, and readable-schema snapshot;
- exact query-version and execution identities and digests;
- immutable Dataset, Widget, and Dashboard version identities and parent links;
- bundle identity, digest, and publication reference; and
- the explicit Superset import receipt, outcome, and resulting dashboard
  identity or actionable error.

An import receipt, not the existence of a bundle, establishes import status.
The metadata records lineage and the browser-visible product evidence required
by Feature 008. It does not introduce a second database comparison path, a
deployment-lifecycle matrix, or a separate acceptance state machine.

Clinical rows, credentials, Superset secrets, and raw model traces remain
outside Dashboard metadata. Bounded result evidence stays attached to the
originating execution and is referenced by identity.

## Other project extensions

Existing project-specific schemas remain authoritative and are unaffected by
the Catalyst simplification. Their extension payloads retain applicable validation facts, with emitters/consumers
aligned to the supplied/observed provenance boundary:

- retrieved and cited record identifiers;
- claim-support and abstention labels;
- reviewer labels and decision rationale;
- mapping versions and source receipts;
- supplied or observed component, image/deployment and configuration identity; and
- model, prompt, retrieval, response, and evaluation provenance.

These fields stay with the project that can interpret them. Shared names do not
imply shared scoring or a shared product acceptance rule.

## OpenTelemetry GenAI guidance

When available, map model and agent metadata to:

- `gen_ai.provider.name`;
- `gen_ai.operation.name`;
- `gen_ai.agent.name`;
- `gen_ai.request.model`;
- `gen_ai.response.model`; and
- `gen_ai.tool.name`.

The manifest may namespace these as `otel.*`. `gen_ai.provider.name` is the
canonical provider identity; do not also emit the deprecated `gen_ai.system`
name for the same fact.

Keep clinical and evaluation semantics in feature-owned extension payloads.
Review events record why evidence supports, contradicts, or is insufficient for
a conclusion instead of reducing the review to an outcome label alone.

## Validation expectations

Validators should prove that:

- the manifest and every event parse against their declared versioned schemas;
- run, case, trace, and referenced entity identities resolve consistently;
- referenced evidence exists at safe relative paths;
- target assertions have explicit supplied/observed/unavailable origins and nullable
  revisions; conflicts and missing metadata remain visible without pin enforcement;
- dataset provenance and captured bytes/digests identify the inputs actually used;
- copied run packets regenerate reports without original inputs or services; and
- prohibited secrets, clinical rows, and private reasoning are absent from the
  shared metadata files.

These are structural and provenance checks. Clinical or factual correctness
remains a feature-specific review question.
