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

exec env HF_HOME="${EMPTY_HF}" llama-server \
  --models-preset "${ROOT}/scripts/llama-router.ini" \
  --models-max 2 --port 8077 --host 0.0.0.0
