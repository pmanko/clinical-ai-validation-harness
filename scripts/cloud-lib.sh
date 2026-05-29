#!/usr/bin/env bash
# Shared constants + helpers for cloud-* scripts. Sourced, not executed.
#
# All values are env-overridable so operators can target a different project,
# zone, machine size, or VM name without editing this file. Defaults assume
# the clinical-ai-harness project in us-central1.

# shellcheck disable=SC2034   # consumed by sourcing scripts

GCP_PROJECT="${GCP_PROJECT:-clinical-ai-harness}"
GCP_ZONE="${GCP_ZONE:-us-central1-a}"
GCP_REGION="${GCP_REGION:-${GCP_ZONE%-*}}"
GCP_VM_NAME="${GCP_VM_NAME:-harness-chartsearch}"
GCP_MACHINE_TYPE="${GCP_MACHINE_TYPE:-e2-standard-4}"
GCP_BOOT_DISK_SIZE="${GCP_BOOT_DISK_SIZE:-50GB}"
GCP_IMAGE_FAMILY="${GCP_IMAGE_FAMILY:-debian-12}"
GCP_IMAGE_PROJECT="${GCP_IMAGE_PROJECT:-debian-cloud}"
GCP_STATIC_IP_NAME="${GCP_STATIC_IP_NAME:-${GCP_VM_NAME}-ip}"
GCP_FIREWALL_HTTP="${GCP_FIREWALL_HTTP:-allow-harness-http}"
GCP_HTTP_PORT="${GCP_HTTP_PORT:-8088}"
# Firewall source range for the proxy port. Defaults to the operator's
# current public IP (single /32) so the dev URL isn't world-open while the
# stack ships with admin/Admin123. To open to the world (e.g. a demo),
# explicitly export GCP_HTTP_CIDR=0.0.0.0/0. Auto-discovered IP fetched
# lazily by cloud-init via gcp_http_cidr().

# Remote path layout on the VM (under the SSH user's home).
GCP_REMOTE_REPO="${GCP_REMOTE_REPO:-clinical-ai-validation-harness}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Local SSH user is what gcloud compute ssh creates on the VM by default
# (project-level SSH keys, no OS Login). Override if your project enables OSL.
GCP_SSH_USER="${GCP_SSH_USER:-${USER}}"
GCP_SSH_KEY="${GCP_SSH_KEY:-${HOME}/.ssh/google_compute_engine}"

gcp_vm_exists() {
  gcloud compute instances describe "${GCP_VM_NAME}" \
    --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
    --format='value(name)' >/dev/null 2>&1
}

gcp_vm_status() {
  gcloud compute instances describe "${GCP_VM_NAME}" \
    --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
    --format='value(status)' 2>/dev/null || echo "MISSING"
}

gcp_vm_ip() {
  gcloud compute instances describe "${GCP_VM_NAME}" \
    --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
    --format='value(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null
}

gcp_ssh() {
  # Direct ssh using the gcloud-managed key. Falls back to `gcloud compute ssh`
  # if the key file isn't there yet (first-run bootstrap path).
  local ip
  ip="$(gcp_vm_ip)"
  if [ -z "${ip}" ]; then
    echo "error: VM ${GCP_VM_NAME} has no external IP (is it running?)" >&2
    return 1
  fi
  if [ -f "${GCP_SSH_KEY}" ]; then
    ssh -i "${GCP_SSH_KEY}" \
        -o StrictHostKeyChecking=accept-new \
        -o UserKnownHostsFile="${HOME}/.ssh/known_hosts" \
        -o ConnectTimeout=10 \
        "${GCP_SSH_USER}@${ip}" "$@"
  else
    gcloud compute ssh "${GCP_VM_NAME}" \
      --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
      --quiet --command="$*"
  fi
}

gcp_ssh_keygen_once() {
  # Force gcloud to mint / register the SSH key pair if it isn't there yet.
  if [ ! -f "${GCP_SSH_KEY}" ]; then
    echo "==> bootstrapping SSH key via gcloud compute ssh"
    gcloud compute ssh "${GCP_VM_NAME}" \
      --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
      --quiet --command='true'
  fi
}

gcp_http_cidr() {
  # Resolve the source range for the proxy HTTP firewall rule. Honors an
  # explicit GCP_HTTP_CIDR override; otherwise pins to the operator's
  # current public IP. Aborts if neither is available — refuses to default
  # to 0.0.0.0/0 silently because the stack ships with admin/Admin123.
  if [ -n "${GCP_HTTP_CIDR:-}" ]; then
    echo "${GCP_HTTP_CIDR}"
    return 0
  fi
  local ip
  ip="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [ -z "${ip}" ]; then
    echo "error: could not auto-detect public IP for firewall source range." >&2
    echo "       Set GCP_HTTP_CIDR=<your-ip>/32 (or 0.0.0.0/0 to open to world)." >&2
    return 1
  fi
  echo "${ip}/32"
}

gcp_reconcile_http_firewall() {
  # Reconcile the proxy HTTP firewall rule's source range to the operator's
  # current public IP (or explicit GCP_HTTP_CIDR override). Called by both
  # cloud-init (initial create) and cloud-up (every bring-up, in case the
  # operator's IP shifted on DHCP / coffee-shop / home network).
  #
  # If the firewall rule does not yet exist, returns silently — cloud-init
  # is the only path that creates it. cloud-up calls this purely to update.
  local desired_cidr current_cidr
  if ! desired_cidr="$(gcp_http_cidr)"; then
    return 1
  fi
  current_cidr="$(gcloud compute firewall-rules describe "${GCP_FIREWALL_HTTP}" \
                    --project="${GCP_PROJECT}" \
                    --format='value(sourceRanges)' 2>/dev/null || echo '')"
  if [ -z "${current_cidr}" ]; then
    # Rule doesn't exist yet; cloud-init owns creation.
    return 0
  fi
  # gcloud returns sourceRanges as a semicolon-separated string when multiple;
  # we set exactly one. Normalize whitespace for the compare.
  current_cidr="$(echo "${current_cidr}" | tr -d '[:space:]')"
  if [ "${current_cidr}" = "${desired_cidr}" ]; then
    echo "    firewall ${GCP_FIREWALL_HTTP} source range already ${desired_cidr}"
    return 0
  fi
  echo "==> reconciling firewall ${GCP_FIREWALL_HTTP}: ${current_cidr} → ${desired_cidr}"
  gcloud compute firewall-rules update "${GCP_FIREWALL_HTTP}" \
    --source-ranges="${desired_cidr}" \
    --project="${GCP_PROJECT}" --quiet
}
