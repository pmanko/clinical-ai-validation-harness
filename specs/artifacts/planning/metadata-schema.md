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
- `reviewer_change_record`

## OTel GenAI Alignment

When available, map fields to:

- `gen_ai.provider.name`
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

Evaluation and review events should record why the cited evidence supports,
does not support, or is insufficient for a validation decision. This keeps
alignment and safety claims reviewable instead of reducing them to outcome
labels alone.
