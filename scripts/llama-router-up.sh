#!/usr/bin/env bash
# Launch the llama.cpp Router Mode server backing the harness chat picker's
# "llama-server" section (GGUF + DRY, OpenAI-compatible, on :8077).
#
# Why HF_HOME is redirected to an empty dir: build 9430's router auto-publishes
# EVERY model in the HF cache as an extra preset on top of scripts/llama-router.ini
# (with default/untuned settings — no DRY, no seed), and there is no flag to disable
# it. All INI sections use local model= paths (stable symlinks under
# ~/.cache/llama-router-models -> the real HF blobs), so pointing HF_HOME at an empty
# dir costs nothing at runtime and makes /v1/models == exactly the INI's sections.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMPTY_HF="${HOME}/.cache/llama-router-emptyhf"
mkdir -p "${EMPTY_HF}"

# LLAMA_ROUTER_MODELS_MAX caps how many model instances stay co-resident. Default
# 2 keeps a second model warm (fast role-switches for small low/med models). Set to
# 1 for the HIGH tier: its 19G/17G/29G GGUFs can't safely co-reside — any two
# (46-48G of weights + KV + compute buffers) exceed Metal's ~48G working-set limit
# on a 64G host, so the router thrashes (spawn → child OOM-dies → 500). One at a
# time loads each big model alone, well under the limit.
exec env HF_HOME="${EMPTY_HF}" llama-server \
  --models-preset "${ROOT}/scripts/llama-router.ini" \
  --models-max "${LLAMA_ROUTER_MODELS_MAX:-2}" --port 8077 --host 0.0.0.0
