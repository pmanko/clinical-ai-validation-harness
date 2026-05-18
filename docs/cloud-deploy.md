# Cloud deploy target (GCE)

Push the chartsearch harness stack to a GCE VM in the `clinical-ai-harness`
GCP project so you can iterate on chartsearchai changes with a one-command
push. The cloud backend reaches your local LM Studio via LM Link (end-to-end
encrypted, no public exposure of `localhost:1234`).

Scope: **local-driven deploy only** — no CI, no auto-pipeline. Run targets
from your laptop against a GCE VM you own.

## Prerequisites

| Tool | Why | Check |
|---|---|---|
| `gcloud` SDK, authenticated as you | provisions + ssh's to the VM | `gcloud auth list` |
| Active project = `clinical-ai-harness` | the VM lives there | `gcloud config list project` |
| LM Studio on the Mac, signed in, LM Link enabled | host of the actual model | LM Studio → Developer → LM Link |
| At least one chat model loaded in LM Studio | the LLM the cloud backend will hit | `lms ps` |

## How the LLM path works

```
[GCE VM]                          [Your Mac]
  chartsearchai backend              LM Studio
    │                                    ▲
    │  POST localhost:1234/v1/chat       │ LM Link  (Tailscale-based,
    │      /completions                  │           end-to-end encrypted)
    ▼                                    │
  llmster (LM Studio, headless) ─── LM Link tunnel
   (signed in, preferred-device = Piotrs-MBP)
```

llmster on the VM listens on `:1234` for OpenAI-compatible HTTP. When it
sees the requested model isn't local, it routes the call over LM Link to
the device that has the model loaded (your Mac). chartsearchai sees a
plain OpenAI HTTP server; nothing public is exposed.

For cloud LLMs (Anthropic, OpenAI, etc.), skip LM Link entirely — set the
endpoint URL in `.env.chartsearch.cloud` to the provider directly.

## One-time setup

```bash
# 1. provision: static IP, firewall, VM, docker install
make cloud-init

# 2. install llmster on the VM (headless LM Studio) and sign in
make cloud-ssh ARGS='sudo apt-get install -y libatomic1'
make cloud-ssh ARGS='export PATH=/sbin:/usr/sbin:$PATH && curl -fsSL https://lmstudio.ai/install.sh | bash'
make cloud-ssh   # interactive: run `lms daemon up && lms login` and follow
                 # the pairing URL it prints (approve in your browser).

# 3. enable LM Link on the VM and pair with your Mac
make cloud-ssh ARGS='lms link enable'
# Get your Mac's device identifier from your Mac's `lms link status` output
# (the long hex UUID, not the human-readable device name). Then set it as
# the VM's preferred device:
LM_LINK_PEER_ID=<paste-your-mac-uuid-here>
make cloud-ssh ARGS="lms link set-preferred-device ${LM_LINK_PEER_ID}"

# 4. start llmster's local HTTP server on the VM, bound to 0.0.0.0 so the
#    backend container can reach it via host.docker.internal. GCE firewall
#    does not expose :1234 to the public internet.
make cloud-ssh ARGS='lms server start --port 1234 --bind 0.0.0.0'

# 5. wire the cloud env file
cp .env.chartsearch.cloud.example .env.chartsearch.cloud
# Default endpoint http://host.docker.internal:1234/v1/chat/completions
# (LM Link path) — no edit needed unless using a cloud LLM directly.
```

## First-time bring-up (~25 min, mostly Liquibase)

```bash
# 6. build the .omod locally (once)
make chartsearch-build

# 7. push everything to the VM
make cloud-sync

# 8. compose up on the VM, wait for backend healthy, run chartsearch-configure
make cloud-up

# 9. one-time seed of the 5,284-patient corpus from your local DB to the VM (~5-10 min)
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

Rebuilds the `.omod` locally, rsyncs the diff to the VM, restarts only
the backend container (~30-60s), waits for healthy. Test in browser.

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

## Why LM Link (and not a tunnel)

LM Link is LM Studio's distributed inference layer built on Tailscale primitives:
end-to-end encrypted peer-to-peer between your signed-in devices, no public
URL, no rotating tunnel hostnames, no separate auth to manage. The VM-side
llmster appears as a normal OpenAI HTTP server to chartsearchai; under the
hood it routes the inference call to the device that has the model loaded.

Tunneling (cloudflared/ngrok) was an earlier draft of this; LM Link makes
it unnecessary for the local-models use case.

## Cost notes

| Resource | ~Cost (us-central1, on-demand) |
|---|---|
| `e2-standard-4` VM running | ~$0.13/hr → ~$95/mo always-on |
| Same VM stopped | ~$0 compute (boot disk still billed) |
| 50GB `pd-balanced` boot disk | ~$5/mo |
| Static IPv4 (in use) | $0 |
| Static IPv4 (reserved, VM stopped) | ~$1.50/mo |

Stop the VM (`make cloud-stop`) whenever you're not actively testing. The
static IP keeps its address so the browser URL doesn't change between
sessions.

## Troubleshooting

| Symptom | Diagnosis |
|---|---|
| `make cloud-init` exits with "Address already in use" | Static IP exists from a previous run. Re-run is fine; it's idempotent. |
| Backend stuck on `unhealthy` for >10 min | Liquibase is slow first boot. `make cloud-logs SERVICE=backend` to watch. |
| ChartSearch UI shows "Unknown error" | VM-side llmster can't reach Mac. From VM: `lms link status` (peer should be Online) and `curl localhost:1234/v1/models` (should list Mac's models). If empty, restart `lms server` and confirm Mac LM Link is still enabled. |
| `gcloud compute ssh` keeps prompting for a passphrase | One-time: `ssh-add ~/.ssh/google_compute_engine` (macOS keychain) |
| Rsync deletes a file on the VM I didn't want deleted | Sync runs `--delete` — anything not in the local tree (and not excluded) is removed. Add your file to local. |
