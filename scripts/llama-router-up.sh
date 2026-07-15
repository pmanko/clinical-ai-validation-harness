#!/usr/bin/env bash
# Launch the llama.cpp Router Mode server behind med-agent-hub profiles
# (GGUF + OpenAI-compatible API on :8077). Product clients never call it directly.
#
# Why HF_HOME is redirected to an empty dir: build 9430's router auto-publishes
# EVERY model in the HF cache as an extra preset on top of scripts/llama-router.ini
# (with default/untuned settings — no DRY, no seed), and there is no flag to disable
# it. All INI sections use local model= paths (stable symlinks under
# LLAMA_MODEL_DIR -> the real GGUF files), so pointing HF_HOME at an empty dir costs
# nothing at runtime and makes /v1/models == exactly the INI's sections.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMPTY_HF="${HOME}/.cache/llama-router-emptyhf"
MODEL_DIR="${LLAMA_MODEL_DIR:-${HOME}/.cache/llama-router-models}"
RUNTIME_DIR="${ROOT}/artifacts/llama-router"
RUNTIME_MODELS="${RUNTIME_DIR}/models"

if [ ! -d "${MODEL_DIR}" ]; then
  echo "ERROR: LLAMA_MODEL_DIR does not exist: ${MODEL_DIR}" >&2
  echo "Place GGUF files there using the filenames in scripts/llama-router.ini," >&2
  echo "or set LLAMA_MODEL_DIR to an existing model directory." >&2
  exit 1
fi

mkdir -p "${EMPTY_HF}" "${RUNTIME_DIR}"
if [ -e "${RUNTIME_MODELS}" ] && [ ! -L "${RUNTIME_MODELS}" ]; then
  echo "ERROR: ${RUNTIME_MODELS} exists and is not a symlink." >&2
  exit 1
fi
ln -sfn "${MODEL_DIR}" "${RUNTIME_MODELS}"
cd "${ROOT}"

# LLAMA_ROUTER_MODELS_MAX caps how many model instances stay co-resident, and it MUST be
# set per-workload — the tiers have wildly different footprints on this 64G host (Metal
# working-set limit ~48G), and one router can only be tuned for one of them at a time:
#
#   LOW / MED (interactive) — DEFAULT 4. Each turn cycles 4 distinct role-models
#     (orchestrator · expert · synthesizer · validator), all small/mid: LOW ~20G of weights,
#     MED ~34G — both fit co-resident, so 4 keeps every role-switch AND the next turn warm
#     (zero reloads). Anything LESS thrashes: with 4 distinct models cycled in order,
#     max=1/2/3 evicts the very model needed next, so every call reloads from disk (max=1
#     is why even the LOW team was painfully slow).
#
#   HIGH (benchmark) — set LLAMA_ROUTER_MODELS_MAX=1. Its 3 big GGUFs (19G/17G/29G) can't
#     co-reside: any two (~46-48G weights + KV) blow past the ~48G Metal limit and the
#     router thrashes (spawn -> child OOM-dies -> 500). One at a time loads each alone.
#
# Note: on a 64G host you cannot serve LOW/MED co-resident AND HIGH loaded at once
# (LOW+MED weights ~41G + one HIGH model ~29G > 64G) — pick the workload, restart to switch.
exec env HF_HOME="${EMPTY_HF}" llama-server \
  --models-preset "${ROOT}/scripts/llama-router.ini" \
  --models-max "${LLAMA_ROUTER_MODELS_MAX:-4}" --port 8077 --host 0.0.0.0
