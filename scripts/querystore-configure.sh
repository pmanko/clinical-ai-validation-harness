#!/usr/bin/env bash
# Configure Querystore's own embedding assets. This is deliberately separate
# from ChartSearchAI relay configuration because Querystore is one optional hub source.

set -euo pipefail

# shellcheck source=scripts/openmrs-settings-lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openmrs-settings-lib.sh"

MODEL_PATH="${QUERYSTORE_EMBEDDING_MODEL_PATH:-chartsearchai/model.onnx}"
VOCAB_PATH="${QUERYSTORE_EMBEDDING_VOCAB_PATH:-chartsearchai/vocab.txt}"

echo "Configuring Querystore embedding assets at ${OPENMRS_SETTINGS_BASE_URL}:"
set_openmrs_property "querystore.embedding.modelFilePath" "${MODEL_PATH}"
set_openmrs_property "querystore.embedding.vocabFilePath" "${VOCAB_PATH}"
