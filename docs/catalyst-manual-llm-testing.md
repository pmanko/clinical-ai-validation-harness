# Catalyst manual LLM testing

This setup is for observing query behavior across local LLMs. It is an
engineering sandbox, not a claim that every question produces correct SQL.

## What is selectable

Catalyst Gateway owns the query-profile registry, exact role/model mappings,
prompts, sampling/output settings, lint, and writer/reviewer orchestration.
Med-Agent Hub exposes a generic single-role completion endpoint plus a versioned
backend model inventory. The UI lists a Gateway profile only when Hub advertises
all of its exact required writer and optional reviewer aliases.

The sibling Hub's existing product execution profiles remain in
`targets/med-agent-hub/server/levels.yaml`; they are separate from Catalyst's
Gateway-owned query profiles and are not edited to add Catalyst prompts or SQL
orchestration.

Treat the UI picker (backed by the Gateway registry filtered through Hub's live
inventory) as the source of truth for currently available profiles, writer
models, and reviewer models. The external OpenAI-compatible server must
advertise every exact runtime model ID required by a profile in its `/v1/models`
response.

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

Open `http://localhost:13000`, or the port set by `CATALYST_UI_PORT`. The
`make catalyst-mvp-*` targets run the isolated stack, which publishes the UI
on `13000` and the gateway on `18000`; `3000` is Catalyst's own default, which
applies only when running its compose directly from `targets/catalyst`. The
first initialization loads the synthetic OpenELIS cohort, backfills FHIR, and
materializes the governed analytics view, so it takes longer than ordinary
restarts. That state is retained in this stack's named Docker volumes. Use
`make catalyst-mvp-restart` for a normal stop/start without reloading FHIR or
Data Pipes, `make catalyst-mvp-seed` only when you deliberately want to reload
the fixture, and `make catalyst-mvp-reset` only for a clean slate.

## Compare models manually

1. Load or serve every exact model alias required by a Gateway query profile.
2. Refresh the Catalyst UI and select a **Model profile**.
3. Enter a question using the runtime catalog as the available-data reference.
4. Inspect the generated SQL, parameters, profile/model roles, and lint attempts.
5. Accept only the queries you want to execute; compare the returned table and
   truncation notice with the dataset browser.
6. Swap the served model, refresh, select the other profile, and repeat the same
   questions.

## Compare across data sources

The stack registers a second data source (OpenMRS HIV/ART) alongside
OpenELIS once `catalyst-sources/openmrs-hiv/` is provisioned (see its
`run-ingestion.sh`). When more than one source is registered, a **Data
source** selector appears next to the model-profile picker:

1. Ask a question against the default source (OpenELIS Laboratory) as above.
2. Switch the **Data source** selector to the other source mid-session.
3. Enter a follow-up instruction referencing that source's schema (or ask
   Catalyst to adapt the current query to it); the generated SQL should
   target that source's catalog, and the turn timeline should show which
   source each turn used.
4. Validate and run — execution routes to that source's own analytics
   database, distinct from the default source's.

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

## Add another Gateway-owned query profile

For a local experiment, add an `EngineProfile` to
`targets/catalyst/catalyst-gateway/src/catalyst/query_profiles.py` and add its
focused discovery/orchestration tests. Keep the profile ID stable, map each role
to the exact router alias, and keep SQL sampling bounded (`temperature: 0`,
`dry: 0`, and an explicit `maxTokens`). A writer-only profile needs only
`query_generate`; a reviewed profile declares `query_review` as well. Hub needs
no Catalyst-specific profile or prompt change.

Rebuild the sibling Hub through the harness runner:

```bash
make catalyst-mvp-external
```

Refresh the UI. The profile is omitted until every exact role model is served.
Preserve a useful query profile through review in Catalyst. Change Hub only if
the generic role/inventory contract itself must change; if it does, merge Hub
first and repin Catalyst's fallback plus the harness sibling pin to the same
commit.

## Restart, stop, or reset

```bash
# Stop and start containers while retaining the OpenELIS, HAPI, Data Pipes,
# analytics, Gateway, and Superset volumes. Does not re-seed.
make catalyst-mvp-restart

# Stop containers; `make catalyst-mvp-up` resumes the same volumes.
make catalyst-mvp-down

# Delete the disposable data volumes. The next boot needs an explicit seed.
make catalyst-mvp-reset
```
