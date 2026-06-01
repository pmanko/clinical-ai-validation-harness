#!/usr/bin/env bash
# PreToolUse self-guard: deny edits to the TDD-gate config so the gate cannot be
# silently removed by an agent. Fail-OPEN by design — any extraction error yields
# an empty target, which does not match, so the edit is allowed (exit 0). Only an
# edit whose file_path positively resolves to the gate config is blocked (exit 2).
payload="$(cat 2>/dev/null)"
target="$(printf '%s' "$payload" | python3 -c 'import sys, json
try:
    d = json.load(sys.stdin)
    print((d.get("tool_input") or {}).get("file_path", ""))
except Exception:
    print("")' 2>/dev/null)"
case "$target" in
  */.claude/settings.json | */.claude/hooks/protect-tdd-config.sh)
    echo "Blocked: the TDD-gate config (.claude/settings.json, .claude/hooks/) is protected. A human must edit it directly." >&2
    exit 2
    ;;
esac
exit 0
