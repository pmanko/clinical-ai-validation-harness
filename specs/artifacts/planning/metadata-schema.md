# Metadata Schema v0

The metadata schema supports the constitution's provenance and traceability
requirements in `.specify/memory/constitution.md`.

Each run emits:

- `run_manifest.json`
- `events.jsonl`

## Manifest Fields (minimum)

- `run_id`
- `project`
- `component`
- `git_sha`
- `dataset_id`
- `dataset_version`
- `schema_mapping_version`
- `generated_at`
- `otel.gen_ai.provider.name` for runs that invoke an LLM; non-LLM runs omit it
- `otel.gen_ai.operation.name`
- `target_provenance`

For Catalyst query-validation runs, `target_provenance` contains separate,
control-plane-compatible Catalyst and Med-Agent Hub entries. The runner rejects
an uninitialized, dirty, or pin-mismatched target before contacting either
service. The Catalyst entry records the suite and the preflight dataset-overview
and editor-catalog payloads with canonical SHA-256 digests; the exact runtime
catalog version becomes `schema_mapping_version`. The Hub entry records the
selected profile discovery payload and digest. Writer/reviewer provider evidence
must agree, and the resulting provider becomes `otel.gen_ai.provider.name`; the
suite's provider is an expected value, not the evidence source. A run that fails
before profile discovery records the provider as unresolved. Catalyst model
operations use `otel.gen_ai.operation.name = chat`.

Validation comparison runs also emit `dataset_provenance` with:

- the selected comparison-set file and SHA-256;
- every selected scenario file and SHA-256;
- every patient chart fixture and both file and canonical-ledger SHA-256;
- any missing patient fixtures;
- the locally restored corpus receipt and source-dump SHA-256 when available; and
- one combined SHA-256 over that complete run input identity.

The corpus receipt is created by `scripts/seed-local.sh` only after the portable dump
and its provenance sidecar pass `scripts/verify-portable-dump.py`. Fixture/live ledger
equality is still enforced immediately before a run; manifest hashes make that checked
input identity auditable afterward.

## Event Types

- `run`
- `query`
- `retrieval`
- `model`
- `response`
- `evaluation`
- `profile_discovery_failed`
- `runtime_identity`
- `runtime_identity_failed`
- `reviewer_change_record`

## OTel GenAI Alignment

When available, map fields to:

- `gen_ai.provider.name`
- `gen_ai.operation.name`
- `gen_ai.agent.name`
- `gen_ai.request.model`
- `gen_ai.tool.name`

Keep clinical-specific fields in extension payload:

- retrieved record ids
- cited record ids
- claim support labels
- abstention label
- reviewer label
- decision rationale
- mapping version
- component pin and working-tree state
- profile/model/configuration/prompt digests
- canonical row digests and bounded record identifiers for query-table evidence

Evaluation and review events should record why the cited evidence supports,
does not support, or is insufficient for a validation decision. This keeps
alignment and safety claims reviewable instead of reducing them to outcome
labels alone.
