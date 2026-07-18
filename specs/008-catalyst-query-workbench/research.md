# Research: Catalyst Query Workbench

## Progressive disclosure for dataset context

Use a compact, always-visible dataset identity/scale summary followed by one
Carbon accordion item containing the filterable record browser. Remove the
duplicate static distribution table and example-question list. The detail region
starts collapsed, retains state while hidden, and uses native accordion
keyboard/focus semantics.

Carbon recommends accordions for progressive disclosure and notes that important
content should not be hidden. The WAI-ARIA pattern defines the expected button,
expanded state, controlled panel, and keyboard behavior. A permanent side drawer
would reduce editor width; nested accordions would add navigation overhead.

Sources: [Carbon accordion usage](https://carbondesignsystem.com/components/accordion/usage/),
[WAI-ARIA accordion pattern](https://www.w3.org/WAI/ARIA/apg/patterns/accordion/).

## Input-first composer and direct access

Use one canonical, visibly labelled question text area with a compact attached
toolbar for the labelled profile selector and explicit submit action. Do not use
an example-question placeholder. While the composer is outside the viewport,
expose a small jump control inside the existing sticky status banner; activation
scrolls to and focuses the actual text area. Hide it while the composer is
visible, retain it while keyboard-focused, and wrap it with the banner at narrow
widths. This preserves state and logical DOM order without a duplicate editor or
a second fixed layer that can cover table controls.

The short design-system and accessibility review, implementation recommendation,
and manual validation checklist are recorded in
[`ux-composer-research.md`](ux-composer-research.md).

## PostgreSQL-aware expert editor in the first slice

Use a reviewed code-editor integration rather than a plain text area because the
required interaction includes PostgreSQL syntax highlighting, logical line
numbers, keyboard completion, and wrap control. Default wrapping to on for the
narrow workbench, retain the toggle as session presentation state, and source
completion from a stable PostgreSQL keyword set plus the active approved catalog.
Sort suggestions deterministically and remain fully editable if catalog loading
fails; the UI must not carry a second schema mapping.

Keep deterministic formatting separate from model behavior and version it as an
accepted implementation input. Formatting updates only the working buffer,
returns a useful no-change failure when semantic preservation cannot be proven,
and must produce byte-identical output for the same SQL and formatter revision.
Validate or Run persists that exact buffer as a new immutable child before the
operation; keystrokes, completion, wrapping, and Format never rewrite an earlier
version.

The selected implementation is direct CodeMirror 6 with the official
`@codemirror/lang-sql` PostgreSQL dialect and `sql-formatter`. CodeMirror's
`basicSetup` supplies line numbers and completion, `SQLConfig.schema` accepts the
gateway catalog as a nested schema/view/column namespace, and
`EditorView.lineWrapping` provides wrapping without a second text buffer. A
small React lifecycle adapter avoids another wrapper dependency. Format is a
manual `formatDialect` action configured for PostgreSQL and Catalyst's `:name`
parameters. The dependency graph remains pinned by `package-lock.json`.

Expose completion identifiers through a small read-only workbench catalog route
derived from the gateway's already-loaded approved catalog. This keeps the Hub
prompt, deterministic validator, and editor on one vocabulary; when the route is
unavailable, CodeMirror retains PostgreSQL dialect completion and ordinary
editing without inventing identifiers.

Monaco was rejected for this focused browser workbench because its schema
completion and formatting require custom providers, Vite requires worker
configuration, and its official README does not support mobile browsers. The
CodeMirror choice must still pass keyboard, accessible naming, 200%-zoom,
narrow-layout, and build review.

Sources: [CodeMirror reference](https://codemirror.net/docs/ref/),
[CodeMirror SQL API](https://github.com/codemirror/lang-sql#api-reference),
[sql-formatter dialect API](https://github.com/sql-formatter-org/sql-formatter/blob/master/docs/dialect.md),
[sql-formatter parameter configuration](https://github.com/sql-formatter-org/sql-formatter/blob/master/docs/paramTypes.md),
[Monaco FAQ](https://github.com/microsoft/monaco-editor#faq).

A plain Carbon text area was rejected because it cannot natively satisfy the
highlighting, line-number, and completion requirements. A model-driven formatter
was rejected because it is neither deterministic nor limited to presentation.

## Recurring missing `name` contract failure

The failure is now localized. For “how many patients had viral load tests above
1000 count/ml?”, Gemma E4B failed query-generation attempts 2–3 at
`parameters.1: 'name' is required` at 02:56 UTC; Gemma 4 12B failed attempts
1–3 at the same path at 02:58 UTC. It is not a profile-name or review-stage
field. The executor requires each generated parameter name to bind a SQL
`:placeholder`. The owning defect is the shared Hub normalizer: it handles
catalog-grounded analytes, question dates, and turnaround thresholds, but not a
sole remaining question-grounded unnamed parameter and sole remaining SQL
placeholder.

The E4B evidence is session `2bed91de-fa7d-4ffa-b4ae-0a454a883930`, trace
`07740499-387c-40b4-97c3-2bf7c4e08b7e`. The workbench preserved editable
version `d801dc1d-fc94-435b-bee6-2b45c3173af1` from schema-valid attempt 1,
including SQL literals and an advisory unbound-literal finding. Draft retention
is therefore proven. At this historical pre-fix checkpoint, raw malformed retry
retention was not yet proven because Hub diagnostics used a candidate-or-
`rawOutput` branch. G2.2 subsequently changed the diagnostic to preserve both;
post-G2.3 E4B session `11c585d8-c8ab-4fa6-a421-d6435b81845d` visibly retains
the best candidate and latest raw patch together after budget exhaustion.

Only a sole remaining parameter with a supported type, `source: question`, and
a value grounded in the question may receive the sole remaining placeholder
name. This joins two already-generated artifacts; it does not invent SQL, type,
value, or ordering. Zero, multiple, or ungrounded matches remain visible invalid
findings. The workbench must preserve both the latest raw failed response and the
best parsed draft/parameters, together with all per-attempt schema findings,
response-schema revision, profile/model roles, prompt/config digests, router
identity, seed, and timestamps. Write regressions at both the Hub normalization
and diagnostic-retention boundaries before either fix.

Supplying a fabricated `name`, dropping the candidate, or handling it only in
the UI would hide the defect and corrupt cross-model comparison. Cross-profile
agreement at the same object path is evidence of a shared contract/normalization
problem, while the different failed-attempt ranges remain variance to capture.

The same case exposed a separate semantic gap: the question uses `count/ml`, but
the connected catalog and records use `copies/ml`. This should become a catalog-
grounded advisory unit finding in a later validation iteration, not a silent
rewrite and not an editor gate.

## Post-G2.3 comparative observation

The same prompt now demonstrates the intended difference between deterministic
correction integrity and model quality. E4B session
`11c585d8-c8ab-4fa6-a421-d6435b81845d` retained earlier patch work and produced
executable SQL; immutable execution returned `count=0` in 7 ms because the model
kept the question-grounded `count/mL` value rather than the catalog's
`copies/ml`. Its final threshold binding was also typed as string. Those are
model/semantic-quality findings, not retry-integrity failures.

Gemma 4 12B session `902bd844-e8f1-403d-90ee-8fccd9417f99` omitted multiple
parameter names in every full candidate. Multiple unresolved bindings are not a
safe 1:1 repair, so the Hub retained raw output and exact paths without guessing.
The picker and provenance both restored to 12B after refresh. Logs identify the
physical calls as `gemma-e4b` and `gemma-4-12b`, respectively.

The comparison also shows that Hub candidate validation and gateway workbench
validation are complementary, not interchangeable: the E4B draft retained a
Hub `expectedColumns` finding while its SQL/parameters passed gateway validation
and executed. Experiment metadata must retain both until their scopes are
explicitly aligned.

## Generator-facing optional names, strict final bindings

The 12B raw response demonstrates that requiring every model parameter to name
itself can reject before the more meaningful SQL/catalog checks run. Relax the
structured schema only at the initial model boundary: `type` and `value` remain
required, while `name` and `source` are optional. Before candidate validation,
the Hub may assign the ordered SQL placeholder at the same array position and
`source: question`. If parameter and placeholder counts differ, it keeps the
draft unresolved for manual editing. The final contract, review input, gateway
version, and executor remain fully named.

This is deterministic canonicalization, not model repair. It avoids spending an
inference retry on redundant binding metadata and allows lint to focus retries
on material SQL/catalog defects. Named output remains preferred—especially for
longer queries. Database execution remains evidence of operational validity,
not proof that the result semantically answers the question.

## Complete writer–reviewer collaboration for the MVP

The post-binding 12B run shows that finding-scoped generator patches are the
wrong internal collaboration unit. Deterministic lint correctly identified a
missing aggregate alias, but the same writer model produced two patches anchored
to SQL that was not the retained candidate. The nominal reviewer never ran
because `_generate` owned the entire retry budget, and the profile assigned the
same Gemma model to both roles.

Use one complete candidate at each model boundary. Gemma 4 12B writes once;
deterministic lint emits structured findings; Qwen 2.5 14B receives the complete
writer query plus those findings and returns one complete corrected candidate.
The Hub applies strict candidate validation and deterministic re-lint. This makes
the two model roles genuinely collaborative while keeping accepted execution
behavior reproducible. Model diversity reduces correlated failure modes but is
not treated as proof of correctness.

Preserve the writer and reviewer candidates as linked immutable workbench
versions (`model` then `model_repair`) and expose the collaboration trace. The
reviewer's full replacement is acceptable inside this internal generation flow
because neither model version is hidden and deterministic lint checks the final
candidate. This does not change the later user-initiated W2 repair contract,
which remains explicitly scoped and acceptance-based.

## Advisory workbench versus governed previews

Keep `/v1/catalyst/queries` and preview execution unchanged for policy-gated
callers. Add workbench endpoints whose Run operation submits the exact displayed
SQL and typed values to the existing PostgreSQL adapter. Validator findings are
captured with the execution but never used as an application-level gate.

The database transaction remains read-only and uses the configured database
role. Statement timeout and fetch bounds remain operational controls. The
adapter does not add or change a `LIMIT` clause. Separate APIs keep the research
workflow frictionless without weakening existing governed behavior.

## Repair AST units, not whole responses or raw token spans

Parse PostgreSQL with SQLGlot and represent editable units by stable AST path,
unit kind, normalized SQL, source span when available, and digest. A repair scope
contains editable units plus digests for frozen units. Simple identifier,
operator, literal, and binding substitutions use deterministic code. Contextual
repairs call med-agent-hub with a typed patch contract and reject full-query
replacements, stale source digests, or changes outside the scope.

After patch application, rebuild the full SQL and rerun every deterministic
check. If SQL cannot be parsed, direct manual editing and execution remain
available; automated repair may use only a parser-localized raw span and cannot
claim frozen-AST integrity.

Interactive text-to-SQL research uses clause-level decomposition and finds many
simple edits can be deterministic. Error-correction work reports that clause-
level edits outperform token-level edits. This also applies the Hub's DRY lesson:
one canonical lint result feeds the UI, repair scope, retry feedback, trace, and
harness event instead of each layer reinterpreting prose.

Sources: [Interactive Text-to-SQL with Editable Explanations](https://arxiv.org/abs/2305.07372),
[Text-to-SQL Error Correction with Language Models](https://aclanthology.org/2023.acl-short.117/).

## Gateway persistence for operating metadata

Extend the existing WAL-backed SQLite store with workbench sessions, immutable
versions, validation runs, repair proposals, execution attempts, and ordered
events. The browser keeps only the active session ID and restores from the
gateway. Mutations include parent version/digest for optimistic concurrency;
stale tabs receive a conflict rather than overwriting history.

Browser-only storage cannot provide authoritative lineage or later harness
export. PostgreSQL is reserved for clinical analytics data, so SQLite remains
the correct operating-metadata boundary.

## Stage harness export after the manual loop

The first slice records all fields needed by the existing harness `RunManifest`,
Catalyst scenario runner, and event stream. A later endpoint materializes
`run_manifest.json` and `events.jsonl`, and the harness validates or imports the
bundle. Format alignment is straightforward; deployment-specific handoff should
not block editable queries, database errors, or persistence.
