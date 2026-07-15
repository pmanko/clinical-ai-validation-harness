#!/bin/sh
# Backend runtime init for the harness — chartsearchai's own backend-init.sh, minus the local-LLM
# GGUF download: chartsearchai has no bundled local engine (chartsearchai.llm.engine is remote-only),
# so only Querystore's ONNX embedding model is needed here.
# Everything else mirrors targets/chartsearchai/backend-init.sh.
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
# points at chartsearchai/model.onnx relative to the app data directory. The path
# name is retained for data-volume compatibility; ChartSearchAI does not load it.
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

exec /openmrs/startup.sh
