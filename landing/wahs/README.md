# WAHS discussion report

Canonical URL: https://wahs.openclinai.org/
Also available under the main site's `/wahs/` directory. The homepage links to
this report. This is a dated collaboration proposal, not an approved WAHS roadmap
or a live status feed. Meeting and research sources may require team access.

The HTML is the editable source. CSS controls responsive and print layout;
JavaScript adds section navigation, filtering and expandable source links.
Without JavaScript all sections remain readable. No build, account, backend,
external font or model call is needed to read the report.

The Word companion follows the selected Design Report template. Keep its content
aligned with the browser report when changing conclusions or recommendations.

## Preview and verification

Serve this directory with a static HTTP server, then check section navigation,
the opportunity filter, source drill-downs, keyboard access and narrow layouts.
Run `python -m pytest tests/test_landing_site.py tests/test_wahs_report.py` from
the repository root. Inspect the rendered Word pages after editing that file.

## Publishing

The existing Caddy proxy serves `landing/`. The optional `CADDY_SITE_WAHS`
setting enables the report host using the same mounted directory; the local
fallback port is not published. Set it to `wahs.openclinai.org` on the existing
cloud host. The wildcard DNS record already points there as of 9 September 2026.

Follow the repository's main-before-deployment policy. `scripts/publish-landing.sh`
is the existing full landing publish path. Compare live proxy files before
publishing; do not overwrite unrelated deployment changes. A report-only update
needs only the files under `landing/wahs/`, and no proxy restart. Changes to the
host configuration require validation and restarting only the proxy.

The report cites inspected Hub and QueryStore revisions, the harness roadmap and
run metadata, the WAHS meeting and transcript, research plans, and current FHIR
guidance. UX sources are listed in its final section. No pilot results or patient
usability findings are claimed.
