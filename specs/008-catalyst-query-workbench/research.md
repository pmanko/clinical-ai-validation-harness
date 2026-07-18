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

## Full expert editor in the first slice

Use existing Carbon controls: a monospace SQL text area and structured parameter
rows for name, logical type, and value. Create a new immutable version on
Validate or Run rather than autosaving each keystroke. Guided fixes alone cannot
express arbitrary corrections, while a new Monaco/CodeMirror dependency adds
packaging and accessibility work without changing the experiment contract.

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
