# Catalyst manual LLM testing

This setup is for observing query behavior across local LLMs. It is an
engineering sandbox, not a claim that every question produces correct SQL.

## What is selectable

Med-Agent Hub owns the model configuration. Catalyst sends only a profile ID,
the question, the approved catalog, and policy context. The UI discovers the
profiles from Hub and lists a profile only when all of its required models are
served.

Treat the UI picker (backed by the Gateway's Hub-discovered query options) as
the source of truth for available profiles, writer models, and reviewer models.
Do not rely on a copied profile list: it changes as the pinned Hub revision
changes. The external OpenAI-compatible server must advertise every exact
runtime model ID required by a profile in its `/v1/models` response.

## Start with an external model server

Initialize both harness-owned sibling targets. The harness runner builds the
pinned Med-Agent Hub checkout directly and supplies it to Catalyst as the Hub
build context.

```bash
git submodule update --init targets/catalyst targets/med-agent-hub
cp targets/catalyst/env.recommended targets/catalyst/.env
```

Set these values in `targets/catalyst/.env`:

```dotenv
MVP_MODEL_BACKEND=external
MVP_EXTERNAL_ROUTER_URL=http://host.docker.internal:1234
MVP_EXTERNAL_PROFILE_ID=catalyst-query-gemma-4-12b
MVP_EXTERNAL_MODEL_ID=gemma-4-12b
MVP_EXTERNAL_EXPECTED_ROLE_MODELS_JSON='{"query_generate":"gemma-4-12b","query_review":"qwen2.5-14b"}'
```

The URL is the OpenAI-compatible server root, without a trailing `/v1`. Then:

```bash
make catalyst-mvp-external
```

Open `http://localhost:3000` with the recommended configuration, or use the
port set by `CATALYST_UI_PORT`. The first boot initializes the synthetic
OpenELIS cohort and the governed analytics view, so it takes longer than later
boots.

## Compare models manually

1. Load or serve a model whose ID matches one of the Hub profiles.
2. Refresh the Catalyst UI and select **Med-Agent Hub profile**.
3. Enter a question using the runtime catalog as the available-data reference.
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
`targets/med-agent-hub/server/levels.yaml`. Keep the profile ID stable, set each
role to its exact served model ID, and disable stochastic sampling and the DRY
repetition penalty for SQL (`temperature: 0`, `dry: 0`):

```yaml
catalyst-query-my-model:
  label: Catalyst governed query — My model
  topology: single
  stages: *catalyst_query
  models: {query_generate: exact/writer-model-id, query_review: exact/reviewer-model-id}
  prompts: {query_generate: catalyst-query-generate, query_review: catalyst-query-review}
  policies:
    output: query
    temporal_gate: "off"
    allowed_operation: select
    generation_attempts: 1
    collaborative_review: true
    model_classes: {query_generate: writer-family, query_review: reviewer-family}
  capabilities: {staged: false, validation: true}
  outputContracts: [catalyst.query.v1]
  visibility: product
  knobs: {query_generate: {temperature: 0, dry: 0}, query_review: {temperature: 0, dry: 0}}
```

Rebuild the sibling Hub through the harness runner:

```bash
make catalyst-mvp-external
```

Refresh the UI. The profile is omitted until every exact role model is served.
Preserve a useful profile through review in the Med-Agent Hub repository, then
update the Hub pin in the harness and Catalyst's same-commit standalone fallback.

## Stop or reset

```bash
make catalyst-mvp-down
make catalyst-mvp-reset
```
