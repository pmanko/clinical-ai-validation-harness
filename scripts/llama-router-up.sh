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
