# Cloud deploy target (GCE)

Push the chartsearch harness stack to a GCE VM in the `clinical-ai-harness`
GCP project, point its chartsearchai backend at your local LM Studio over a
cloudflared tunnel, and iterate on chartsearchai changes with a one-command
push.

Scope: **local-driven deploy only** — no CI, no auto-pipeline. Run targets
from your laptop against a GCE VM you own.

## Prerequisites

| Tool | Why | Check |
|---|---|---|
| `gcloud` SDK, authenticated as you | provisions + ssh's to the VM | `gcloud auth list` |
| Active project = `clinical-ai-harness` | the VM lives there | `gcloud config list project` |
| `cloudflared` (Homebrew) | tunnel local LM Studio → public URL | `cloudflared --version` |
| LM Studio with at least one chat model loaded, serving on `localhost:1234` | the LLM the cloud backend will hit | `curl -s http://localhost:1234/v1/models` |

## One-time setup (~5 min)

```bash
# 1. provision: static IP, firewall, VM, docker install
make cloud-init

# 2. configure the cloud-side chartsearchai env
cp .env.chartsearch.cloud.example .env.chartsearch.cloud
# leave CHARTSEARCH_REMOTE_ENDPOINT_URL as a placeholder for now — the
# next step gives you the real URL
```

In a dedicated terminal, start the tunnel and copy the URL it prints:

```bash
make cloud-tunnel
# → https://random-words-here.trycloudflare.com
# Leave this terminal running for the lifetime of your iteration session.
```

Paste the URL into `.env.chartsearch.cloud` as `CHARTSEARCH_REMOTE_ENDPOINT_URL`,
**with `/v1/chat/completions` appended**:

```ini
CHARTSEARCH_REMOTE_ENDPOINT_URL=https://random-words-here.trycloudflare.com/v1/chat/completions
```

## First-time bring-up (~25 min, mostly Liquibase)

```bash
# 3. build the .omod locally (once)
make chartsearch-build

# 4. push everything to the VM
make cloud-sync

# 5. compose up on the VM, wait for backend healthy, run chartsearch-configure
make cloud-up

# 6. one-time seed of the 5,284-patient corpus from your local DB to the VM (~5-10 min)
make cloud-seed
# then restart backend so it sees the seeded schema
make cloud-ssh ARGS='cd clinical-ai-validation-harness && docker compose -f compose/openmrs-2.8-refapp.yml restart backend'
```

After this, visit `http://<vm-ip>:8088/openmrs/spa`. The VM's external IP is
in `make cloud-status` output.

## Fast iteration loop

After editing chartsearchai code:

```bash
make cloud-deploy
```

This rebuilds the `.omod` locally, rsyncs the diff to the VM, restarts only
the backend container (~30-60s), and waits for healthy. Test in browser.

For changes that don't touch chartsearchai code (compose, Caddyfile,
chartsearch-configure values), use `cloud-sync` alone, or `cloud-up` for a
full recreate.

## Lifecycle

| Goal | Command |
|---|---|
| Park the VM (save ~$3/day) | `make cloud-stop` |
| Bring it back online | `make cloud-start` then `make cloud-up` |
| See VM state + browser URL | `make cloud-status` |
| Open a shell on the VM | `make cloud-ssh` |
| Tail compose logs | `make cloud-logs SERVICE=backend` |
| Dump-and-restore openmrs_test again | `make cloud-seed` (destructive on cloud side) |
| Burn it down | `make cloud-destroy` (VM + firewall + static IP) |

## Why a cloudflared tunnel and not LM Link

LM Link is LM Studio's **device-to-device** discovery protocol — one
LM Studio instance finds models on another LM Studio instance, peer-to-peer.
chartsearchai talks the OpenAI-compatible HTTP API (`POST /v1/chat/completions`),
not LM Link's peer protocol, so the link can't carry chartsearchai's calls
even when both endpoints are LM Studio.

A cloudflared quick-tunnel is the simplest off-the-shelf primitive that
exposes `localhost:1234` as a public HTTPS URL the cloud VM can hit. The
URL is anonymous and rotates whenever you restart `cloud-tunnel` — fine for
PoC. If you outgrow that:

- **named tunnel + Cloudflare Access**: stable URL, OAuth gate (`cloudflared tunnel login` → `cloudflared tunnel create harness-llm` → `cloudflared tunnel route dns ...`)
- **Tailscale**: cloud VM joins your tailnet, hits `host.tailnet:1234` over MagicDNS, end-to-end encrypted, no public exposure

## Cost notes

| Resource | ~Cost (us-central1, on-demand) |
|---|---|
| `e2-standard-4` VM running | ~$0.13/hr → ~$95/mo always-on |
| Same VM stopped | ~$0 compute (boot disk still billed) |
| 50GB `pd-balanced` boot disk | ~$5/mo |
| Static IPv4 (in use) | $0 |
| Static IPv4 (reserved, VM stopped) | ~$1.50/mo |
| Egress to `*.trycloudflare.com` | <1¢/day at PoC volumes |

Stop the VM (`make cloud-stop`) whenever you're not actively testing. The
static IP keeps its address so the browser URL doesn't change between
sessions.

## Troubleshooting

| Symptom | Diagnosis |
|---|---|
| `make cloud-init` exits with "Address already in use" | Static IP exists from a previous run. Re-run is fine; it's idempotent. |
| Backend stuck on `unhealthy` for >10 min | Liquibase is slow first boot. `make cloud-logs SERVICE=backend` to watch. |
| ChartSearch UI shows "Unknown error" | Cloud backend can't reach the tunnel. From VM: `make cloud-ssh ARGS='curl -fsS $(grep ENDPOINT_URL .env.chartsearch.cloud | cut -d= -f2 | sed s,/chat/completions,/models,)'`. If 502, restart `cloud-tunnel` on your laptop. |
| `gcloud compute ssh` keeps prompting for a passphrase | One-time: `ssh-add ~/.ssh/google_compute_engine` (macOS keychain) |
| Rsync deletes a file on the VM I didn't want deleted | Sync runs `--delete` — anything not in the local tree (and not excluded) is removed. Add your file to local. |
