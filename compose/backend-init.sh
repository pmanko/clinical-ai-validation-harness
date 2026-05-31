#!/bin/sh
# Backend runtime init for the harness — chartsearchai's own backend-init.sh,
# with the local-engine GGUF download removed (the harness runs the remote chat
# engine, so only the ONNX embedding model is needed — read by BOTH querystore
# and chartsearchai). Everything else mirrors targets/chartsearchai/backend-init.sh.
#
# When started as root (no separate init container chowns the volume), heal
# pre-uid-1001 root-owned contents and drop to the openmrs user. The OpenMRS
# process always runs as uid 1001.
if [ "$(id -u)" = "0" ]; then
  chown -R 1001:1001 /openmrs/data 2>/dev/null || true
  exec runuser -u openmrs -- "$0" "$@"
fi

MODEL_DIR="/openmrs/data/chartsearchai"
mkdir -p "$MODEL_DIR"

# Embedding model (all-MiniLM-L6-v2, ~86MB). querystore.embedding.modelFilePath
# and chartsearchai.embedding.modelFilePath both point at chartsearchai/model.onnx
# (relative to the app data dir). Downloaded once if absent; persisted in the
# data volume.
ONNX_FILE="$MODEL_DIR/model.onnx"
VOCAB_FILE="$MODEL_DIR/vocab.txt"
HF_EMBED="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main"

if [ ! -f "$ONNX_FILE" ]; then
  echo "Downloading all-MiniLM-L6-v2 ONNX model (~86MB)..."
  curl -fsSL -o "$ONNX_FILE" "$HF_EMBED/onnx/model.onnx"
  echo "Embedding model downloaded."
fi

if [ ! -f "$VOCAB_FILE" ]; then
  echo "Downloading all-MiniLM-L6-v2 vocab..."
  curl -fsSL -o "$VOCAB_FILE" "$HF_EMBED/vocab.txt"
  echo "Vocab downloaded."
fi

# Local-engine GGUF — downloaded only when CHARTSEARCH_LLM_ENGINE=local (the
# bundled llama-server path). The harness default is `remote` (no 5GB pull).
# Mirrors chartsearchai's own backend-init.sh: resumable background download so
# OpenMRS can become healthy without waiting; chart search returns errors until
# the .partial is renamed. The module's chartsearchai.llm.modelFilePath GP (set
# by chartsearch-configure.sh for local) points at this filename.
if [ "${CHARTSEARCH_LLM_ENGINE:-remote}" = "local" ]; then
  LLM_FILE="$MODEL_DIR/gemma-4-E4B-it-Q4_K_M.gguf"
  LLM_PARTIAL="$LLM_FILE.partial"
  HF_LLM="https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"
  if [ ! -f "$LLM_FILE" ]; then
    if [ -f "$LLM_PARTIAL" ]; then
      echo "Resuming Gemma 4 E4B Q4_K_M download (~5GB) in background..."
    else
      echo "Starting Gemma 4 E4B Q4_K_M download (~5GB) in background; local chart search is unavailable until it completes..."
    fi
    (
      # --speed-time/--speed-limit aborts a stalled transfer (HF hangs the
      # socket without closing it); curl -C - resumes on the next start.
      if curl -fsSL -C - --speed-time 60 --speed-limit 1024 -o "$LLM_PARTIAL" "$HF_LLM"; then
        mv "$LLM_PARTIAL" "$LLM_FILE"
        echo "LLM model downloaded."
      else
        echo "LLM model download failed; will retry on next container start."
      fi
    ) &
  fi
fi

exec /openmrs/startup.sh
