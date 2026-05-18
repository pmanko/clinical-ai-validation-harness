#!/usr/bin/env bash
# Pre-load LM Studio models with the right context length so chartsearchai's
# requests don't trigger JIT-reload-with-default-context (which is 4096 unless
# overridden).
#
# Reads from .env.chartsearch:
#   CHARTSEARCH_WARMUP_MODELS    comma-separated model identifiers (matches `lms ls` / /v1/models)
#                                default: just CHARTSEARCH_REMOTE_MODEL_NAME if set
#   CHARTSEARCH_CONTEXT_LENGTH   tokens; default 32768
#   CHARTSEARCH_REMOTE_ENDPOINT_URL  used to derive LM Studio host (the /v1/chat/completions URL)
#
# Side effects:
# 1. `lms load <model> -c <ctx>` for each model (ephemeral — until LM Studio restart or manual unload)
# 2. Writes ~/.lmstudio/.internal/user-concrete-model-default-config/.../<gguf>.json
#    so the context survives LM Studio restart + JIT-reload (persistent — until user clears it)

set -uo pipefail   # don't `set -e` — a failed `lms load` shouldn't stop warming up the rest

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# Preserve command-line env over .env.chartsearch file values (the obvious
# "override the file" path). `set -a; . file; set +a` would otherwise clobber
# pre-exported vars.
__OVR_MODELS="${CHARTSEARCH_WARMUP_MODELS:-}"
__OVR_REMOTE_MODEL="${CHARTSEARCH_REMOTE_MODEL_NAME:-}"
__OVR_CTX="${CHARTSEARCH_CONTEXT_LENGTH:-}"
if [ -f .env.chartsearch ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.chartsearch
  set +a
fi
[ -n "${__OVR_MODELS}" ]       && CHARTSEARCH_WARMUP_MODELS="${__OVR_MODELS}"
[ -n "${__OVR_REMOTE_MODEL}" ] && CHARTSEARCH_REMOTE_MODEL_NAME="${__OVR_REMOTE_MODEL}"
[ -n "${__OVR_CTX}" ]          && CHARTSEARCH_CONTEXT_LENGTH="${__OVR_CTX}"

MODELS="${CHARTSEARCH_WARMUP_MODELS:-${CHARTSEARCH_REMOTE_MODEL_NAME:-}}"
CTX="${CHARTSEARCH_CONTEXT_LENGTH:-32768}"

if [ -z "${MODELS}" ]; then
  echo "error: no models to warm up. Set CHARTSEARCH_WARMUP_MODELS (comma-separated) or CHARTSEARCH_REMOTE_MODEL_NAME in .env.chartsearch"
  exit 1
fi

LMS="${LMS:-lms}"
if ! command -v "${LMS}" >/dev/null 2>&1; then
  if [ -x "$HOME/.lmstudio/bin/lms" ]; then
    LMS="$HOME/.lmstudio/bin/lms"
  else
    echo "error: lms CLI not found. Install LM Studio + run \`lms bootstrap\` or set LMS env var to the binary path."
    exit 1
  fi
fi

DEFAULTS_DIR="$HOME/.lmstudio/.internal/user-concrete-model-default-config"
MODELS_DIR="$HOME/.lmstudio/models"

write_default_for_model() {
  local model_id="$1"
  local ctx="$2"

  # Resolve the model's GGUF file path from its identifier. The identifier may
  # already include the publisher prefix (e.g. "unsloth/gemma-4-e4b-it") or be
  # the model's id under the publisher's default (e.g. "gemma-4-e2b-it").
  # We search for any GGUF whose path matches.
  local hit
  hit=$(find "${MODELS_DIR}" -name '*.gguf' 2>/dev/null \
    | grep -i -- "/${model_id##*/}" \
    | grep -v 'mmproj' \
    | head -1 || true)

  if [ -z "${hit}" ]; then
    echo "    warn: couldn't locate GGUF for ${model_id} under ${MODELS_DIR}; skipping persistent default"
    return 0
  fi

  # The default-config path mirrors the GGUF path under MODELS_DIR:
  #   $MODELS_DIR/<pub>/<repo>/<file>.gguf
  #   $DEFAULTS_DIR/<pub>/<repo>/<file>.gguf.json
  local rel="${hit#${MODELS_DIR}/}"
  local target="${DEFAULTS_DIR}/${rel}.json"

  mkdir -p "$(dirname "${target}")"
  cat > "${target}" <<JSON
{"preset":"","operation":{"fields":[]},"load":{"fields":[{"key":"llm.load.contextLength","value":${ctx}}]}}
JSON
  echo "    persistent default written: ${target} (contextLength=${ctx})"
}

already_loaded() {
  local id="$1"
  # `lms ps` lists identifiers in first column. An exact match means it's
  # loaded; partial match (e.g. ":2" suffix) means a previous load was
  # incomplete and we should skip rather than spawn duplicates.
  "${LMS}" ps 2>/dev/null | awk -v want="$id" '
    NR > 1 && $1 == want { found = 1 }
    END { exit (found ? 0 : 1) }
  '
}

echo "Warming up LM Studio models (context=${CTX}):"
IFS=',' read -ra MODEL_LIST <<<"${MODELS}"
for raw_model in "${MODEL_LIST[@]}"; do
  model=$(echo "${raw_model}" | xargs)  # trim
  [ -z "${model}" ] && continue
  echo "  [${model}]"
  if already_loaded "${model}"; then
    echo "    already loaded — skipping load (will refresh persistent default below)"
  else
    "${LMS}" load "${model}" -c "${CTX}" 2>&1 | tail -2 | sed 's/^/    /' \
      || echo "    warn: load failed for ${model}"
  fi
  write_default_for_model "${model}" "${CTX}"
done

echo ""
echo "Current loaded models:"
"${LMS}" ps 2>&1 | sed 's/^/  /'
