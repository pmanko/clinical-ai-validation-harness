# Multi-data-source: PR contracts and merge order

Draft PR titles/bodies for the two repos involved in the multi-data-source
feature, kept here so they're ready to use verbatim when the user decides to
push. **Not executed by this document** — pushing to remotes and opening PRs
is a separate, explicitly user-triggered step (see
`specs/artifacts/planning/catalyst-validation-integration-roadmap.md` and the
code-qa remediation plan for context on why this is deferred).

## Merge order

1. **`targets/catalyst` (branch `feat/multi-dataset`) merges first.**
   The harness's submodule pin (`git submodule status`) must point at a
   commit reachable on the target repo's default branch (or at least pushed
   and mergeable) before the harness re-pins to it — a fresh clone can't
   resolve a submodule commit that only exists on someone's local branch.
2. **The harness merges second**, in a commit that bumps the submodule pin
   alongside the harness-side additions this feature needed: the
   `catalyst-sources/openmrs-hiv/` source directory,
   `compose/catalyst-mvp-isolated.override.yml`,
   `scripts/generate-catalyst-source-catalog.py`, and the new
   `tests/test_hiv_fact_view_semantics.py` /
   `evals/scripts/test_generate_catalyst_source_catalog.py` guards.
3. Re-verify the pin from a **scratch clone** (not this worktree) before
   merging the harness side: `git submodule update --init` should resolve
   cleanly against the target repo's default branch.

## PR 1 — `targets/catalyst` (feat/multi-dataset)

**Title:** Add multi-data-source support (registry, per-turn targeting,
switcher UI)

**Body:**

```
## Summary
- Data-source registry (DataSourceBundle) with per-turn/session targeting;
  sessions are source-agnostic — "adapt this query to the other data source"
  works mid-session with last-turn-wins inheritance and per-source staleness
  baselines.
- Ingestion layering rule made explicit and enforced: upstream
  fhir-data-pipes default ViewDefinitions (lossless, one row per resource per
  coding) + documented additive extensions + gap-fill views for resources
  upstream ships none for; ALL curation happens in SQL over those defaults.
  The catalog is GENERATED from view/column comments plus a small
  catalog-overlay.json (see the harness's
  scripts/generate-catalyst-source-catalog.py).
- UI: a "Data source" switcher (hidden with one registered source), a
  session strip, and per-turn source badges in the notebook timeline.

## Test plan
- [ ] catalyst-gateway: `uv run --extra dev pytest` (158 tests)
- [ ] catalyst-gateway: `uv run --extra dev mypy src` (21-error baseline,
      unchanged from before this branch)
- [ ] catalyst-ui: `npx vitest run` (114 tests), `npx tsc -b`, `npx eslint .`
- [ ] tests/analytics (real PostgreSQL, requires the analytics-db container):
      `uv run python -m pytest tests/analytics/`
- [ ] Live two-source demo:
      `PLAYWRIGHT_LIVE=true PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000
      npx playwright test e2e/two-source-demo.spec.ts --project=demo-video`
      (requires the full live stack + harness's openmrs-hiv source
      provisioned)
```

## PR 2 — harness (this repo)

**Title:** Add OpenMRS HIV/ART data source + bump Catalyst pin

**Body:**

```
## Summary
- New `catalyst-sources/openmrs-hiv/` source: fhir-data-pipes config,
  curated SQL (hiv_observation_fact_v1, hiv_visit_fact_v1,
  hiv_concept_mapping_v1, hiv_patient_dim_v1), catalog-overlay.json,
  GENERATED catalog, data-sources.json, and a run-ingestion.sh runbook.
- Compose wiring: catalyst-mvp-isolated.override.yml adds the gateway's
  CATALYST_DATA_SOURCES_PATH env + read-only source mounts (relative default
  path so plain `make catalyst-mvp-up` still works single-source).
- New guards: tests/test_hiv_fact_view_semantics.py (real-Postgres SQL
  semantics) and evals/scripts/test_generate_catalyst_source_catalog.py
  (generator fail-fast contracts) — see targets/catalyst's companion PR for
  the corresponding gateway/UI test additions.
- Bumps the targets/catalyst submodule pin to <commit-after-PR-1-merges>.

## Depends on
- targets/catalyst PR 1 above must merge first; this PR's submodule pin
  must resolve against that repo's default branch from a scratch clone.

## Test plan
- [ ] `uv run pytest -m 'not slow' --ignore=targets`
- [ ] `uv run python -m pytest tests/test_hiv_fact_view_semantics.py
      evals/scripts/test_generate_catalyst_source_catalog.py` (real
      PostgreSQL, analytics-db container up)
- [ ] Scratch-clone submodule resolution check (see Merge order above)
- [ ] Manual: gateway container rebuild + restart;
      `GET /v1/catalyst/data-sources` lists both sources
```
