# Quickstart: Query Workbench Development

## Isolated stack

Use the dedicated harness worktree and Catalyst submodule checkout. Do not run
this feature from the user's primary harness checkout.

From an isolated harness worktree, initialize the two pinned sibling targets:

```bash
git submodule update --init targets/catalyst targets/med-agent-hub
make catalyst-mvp-fake
```

The tracked umbrella runner uses
`compose/catalyst-mvp-isolated.override.yml`, project
`catalyst-mvp-isolated`, Gateway `http://127.0.0.1:18000`, and browser
`http://localhost:13000/`. For real local models, configure the external
OpenAI-compatible router in `targets/catalyst/.env` and run
`make catalyst-mvp-external`.

Current query ownership is Catalyst Gateway → Hub generic role executor → model
router. Before relying on a stack, verify:

```bash
test -f targets/catalyst/catalyst-gateway/src/catalyst/query_profiles.py
test -f targets/catalyst/catalyst-gateway/src/catalyst/query_engine.py
test -f targets/med-agent-hub/server/generic_role.py
rg -n 'POST /v1/hub/generate|/v1/hub/generate' \
  targets/catalyst/catalyst-gateway/src/catalyst \
  targets/med-agent-hub/server
```

Gateway owns the query profile IDs, prompts, writer/reviewer flow, and required
model aliases. Catalyst does not use the Hub profile objects in
`GET /v1/models` `data[]` as query-profile discovery; those remain Hub's own
clinical-answer/report profiles. `LocalHub` does consume that response's
versioned top-level `backend` inventory to determine whether every exact model
alias required by a Gateway profile is currently advertised. A missing,
malformed, or unreachable inventory makes affected profiles unavailable without
substitution. Historical G2.8 steps below refer to the earlier Hub-owned query
engine and are retained only to explain the evidence produced then.

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
2. Confirm health reports the selected Gateway query profile and role models
   while independently confirming the generic Hub executor/model-router path is
   ready.
3. Create a workbench session from a natural-language question.
4. Verify the generated SQL, typed parameters, model/profile provenance, and
   all findings are visible even when validation fails.
   If only one parseable raw JSON object survived, verify it appears as an
   unresolved editor buffer with blank missing names while the raw output stays
   separately visible; refresh must restore that buffer without another model
   call.
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

Only after Catalyst and sibling-Hub checks pass should their commits be pinned
in the umbrella harness branch.

## G2.8b pre-UI backend checkpoint

Do not implement the notebook UI until this checkpoint passes.

1. Confirm the Hub registry publishes an offline-resolvable bundle containing
   query request v1/v2, revision context, editor snapshot, turn request, and all
   transitive references; confirm the gateway registry publishes the request,
   snapshot, snapshot-record, turn, timeline, and generation-evidence workbench
   schemas.
2. Create successful and failed new sessions. Each must persist an initial
   `query_turn.requested` plus exactly one terminal event with
   `origin: recorded`, and
   `GET /sessions/{sessionId}/turns/{turnId}/generation-evidence` must return the
   typed evidence without result rows, credentials, or reasoning. It must have
   an empty omissions list and one timing/digest entry for every successful or
   failed writer/reviewer invocation.
3. Load deterministic pre-event fixtures for model-current, later-human-current,
   draft-only, and raw-only sessions. Repeated timeline/evidence GETs must return
   stable synthesized legacy IDs and references, make no model call or write,
   select only attributable initial model output, and restore the actual later
   human current pointer independently. The terminal time must come from the
   selected initial output, otherwise raw/generation outcome, otherwise session
   creation. Any unavailable prompt/model/config/timing/digest field must remain
   null with a typed omission; the projection must invent no provenance.
4. Exercise the same unchanged and dirty buffers through follow-up, Validate,
   and Run. The shared resolver must reuse one unchanged version, promote one
   dirty human version, make that version current, and record the correct active
   turn ID for every path.
5. Verify exact-digest execution context for `failed`, `timed_out`, and
   `cancelled` attempts includes only bounded sanitized diagnostics and never
   rows. Dirty, unresolved, or mismatched snapshots receive no execution
   context.
6. Pass Hub, store/gateway, root sibling-runtime, schema registry, contract,
   lint, and diff checks. Assert that recorded initial/follow-up turn, snapshot,
   and generation-evidence events map into the current versioned
   `events.jsonl` envelope without implementing W3 export. Record any drift and
   stop before UI work.

## G2.8c iterative-notebook live checkpoint

Run this sequence only after the G2.8 turn/context contracts and deterministic
tests pass. Use the isolated real stack, not the fake router, and pause for user
acceptance after recording the evidence.

### Required scenario matrix

Use connected catalog terms and dates discovered at runtime; record the exact
phrasing rather than hard-coding an assumed cohort.

1. **Narrowing:** begin with recent laboratory observations, manually edit and
   run the base, then refine it to one catalog-backed test/date/status subset.
   Inspect included and excluded record IDs to prove the predicate, not merely a
   lower count.
2. **Aggregation/output-shape change:** refine a row-producing query into a
   grouped or distinct-patient aggregate. Verify every grouping key and value
   with independent PostgreSQL SQL and record samples from the contributing
   groups.
3. **Unresolved correction:** submit a representable editor snapshot with an
   unresolved binding. Prove the snapshot is not promoted to a QueryVersion,
   Hub receives it as correction context, and only the selected complete output
   becomes current.
4. **Lint-clean semantic reviewer correction:** capture a structurally clean
   writer candidate that still answers the wrong row/aggregation/latest-record
   meaning. Prove Qwen is invoked despite the empty finding set, returns a
   complete semantic correction, deterministic re-lint remains clean, and the
   reviewer child—not the writer—is selected. Do not substitute a structural
   lint failure for this case.
5. **Hub/tool failure:** induce one bounded router/tool failure through the real
   Hub path, then restore the dependency. Prove one failed terminal turn retains
   bounded raw evidence and no output is selected. The base/current anchor stays
   current: effective when non-null, otherwise observed when present, otherwise
   null. If the writer was contract-valid before reviewer failure, it remains an
   immutable but unselected output; invalid/parseable candidates remain
   diagnostics. The next follow-up succeeds without importing failure payloads.

### Execution sequence and evidence

1. Confirm Gateway profile discovery reports the selected Gemma 4 12B writer
   and Qwen 2.5 14B reviewer, including profile/prompt/configuration digests.
   Confirm each role reaches sibling `targets/med-agent-hub` only through the
   generic executor and that no disposable patched clone is used.
2. Confirm the new session's initial recorded events and retrieve typed
   generation evidence for the initial and follow-up turns. For each scenario,
   record dataset ID/version, catalog version, session and turn IDs, observed CAS
   base, reconciled effective base/current anchor, exact editor/context/request/
   evidence digests, profile, writer/reviewer candidates and models, every output
   disposition, every invocation's identity/timing/request/response-or-failure
   digests, selected query-version ID/digest, validation IDs, and execution ID.
   Preserve exact SQL and typed parameters. Confirm compact timeline rows expose
   only prompt references/digests while evidence detail retains the full prompts.
3. Exercise unchanged, dirty contract-valid, and unresolved editor bases. An
   unchanged Validate/Run/follow-up reuses its version; a dirty buffer creates
   exactly one current human effective base before inference; an unresolved
   buffer remains only snapshot evidence with no effective version.
4. Inspect the revision request. It contains the initial question and no more
   than five preceding follow-ups in chronological order plus only exact-digest
   validation/execution summaries. Confirm absence of result rows, credentials,
   connection details, hidden reasoning, raw traces, historical SQL copies,
   full chat replay, and unrelated-session content.
5. Prove selected-output integrity: reviewer approval selects the writer; a
   reviewer correction selects its immutable child; a failed turn selects
   nothing. Reviewer failure leaves any contract-valid writer immutable but
   unselected and keeps the base/current anchor current—the effective base when
   non-null, otherwise the observed version when present, otherwise null.
   Invalid candidates never become versions. The session pointer always agrees
   and execution is never automatic.
6. Independently run reproducible PostgreSQL checks for each successful data
   claim. Record the check SQL/parameters, inspected patient/observation IDs,
   relevant values/units/timestamps/group membership, and a short rationale for
   why those records establish the intended narrowing or shape change. Counts
   alone are insufficient.
7. Label prior output `Results from Query vN` and confirm it becomes stale after
   an edit or successor without being hidden or reassigned. Switch to another
   available profile for one turn and prove its exact models/config remain local
   to that turn.
8. Submit stale lineage from a second tab and confirm
   `409 stale_query_version` with no event/model call. Submit two follow-ups
   concurrently against the same observed base and confirm exactly one atomic
   claim; the active-generation conflict takes precedence if the winner created
   a dirty-valid human effective base. Restart with one requested turn
   deliberately orphaned and confirm one terminal failure with stage
   `orphan_recovery` and code `generation_interrupted`, no automatic retry, a
   released claim, and the base/current anchor still current.
9. Refresh after completed and failed turns. Restore timeline, current saved
   editor, selected profile, validation/results and staleness. Clear Draft offers
   `Restore Query vN`; New Session excludes every prior instruction, SQL,
   finding, execution, and model-context reference.
10. Repeat the same snapshot/instruction in isolated fresh sessions with
    temperature zero and the DRY repetition penalty disabled. Retain every
    candidate and query digest. Report differing digests only if outputs actually
    differ; neither equality nor divergence is required, and seed/sampling
    configuration is never reproducibility proof.
11. Start timing at initial-question submission and stop when the successor
    query becomes visible. The primary adjusted duration is wall time minus all
    exact recorded `durationMs` values for every initial and follow-up writer/
    reviewer invocation and must be under 180 seconds. For each subtraction,
    reconcile `startedAt`/`endedAt`, role, stage, attempt, provider/model,
    request digest, outcome, and response-or-failure digest from typed evidence.
    Report unadjusted wall time and each invocation duration; time the later
    explicit Run/database operation separately as a secondary measure. Do not
    substitute follow-up-only or generation-to-result timing.
12. Complete the interaction with keyboard only, then at a narrow viewport and
    at 200% zoom. Verify timeline disclosure, profile picker, SQL completion,
    wrap/Format, Generate next query, Restore, Validate/Run, result access, New
    Session, and sticky-jump focus; record any focus obstruction, overflow, or
    mismatch with automated tests.

The 2026-08-03 evidence in runs `0671dc34` (12/12 matrix) and `fb6377c1`
(one-shot failure plus same-session recovery) is accepted. The PHI-safe receipt
is `evidence/t111-final-acceptance-2026-08-03.json`. On 2026-08-04 the user
confirmed actual keyboard traversal and actual browser 200% zoom passed and
accepted T094/T095/T111. The deterministic Playwright notebook test now guards
unobscured Tab focus and the corresponding 200%-equivalent reflow boundary.

The root `README.md`, Catalyst user docs, roadmap, quickstart, and PCCP evidence
are updated after acceptance. Hub is already merged; Catalyst squash and the
post-merge health/provenance and real-model/PostgreSQL/gold verification pass;
Harness PR #37 approval, repin, verification, and squash completed T112.

## G2.10 multi-source/lossless checkpoint

Implementation plumbing is not acceptance evidence. Before closing G2.10:

1. Inventory every registered source and prove an absent catalog yields
   `available: false` and rejection before any model or database call.
2. Pin or record each base ViewDefinition's upstream provenance. Use a
   multi-coding/repeated-element fixture to prove the raw projection retains the
   full `forEachOrNull` multiplicity before SQL curation.
3. Reapply curated SQL from a clean baseline, verify every approved view/column
   comment, then run `scripts/generate-catalyst-source-catalog.py` twice and
   compare bytes. Also prove missing comments and a zero-match canonical overlay
   value fail generation.
4. Compare each generated catalog with live information schema and confirm the
   schema guide, completion, validator, model request, versions, and executions
   carry the same `dataSourceId` and catalog version.
5. In one new session, execute A → B → inherited B → A. Exercise first-use
   baselines, a real per-source stale-catalog conflict, refresh, and an
   unavailable source. Independently verify every successful query in the
   corresponding PostgreSQL database with record-level evidence.
6. Confirm readiness documents and reports only the default source. Record the
   G2.10b evidence and pause at G2.10c for explicit user acceptance.

## D1 Superset-backed Dashboard Builder checkpoint

This is the selected next product checkpoint. It requires only the accepted
query/version/execution/table foundation; G2.10, W2, W3/CVR, R4, and R5 remain
parallel. Commands below are the implementation contract for T137–T182; until
those tasks are checked, an absent command is an expected open item rather than
evidence that the runtime exists.

### Planned operator commands and endpoints

```bash
# boot the full isolated Catalyst + Superset stack
scripts/catalyst-mvp.sh up

# inspect/import the exact current outbox bundle without a background watcher
scripts/catalyst-mvp.sh superset-status
scripts/catalyst-mvp.sh superset-import

# explicit local-only recovery after a post-import verification failure;
# validates the per-Dashboard last-verified projection, fully resets only the
# Superset-local metadata database/home volumes, and reimports that exact bundle
scripts/catalyst-mvp.sh superset-reset --reimport-last-verified
```

The harness routes these commands to the dedicated target-side operator
boundary `targets/catalyst/scripts/mvp-superset.sh {status|import|reset}`;
`mvp-up.sh` remains the stack lifecycle helper, not a second import dispatcher.
The importer/state programs are standalone Python-3.10-compatible scripts under
`targets/catalyst/scripts/`; they import no Catalyst package and rely only on
the standard library plus dependencies already built into the pinned Superset
image. Their tests remain in the Gateway CI suite.

- Catalyst UI: `http://localhost:13000`
- Catalyst Gateway: `http://localhost:18000`
- Superset: `http://localhost:18088`
- Superset health: `http://localhost:18088/health`
- Catalyst-owned runtime state:
  `targets/catalyst/runtime/superset/{outbox,receipts,backups}/`, covered by
  `/runtime/superset/` in `targets/catalyst/.gitignore`
- D1 evidence: `artifacts/catalyst-dashboard/<run-id>/` containing
  `run_manifest.json`, `events.jsonl`, `acceptance.json`, exact bundle/pointer/
  receipt copies, PostgreSQL reconciliation, and screenshots/video

### Acceptance flow

1. Boot Catalyst, digest-pinned Superset 6.1.0, and its metadata database with
   the isolated-stack command. Require Catalyst health plus `GET /health` = 200
   on localhost port 18088. Record the Superset application/platform digest and
   PostgreSQL driver revision. Superset reads the outbox through a read-only
   mount; the importer alone receives a writable receipt/lock mount. Stack
   configuration proves the driver/network path and DB-enforced SELECT-only
   access. The canonical native fixture—not `superset_config.py` or
   `superset set-database-uri`—creates the persisted analytics Database asset.
2. In Ask, select a profile with its writer/reviewer models, generate Query v1,
   use the sole SQL editor's completion/Format/manual version flow, Validate,
   explicitly Run, and inspect findings/raw failure or database diagnostics and
   typed results. Confirm the Dataset tile/panel exposes the exact Query v1,
   complete accepted table wire types, parameters, bounded rows, warning codes
   plus display prose, truncation truth, and provenance. There must be no
   duplicate editor, example-prompt buttons, automatic execution, or missing
   prior action/evidence.
3. While Query v1 and its editor digest are still current, save **Dataset v1**.
   Then ask a contextual follow-up from that exact visible buffer, review the
   complete successor Query v2, explicitly rerun it, and save **Dataset v2**
   while Query v2 is current. Only after both saves, refresh and confirm the
   timeline, stale-result labels, libraries, and New session behavior. A stale
   unsaved execution remains inspectable but is not promotable.
4. Review or override deterministic Widget suggestions for the two saved
   Dataset versions and create two heterogeneous Widgets. Place them on a newly
   named Dashboard only when both share its locked `dataSourceId` and
   `catalogVersion`; either mismatch must be rejected. After a catalog refresh,
   create a new Dashboard rather than mixing catalog versions.
5. Select **Publish to Superset**. Catalyst atomically writes a native Superset
   ZIP to the host-visible outbox and offers the same artifact for download.
   Bundle creation makes no model call and does not rerun the query.
6. For a clean stack, let the bootstrap importer load the eligible selected
   current desired bundle. For an already-running stack, run the documented Superset import
   helper. Only a successful CLI result plus exact post-import verification and
   a validated receipt/latest projection changes `Bundle ready` to `Imported`;
   generating the file alone never claims synchronization. Missing, malformed,
   wrong-version, or foreign-digest pointers/receipts never claim Imported;
   pointer/bundle/preflight/credential failures and a transactionally rolled-
   back Superset CLI failure leave the previously verified Dashboard usable. If the CLI
   succeeds but UUID/slug/relationship verification fails, report
   **Import failed**, retain the diagnostic, and disable Open Superset and any
   current-success claim. Do not claim an automatic rollback. Recovery first
   validates `receipts/last-verified/<logicalDashboardId>.json` and its
   referenced bundle; missing/corrupt projection data stops before reset. Then
   explicitly reset the complete Superset-local metadata database/home volumes
   and reimport/verify that bundle. Do not selectively delete assets or mutate
   Superset through ORM or REST. If verified A is recovered while failed desired
   B remains in `current.json`, B stays `import_failed` and automatic bootstrap/
   retry is suppressed until explicit retry or a new publication.
7. Open
   `/superset/dashboard/catalyst-<lowercase-dashboard-id>/` in Superset,
   require the observed UUID and slug to match the bundle/receipt, require at
   least two Widgets to
   render, and independently reconcile keyed identifiers/values with the exact
   PostgreSQL verification SQL. Publish a changed child and a layout-only
   version: changed children receive new version-addressed UUIDs, unchanged
   children are reused, and the logical Catalyst Dashboard ID, slug, and
   Superset Dashboard UUID remain stable.
8. Refresh Catalyst and prove immutable Dataset/Widget/Dashboard versions,
   import evidence, and stale-source states restore. Repeat with keyboard only,
   desktop, 390×844, 320 CSS px, and actual 200% browser zoom. Capture Escape/
   focus return, focus containment, status announcements, reduced motion, and
   unobscured fixed-composer/editor evidence.
9. Run the all-five-family canonical Superset fixture matrix, same-digest no-op,
   concurrent import, ordinary restart, the scoped preserving-failure matrix,
   a post-verification failure with no Open/current-success claim, missing/
   corrupt recovery-projection refusal, full Superset-local reset plus per-
   Dashboard last-verified reimport, recovered-A/failed-desired-B retry
   suppression, and database write-denial checks. Also prove the standalone
   Python 3.10 importer inside the pinned Superset container, constrained
   canonical-JSON parity with `rfc8785`, and a clean Catalyst target after
   publication. Record actual start/end time from the eligible execution to Bundle
   ready and require under 180 seconds with zero model/database calls after
   execution.

The bundle contains configuration and provenance, not result rows. Named
parameters are compiled from exact typed execution values; the original
parameterized SQL remains in the Catalyst manifest. `resultDigest` hashes the
canonical RFC 8785 bounded execution object; its row-free `executionBounds` and
manifest `resultBounds` projections are byte-identical, and only stable ordered
warning codes enter the digest. Only the labelled local
demo may carry a read-only demo credential. Superset API publication, embedded
viewing, cross-system undo/reconciliation, narratives, sharing, scheduling,
automatic refresh, and production authorization/deployment are not claimed.

### D1 completion receipt

D1 is not complete from a generated ZIP, passing unit tests, or a Superset health
check alone. Before this flow starts, positive and negative tests must validate
the D1 event emitter and
`harness.catalyst-dashboard.acceptance.v1` schema. `acceptance.json` must resolve
the exact component and image SHAs,
real writer/reviewer profile and candidate digests, session/turn/query/execution/
Dataset/Widget/Dashboard IDs, bundle/current/receipt/per-Dashboard-last-verified
digests, stable Superset
UUID/slug/URL,
reproducible PostgreSQL SQL plus inspected record identifiers/values, reviewer
rationale, failure-recovery evidence, accessibility artifacts, and the matching
versioned harness manifest/events. `events.jsonl` must include structured
`query_turn`, `query_version`, and `query_execution` D1 projections plus immutable
Dataset/Widget/Dashboard versions, bundle publication, import/status,
scoped failure classification, explicit full-reset/reimport recovery, PostgreSQL
reconciliation, accessibility observation, and acceptance-decision events with
materialized traversal-safe evidence references. `acceptance.json` must also
carry the fixed six-step `orderedWorkflow` from initial Query selection through
Dataset v2 save. The final
checkpoint is explicit user acceptance of that deployed dashboard.
