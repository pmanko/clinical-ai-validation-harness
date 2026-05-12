# Metadata Schema v0

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
- `otel.gen_ai.system`

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

- `gen_ai.system`
- `gen_ai.agent.name`
- `gen_ai.request.model`
- `gen_ai.tool.name`

Keep clinical-specific fields in extension payload:

- retrieved record ids
- cited record ids
- claim support labels
- abstention label
- reviewer label
- mapping version
