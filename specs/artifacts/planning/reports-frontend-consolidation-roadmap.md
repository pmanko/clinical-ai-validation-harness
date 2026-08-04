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

## Sync & consolidation roadmap: clear scope, clear deploy, landing-first

Owner ruling (2026-07-22): **`landing/` is the front-facing page** — a clean,
fast, hand-authored homepage at the apex — and **the Pages site is the
documentation visualization** (a rendered view of the repo's specs, canvases,
and README), not a competing homepage. Consolidation means giving every
surface a declared scope and a declared deploy mechanism, and getting every
source of truth onto the mainline — not collapsing everything into one app.

### Target architecture

| Surface | Scope (what it is FOR) | Source of truth | Deploy mechanism |
|---|---|---|---|
| `openclinai.org` — `landing/` | THE front door: mission, the products (Catalyst first-class, chart search, live demo), demo videos, and links out to docs/reports/demo | `landing/` on the mainline (today: unmerged m2 branch — must move) | a single documented publish step from the mainline (`make landing-publish` → rsync `landing/` only); optionally CI later |
| Pages site (`pmanko.github.io/...`) | Documentation visualization: specs, canvases, README, research — the codebase's own docs, browsable | `site/` + `specs/**` on `main` | CI: push to `main` → Pages (already true) |
| `reports.openclinai.org` | Validation-run evidence archive (generated reports + curated index) | run data + `reports-index.json` in git; rendered corpus committed (today: VM-only — must sync down) | `scripts/validate-publish.sh` (existing), simplified over time |
| `openmrs.openclinai.org` | The live clinical demo (needs a server) | compose stack on the mainline | `make cloud-*` (deploys the STACK; never website content) |

Consistency rule: every surface links to the others by role — the landing
links to docs, reports, and the live demo; the docs site and reports index
link back to the landing as home. Shared identity (name, favicon, tone), not
necessarily shared CSS: the landing and the docs site may keep their own
styling as long as branding and cross-links are coherent. Palette #3 (the
reports index's private CSS) has no such excuse — fold it into
`report_shell`'s.

### Phase 0 — sync the sources to the mainline (hours; unblocks everything)

The fragmentation is first a *source-control* problem: public content lives
on two branches plus a VM disk.

- Bring `landing/` from `codex/m2-openmrs-relay-reconciliation` onto the
  mainline (this umbrella branch, then `main` via PR #37), along with the
  m2 branch's newer apex Caddyfile block (`root * /srv/landing`) that this
  branch lacks.
- Reverse-rsync the VM's `artifacts/reports/` down and commit it — the
  published evidence corpus must be reproducible from git; the VM becomes a
  cache, not the only copy.
- Document in `cloud-sync` that it deploys the demo stack, and in
  `make landing-publish` (new, trivial) that IT is how the homepage ships.

### Phase 1 — landing as the flagship (the immediate payoff)

- Add the Catalyst section to `landing/`: what it is, the two per-dataset
  demo videos, and links to the published validation report, the docs site's
  Catalyst pages, and the live demo. (This completes the "make Catalyst
  first-class on the published homepage" goal on the page that is actually
  published.)
- Cross-link the constellation from the landing: Docs (Pages site), Evidence
  (reports index), Live demo (openmrs subdomain) — and add the reciprocal
  "home" links on the docs site and reports index.
- Deploy via the new `make landing-publish`; verify live.

### Phase 2 — deploy + hosting hygiene (hours)

- Drop `browse` from the reports Caddy block (stops leaking unlisted slugs).
- Move `validate-publish.sh`'s two inline Python heredocs into tested code
  next to the renderer.
- Reports index drops palette #3 for `report_shell`'s shared styling.
- Optional: a CI job that rsyncs `landing/` on push to `main` (needs a VM
  SSH secret in Actions) — replaces the manual make target if wanted.

### Phase R (optional, unscheduled) — restyle report bodies

`harness/validate/report.py` (~2000 LOC inline CSS/JS) keeps `report_shell`
styling through all phases above. Unify only when something else forces a
touch of `report.py`; least payoff, largest surface.

### Explicitly out of scope

- Pointing the apex at GitHub Pages / making the docs site the homepage —
  rejected: the landing is deliberately the front door; the docs site is
  documentation.
- Retiring the VM (it hosts the live OpenMRS/chartsearchai demo — Tomcat,
  long-timeout chat backends; genuinely needs a server).
- Rewriting the Python report renderers (generated evidence pages are fine;
  the smell was the publish paths and palettes, not "Python makes HTML").
- Any change to validation-run *data* formats or the run-manifest spine.

### End state

Four surfaces, each with one declared job and one declared deploy path, all
reproducible from the mainline: the landing (front door, `make
landing-publish`), the docs site (documentation, CI Pages), the reports
archive (evidence, `validate-publish.sh`), and the live demo (the only
server). No public byte whose source lives on a side branch or only on a VM
disk, and no working-tree rsync masquerading as a release process.
