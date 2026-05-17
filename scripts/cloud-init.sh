#!/usr/bin/env bash
# Provision the chartsearch harness VM in GCE: reserve a static IP, create
# the instance with docker pre-installed (via startup script), open the
# proxy HTTP port to the world, and bootstrap SSH access.
#
# Idempotent — re-runs detect existing resources and skip creation.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

echo "==> targeting project=${GCP_PROJECT} zone=${GCP_ZONE} vm=${GCP_VM_NAME}"

# 1. Reserve a static external IP so the VM can be stopped without losing its
#    public address (browser URL stays stable across iterations).
if ! gcloud compute addresses describe "${GCP_STATIC_IP_NAME}" \
       --region="${GCP_REGION}" --project="${GCP_PROJECT}" \
       --format='value(name)' >/dev/null 2>&1; then
  echo "==> reserving static IP ${GCP_STATIC_IP_NAME} in ${GCP_REGION}"
  gcloud compute addresses create "${GCP_STATIC_IP_NAME}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT}" --quiet
else
  echo "    static IP ${GCP_STATIC_IP_NAME} already reserved"
fi
STATIC_IP="$(gcloud compute addresses describe "${GCP_STATIC_IP_NAME}" \
  --region="${GCP_REGION}" --project="${GCP_PROJECT}" --format='value(address)')"
echo "    address: ${STATIC_IP}"

# 2. Firewall rule for the proxy port (HTTP from anywhere). SSH on :22 is
#    already covered by the default-allow-ssh rule that ships with every
#    new GCP project's `default` network.
if ! gcloud compute firewall-rules describe "${GCP_FIREWALL_HTTP}" \
       --project="${GCP_PROJECT}" --format='value(name)' >/dev/null 2>&1; then
  echo "==> creating firewall rule ${GCP_FIREWALL_HTTP} (TCP/${GCP_HTTP_PORT} from 0.0.0.0/0)"
  gcloud compute firewall-rules create "${GCP_FIREWALL_HTTP}" \
    --network=default \
    --direction=INGRESS \
    --action=ALLOW \
    --rules="tcp:${GCP_HTTP_PORT}" \
    --source-ranges=0.0.0.0/0 \
    --target-tags=harness-http \
    --project="${GCP_PROJECT}" --quiet
else
  echo "    firewall rule ${GCP_FIREWALL_HTTP} already exists"
fi

# 3. Create the instance with a startup script that installs docker.
if gcp_vm_exists; then
  echo "    instance ${GCP_VM_NAME} already exists (status: $(gcp_vm_status)); skipping create"
else
  echo "==> creating instance ${GCP_VM_NAME} (${GCP_MACHINE_TYPE}, ${GCP_BOOT_DISK_SIZE} pd-balanced)"
  gcloud compute instances create "${GCP_VM_NAME}" \
    --project="${GCP_PROJECT}" \
    --zone="${GCP_ZONE}" \
    --machine-type="${GCP_MACHINE_TYPE}" \
    --image-family="${GCP_IMAGE_FAMILY}" \
    --image-project="${GCP_IMAGE_PROJECT}" \
    --boot-disk-size="${GCP_BOOT_DISK_SIZE}" \
    --boot-disk-type=pd-balanced \
    --address="${STATIC_IP}" \
    --tags=harness-http \
    --metadata-from-file=startup-script="${ROOT}/scripts/cloud-startup.sh" \
    --quiet
fi

# 4. Wait for the startup script (docker install) to finish.
echo "==> waiting for VM to boot + docker to install (up to 3 min)"
for i in $(seq 1 36); do
  status="$(gcp_vm_status)"
  if [ "${status}" = "RUNNING" ]; then
    # Probe sshd directly — cloud-init may still be mid-flight even after RUNNING.
    if nc -z -w 2 "${STATIC_IP}" 22 2>/dev/null; then
      echo "    sshd reachable after $((i*5))s"
      break
    fi
  fi
  sleep 5
done

# 5. Bootstrap SSH key. First gcloud-mediated ssh creates the user account
#    (${GCP_SSH_USER}) on the VM via project-level SSH keys. The startup
#    script's awk loop adds existing users to the docker group, but our user
#    didn't exist yet at first boot — so add it explicitly now.
gcp_ssh_keygen_once

echo "==> adding ${GCP_SSH_USER} to docker group (needs new SSH session to take effect)"
gcp_ssh 'sudo usermod -aG docker $USER && sudo systemctl restart docker' || \
  echo "    warning: docker group assignment failed; may need manual sudo"

# 6. Confirm docker is up on the VM. This opens a FRESH SSH session — the
#    one above's group change only applies to subsequent logins.
echo "==> verifying docker on VM (fresh SSH session picks up the docker group)"
if gcp_ssh 'docker --version && docker compose version && docker ps' 2>&1; then
  echo "    docker ready"
else
  echo "    warning: docker not ready yet — startup script may still be running,"
  echo "    or the group change hasn't propagated. Re-check with:"
  echo "      make cloud-ssh ARGS='docker ps'"
fi

echo ""
echo "VM ready. External IP: ${STATIC_IP}"
echo "Browser will be:       http://${STATIC_IP}:${GCP_HTTP_PORT}/openmrs/spa"
echo "Next:                  make cloud-sync && make cloud-up"
