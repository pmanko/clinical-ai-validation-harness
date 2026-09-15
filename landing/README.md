# OpenClinAI public website

`landing/` is the static website served at https://openclinai.org/. It is separate
from the documentation application in `site/`. Caddy serves these files directly;
there is no JavaScript runtime or build step.

## Approved website iteration

The homepage introduces one initiative with four first-class projects:
ChartSearchAI, Catalyst, Med Agent Hub and the Validation Harness. The two
applications lead with patient-chart review and reporting use cases. Hub and the
Harness appear immediately afterward as critical shared components, each with
its own purpose and overview page. This is a website iteration, not an expansion
of application scope or a replacement for product roadmaps.

The working headline is “Open tools for clinical questions and reporting.”
Global navigation is Projects, Evidence and About. Keep the homepage concise;
use descriptive headings rather than slogans or narration of the design approach;
full demonstrations, processing explanations and case studies belong on project
pages. Preserve the restrained existing identity and real application imagery.

### Page responsibilities

| Destination | Responsibility |
| --- | --- |
| `/` | Purpose, four-project collection, relationship, concise evidence/contribution links |
| `/chartsearchai/` | Patient-chart use cases, OpenMRS demos, source evidence and integration resources |
| `/catalyst/` | Query/import-to-dashboard workflow, human review and correction, demonstrations and resources |
| `/med-agent-hub/` | Shared model profiles/roles and application integration patterns |
| `/validation-harness/` | Reproducible environments, integrated workflow checks and evidence |
| `/catalyst/reporting-pathways/` | Four complementary OpenELIS reporting routes, their limits and independently watchable demonstrations when verified |

Retain the existing question gallery, HIV walkthrough, reports, transcripts and
WAHS destinations. Update parent links. Old homepage fragments have lightweight
onward links; do not keep obsolete full sections to preserve those fragments.
The native OpenELIS CSV-to-Superset route does not require Catalyst or Hub.
ChartSearchAI retains its bundled provider. Never imply every deployment must
pass through all four projects.

### Delivery checkpoints

1. **Local hierarchy review:** homepage and Catalyst overview with real copy and
   assets; all four project entries and the reporting-pathway destination are
   navigable. Review clarity, balance and visual quality before final migration.
2. **Complete migration and PR:** finish project-page content and links;
   reconcile the existing OpenMRS contributions PR, placing its destination
   under ChartSearchAI; update existing public-surface records. Amend the current
   reporting roadmap's publication location while preserving its video and
   deployment acceptance requirements. Use one cohesive website PR.
3. **Review and publish:** finish local checks and owner review, merge, publish
   the exact reviewed revision with the existing isolated publication flow, and
   inspect live pages and media.

Current state: the owner approved the presentation and revised descriptive copy
on 15 September 2026 and authorized publication after validation. The website
change is consolidated in PR #184; its release record identifies the merged
revision and subsequent live verification.
This is the website's delivery record. Detailed reporting-pathway progress stays
in its existing integration roadmap and task register.

### Acceptance

- Visitors can identify the four purposes and select a destination for chart
  review, reporting, shared model configuration or reproducible validation.
- ChartSearchAI and Catalyst have balanced application entry points; Hub and the
  Harness are visible named projects with useful destinations.
- The reporting routes are easy to find under Catalyst. Pending demonstrations
  are labelled honestly; old recordings do not establish new acceptance.
- Useful demos, transcripts, galleries, evidence and contribution links remain
  reachable, including historical entry points.
- Inspect wide/narrow screenshots, keyboard focus, headings, mobile navigation
  and text zoom. No clipped text or horizontal overflow. Ask the owner to try
  representative navigation tasks without coaching.
- Run the landing tests for project navigation, local links/fragments, image
  references, accessible video controls and publication verification. Inspect
  rendered media separately from static checks.
- Record local validation, owner acceptance and publication separately. Do not
  infer clinical safety or model performance from application delivery.

Raw screenshots and personal review notes stay outside Git. Reuse the current
styles and serving infrastructure; add no framework, tracker or spec family.

## Design basis

- [USWDS landing pages](https://designsystem.digital.gov/templates/landing-page/):
  brief contextual introductions leading to detail on internal pages.
- [NN/g information scent](https://www.nngroup.com/articles/information-scent/):
  concrete labels and adjacent descriptions that help visitors choose a route.
- [DIGI at UW](https://digi.uw.edu/): purpose, real product imagery and restrained
  purple/gold cues.
- [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  and [focus visibility](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html).

## Verify and preview

```bash
uv run pytest -q tests/test_landing_site.py
python3 -m http.server 4173 --bind 127.0.0.1 --directory landing
```

Open http://127.0.0.1:4173/ so root-relative assets resolve correctly.

## Publish

After owner review and merge, publish only the website:

```bash
./scripts/publish-landing.sh --landing-only
```

The script verifies referenced demo-host media before publication and compares
published HTML/CSS bytes with the reviewed source afterward. Verify browser
navigation and playback separately; successful copying is not owner acceptance.

## Approved follow-up: navigation and publication audit

The owner approved this follow-up for **local review** on 15 September 2026.
It extends this website plan; it is not a new roadmap or application feature.

1. **Find the useful material:** give the narrated Catalyst screenshot walkthrough
   a direct homepage link and an opening action on the Catalyst page. Replace the
   documentation introduction with a practical index using existing content.
2. **Connect and consolidate:** add consistent parent links to documentation,
   status, design-review and report-index templates; reconcile the three published
   reports missing from the source catalog, retaining their historical findings.
   Use one explicit content selection for interactive and static documentation.
3. **Validate for local review:** check destinations, generated pages, catalog
   preservation, source-copy checksums, keyboard navigation, narrow layouts and
   screenshots. Keep public publication and owner review separately recorded.

Every page has one purpose, owning section, source and parent link. The homepage
and project pages explain capabilities; documentation explains usage and
architecture; status records dated progress; designs show proposed/approved
interactions; reports preserve dated observations. Keep media in its existing
home and link to it. WAHS keeps its existing canonical subdomain and path alias.

Use the existing publication flows: landing is explicitly published after merge;
documentation/status/designs are built by Pages; report indexes use the existing
report publisher. Merging the website branch can publish Pages, so this local
review checkpoint includes neither merge nor publication.

### Follow-up acceptance

- Find the screenshot walkthrough directly from the homepage and before the
  embedded videos on the Catalyst overview, with labels distinguishing pictures,
  videos and design mocks. Preserve the gallery URL, screenshots and recorded context.
- Documentation has one concise index; its interactive and static versions link
  to the same existing material and the public project overview. Preserve cited research.
- Each updated surface has a clear Open Clinical AI parent link and retains its
  local controls, search and navigation. No extra header framework is introduced.
- All previously published report entries remain listed. Historical conclusions
  are labelled as historical, not adopted as current release requirements.
- Public documentation selection is explicit and shared by both renderers;
  adding a private file must not automatically publish it or add it to search.
- Update only the affected status entries with their actual check dates. An index
  refresh does not revalidate old runtime observations, report results or acceptance.
- Existing relevant tests/builds pass; inspect desktop/narrow screenshots, focus,
  text zoom and links. Raw evidence stays outside Git. The local review includes
  the landing page, documentation, status, design wrapper and report index.

Status: implemented for local review on 15 September 2026. The focused Python
checks (26), site tests (92), Pages build, documentation checks, generated views
and design-source manifest passed. Desktop and narrow screenshots were inspected;
320-pixel layouts, documentation search, skip-link focus and gallery navigation
were checked. Browser text zoom and owner navigation review remain outstanding.
No remote merge or publication is included in this checkpoint.


### Functional scope and discovery follow-up

| Surface | Reader's task | Content ownership |
| --- | --- | --- |
| Homepage | Choose a project | Short purpose, relationship and project links |
| Project overviews | Understand what a tool can do | Use cases, current capabilities/limits, demonstrations and next steps |
| Catalyst reporting pathways | Understand the four reporting routes | Journeys and demonstrated limits; detailed progress remains in the delivery register |
| Screenshot/question galleries | Follow a recorded example | Captioned, dated demonstrations; shared evaluation material is labelled and linked to the Harness |
| Documentation and technical canvases | Set up, integrate and understand mechanisms | Guides, technical context and cited research; project introductions and current delivery status are linked |
| Project status | Find progress and next checkpoints | Dated inventory summaries linking authoritative tasks and evidence |
| Design review | Inspect proposed/approved interactions | Fictional mock state and design-source revision; separate from working product claims |
| Reports | Inspect recorded findings | Immutable run evidence and methods; the catalog can correct availability/context |

Cross-links connect these responsibilities; they do not transfer ownership. Reuse
media in technical explanations when it adds context, but maintain the main
walkthrough destination under its product. Keep old gallery/report URLs and
anchors when clarifying the surrounding context. Research snapshots stay dated;
they do not become the current delivery sequence.

The owner also requested a search-engine and AI-agent accessibility audit.
Read-only checks covered the ten landing routes, documentation/static exports,
status/design/report entry points and common robots/sitemap endpoints. Project
pages already provide server-rendered text, captions, titles and canonical links;
documentation already emits static pages, a search index and `llms.txt`.

The next discovery iteration should address documentation/static-page canonical
URLs and descriptions, generated sitemaps from existing public content lists,
and an ordinary HTML fallback linking the status sources. Decide indexing of
draft mocks and operational snapshots separately from product information.
No robots or indexing policy was changed in this local-review iteration. Missing
robots.txt is not evidence that crawlers are blocked; absence of a sitemap is not
proof that a page is unindexed. Search Console and real crawler logs were not
inspected, so search visibility and AI citation cannot be claimed from these checks.

Use conventional readable HTML, crawlable links and accurate metadata. There is
no need for a new AI-specific website or a second maintained content catalog.
Generate additional discovery files from the existing public sources when that
follow-up is approved. Search access and model-training crawler permissions are
separate choices.

References: [Google JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics),
[Google AI search guidance](https://developers.google.com/search/docs/appearance/ai-features),
[canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls),
[sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap),
and [OpenAI crawler roles](https://developers.openai.com/api/docs/bots).


### Authorized completion and publication — 15 September 2026

The owner authorized completing and publishing this iteration without another
routine local-review pause. Navigation/consolidation changes and discovery fixes
ship together through the existing landing, Pages and report-catalog flows.

Implemented: canonical URLs and descriptions for static documentation, status,
design review and the report index; readable documentation/status entry content;
sitemaps generated from existing page outputs, landing canonical links and the
report catalog; and the WAHS heading/navigation correction. The sitemap omits the
unavailable historical report and the landing alias owned by the WAHS subdomain.

Search and training permissions remain unchanged. Draft designs and dated status
records retain explicit context; this release introduces no crawler exclusions
or promise of indexing. The historical Catalyst release report is absent from
the serving host and the configured archive bucket is unavailable, so its catalog
entry remains labelled unavailable. No historical result has been recreated.

Local checks: 28 focused Python tests, 94 site tests, documentation checks and the
Pages build passed. Mobile WAHS navigation/focus and static documentation were
inspected. Browser-controlled 200% text zoom is unverified; narrow-layout checks
are not a substitute for it. Existing bundle-size warnings remain. The full
repository-line gate encounters pre-existing application checkout differences;
this static-only release excludes those gitlinks and changes no running service.
Public file hashes, destination checks and publication receipts are captured in
the private website audit after deployment; source approval is not that receipt.
