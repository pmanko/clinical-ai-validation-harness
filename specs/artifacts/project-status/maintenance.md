# Keeping the project status current

This hub records the state of work and links to its evidence. The approved product roadmaps, feature requirements, and acceptance criteria retain their existing authority. Inventory identifiers are stable cross-references, not new milestones.

**Browse and update together.**

Use the dashboard overview for the current project summaries and restart list. Choose a project, search the inventory, and open an item for its next deliverable, acceptance limits, related work, and sources. The full report is readable inside the dashboard. Bookmark a filtered view or an open item to return to it directly.

To update it, edit its repository record from any editor or agent. The dashboard is a dated view of these files; it does not automatically poll GitHub or save edits in the browser. The overview copy and navigation groups live in `dashboard.json`. After an update, run `scripts/project-status.sh refresh`. This keeps one editable source and makes changes reviewable.

**Use each existing surface for one purpose.**

| Surface | What belongs there | What should link elsewhere |
|---|---|---|
| This repository status hub | Current efforts, next deliverable, dependencies, open decisions, evidence and publication links, date checked | Full product requirements and detailed run results |
| Existing roadmaps and feature plans | Scope, ordering, agreed behavior, completion conditions | Repeated pull-request status and changing deployment details |
| GitHub pull requests and checks | Actual code changes, review, source revisions, merge state | Product acceptance that was not demonstrated |
| Run artifacts and acceptance records | Exact revisions, dataset and model configuration, results, screenshots, interpretation, owner decision | Mutable portfolio status |
| openclinai.org | Brief public explanation of each product and a representative current demonstration | Internal task lists and historical benchmark claims presented as current acceptance |
| reports.openclinai.org | Curated links to dated reports and their case-level evidence, with the evaluation method and limitations visible | The current work backlog |
| GitHub Pages documentation | Public architecture, research background, diagrams and navigation | A second independently edited implementation roadmap |
| Coding-agent tasks and conversations | Working conversation, investigation and implementation context | The only surviving copy of a result, decision, branch or acceptance record |

**Update at meaningful events.**

At the end of a substantial working session, update the relevant effort's current state, next deliverable, source revision, evidence link and date. After a merge, refresh the GitHub snapshot and pin references. After a deployment, record the actual deployed revision and configuration. After a validation run, link its durable artifacts and separate source tests from browser proof. After owner review, record the explicit acceptance or remaining findings with its source.

A new work session starts by reading this hub, then the named product authority and relevant current effort. Run `scripts/project-status.sh github` when pull-request facts may have changed, reconcile the recorded snapshot, then run `scripts/project-status.sh refresh`. A session ends by leaving a concrete next action and links in the inventory; its title and identifier remain useful supporting references.

There is no scheduled automation in this change. A short weekly reconciliation is a suggested habit: compare open work against GitHub, inspect stale evidence dates, and identify public pages whose status no longer matches the accepted deployment. More frequent automatic polling can be added only if it provides useful changes to review.

**Keep states separate.**

For each effort, distinguish implemented code, automated source validation, real product-path evidence, review/merge status, and owner acceptance. Do not collapse these into one percentage complete. A successful demonstration can exist on an unmerged branch; a green main branch can still precede that demonstration. Unknown or unverified is a valid recorded state.

Each active effort should point to one next deliverable and one actual acceptance record or explicit remaining acceptance condition. Record an implementation owner only when assigned; an unassigned owner is preferable to an invented commitment. Closed or superseded work remains searchable with its replacement link and rationale.

**Edit and regenerate the tables.**

The JSON files beside this guide are the editable inventory. The Markdown tables and CSV exports are generated views. Change the relevant JSON row, then run from the repository root:

```bash
scripts/project-status.sh refresh
```

`refresh` regenerates the tables, verifies they match their inputs, and runs the dashboard model test and production build. Its GitHub collection command is separate and explicit; the renderer performs no network requests, publication, Git changes, or model calls.

Local Markdown links target files in the repository's committed tree. Runtime
artifacts, uncommitted files and external machine paths remain readable references,
even if they exist on the machine running the renderer. Use an explicit published
HTTP(S) URL when evidence should be accessible outside the checkout. Paths are
repository-relative except the status hub's own views and `reports/`, `reviews/`,
`evidence/`, `exports/`, `./` and `../` references, which are relative to this
directory. A `:123` line suffix becomes `#L123`. After committing a new local target,
regenerate the views to make its link available.

`pull-requests.json` is a dated GitHub snapshot. Refresh it from GitHub rather than manually marking a pull request merged. Preserve scope and retrieval date. Review-thread counts describe GitHub markers, not verified defects. Public-surface checks establish HTTP availability only, not functional acceptance.

**Use the existing publication paths.**

For report publication, use the family-aware staging/publishing flow in `scripts/publish-report.sh` and its curated `reports-index.json`. For the main landing page, use `scripts/publish-landing.sh`. The public documentation site is built from the selected README/canvas/research surface and deploys from main. Its GitHub Pages build also publishes the status dashboard at `/status/`. These flows remain separate; none is invoked by the status renderer.

Before the next publication, reconcile the three deployed Catalyst report entries missing from main's report manifest, correct the two Catalyst entries carrying the default ChartSearchAI family, and make the older comparison's method/date clear. Preserve historical evidence and describe why it no longer represents the current Spark comparison. Publish only the reviewed public summary, not this internal inventory by default.

**Suggested next improvement after this hub is reviewed.**

Add a small curated “Current work” link to openclinai.org and the public documentation navigation, pointing to an approved summary derived from the effort inventory. Continue to use the existing reports index for evidence. A full new project-management application, duplicated roadmap, or automatic scoring system is unnecessary for the current coordination problem.
