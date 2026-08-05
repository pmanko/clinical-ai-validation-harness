#!/usr/bin/env bash
# Backward-compatible ChartSearchAI publisher.
# Usage: validate-publish.sh <run_id> <slug> [title] [summary] [takeaway]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="${1:?usage: validate-publish.sh <run_id> <slug> [title] [summary] [takeaway]}"
shift
exec "${ROOT}/scripts/publish-report.sh" \
  chartsearchai "${ROOT}/artifacts/validate/${RUN}" "$@"
