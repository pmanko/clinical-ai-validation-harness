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

## What runs here

| Group | Role |
| --- | --- |
| `catalyst-mvp-isolated-*` | Current Catalyst UI, Gateway, Hub, Spark, OpenELIS, FHIR, Data Pipes and Superset services, with retained datasets |
| `catalyst-demo-caddy-1` | Shared HTTPS entry point and immutable demo media |
| `catalyst-demo-model-router-1` | Shared model inference service |
| Older `catalyst-demo-*` UI, Gateway, Hub and analytics database | Previous application retained for rollback pending final release proof |
| `csim-*` | Separate Superset investigation and preview stacks; not owned by Catalyst release cleanup |

The current UI and API are routed to the isolated stack. Its Superset endpoint
is `/catalyst-dashboards/`. Existing `/superset/`, `/superset-preview/`, media and
CSIM domains remain independent. The public proxy configuration is currently
`/home/ubuntu/catalyst-demo/targets/catalyst/Caddyfile`.

The proxy and shared model service have explicit Docker network connections to
the isolated stack. Those connections survive container restart but must be
restored if either container is recreated. Inspect the live network and Caddy
configuration before changing them; the proxy serves other applications too.

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
export CATALYST_ROUTER_WARM_MODEL=gemma-4-12b-q4
```

`CATALYST_ROUTER_MODELS_MAX` is a deployment capacity setting. One is appropriate
for this 30 GiB CPU host. A GPU or higher-memory deployment may configure a
larger value after measuring memory, cold/repeated latency, and concurrency.

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

The server override retains the previous CPU demo budgets: set
`CATALYST_HUB_TIMEOUT_SECONDS: "1800"` on `catalyst-gateway` and
`LLM_REQUEST_TIMEOUT_SECONDS: "1800"` on `med-agent-hub`. The isolated stack's
360-second Gateway default caused a verified OpenMRS preparation failure on
11 September UTC, before SQL execution. Model processing in the same time window
exceeded nine minutes. Restoring the previous budget prevents that premature
cutoff but does not make inference faster or guarantee successful generation.

Check for active preparations before applying lifecycle changes. The wrapper's
`up` rebuilds services and can recreate otherwise unchanged application containers;
run it outside recording, import and query validation. Keep each validation run
on an uninterrupted deployment.

## Capacity, evidence and publication

The root volume is now 100 GiB. The expansion and targeted Docker cache pruning
preserved all application volumes. Check `df -h /` and `docker system df` before
cleaning; do not prune volumes or remove other stacks as part of cache cleanup.

Release evidence lives under `/home/ubuntu/catalyst-release-evidence/`, outside
Git. Keep raw footage, traces, exact revisions, configuration and import receipts
together. Current acceptance is tracked only in
[Feature 008 tasks](../specs/008-catalyst-query-workbench/tasks.md).

Final videos and posters go into
`/home/ubuntu/catalyst-demo/targets/catalyst/runtime/media` with new immutable
filenames. Verify the public media before changing `openclinai.org`, whose
homepage is served separately from the GCP harness host. Publish only the
reviewed homepage change, preserving unrelated proxy configuration and content.
