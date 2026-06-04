#!/usr/bin/env bash
# Launch the llama-router serving every GGUF arm on :8077 (the picker's "llama-server"
# section + the med-agent-hub team roles when pointed here).
#
# Self-healing: (re)builds the model symlinks from the HF cache before launch, so a
# vanished ~/.cache/llama-router-models/ can't silently break the INI's `model =` paths.
# Each model must already be in the HF cache — pull a missing one with:
#   llama-server -hf <repo>:Q4_K_M --no-warmup
#
# HF_HOME is redirected to an empty dir so the router advertises ONLY the INI presets,
# not every other repo in the real HF cache. --models-max 2 bounds resident GGUFs (64GB
# safety); the router queues/evicts across calls rather than 400-ing, so the HIGH team's
# three big models serialize (slow) instead of failing on an eviction race.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HF_HUB="${HOME}/.cache/huggingface/hub"
LINKS="${HOME}/.cache/llama-router-models"
EMPTY_HF="${HOME}/.cache/llama-router-emptyhf"
mkdir -p "${LINKS}" "${EMPTY_HF}"

# section-name : HF cache repo dir : gguf filename glob (first match wins, incl. shard 1)
MODELS=(
  "gemma-e4b:models--unsloth--gemma-4-E4B-it-GGUF:*Q4_K_M.gguf"
  "gemma-26b-a4b:models--unsloth--gemma-4-26B-A4B-it-GGUF:*Q4_K_M.gguf"
  "medgemma-4b:models--unsloth--medgemma-1.5-4b-it-GGUF:*Q4_K_M.gguf"
  "medgemma-27b:models--unsloth--medgemma-27b-text-it-GGUF:*Q4_K_M.gguf"
  "qwen2.5-14b:models--bartowski--Qwen2.5-14B-Instruct-GGUF:*Q4_K_M.gguf"
  "qwen2.5-32b:models--bartowski--Qwen2.5-32B-Instruct-GGUF:*Q4_K_M.gguf"
  "qwen3.6-35b:models--unsloth--Qwen3.6-35B-A3B-GGUF:*Q4_K_M.gguf"
)
for entry in "${MODELS[@]}"; do
  name="${entry%%:*}"; rest="${entry#*:}"; repo="${rest%%:*}"; glob="${rest#*:}"
  gguf="$(find "${HF_HUB}/${repo}/snapshots" -name "${glob}" 2>/dev/null | sort | head -1 || true)"
  if [[ -z "${gguf}" ]]; then
    echo "ERROR: no ${glob} under ${HF_HUB}/${repo}" >&2
    echo "       pull it first:  llama-server -hf ${repo#models--}:Q4_K_M --no-warmup" | sed 's#--#/#' >&2
    exit 1
  fi
  ln -sfn "${gguf}" "${LINKS}/${name}.gguf"
done

exec env HF_HOME="${EMPTY_HF}" llama-server \
  --models-preset "${ROOT}/scripts/llama-router.ini" \
  --models-max 2 \
  --port 8077 --host 0.0.0.0
