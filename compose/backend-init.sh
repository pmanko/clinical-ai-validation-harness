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

# No local-engine GGUF download here: the harness uses chartsearchai.llm.engine=remote.

exec /openmrs/startup.sh
