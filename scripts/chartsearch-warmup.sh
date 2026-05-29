#!/usr/bin/env bash
# Pre-load LM Studio models with the right context length so chartsearchai's
# requests don't trigger JIT-reload-with-default-context (which is 4096 unless
# overridden).
#
# Reads from .env.chartsearch:
#   CHARTSEARCH_WARMUP_MODELS    comma-separated model identifiers (matches `lms ls` / /v1/models)
#                                default: just CHARTSEARCH_REMOTE_MODEL_NAME if set
#   CHARTSEARCH_CONTEXT_LENGTH   tokens; default 32768
#   CHARTSEARCH_WARMUP_TTL       idle seconds before LM Studio auto-unloads a warmed model, freeing
#                                RAM for JIT loads of other models (timer resets on each request, so
#                                a model in active use stays warm). default 3600; set 0 to pin until
#                                restart. NOTE: LM Studio never evicts an explicitly-loaded model under
#                                memory pressure (only this idle-TTL unload), so the warmed base set
#                                plus the largest model you JIT-load must still fit in RAM together.
#   CHARTSEARCH_REMOTE_ENDPOINT_URL  used to derive LM Studio host (the /v1/chat/completions URL)
#
# Side effects:
# 1. `lms load <model> -c <ctx> [--ttl <s>]` for each model (idle-TTL unload; pinned until restart if TTL=0)
# 2. Writes ~/.lmstudio/.internal/user-concrete-model-default-config/.../<gguf>.json
#    so the context survives LM Studio restart + JIT-reload (persistent — until user clears it)

set -uo pipefail   # don't `set -e` — a failed `lms load` shouldn't stop warming up the rest

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [ -f .env.chartsearch ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.chartsearch
  set +a
fi

MODELS="${CHARTSEARCH_WARMUP_MODELS:-${CHARTSEARCH_REMOTE_MODEL_NAME:-}}"
CTX="${CHARTSEARCH_CONTEXT_LENGTH:-32768}"
TTL="${CHARTSEARCH_WARMUP_TTL:-3600}"
TTL_ARGS=""
if [ -n "${TTL}" ] && [ "${TTL}" != "0" ]; then
  TTL_ARGS="--ttl ${TTL}"
fi

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
    "${LMS}" load "${model}" -c "${CTX}" ${TTL_ARGS} 2>&1 | tail -2 | sed 's/^/    /' \
      || echo "    warn: load failed for ${model}"
  fi
  write_default_for_model "${model}" "${CTX}"
done

echo ""
echo "Current loaded models:"
"${LMS}" ps 2>&1 | sed 's/^/  /'
