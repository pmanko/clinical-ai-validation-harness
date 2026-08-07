#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/targets/chartsearchai-esm"

yarn test
yarn typescript
yarn lint
yarn build
