#!/usr/bin/env bash
# Live monitor for a validate run: progress + which GGUF models the llama-router
# has resident right now (the LM-Studio-style "loaded models" view).
#
#   watch -n 3 scripts/validate-monitor.sh      # live, refreshes every 3s
#   scripts/validate-monitor.sh                 # one-shot
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# newest run dir (robust against an aliased `ls`)
RUN=$(for d in "$ROOT"/artifacts/validate/*/; do
        [ -d "$d" ] && printf '%s %s\n' "$(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d" 2>/dev/null)" "${d%/}"
      done | sort -rn | head -1 | cut -d' ' -f2-)
rows=$(wc -l < "$RUN/results.jsonl" 2>/dev/null | tr -d ' ' || echo 0)

echo "RUN  $(basename "$RUN")   rows=${rows:-0}   $(date '+%H:%M:%S')"
tail -1 "$RUN/results.jsonl" 2>/dev/null | python3 -c "import sys,json
try:
    r=json.load(sys.stdin); m=r.get('metrics',{})
    print(f\"  last: {r['scenario_id']} / {r['backend_id']}  status={m.get('http_status')} chars={m.get('answer_chars')}\")
except Exception: pass"

echo "MODELS RESIDENT (llama-router GGUF handles):"
lsof -c llama-server 2>/dev/null | grep -oE "[A-Za-z0-9._-]+\.gguf" | sort -u | sed 's/^/  • /'
[ -z "$(lsof -c llama-server 2>/dev/null | grep -c '\.gguf')" ] && true
