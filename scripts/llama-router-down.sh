#!/usr/bin/env bash
# Stop the managed local llama.cpp router started by `llama-router-up.sh --daemon`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${LLAMA_ROUTER_RUNTIME_DIR:-${ROOT}/artifacts/llama-router}"
PID_FILE="${RUNTIME_DIR}/router.pid"

if [ "$(uname -s)" = "Darwin" ] && command -v launchctl >/dev/null 2>&1; then
  launchctl remove org.openclinai.llama-router >/dev/null 2>&1 || true
elif [ -f "${PID_FILE}" ]; then
  ROUTER_PID="$(cat "${PID_FILE}")"
  case "${ROUTER_PID}" in
    ''|*[!0-9]*)
      echo "WARN: ignoring invalid router PID: ${ROUTER_PID}" >&2
      ;;
    *)
      ROUTER_COMMAND="$(ps -p "${ROUTER_PID}" -o command= 2>/dev/null || true)"
      case "${ROUTER_COMMAND}" in
        *llama-server*"--models-preset ${ROOT}/scripts/llama-router.ini"*"--port 8077"*)
          kill "${ROUTER_PID}" >/dev/null 2>&1 || true
          ;;
        '')
          if kill -0 "${ROUTER_PID}" >/dev/null 2>&1; then
            echo "WARN: refusing to stop unverified PID ${ROUTER_PID}" >&2
          fi
          ;;
        *)
          echo "WARN: refusing to stop unverified PID ${ROUTER_PID}" >&2
          ;;
      esac
      ;;
  esac
fi

rm -f "${PID_FILE}"
echo "llama.cpp router stopped"
