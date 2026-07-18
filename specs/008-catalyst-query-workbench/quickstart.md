# Quickstart: Query Workbench Development

## Isolated stack

Use the dedicated harness worktree and Catalyst submodule checkout. Do not run
this feature from the user's primary harness checkout.

The current isolated demo is composed with:

- compose file: `/private/tmp/catalyst-mvp-harness/isolated.compose.yml`
- environment: `/private/tmp/catalyst-mvp-harness/isolated.env`
- project: `catalyst-mvp-isolated`
- browser: `http://localhost:13000/`

## W1 verification sequence

1. Start or rebuild the isolated gateway and UI while retaining the existing
   Hub, model router, seeded analytics database, and SQLite volume.
2. Confirm health reports the selected Hub query profile and model roles.
3. Create a workbench session from a natural-language question.
4. Verify the generated SQL, typed parameters, model/profile provenance, and
   all findings are visible even when validation fails.
5. Change SQL and one parameter; Validate must create a new immutable version.
6. Run a warning/error-bearing version; Run must remain enabled and submit the
   exact version to PostgreSQL.
7. Confirm a successful, empty, truncated, and database-error response are
   visually distinct and attached to the correct version.
8. Refresh the browser; the same session, current version, history, findings,
   results, and dataset-browser state must return.

## Required checks before pinning Catalyst

- Gateway unit/contract tests, including exact-query execution and PostgreSQL
  diagnostic redaction.
- UI typecheck, unit tests, and accessibility assertions.
- Playwright flow for invalid draft → edit → validate → run → refresh → rerun.
- Live real-path smoke using med-agent-hub and the configured local model.
- Harness metadata tests remain green even though W3 export is not yet exposed.
- `git diff --check` in both Catalyst and the umbrella harness.

Only after Catalyst checks pass should its submodule commit be pinned in the
umbrella harness branch.
