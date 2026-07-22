# Reports-stack audit + one-frontend consolidation roadmap

2026-07-22. Prompted by the question "why do we have two user-facing frontend
stacks?" while making Catalyst first-class on the openclinai.org homepage.
Audit performed against this worktree; file references are current as of the
`codex/catalyst-mvp-umbrella` branch.

> **CORRECTION (2026-07-22, same day).** The original audit below understated
> the fragmentation: it assumed the `site/` React SPA is what serves
> `openclinai.org`. It is not. Verified: `openclinai.org` (apex) resolves to
> the GCP VM, whose Caddy serves a **fourth surface** — `landing/`, a
> hand-written static HTML homepage whose source lives only on the
> `codex/m2-openmrs-relay-reconciliation` branch (never merged to `main`),
> deployed by rsyncing a *working tree* to the VM (`make cloud-sync`; the VM
> copy is not a git checkout). The Pages-deployed `site/` SPA has **no custom
> domain** (`gh api .../pages` → `cname: null`) and is published only at
> `pmanko.github.io/clinical-ai-validation-harness/`. Consequences: (a) four
> frontend surfaces and four design systems, not three; (b) the homepage's
> source of truth is an unmerged feature branch plus VM disk state; (c) an
> audit from any single branch cannot see the whole public surface — this
> correction exists because exactly that blind spot caused a wrong "merging
> the PR deploys the homepage" claim. The consolidation end-state below gains
> a step: fold `landing/` into the one frontend (or make the Pages site the
> apex via a custom domain + DNS change, which additionally breaks
> `openclinai.org/openmrs/*` legacy paths — `openmrs.openclinai.org` is the
> canonical demo URL and is unaffected).

## What exists today (and why it smells)

Two harness-repo frontends, three design systems (see the correction above:
plus `landing/` on the m2 branch, the count is four and four):

1. **The `site/` React/Vite SPA** — auto-deployed to GitHub Pages on every
   push to `main` (`.github/workflows/pages.yml`), published at
   `pmanko.github.io/clinical-ai-validation-harness/` (no custom domain).
   Design system #1: `site/styles.css`.
2. **reports.openclinai.org** — Python-generated static HTML
   (`harness/validate/report.py`, `harness/catalyst/report.py`,
   `scripts/build-reports-index.py`) rsynced by `scripts/validate-publish.sh`
   to a GCP VM and served by a Caddy `file_server` block. Design system #2:
   `harness/report_shell/assets.py`. Design system #3: `build-reports-index.py`
   hand-rolls a *third* palette/card/table CSS (~50 lines) for the index page
   alone — it doesn't even match the report pages it links to.

Ranked findings:

1. **The reports host is orphaned.** No page in `site/` links to
   `reports.openclinai.org` at all (grep confirms zero references). A second
   domain with its own TLS cert is being maintained for pages users can only
   reach by typing the URL. The assumed "landing page links out to reports"
   coupling does not exist yet — which is a freedom: nothing breaks when the
   URL scheme changes.
2. **The published corpus exists only on the VM.** `artifacts/reports/` and
   the source run data in `artifacts/validate/` are git-ignored and empty
   locally; only `reports-index.json` (15 KB of curated prose) is tracked.
   The rsync is additive-only (no `--delete`), so the VM accumulates state
   that can never be reconciled from git. A lost VM disk = lost published
   reports unless the operator still has every local run dir.
3. **`build-reports-index.py` (329 LOC) is a bespoke static-site generator**
   duplicating exactly what `site/` already does with tests (curated cards,
   nav, theme toggle) — including an overfit `human_arm()` substring-matching
   label translator (lines 52-90) that has already mislabeled arms once and
   duplicates knowledge the shared model registry owns.
4. **The publish pipeline is manual and fragile**: requires the VM RUNNING,
   `gcloud` auth, minted SSH keys, and the operator's current public IP in a
   /32 firewall allowlist (`scripts/cloud-lib.sh:93-142`); logic lives in
   untested inline `python3` heredocs; the dashboard-freeze step fails
   silently.
5. **`file_server browse` leaks structure** — the auto directory listing
   exposes every rsynced slug, including deployed-but-unlisted runs the index
   generator explicitly warns about.

## The constraint that shapes the fix

**The VM is not retirable.** The same Caddy/compose stack serves the live
OpenMRS RefApp + chartsearchai chat at `openmrs.openclinai.org` (dynamic
backends: Tomcat, long-timeout chat, reverse proxies). The VM exists
regardless. Only the report HTML — which is pure static file serving, the
textbook GitHub Pages case — is misplaced on it.

Also already decided (2026-07-22): demo videos bundle into `site/public/`
and ship with the Pages build. The reports host's scope question is therefore
*only* about validation-run reports.

## Roadmap

### Phase 1 — durability + linkage (hours; do before anything else)

- Commit the published corpus: track `artifacts/reports/**` in git (HTML/JSON
  compress well; measure first, but expect low single-digit MB for ~13 runs).
  This makes the VM a cache instead of the only copy, and makes every later
  phase reversible.
- Pull the VM's current `artifacts/reports/` down first (reverse rsync) so
  the repo becomes the source of truth including historical runs.
- Drop `browse` from the reports Caddy block (curated index only).
- Add the missing link: the site's landing should link to the reports index
  (whatever its URL is at the time) — the audit showed it never has.

### Phase 2 — one domain, one deploy path (~1-2 days)

- Publish reports as part of the Pages build: copy rendered
  `artifacts/reports/**` into the Pages artifact (e.g. served at
  `openclinai.org/reports/<slug>/`) in `.github/workflows/pages.yml`.
  `validate-publish.sh` shrinks to "render, commit, push" — no VM, no rsync,
  no firewall/SSH in the publish path. Reports publishing becomes the same
  motion as every other site change (a commit), and CI redeploys.
- Repoint or retire the `reports.openclinai.org` DNS record (registrar access
  is the operator's; a Caddy `redir` block can bridge old URLs during the
  transition).
- Move the two inline heredocs in `validate-publish.sh` into tested Python
  (or delete them — `meta.json` writing belongs next to the renderer).

### Phase 3 — one index, one design system for chrome (~2-3 days)

- Replace `build-reports-index.py`'s generated index with a React route in
  `site/` that reads `reports-index.json` directly (it is already the curated
  data source) and renders cards in the site's design system. Delete the
  generator (−329 LOC) and palette #3.
- Replace `human_arm()` with lookups against `harness.validate.model_registry`.
- Fold the ChartSearchAI demo videos into the site-bundled demos surface
  (same pattern as the Catalyst videos; cut/caption selection is the open
  question recorded in `specs/demos-publishing-plan.md`).

### Phase 4 (optional, largest) — restyle the report bodies

The rendered `report.html` pages themselves (~2000 LOC of inline CSS/JS in
`harness/validate/report.py`) keep design system #2 through Phases 1-3.
Unifying them with the site's look is a separate, larger effort with the
least user-facing payoff (the pages are self-consistent artifacts). Defer
until something else forces a touch of `report.py`; `report_shell` stays the
shared shell for the Python-rendered family in the meantime.

## End state

One domain (`openclinai.org`), one deploy mechanism (push to `main` →
Pages), one design system for all navigation/index chrome, the VM scoped to
the one thing that genuinely needs a server (the live clinical demo), and
every published byte reproducible from git. The reports *renderers* stay in
Python — generated evidence pages are fine; the smell was never "Python
makes HTML," it was two publish paths, three palettes, and a corpus that
lived only on a VM disk.
