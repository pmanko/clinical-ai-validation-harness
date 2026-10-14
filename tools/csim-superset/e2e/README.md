# CSiM workflow checks and visual evidence

One Playwright suite serves regression checks and recorded demonstrations. It
uses the real synthetic Superset installation, its normal controls and its real
chart requests. It does not mock responses or change clinical data.

## Run

Start the existing local demo and overview preview first. The full dashboard
can be initialized from files with `bash ../local.sh bundle-boot` from this directory. The overview can be
served with `python3 -m http.server 18769 --bind 127.0.0.1 --directory ../design`.

```sh
npm ci
npx playwright install chromium
python3 -m venv ../output/video-venv
../output/video-venv/bin/pip install -r video/requirements.txt
npm test                              # all assertions and screenshots; no video
npm run demo                          # same assertions; videos for dashboard workflows only
CSIM_E2E_TARGET=server npm run demo    # published synthetic dashboard and overview
CSIM_E2E_TARGET=server npm run check-publication # hosted media, playback, captions and mobile links
npm test -- --grep '03'               # one workflow
```

Defaults read the private `../.env.local` or `../.env.server`. Alternatively set
`CSIM_ENV_FILE`, `CSIM_ADMIN_PASSWORD`, `CSIM_USERNAME`, `CSIM_BASE_URL` and
`CSIM_OVERVIEW_URL`. These tests are designed for the invented CSiM fixture.
Do not point this evidence publication workflow at a clinical-data installation.

## Workflows

1. Understand reporting requirements, expand the date-label solution, change the
   illustrative time grouping, and read the overview on a narrow screen.
2. Open every one of the 21 charts using saved default filters.
3. Switch Month → Quarter → Year; assert exact values and the chronological
   labels actually painted on the chart canvas.
4. Select February–March and Quarter; exclude January from the rate while keeping
   the two deliberately all-time total cards unchanged.
5. Change care location and hospital, and verify the selected population changes the results.
6. Clear selections without combining overlapping totals, then restore defaults.
7. Follow a problem to its evidence, open the dashboard, and return to the overview.
8. Check Month/Quarter/Year choices, hospital-only and cohort/state-only menus,
   internal section links, and the unresolved dashboard-specific Time Unit choice.
9. With `CSIM_IMPORT_EVIDENCE=1`, open the independently imported dashboard,
   check all 21 chart identities and results, change to Quarter, and show the
   production-promotion checks that remain. Run `bash ../bundle-check.sh test`
   first; the independent instance must be running on port 18094.

The existing `verify_full.py` adds 91 chart-data requests and broader numerical
assertions, including every chart at three grains. Browser workflows provide
additional assurance that controls, browser requests and displayed results agree.
The independent bundle check additionally verifies native import, exact SQL and
remapped chart/filter relationships. Clinical agreement, production parity,
WordPress integration and comprehensive accessibility remain separate checks.

## Evidence

Each run writes a dated directory under `../output/browser/`:

- `public/index.html`: a shareable workflow gallery with pass/fail status,
  screenshots, and videos when recorded;
- `public/summary.json`: target, time, source fingerprints and workflow outcomes;
- `playwright-report/`: the standard detailed report for local diagnosis;
- `results.json` and `results/`: raw local test results and attachments.

Only `public/` is intended for the public `/superset/design/evidence/` route.
The gallery is generated from test results, so failed workflows remain failed.
`npm run demo` records only workflows 2–6, 8 and 9. It encodes an introduction,
large screens for major topic changes, a compact caption strip below the full
dashboard, and closing results or gaps. Minor control changes use captions.
Result holds last at least six seconds and extend for longer captions. `video/render.py` extracts
frames from the final MP4 and compares them with every checkpoint and title card.
A mismatch fails publication preparation. Contact sheets are included for visual
review of both the results and caption accuracy.

The renderer uses the caption guide saved with the run, preserves the recorded
control interactions, and adds a caption strip below the dashboard pixels. It
retains original raw footage privately. For a custom runtime, set
`CSIM_VIDEO_PYTHON` and optionally `CSIM_FFMPEG` / `CSIM_VIDEO_FONT`.
Each section includes instructions, expected results, a stable issue link and a live-dashboard link. The date, Time Unit and import videos state remaining gaps in their closing cards. They omit website footage. Video dimensions are reserved before loading so deep links do not shift.
A successful screenshot does not override an assertion failure.

After publication, `check-publication` checks every hosted asset, plays all eight dashboard
videos in Chromium, verifies their dimensions, duration and caption tracks, and
captures desktop and mobile navigation screenshots under `output/publication/`.
It also catches duplicate recordings from workflows that open multiple pages.

Login occurs before recording. The temporary authentication file is mode 600 and
removed at completion. Traces are disabled because they can include authenticated
request headers. The public gallery copies only PNG/MP4/VTT evidence and video frame contact sheets and a curated
summary; it excludes authentication state, request headers, raw SQL and traces.

The canvas check observes `fillText` calls and their screen positions while
preserving the original drawing calls. This catches the actual Superset issue
where comparison charts can reorder text dates after the query returns them.
It does not assert against private ECharts or React state.

## References

The small suite follows the pinned Playwright setup and workflow-focused tests in
[DIGI-UW/openelis-review-tooling](https://github.com/DIGI-UW/openelis-review-tooling),
and the named screenshot/evidence conventions in this repository's `e2e/` and
`tests/e2e/` suites. It does not install the review overlay, create Grist checklists,
or mark any human review accepted.

Superset can cancel older requests after a filter change, and Chromium can discard
response bodies during navigation. Those capture notes remain in run details;
network/HTTP/query failures still fail the suite. Each asserted chart result must
have a readable response, and axis assertions independently check painted labels.

The independent bundle check runs the six dashboard scenarios on port 18094 after native import. It does not depend on the original private source snapshot. Source fingerprints include the native YAML files and import helpers.

## Continuous integration

`.github/workflows/csim-dashboard.yml` runs all ten workflows on pull requests
and main changes to this tool. It starts two release instances and a pinned upstream snapshot,
imports the native files, loads only invented fixtures, and runs numerical,
relationship and browser checks. No shared server credentials are needed.

`CI` disables recording even if `CSIM_RECORD=1` is also set. `assert-ci.mjs`
requires every selected workflow to pass and rejects any generated video files.
The website and navigation checks run alongside the dashboard checks, and
remain in CI diagnostics; they are excluded from the public gallery and films.

`report.mjs <directory> --preview` renders the same gallery navigation without
execution results or media. CI serves this with the current overview source so
navigation tests do not depend on previously published evidence. It cannot pass
the publication guard. `CSIM_OVERVIEW_URL` adjusts the imported dashboard's
overview links for the test installation; dataset SQL and filter definitions
remain the native bundle's files.

## Snapshot comparison

Set `CSIM_PREVIEW_EVIDENCE=1` to include workflow 10. Start the snapshot with
`../preview.sh up`, `seed` and `import` first. CI starts it automatically and runs
all ten workflows without video. A complete published run also sets
`CSIM_IMPORT_EVIDENCE=1`, producing eight dashboard films and two unrecorded
website checks.

For the shared server, set `CSIM_PREVIEW_URL` if needed, and provide
`CSIM_PREVIEW_ENV_FILE` plus `CSIM_PREVIEW_USERNAME`. Authentication happens before
recording. The default local preview uses its separate `.env.preview` account.
The snapshot's native export/import check and full numerical assertions run
before the browser comparison of Month/Quarter/Year with Hour/Day/Week.

The same six full-dashboard browser workflows also run against the snapshot in CI.

To validate an overview before publishing it, set `CSIM_OVERVIEW_URL` to its local
preview and `CSIM_PUBLIC_OVERVIEW_URL` to its published destination. Evidence
records both addresses and links readers to the published overview. Dashboard
requests and recordings still use `CSIM_BASE_URL` (or the selected target).
