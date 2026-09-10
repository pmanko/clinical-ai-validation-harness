# CSiM dashboard demo deployment

## Available resources

- [Overview, issues and solutions](https://catalyst.openelis-global.org/superset/design/)
- [Full 21-chart dashboard](https://catalyst.openelis-global.org/superset/superset/dashboard/csim-full-synthetic/)
- [Workflow screenshots and recordings](https://catalyst.openelis-global.org/superset/design/evidence/)
- [Native dashboard definition ZIP](https://catalyst.openelis-global.org/superset/design/definitions/csim-full-native.zip)
- [Local dashboard](http://127.0.0.1:18089/superset/dashboard/csim-full-synthetic/)

The overview displays the shared `csim-viewer` login. The public `access.json`
supplies that account's credentials; the file is excluded from Git. The account
can read the invented CSiM datasets. Local setup uses `demo` and `.env.local`.

The full example uses the September 9 development layout, six filters, eight
dataset definitions and 262 invented records. It covers date grouping, labels,
missing periods and filter coverage throughout the dashboard. Existing clinical
formulas remain visible in the dashboard. See [the guide](README.md) for behavior
and [source authority](SOURCE-AND-REMEDIATION.md) for the development definition.

## Runtime

Host: `catalyst.openelis-global.org` (`52.25.10.176`), Ubuntu, aarch64.
Use the existing SSH alias and key with `ssh -4` or `scp -4`.

- Demo directory: `/home/ubuntu/csim-superset-demo`
- Docker project: `csim-date-repro`
- Application container: `csim-date-repro-superset-1`
- Proxy container: `catalyst-demo-caddy-1`
- Guide directory: `/home/ubuntu/catalyst-demo/targets/catalyst/runtime/media/csim-design`
- Proxy config: `/home/ubuntu/catalyst-demo/targets/catalyst/Caddyfile`

The demo has its own PostgreSQL database and metadata volume. Superset joins
`catalyst-demo_default` as `csim-superset`. Application ports bind to loopback;
Caddy serves HTTPS with the `/superset` prefix. The pinned base is:

```
apache/superset:6.1.0-dev@sha256:5822dff49c41fd745ce33e38af502f9c64df30d133aeba148c5d89b35a1004ef
```

It reports version 6.1.0. Local Superset adds Hive dependencies to that base;
these tests use PostgreSQL. Demo metadata is SQLite with write-ahead logging and a 30-second writer wait,
so event logging can proceed alongside concurrent dashboard metadata reads. Month, Quarter and Year
are the instance-wide time choices.

From the demo directory:

```sh
bash local.sh up           # start without reseeding
bash local.sh status
bash local.sh full-test    # 91 chart-data requests with assertions
bash local.sh bundle-pack  # deterministic native ZIP from bundle/
bash local.sh down         # stop, retaining volumes
```

`bundle-boot` initializes a dashboard from native files and explicitly seeds the
invented fixture. The Catalyst application has its own lifecycle wrapper,
`scripts/catalyst-mvp.sh`.

## Upstream snapshot alongside the release

The separate instance at `/superset-preview/` uses the exact image and upstream
commit in `preview.json`. It is development code, not a stable or preview release.
The official image embeds commit `e22ce197866ded732e4990063ae74697d89d383a`.
Docker Hub's `master` and `master-dev` tags still point to March 2024 images;
use the verified commit tag and digest rather than those mutable names.

- Directory: `/home/ubuntu/csim-superset-preview`
- Docker project: `csim-upstream-preview`; loopback port: `18095`
- Proxy alias: `csim-superset-preview`; cookie: `csim_preview_session`
- Independent PostgreSQL and metadata volumes; all database time units enabled
- CSiM control: Month/Quarter/Year; hourly example control: Hour/Day/Week

`preview.sh` uses the common Compose services with explicit preview overrides.
It does not use the release instance's environment or volumes. On a new server,
set `CSIM_PREVIEW_SERVER=1` for `up`; configure and validate the route with
`prepare_preview_route.py` before importing through HTTPS. Local runs omit that
variable and use port 18095 directly.

```sh
bash preview.sh up
bash preview.sh seed       # explicit invented fixture
bash preview.sh import     # native import, saved menus, export/import assertions
bash preview.sh test       # the same 91 full-dashboard data checks
bash preview.sh status
bash preview.sh down       # retain volumes
```

The snapshot no longer injects `from_dttm` and `to_dttm` into virtual SQL.
`sql/preview-date-context.sql` obtains those values from `get_time_filter` before
the existing date, calendar and calculation expressions run. The seven affected
virtual datasets receive this versioned prefix in `preview_setup.py`.
Quarter intervals use PostgreSQL’s explicit `3 months` spelling.
The native export contains the resulting SQL and each control's `time_grains`.
`verify_preview_import.py` changes the menus and proves import restores them,
including defaults. The browser tests check the actual chart values afterward. The snapshot enables
its table renderer because native import migrates two comparison tables to it.
Cleared controls can be applied so the dataset guards return empty results;
required-control validation otherwise leaves the preceding results visible.

## Proxy connection settings

The Superset route uses `transport http { keepalive 1s }`. The proxy must retire
idle upstream connections before Gunicorn's active two-second keep-alive timeout.
Caddy's default two-minute timeout can reuse a closed connection and return 502
for chart POST requests. [Caddy documents this behavior](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#the-http-transport).
`prepare_caddy.py` includes the setting for repeatable installation.

For diagnostics, match the browser failure's UTC time and chart ID against
Caddy's error log, Superset's access/error log, and container state. The browser
harness retains HTTP failures even when another request returns the expected
chart value. A passing numerical assertion cannot hide a failed request.

```sh
docker logs --since 10m catalyst-demo-caddy-1
docker logs --since 10m csim-date-repro-superset-1
docker inspect csim-date-repro-superset-1 --format '{{.State.Status}} OOM={{.State.OOMKilled}} restarts={{.RestartCount}}'
docker top csim-date-repro-superset-1 -eo pid,args
```

Proxy logs include request headers; use selected diagnostic fields in shared
reports. The configuration backup before this setting is
`output/Caddyfile.before-keepalive-20260910T051749Z` on the server. Validate any
candidate with `caddy validate` in the existing proxy container and compare with
the live file before replacing it. The proxy has its admin endpoint disabled,
so configuration updates require a brief proxy restart. Check the Catalyst root,
Superset health and overview routes after applying; restore the matching backup
if those health checks fail. Preserve unrelated changes when rolling back.

## Native files and independent import

`bundle/` contains a dashboard, 21 charts, eight datasets including SQL, and a
connection template. `bundle-check.sh` imports the native ZIP through Superset's
normal API into a separate instance on port 18094. All 21 numeric chart IDs differ
from the exporter. Exact SQL, chart-to-dataset UUIDs, filter targets, defaults and
exclusions match the files. The imported dashboard passes 91 chart-data checks
and six browser workflows. No custom Superset importer is required.
The 6.1.0 importer nevertheless leaves cached `chartsInScope` lists stale.
The relationship receipt reports that defect separately, and workflow 09 verifies
the remaining gap as well as the working interactions. A green run is not a claim
that the original import defect is fully fixed. See [report coverage](REPORT-COVERAGE.md).

Reports: `output/bundle-relationships.json`, `output/bundle-verification.json`,
and the dated browser run directories. See [reproduction commands](README.md).
The independent import verifies a new installation. Updating objects shared by
multiple existing dashboards and the actual production promotion route require
separate checks.

## Guide and evidence publication

`design/index.html` is the overview source. Its resources are `assets/`,
`definitions/csim-full-native.zip`, approved `access.json`, and the `evidence/`
symlink. The guide explains reporting needs, current problems, solutions and
supported workflows. Details expand where needed.

The Playwright harness is in `e2e/`. `npm test` runs assertions;
`npm run demo` adds dashboard recordings with short captions, major section screens
and checked video frames; website checks run without recording. The default eight checks include two website checks and six dashboard workflows.
`CSIM_IMPORT_EVIDENCE=1` adds the independent-import workflow;
`CSIM_PREVIEW_EVIDENCE=1` adds the snapshot comparison. Set both for publication. To test the shared viewer:

```sh
CSIM_E2E_TARGET=server CSIM_USERNAME=csim-viewer \
  CSIM_ENV_FILE=../.env.viewer.server npm run demo
```

`python3 publish_evidence.py output/browser/<run>` verifies all ten regression results and the eight dashboard films
and their encoded-frame checks, then publishes the curated files. It verifies
file hashes on the destination before changing the gallery link.
Then run `CSIM_E2E_TARGET=server npm --prefix e2e run check-publication` to check
hosted assets, video playback, captions and mobile links.

Publish an explicit successful run's `public/` directory to
`evidence-releases/<run>/`, then atomically update `evidence` to that directory.
Publish only the gallery, curated summary, PNGs, captioned MP4s, VTT captions and frame contact sheets. Authentication
state, raw results and traces remain outside the guide. The report preserves
actual pass/fail status and fingerprints of the local source files; its Git HEAD
alone does not establish the deployed target revision.

Guide and evidence updates require no service restart. `/superset/design`
redirects to `/superset/design/`. Verify the overview → issue → recording →
dashboard → overview links after publication, including narrow-screen navigation.
