#!/usr/bin/env bash
# Build the CPU router from the deployed upstream revision plus its reviewed fix.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
UPSTREAM_REVISION=12127defda4f41b7679cb2477a4b0d65ee6a0c8f
PATCH="${ROOT}/patches/catalyst-router-cancellation.patch"
OUTPUT="${CATALYST_ROUTER_BUILD_OUTPUT:-${ROOT}/artifacts/catalyst-router-build}"
PLATFORM="${CATALYST_ROUTER_BUILD_PLATFORM:-linux/arm64}"
mkdir -p "${OUTPUT}"
SOURCE="$(mktemp -d "${TMPDIR:-/tmp}/catalyst-router-build.XXXXXX")"
trap 'rm -rf "${SOURCE}"' EXIT

git -C "${SOURCE}" init -q
git -C "${SOURCE}" fetch -q --depth 1 https://github.com/ggml-org/llama.cpp.git "${UPSTREAM_REVISION}"
git -C "${SOURCE}" checkout -q --detach FETCH_HEAD
test "$(git -C "${SOURCE}" rev-parse HEAD)" = "${UPSTREAM_REVISION}"
git -C "${SOURCE}" apply --check "${PATCH}"
git -C "${SOURCE}" apply "${PATCH}"
PATCH_SHA="$(shasum -a 256 "${PATCH}" | awk '{print $1}')"

docker build --platform "${PLATFORM}" --target server \
  --file "${SOURCE}/.devops/cpu.Dockerfile" \
  --build-arg "APP_REVISION=${UPSTREAM_REVISION}" \
  --build-arg APP_VERSION=b10015-cancellation-fix \
  --label "org.openclinai.router.patch-sha256=${PATCH_SHA}" \
  --iidfile "${OUTPUT}/image-id.txt" "${SOURCE}"

python3 - "${OUTPUT}" "${UPSTREAM_REVISION}" "${PATCH_SHA}" "${PLATFORM}" <<'PY'
import json
from pathlib import Path
import re
import sys

output, revision, patch, platform = sys.argv[1:]
output = Path(output)
image = (output / "image-id.txt").read_text().strip()
assert re.fullmatch(r"sha256:[a-f0-9]{64}", image), image
(output / "build.json").write_text(json.dumps({
    "imageId": image, "upstreamRevision": revision,
    "patchSha256": patch, "platform": platform,
}, indent=2) + "\n")
print(f"Built {image}; run the cancellation probe before rollout.")
print(f"export CATALYST_ROUTER_IMAGE={image}")
PY
