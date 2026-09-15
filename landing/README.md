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
