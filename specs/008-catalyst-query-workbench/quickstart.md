# Quickstart: Query Workbench Development

## Isolated stack

Use the dedicated harness worktree and Catalyst submodule checkout. Do not run
this feature from the user's primary harness checkout.

The current isolated demo is composed with:

- compose file: `/private/tmp/catalyst-mvp-harness/isolated.compose.yml`
- environment: `/private/tmp/catalyst-mvp-harness/isolated.env`
- project: `catalyst-mvp-isolated`
- browser: `http://localhost:13000/`

## Historical G2.2 checkpoint used before editor implementation

1. Re-run “how many patients had viral load tests above 1000 count/ml?” through
   Gemma E4B and Gemma 4 12B; inspect the recorded
   `parameters.1: 'name' is required` query-generation failures and capture raw
   candidates plus profile/model/prompt/schema/seed/attempt provenance.
2. Confirm E4B session `2bed91de-fa7d-4ffa-b4ae-0a454a883930` retains editable
   attempt-1 version `d801dc1d-fc94-435b-bee6-2b45c3173af1`, then add a failing
   regression proving the current candidate-or-raw diagnostic loses the latest
   malformed response. Require both the best parsed draft and latest raw response.
3. Record which contract layer owns the missing-`name` correction and add a
   failing regression there. A deterministic name is allowed only for one
   provably unmatched parameter and one remaining SQL placeholder; otherwise
   retain a manual finding.
4. Add failing UI tests for failed-draft/raw-output retention, highlighting,
   line numbers, default wrap/toggle,
   keyword and approved-catalog completion, deterministic Format, graceful
   catalog failure, and immutable Validate/Run versioning.
5. Record the reviewed editor/formatter versions and accessibility/build
   decision. Do not begin editor implementation until this evidence is present.

## W1 verification sequence

The post-G2.3 comparison evidence is E4B session
`11c585d8-c8ab-4fa6-a421-d6435b81845d` and 12B session
`902bd844-e8f1-403d-90ee-8fccd9417f99`. Use the same question and inspect both
the workbench validation and Hub generation attempts; they intentionally report
different validation scopes.

1. Start or rebuild the isolated gateway and UI while retaining the existing
   Hub, model router, seeded analytics database, and SQLite volume.
2. Confirm health reports the selected Hub query profile and model roles.
3. Create a workbench session from a natural-language question.
4. Verify the generated SQL, typed parameters, model/profile provenance, and
   all findings are visible even when validation fails.
5. Verify PostgreSQL highlighting and logical line numbers; wrapping starts on,
   the toggle is keyboard operable, and its session preference survives refresh
   without changing the query digest.
6. Request completion for a PostgreSQL keyword and an approved catalog object;
   suggestions must be stable, catalog-backed, and absent rather than invented
   when the catalog is unavailable.
7. Format the same SQL twice and compare bytes and parsed meaning. Formatting
   must make no model call and must not alter the stored source version.
8. Change SQL and one parameter; Validate must persist the exact buffer as a new
   immutable child while the source version remains unchanged.
9. Run a warning/error-bearing version; Run must remain enabled and submit the
   exact version to PostgreSQL.
10. Confirm a successful, empty, truncated, and database-error response are
   visually distinct and attached to the correct version.
11. Refresh the browser; the same session, current version, history, findings,
   results, and dataset-browser state must return.

## Required checks before pinning Catalyst

- Gateway unit/contract tests, including exact-query execution and PostgreSQL
  diagnostic redaction.
- UI typecheck, unit tests, and accessibility assertions.
- Playwright flow for invalid draft → edit → validate → run → refresh → rerun.
- Manual desktop, narrow-viewport, keyboard-only, and 200%-zoom verification of
  highlighting, line numbers, wrap behavior, completion, Format, and version
  history; record any mismatch with automated tests as an open inconsistency.
- Live real-path smoke using med-agent-hub and the configured local model.
- Harness metadata tests remain green even though W3 export is not yet exposed.
- `git diff --check` in both Catalyst and the umbrella harness.

Only after Catalyst checks pass should its submodule commit be pinned in the
umbrella harness branch.
