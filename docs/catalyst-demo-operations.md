# Catalyst demo operations

The public application is at <https://catalyst.openelis-global.org/>. Its owning
checkout is `/home/ubuntu/catalyst-release` on that host. Use the existing SSH
alias, which selects the `ubuntu` user and the dedicated demo key:

```bash
ssh catalyst.openelis-global.org
source /home/ubuntu/catalyst-release-config/env.sh
cd /home/ubuntu/catalyst-release
scripts/verify-repository-lines.sh
scripts/catalyst-mvp.sh health
```

The environment file selects the server's isolated override and ports. Source
it for **every** lifecycle or Superset import operation. Use the harness wrapper;
the older checkout's Compose files do not describe the current public topology.
Do not rebuild or restart services during a recording or an import.

## Local development storage

Keep the local runtime checkout under a persistent code directory, never `/tmp`
or the operating system's temporary directory. The wrapper refuses startup,
seeding, and imports from temporary checkouts. Review/build checkouts may still
be temporary. Run lifecycle and import commands from the checkout that owns the
environment, with the same Compose project name on every invocation.

For a new local environment, put this setting in `targets/catalyst/.env` before
the first `up`:

```bash
CATALYST_OPENELIS_DATABASE_STORAGE=openelis-data
```

This selects the project-scoped Docker volume for the OpenELIS and HAPI database.
Existing deployments retain their original database bind mount by default.
**Do not change storage on a populated installation without a stopped-database
backup and explicit migration.** Selecting an empty volume does not migrate data.
The current local recovery explicitly rebuilds the approved synthetic fixture.

Gateway state, the analytics warehouse, and Superset metadata already use named
volumes. Publication bundles and receipts remain under the persistent checkout's
`targets/catalyst/runtime/superset/`; preserve that directory when relocating it.
`restart` and `down` retain data; `reset` and Docker volume pruning are destructive.
Seed only for an explicitly requested fixture rebuild, never as a startup repair.

## What runs here

| Group | Role |
| --- | --- |
| `catalyst-mvp-isolated-*` | Current Catalyst UI, Gateway, Hub, Spark, OpenELIS, FHIR, Data Pipes and Superset services, with retained datasets |
| `catalyst-demo-caddy-1` | Shared HTTPS entry point and immutable demo media |
| `catalyst-router-model-router-1` | Current shared CPU model inference service |
| `catalyst-demo-model-router-1` | Stopped legacy router retained for rollback |
| Older `catalyst-demo-*` UI, Gateway, Hub and analytics database | Previous application retained for rollback pending final release proof |
| `csim-*` | Separate Superset investigation and preview stacks; not owned by Catalyst release cleanup |

The current UI and API are routed to the isolated stack. Its Superset endpoint
is `/catalyst-dashboards/`. Existing `/superset/`, `/superset-preview/`, media and
CSIM domains remain independent. The public proxy configuration is currently
`/home/ubuntu/catalyst-demo/targets/catalyst/Caddyfile`.

The Catalyst host block must include the following routes before its SPA fallback.
Superset is configured with `SUPERSET_APP_ROOT=/catalyst-dashboards`; preserve
that prefix with `handle`, rather than stripping it. Named query preparation has
no proxy response deadline.

```caddyfile
handle /v1/catalyst/* {
    reverse_proxy catalyst-mvp-isolated-catalyst-gateway-1:8000
}
redir /catalyst-dashboards /catalyst-dashboards/ 308
handle /catalyst-dashboards/* {
    reverse_proxy catalyst-mvp-isolated-superset:8088
}
```

For this shared host, inspect and back up the live file before a narrow route
change; preserve the media and CSiM blocks. Validate the candidate using the
running Caddy version. Caddy 2.11, started with `caddy run --config` and without
`--resume`, supports a graceful `SIGUSR1` reload when its admin endpoint is off.
Confirm the reload in its logs and open an actual published Dashboard in the
browser: a `200` response alone can be the Catalyst SPA fallback.

Publication ZIPs use the existing outbox directory group and mode `0640`, so the
Gateway and importer can share files without granting access to other users.
Keep the outbox group readable by the importer when provisioning this Linux
host. Run `superset-import` through this checkout's wrapper, then verify both the
persisted receipt and the rendered data.

The proxy and shared model service have explicit Docker network connections to
the isolated stack. Those connections survive container restart but must be
restored if either container is recreated. Inspect the live network and Caddy
configuration before changing them; the proxy serves other applications too.

## Native CSV reporting uploads

Lane 1 uses Superset's native **Database Connections → Upload file to database →
Upload CSV** flow. It needs a writable connection separate from both the
OpenELIS operational database and Superset metadata. On the local demo, the
connection **Reporting CSV uploads** uses database `catalyst_imports` on the
existing PostgreSQL service `superset-metadata-db`, with schema `report_uploads`.
The database name denotes a separate database, despite the service's existing
name. Its login has no superuser, role-creation or database-creation privileges.
Other Catalyst analytics connections remain read-only and uploads stay disabled.

To provision the same destination on another environment, use that environment's
PostgreSQL administrator to create a dedicated login and database owned by it,
then create the upload schema as that login. Use a generated environment-specific
password, never a checked-in credential. In Superset, register the PostgreSQL
connection, enable **Allow file uploads to database**, and set the connection's
extra configuration to `{"schemas_allowed_for_file_upload": ["report_uploads"]}`.
Do not use the metadata database or an OpenELIS database as the upload target;
do not alter an existing connection to point at new data. This is operator
configuration, not a new Catalyst upload API.

For each native export, choose a new table name, explicitly select `report_uploads`,
and leave the dataframe-index option off. In Columns, keep identifier columns as
strings (for example `{"Accession Number":"str","Result ID":"str"}`). Review
numeric/mixed-value columns for the actual file rather than assuming every result
is numeric. A raw-record table must preserve the exported column order and each
result row. Aggregated charts must name the selected measurement and grouping.

The 14 September local import baseline used the native team's published server
CSV from backend `8005e4c`, uploaded into local Superset as `report_uploads.oe_results_202605_8005`. Its two result IDs, `1158` and
`1159`, retain value `450` and distinct result-to-validation times of `30` and
`90` minutes. This is native Superset file upload; it does not implement lane 2's
Catalyst Dataset import. A fresh export from the local reporting instance is
still required for the complete local lane; this check does not establish
server/final owner acceptance. Raw files,
setup receipts and screenshots remain outside Git. The integration task register
owns current validation status.

## Native OpenELIS reporting connection

The four-pathway demo uses one retained reporting OpenELIS instance per environment.
Its direct PostgreSQL connection is ordinary Catalyst source configuration, not a
separate application or authorization project. Provision it with:

```bash
python3 scripts/provision-reporting-source.py \
  --database-container reporting-uat-db-1 --admin clinlims \
  --host reporting-uat-db-1 \
  --registry /home/ubuntu/catalyst-release-config/reporting-sources/data-sources.json
```

For the existing local setup use `--database-container reporting-mvp-iteration1-db-1
--admin postgres --host host.docker.internal --port 15439` and registry
`/Users/pmanko/code/catalyst-local-config/sources/data-sources.json`.
The administrator differs between these environments; the application login is
not assumed to be an administrator.

A new synthetic-demo reader uses `catalyst_reporting_reader` / `catalyst-demo`.
Existing registry credentials are preserved, including existing published Dashboard
connections. An explicit `REPORTING_DEMO_PASSWORD` overrides the password; changing
it also requires updating existing Superset connections. This is demo configuration,
not a production credential recommendation. The command grants schema usage and
SELECT on the reporting database's tables and views, including future tables made
by current owners/migration roles. Rerun after adding schemas or migration roles.
It preserves other sources and refuses to retarget an existing source identity.
No fixture reset, reseed or application restart occurs.

Keep the source directory outside the checkout and mount it read-only at
`/app/config/extra`. On the server, declare the existing `reporting-uat_default`
network as an external network in the persistent isolated override, and attach
Gateway, Superset and its importer as well as their existing application network.
Use the stable database service name, not a container IP. These declarations must
survive container recreation; an ad hoc `docker network connect` is insufficient.

After checking that no query, import or recording is active, source the existing
environment and run `scripts/catalyst-mvp.sh source-update` from the owning
checkout. It applies configuration only to Gateway and Superset using existing
images; data services, models and unrelated deployments are untouched. Then check
source discovery, readable schema, a real query and rendered publication. A login
or HTTP health response alone does not establish a working reporting pathway.

The owner permits a tested exact native reporting branch revision on the preview
server before upstream merge. Record its revision and checks and preserve retained
data; preview deployment and upstream release acceptance are separate facts.
The requested local query-lane recordings explicitly select
`catalyst-query-gemma-4-12b-qwen2.5-14b-checked` and retain evidence of both roles.
CSV workflows make no model calls. Manual SQL correction remains valid; model
accuracy tuning and performance benchmarking remain outside this checkpoint.

## Shared model router

Catalyst intentionally consumes an external model router. The harness owns the
containerized server lifecycle so a clean Catalyst deployment does not depend on
a router left behind by an older Compose file. Configure the current demo host in
`/home/ubuntu/catalyst-release-config/env.sh`:

```bash
export CATALYST_ROUTER_MODEL_DIR=/home/ubuntu/catalyst-demo/models
export CATALYST_ROUTER_PUBLIC_NETWORK=catalyst-demo_default
export CATALYST_ROUTER_APPLICATION_NETWORK=catalyst-mvp-isolated-network
export CATALYST_ROUTER_MODELS_MAX=1
export CATALYST_ROUTER_WARM_MODEL=gemma-e4b
export CATALYST_ROUTER_NETWORK_ALIAS=model-router
export MVP_PROFILE_ID=catalyst-query-gemma-4-e4b
```

`CATALYST_ROUTER_MODELS_MAX` is a deployment capacity setting. One is appropriate
for this 30 GiB CPU host. The base deployment targets low-resource CPU inference.
The E4B writer is the owner-selected default; the existing 12B alternative remains
selectable. Increasing residency requires measured memory and concurrency evidence.

Model warmup loads the weights; it does not prime either source schema. The
`warm` lifecycle action additionally sends the neutral question “What
information is available in this data source?” through each source's ordinary
writer request and discards the answers. It does not seed, reset, run generated
or user-visible queries, retrieve clinical rows, or create user work. It makes
only the metadata calls necessary to discover each live schema.
Follow it with a different real question on each source to inspect actual schema
reuse. Record observed timings as diagnostic evidence; no response-time or
cancellation threshold defines acceptance.

Fetch and verify only the model that is missing, then verify the complete set:

```bash
scripts/catalyst-model-router.sh fetch gemma-e4b
scripts/catalyst-model-router.sh verify
```

The default network alias is `model-router-candidate`, so a candidate can start,
warm, and receive direct router smoke requests without taking traffic from the
existing Hubs:

```bash
scripts/catalyst-model-router.sh config
scripts/catalyst-model-router.sh up
scripts/catalyst-model-router.sh health
scripts/catalyst-model-router.sh smoke
```

For cutover, first confirm there is no active Catalyst generation. Stop the old
router without removing it, set `CATALYST_ROUTER_NETWORK_ALIAS=model-router`, and
run `up` again. Both Hubs already use `http://model-router:8077`. Prove the
selected profile through each Hub and both Catalyst sources before removing the
stopped legacy container. If validation fails, restore the legacy router rather
than changing a profile or falling back silently.

## Cancellation repair image

The pinned upstream router can leave a non-streaming model request running after
its caller disconnects. The small patch in `patches/catalyst-router-cancellation.patch`
closes that downstream HTTP request and keeps unrelated queue results from
extending the disconnect-check deadline. The CPU preset uses ChartSearchAI's
4,096-token logical batch and 1,024-token physical batch for prompt processing.
Batch sizing is not tuned for cancellation latency. No numeric generation or
cancellation acceptance threshold is approved.

Build on a local machine for the destination architecture:

```bash
scripts/build-catalyst-model-router.sh
```

The default is `linux/arm64`, matching the demo host; override
`CATALYST_ROUTER_BUILD_PLATFORM` for another host. The builder fetches an exact
upstream commit, applies the checked-in patch, and uses its CPU Dockerfile.
`artifacts/catalyst-router-build/build.json` records the resulting immutable image
ID, upstream revision and patch checksum. Build source and outputs stay outside Git.

Set `CATALYST_ROUTER_IMAGE` to that verified image ID for the isolated candidate.
The wrapper rejects mutable image tags. An unset override retains the original
upstream image for rollback; it does **not** enable the cancellation repair.
After loading/warming the candidate, verify ordinary inference while it is idle:

```bash
scripts/catalyst-model-router.sh smoke gemma-e4b
```

The former five-second cancellation probe and its tests are removed. Run the
inference check against an idle candidate, never during another person's
generation. Local timings are observations, not server performance requirements.

For the existing SSH deployment, transfer a `docker save` archive of the tested
image and the build receipt. Verify the archive checksum before `docker load`,
then verify the loaded image's architecture and patch label against the receipt.
Docker engines can represent the image index differently: select the loaded
immutable image ID, not a transport tag. Save the prior environment/image ID
before setting `CATALYST_ROUTER_IMAGE` and using the router cutover procedure
above. Re-run ordinary generation and both-source application
checks on the server. Restore the prior image and environment if they fail.
Keep receipts private; changing the router requires no database reset or reseed.

## ARM compatibility

The host is ARM64. The pinned OpenELIS and Data Pipes images contain x86 binaries.
This deployment uses the QEMU binary from
`tonistiigi/binfmt@sha256:d3b963f787999e6c0219a48dba02978769286ff61a5f4d26245cb6a6e5567ea3`.
Its persistent registration is `/etc/binfmt.d/qemu-x86_64.conf`; the interpreter
is `/usr/local/libexec/catalyst-qemu-x86_64` with SHA-256
`a71e55bcdd2b93e9b020adf2a357b001f464a041bc81978e2dee455773f1697c`.
The earlier emulator/registration combination caused Java crashes and stalled
database startup. Full wrapper health passed after the replacement.

The server override at
`/home/ubuntu/catalyst-release-config/isolated.override.yml` preserves the harness
configuration and changes the Data Pipes service entrypoint as follows:

```yaml
entrypoint: ["/bin/bash", "-c", "exec java $${JAVA_OPTS} -jar /app/controller-bundled.jar"]
ulimits:
  core: 0
```

This bypasses the image's failing jemalloc preload while keeping the pinned JAR,
Java options, mounts and source data. The original entrypoint failed even for
`java -version` with that preload; the controller now starts successfully.
Keep this explicit server compatibility setting when rebuilding the override.

## Model timeout settings

Normal Catalyst query preparation and neutral-question warmup have no automatic
total generation deadline. Catalyst #120 and Hub #31 removed those deadlines;
older instructions for a 120-second total limit or 360/1,800-second query budgets
are superseded. Existing explicit Stop and request-loss handling remain in place.
Connection and health-check timeouts do not define an inference acceptance target.

Check for active preparations before applying lifecycle changes. The wrapper's
`up` rebuilds services and can recreate otherwise unchanged application containers;
run it outside recording, import and query validation. Keep each validation run
on an uninterrupted deployment.

For a UI-only release, update the persistent checkout to the merged harness
revision, initialize its exact Catalyst and Hub pins, and run
`scripts/catalyst-mvp.sh ui-update` with the environment used for that stack.
This uses the same isolated override and existing `.env`, rebuilds only
`catalyst-ui`, and passes `--no-deps` so Gateway, Hub, models, source databases
and Superset keep running. It does not seed, warm models or import dashboards.
Verify the served asset hashes and the browser afterward. Use normal `up` when
the release also changes backend services.

## Capacity, evidence and publication

The root volume is now 100 GiB. The expansion and targeted Docker cache pruning
preserved all application volumes. Check `df -h /` and `docker system df` before
cleaning; do not prune volumes or remove other stacks as part of cache cleanup.

All recording, editing, and video verification run locally with local inference.
Keep raw footage and review receipts privately alongside the local recordings,
outside Git. Server deployment and query-check receipts may live under
`/home/ubuntu/catalyst-release-evidence/`; the server is not the recorder.
Current acceptance is tracked only in
[Feature 008 tasks](../specs/008-catalyst-query-workbench/tasks.md).

Keep the client awake throughout a browser check or recording. For automated
checks on macOS, run the existing test command under `caffeinate -i`; its sleep
assertion ends with that command. For an interactive check, stop the temporary
assertion when the check ends. Record sleep or network changes when investigating
a disconnected request: two failed September 12 external checks overlapped
laptop sleep and could not establish a server timeout. This is a test-environment
precaution, not a generation deadline or a persistent power-setting change.

Final videos and posters go into
`/home/ubuntu/catalyst-demo/targets/catalyst/runtime/media` with new immutable
filenames. Verify the public media before changing `openclinai.org`, whose
homepage is served separately from the GCP harness host. Publish only the
reviewed homepage change, preserving unrelated proxy configuration and content.
