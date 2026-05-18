#!/usr/bin/env bash
# GCE startup script — runs once on first boot as root. Installs docker
# engine + the compose v2 plugin via the official convenience script, and
# adds the project's SSH user(s) to the docker group so `docker` works
# without sudo for the rsync'd compose flows.
#
# This file is uploaded as instance metadata (startup-script) by
# scripts/cloud-init.sh; GCE re-runs it on every boot, so steps are
# idempotent.

set -euo pipefail
exec >>/var/log/harness-cloud-startup.log 2>&1
echo "==> harness-cloud-startup $(date -Iseconds)"

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y curl ca-certificates rsync
  curl -fsSL https://get.docker.com | sh
fi

# Add every user that has logged in (or might) to the docker group.
for u in $(awk -F: '$3 >= 1000 && $1 != "nobody" { print $1 }' /etc/passwd); do
  usermod -aG docker "${u}" 2>/dev/null || true
done

systemctl enable --now docker

echo "==> docker version: $(docker --version)"
echo "==> compose version: $(docker compose version 2>/dev/null || echo missing)"
