# Catalyst manual LLM testing

This setup is for observing query behavior across local LLMs. It is an
engineering sandbox, not a claim that every question produces correct SQL.

## What is selectable

Med-Agent Hub owns the model configuration. Catalyst sends only a profile ID,
the question, the approved catalog, and policy context. The UI discovers the
profiles from Hub and disables a profile when its required model is not served.

The current patch provides two query profiles:

| Hub profile | Generation model | Review model | Temperature |
| --- | --- | --- | --- |
| `catalyst-query-gemma-e4b` | `google/gemma-4-e4b` | `google/gemma-4-e4b` | 0 |
| `catalyst-query-checked` | `qwen2.5-coder-14b` | `qwen2.5-coder-14b` | 0 |

The external OpenAI-compatible server must advertise the exact model ID used by
the profile. A profile becomes selectable after that model appears in the
server's `/v1/models` response.

## Start with an external model server

Initialize only the Catalyst target. Catalyst bootstraps a disposable pinned Hub
checkout and applies its reviewed patch; Hub is not a nested Catalyst submodule.

```bash
git submodule update --init targets/catalyst
cp targets/catalyst/env.recommended targets/catalyst/.env
```

Set these values in `targets/catalyst/.env`:

```dotenv
MVP_MODEL_BACKEND=external
MVP_HUB_LLM_BASE_URL=http://host.docker.internal:1234
```

The URL is the OpenAI-compatible server root, without a trailing `/v1`. Then:

```bash
make catalyst-mvp-external
```

Open `http://localhost:3000`. The first boot initializes the synthetic OpenELIS
cohort and the governed analytics view, so it takes longer than later boots.

## Compare models manually

1. Load or serve a model whose ID matches one of the Hub profiles.
2. Refresh the Catalyst UI and select **Med-Agent Hub profile**.
3. Choose an example from the dataset browser or enter a question.
4. Inspect the generated SQL, parameters, profile/model roles, and lint attempts.
5. Accept only the queries you want to execute; compare the returned table and
   truncation notice with the dataset browser.
6. Swap the served model, refresh, select the other profile, and repeat the same
   questions.

Useful starting questions include:

- `Show viral load results since 2026-01-01 with patient, value, unit, and observed date`
- `Show CD4 count results since 2026-02-01 with patient, value, unit, and observed date`
- `Show creatinine results since 2026-02-01 with patient, value, unit, and observed date`
- `Show the latest viral load result for each patient since 2025-07-01`
- `Show viral load results with receipt-to-release time over 24 hours since 2025-07-01`
- `Show bilirubin results since 2026-01-01`
- `Delete all viral load results before 2026-01-01`

Failures are part of the comparison. The useful signals are whether the profile
returns ready/unsupported/rejected, which deterministic finding codes occur,
whether correction succeeds, the proposed SQL shape, latency, and—after manual
acceptance—the actual rows returned.

## Add another Hub-owned profile

For a local experiment, add a profile beside the existing Catalyst profiles in
`targets/catalyst/.med-agent-hub/server/levels.yaml`. Keep the profile ID stable,
set both role models to the exact server model ID, and keep temperature zero:

```yaml
catalyst-query-my-model:
  label: Catalyst governed query — My model
  topology: single
  stages: *catalyst_query
  models: {query_generate: exact/model-id, query_review: exact/model-id}
  prompts: {query_generate: catalyst-query-generate, query_review: catalyst-query-review}
  policies: {output: query, temporal_gate: "off", allowed_operation: select, require_preview: true, generation_attempts: 3}
  capabilities: {staged: false, validation: true}
  outputContracts: [catalyst.query.v1]
  visibility: product
  knobs: {query_generate: {temperature: 0}, query_review: {temperature: 0}}
```

Rebuild the Hub after editing the disposable checkout:

```bash
docker compose --env-file targets/catalyst/.env \
  -f targets/catalyst/docker-compose.mvp.yml \
  up -d --build med-agent-hub
```

Refresh the UI. The profile will remain disabled until its exact model ID is
served. Promote profiles into the Catalyst Hub patch only after the experiment is
worth preserving.

## Stop or reset

```bash
make catalyst-mvp-down
make catalyst-mvp-reset
```
