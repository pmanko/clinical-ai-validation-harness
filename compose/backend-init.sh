#!/bin/sh
# Harness backend initialization: prepare QueryStore's embedding assets, then
# start OpenMRS. The parent setup command owns inference-provider configuration;
# this image does not download GGUF weights for the bundled native model server.
#
# When started as root (no separate init container chowns the volume), heal
# pre-uid-1001 root-owned contents and drop to the openmrs user. The OpenMRS
# process always runs as uid 1001.
set -eu

if [ "$(id -u)" = "0" ]; then
  chown -R 1001:1001 /openmrs/data 2>/dev/null || true
  exec runuser -u openmrs -- "$0" "$@"
fi

MODEL_DIR="/openmrs/data/chartsearchai"
mkdir -p "$MODEL_DIR"

# Embedding model (all-MiniLM-L6-v2, ~86MB). querystore.embedding.modelFilePath
# points at chartsearchai/model.onnx relative to the app data directory. The path
# name is retained for data-volume compatibility; ChartSearchAI does not load it.
HF_EMBED="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

prepare_embedding_file() (
  target="$MODEL_DIR/$1"
  relative_path="$2"
  expected="$3"
  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ ! -f "$target" ] || [ ! -s "$target" ]; then
      echo "Unusable existing embedding asset: $target; not replaced. Restore it explicitly." >&2
      exit 1
    fi
    if printf '%s  %s\n' "$expected" "$target" | sha256sum -c >/dev/null 2>&1; then
      echo "Verified existing embedding asset: $1"
    else
      echo "Retaining existing embedding asset: $1 (unverified against the pinned default)."
    fi
    exit 0
  fi

  staged="$(mktemp "$MODEL_DIR/.$1.XXXXXX")"
  trap 'rm -f "$staged"' 0
  trap 'exit 130' INT
  trap 'exit 143' TERM
  echo "Downloading embedding asset: $1"
  curl -fsSL --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 600 --output "$staged" "$HF_EMBED/$relative_path"
  if ! printf '%s  %s\n' "$expected" "$staged" | sha256sum -c >/dev/null 2>&1; then
    echo "Embedding asset checksum failed: $1; nothing installed." >&2
    exit 1
  fi
  # A hard link installs complete bytes without replacing a concurrent writer's file.
  ln "$staged" "$target"
  echo "Installed verified embedding asset: $1"
)

prepare_embedding_file model.onnx onnx/model.onnx \
  6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452
prepare_embedding_file vocab.txt vocab.txt \
  07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3

exec /openmrs/startup.sh
