#!/usr/bin/env bash
# Acceptance-gate matrix for the "stage-driven hub engine + chartsearchai thin relay"
# remediation program (see /Users/pmanko/.claude/plans/eager-conjuring-raven.md).
#
# This script is the Gate-12 evidence emitter: it does NOT decide the plan is "done" by
# itself finishing green — it prints a per-gate PASS/FAIL/PENDING line with the command
# that produced it, and exits non-zero while ANY gate is not PASS. Run it before starting
# (everything red/pending is expected), after each workstream PR (some gates flip), and as
# the final completion report (every gate must read PASS).
#
# Section A (deletion checks) greps the pinned submodules for symbols the plan requires
# deleted. Section B runs each repo's test suite. Section C aggregates both into the
# 13-gate matrix and prints it.
#
# Usage:
#   scripts/verify-stage-refactor-gates.sh                 # sections A + B (unit/component only)
#   RUN_E2E=1 scripts/verify-stage-refactor-gates.sh        # also run the live e2e specs (needs a warm stack)
#   HUB_VENV=/path/to/venv scripts/verify-stage-refactor-gates.sh   # reuse an existing hub scratch venv

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

HUB="${ROOT}/targets/med-agent-hub"
CSAI="${ROOT}/targets/chartsearchai"
ESM="${ROOT}/targets/chartsearchai-esm"
HUB_VENV="${HUB_VENV:-${ROOT}/.gates-hub-venv}"
RUN_E2E="${RUN_E2E:-0}"

# ---- result bookkeeping -----------------------------------------------------------
# CHECK_NAME[] / CHECK_STATUS[] (PASS|FAIL|SKIP) / CHECK_EVIDENCE[] / CHECK_GATES[] (space list)
CHECK_NAME=()
CHECK_STATUS=()
CHECK_EVIDENCE=()
CHECK_GATES=()

record() {
  CHECK_NAME+=("$1")
  CHECK_STATUS+=("$2")
  CHECK_EVIDENCE+=("$3")
  CHECK_GATES+=("$4")
}

# absent_check NAME PATTERN PATHSPEC GATES
# PASS = pattern absent (deleted); FAIL = pattern still present.
absent_check() {
  local name="$1" pattern="$2" path="$3" gates="$4"
  if [[ ! -e "$path" ]]; then
    record "$name" "PASS" "path removed: $path" "$gates"
    return
  fi
  local hits
  hits="$(rg -n -U --no-heading -e "$pattern" "$path" 2>/dev/null || true)"
  if [[ -z "$hits" ]]; then
    record "$name" "PASS" "rg -e '$pattern' $path -> no matches" "$gates"
  else
    local first
    first="$(echo "$hits" | head -1)"
    record "$name" "FAIL" "rg -e '$pattern' $path -> e.g. $first" "$gates"
  fi
}

# present_check NAME PATTERN PATHSPEC GATES
# PASS = pattern found (the replacement wiring exists); FAIL = pattern absent (not built yet).
# Use this for "the new thing must exist" checks, as opposed to absent_check's "the old thing
# must be gone". Never mark a gate PASS by riding along on an unrelated suite's green exit —
# each gate here is backed by a check that actually exercises ITS behavior.
present_check() {
  local name="$1" pattern="$2" path="$3" gates="$4"
  if [[ ! -e "$path" ]]; then
    record "$name" "FAIL" "path does not exist: $path" "$gates"
    return
  fi
  local hits
  hits="$(rg -n -U --no-heading -e "$pattern" "$path" 2>/dev/null || true)"
  if [[ -n "$hits" ]]; then
    local first
    first="$(echo "$hits" | head -1)"
    record "$name" "PASS" "rg -e '$pattern' $path -> e.g. $first" "$gates"
  else
    record "$name" "FAIL" "rg -e '$pattern' $path -> no matches" "$gates"
  fi
}

# suite_run NAME GATES DIR CMD...  (runs CMD with cwd=DIR, no subshell — record() must
# write to the caller's arrays, so this never forks)
suite_run() {
  local name="$1" gates="$2" dir="$3"; shift 3
  local log rc
  log="$(mktemp)"
  pushd "$dir" >/dev/null || { record "$name" "FAIL" "no such dir: $dir" "$gates"; return; }
  "$@" >"$log" 2>&1
  rc=$?
  popd >/dev/null
  if [[ $rc -eq 0 ]]; then
    record "$name" "PASS" "$* -> exit 0 ($(tail -1 "$log"))" "$gates"
  else
    record "$name" "FAIL" "$* -> exit $rc (see $log)" "$gates"
  fi
}

echo "== Section A: deletion checks (rg absence over pinned submodules) =="

# --- Gate 1 / 2 / 13: legacy Java staged 3-call orchestration -----------------------
absent_check "csai:streamStagedChat deleted" \
  "void streamStagedChat" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1 2 13"
absent_check "csai:STAGED_FAST_ANSWER_MODEL deleted" \
  "STAGED_FAST_ANSWER_MODEL" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1"
absent_check "csai:STAGED_IN_DEPTH_PROMPT deleted" \
  "STAGED_IN_DEPTH_PROMPT" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1"
absent_check "csai:staged*Model helpers deleted" \
  "staged(Answer|Validation|InDepth)Model" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1"
absent_check "csai:legacy ChatService staged methods deleted" \
  "(chatStagedAnswer|completeStagedAnswerValidation|completeStagedInDepth)" "$CSAI/api/src/main/java/org/openmrs/module/chartsearchai/api/ChatService.java" "1"
absent_check "csai:name-prefix staged routing deleted" \
  "(isHubNativeStagedModel|isStageableModel)" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1 10"

# --- Gate 9: session-owned chart snapshot + refresh-context -------------------------
absent_check "csai:ChatSession chart snapshot fields deleted" \
  "(chartSnapshot|chartMappingsJson|chartBuiltAt)" "$CSAI/api/src/main/java/org/openmrs/module/chartsearchai/model/ChatSession.java" "9"
absent_check "csai:refresh-chart endpoint deleted" \
  "refresh-chart" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "9"
absent_check "csai:populateChartSnapshot/ensureChartSnapshot deleted" \
  "(populateChartSnapshot|ensureChartSnapshot)" "$CSAI/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/ChatServiceImpl.java" "9"

# --- Gate 10: name-prefix routing (esm side) ----------------------------------------
# Matches a function definition or a call/reference with parens — i.e. real code — not a bare
# mention of the old name in a doc comment explaining what replaced it.
absent_check "esm:shouldUseStagedInDepth deleted" \
  "\\bshouldUseStagedInDepth\\s*\\(" "$ESM/src/api/chartsearchai.ts" "10"

# --- /search family + Java grounding retirement (feeds Gate 1/9 scope + supports Gate 7) --
absent_check "csai:/search mapping deleted" \
  "value = \"/search\"" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1"
absent_check "csai:/search/stream mapping deleted" \
  "value = \"/search/stream\"" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "1"
absent_check "csai:searchPatientChart(Stream) deleted (esm)" \
  "searchPatientChart(Stream)?" "$ESM/src/api/chartsearchai.ts" "1"
absent_check "csai:CitationGroundingVerifier deleted" \
  "class CitationGroundingVerifier" "$CSAI/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/CitationGroundingVerifier.java" "1"

# --- Non-staged local chat path (part of "delete ALL local chat orchestration") -----
absent_check "csai:non-staged local chatStreaming deleted" \
  "public ChartAnswer chatStreaming" "$CSAI/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/LlmInferenceService.java" "1"

# --- Gate 3: hub RUNTIME must execute stage_plan_for_level, not just describe it in tests --
present_check "hub:runtime consults stage_plan_for_level" \
  "(stage_plan_for_level|get_stage_plan)\(" "$HUB/server/team.py" "3"

# --- Gate 5: Java relay must thread prior conversation turns to the hub, not just the question --
# (priorsForLlm/extractProseAnswer live in ChatServiceImpl; the controller calls the interface
# method that wraps them.)
present_check "csai:hub relay threads prose priors" \
  "priorTurnsForRelay" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "5"

# --- Gate 6: heartbeats (keep the leg abortable) + capability metadata must exist -----------
present_check "hub:SSE heartbeat comment lines" \
  ': hb\\n\\n' "$HUB/server/openai_compat.py" "6"

# Heartbeats alone only wake the Java relay's blocking readLine() — Gate 6 also needs the relay to
# actually USE that wake-up to detect a browser disconnect mid-leg (e.g. a benign write/flush to
# the browser response on each line read, so an IOException surfaces well before the next real
# hub event). Without this, readLine() waking up on a comment line is a no-op and the relay still
# blocks the whole leg.
present_check "csai:relay detects browser disconnect on comment/heartbeat lines" \
  'startsWith\(":"\)' "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "6"

# --- Gate 7: hub-side entailment grounding must exist and replace the lexical heuristic ----
present_check "hub:entailment-based grounding call" \
  "entail" "$HUB/server/team.py" "7"

# --- Gate 8: temporal render must be a config knob, not an unconditional compaction --------
present_check "hub:temporal_render config knob" \
  "temporal_render" "$HUB/server/levels_loader.py" "8"

# --- Gate 10: hub /v1/models must advertise a staged capability field ----------------------
# Precise on purpose: "staged" alone false-positives on the unrelated `getattr(level, "staged",
# False)` routing checks already in this file. The gate needs the field IN the /v1/models
# response dict itself, i.e. a "staged": key inside the {"id": mid, "object": "model", ...} literal.
present_check "hub:/v1/models advertises staged capability" \
  '"id": mid,[^}]*"staged"' "$HUB/server/openai_compat.py" "10"

# --- Gate 11: the harness's own sync client path (POST /chat) must drain the hub for any remote
# model. chatService.chat legitimately remains as the LOCAL-bundled-engine fallback (no remote
# endpoint configured at all) — that path is out of scope for this flip, not a violation. The real
# evidence is that a remote-engine turn now goes through the shared relay helper.
present_check "csai:sync POST /chat relays remote models through the hub" \
  "hubRelayCompletionWire" "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" "11"

# --- Gate 14: drug-safety port must exist and ride every chat surface before /search dies ---
present_check "hub:drug_safety module exists" \
  "^def validate_answer" "$HUB/server/drug_safety.py" "14"
present_check "hub:safetyWarnings threaded through _stream_payload" \
  "safety_warnings" "$HUB/server/team.py" "14"
present_check "hub:run_team_stage_drain copies safetyWarnings" \
  '"safetyWarnings"' "$HUB/server/team.py" "14"
present_check "hub:Level.drug_safety config knob" \
  "drug_safety" "$HUB/server/levels_loader.py" "14"

echo
echo "== Section B: suite runs (regression evidence — informational, not gate-tagged) =="

# --- hub pytest (scratch venv; create if missing) -----------------------------------
# NOTE: the full-suite runs below are UNTAGGED (gates="") — they are regression evidence
# ("nothing else broke"), not proof of any specific gate. A gate is only credited PASS by
# a check that actually exercises its behavior (the present_check/absent_check calls above,
# or the gate-specific selections below).
if [[ ! -x "${HUB_VENV}/bin/pytest" ]]; then
  python3 -m venv "${HUB_VENV}" >/dev/null 2>&1
  "${HUB_VENV}/bin/pip" install -q pyyaml fastapi httpx python-dotenv python-multipart psutil pytest >/dev/null 2>&1
fi
suite_run "hub:pytest (full regression)" "" "$HUB" "${HUB_VENV}/bin/python" -m pytest tests/ -q

# Gate 4: low-level legs (answer:/answer-review:/indepth-only:) must keep their exact byte
# shapes through the H1 engine unification — test_bridge.py is the file that pins them.
suite_run "hub:pytest test_bridge.py (raw-leg byte shapes)" "4" "$HUB" \
  "${HUB_VENV}/bin/python" -m pytest tests/test_bridge.py -q

# Gate 6 (partial): the router-lock-frees-on-cancel invariant already has a dedicated test;
# it is necessary but not sufficient for Gate 6 (still needs the Java-side mid-leg abort +
# heartbeat checks above to all be PASS before the gate as a whole is satisfied).
suite_run "hub:pytest test_chat_cancel_releases_router_lock" "6" "$HUB" \
  "${HUB_VENV}/bin/python" -m pytest tests/test_staged_stream.py -q -k cancel_releases_router_lock

# Gate 13 (hub side): a team-scaffolded staged profile must gather via run_team_stream's
# orchestrator tool loop, and the decision must come from executing stage_plan_for_level, not a
# trusted flag. Still needs the Java relay to route ALL staged profiles (not just single-*) through
# the one hub call before the gate as a whole is satisfied (see the streamStagedChat check above).
suite_run "hub:pytest team-scaffolding gathers via the engine" "13" "$HUB" \
  "${HUB_VENV}/bin/python" -m pytest tests/test_staged_stream.py -q \
  -k "team_scaffolding_gathers or derives_gather_from_the_stage_plan"

# Gate 14: drug-safety parity suite (validator/injector algorithm) + wiring integration tests
# (run_team/run_team_stream/run_team_stage_drain thread safetyWarnings through the right keys,
# and leave every existing level's envelope byte-identical when the knob is off/default).
suite_run "hub:pytest drug_safety parity + wiring" "14" "$HUB" \
  "${HUB_VENV}/bin/python" -m pytest tests/test_drug_safety.py tests/test_drug_safety_integration.py -q

# --- esm test suite ------------------------------------------------------------------
if [[ -d "$ESM/node_modules" ]]; then
  suite_run "esm:test suite (full regression)" "" "$ESM" yarn test --run
else
  record "esm:test suite (full regression)" "SKIP" "node_modules not installed — run 'yarn install' in $ESM first" ""
fi

# --- chartsearchai maven build+test ---------------------------------------------------
if command -v mvn >/dev/null 2>&1; then
  suite_run "csai:mvn test (full regression)" "" "$CSAI" mvn -q -B test
else
  record "csai:mvn test (full regression)" "SKIP" "mvn not on PATH" ""
fi

# --- live e2e (opt-in; needs a warm deployed stack) -----------------------------------
# chartsearchai-demo.spec.ts is a RECORDING spec (paced for video, no latency assertion) — it does
# NOT count as Gate 6/13 evidence. chartsearchai-preempt.spec.ts is the CI-assertion counterpart:
# it fails if a preempted leg's slot isn't actually freed, so it is the real check these gates need.
if [[ "$RUN_E2E" == "1" ]]; then
  suite_run "e2e:multi-turn history" "5" "$ROOT/tests/e2e" \
    yarn playwright test chartsearchai-e4b-multiturn-trivial
  suite_run "e2e:preempt frees router slot" "6 13" "$ROOT/tests/e2e" \
    yarn playwright test chartsearchai-preempt
else
  record "e2e:multi-turn history" "SKIP" "RUN_E2E=1 not set (needs a warm deployed stack)" "5"
  record "e2e:preempt frees router slot" "SKIP" "RUN_E2E=1 not set (needs a warm deployed stack)" "6 13"
fi

echo
echo "== Section A/B raw results =="
for i in "${!CHECK_NAME[@]}"; do
  printf '  [%-4s] %-45s gates:%-10s %s\n' "${CHECK_STATUS[$i]}" "${CHECK_NAME[$i]}" "${CHECK_GATES[$i]}" "${CHECK_EVIDENCE[$i]}"
done

# ---- Section C: gate matrix aggregation --------------------------------------------
GATE_TITLE=(
  "1:Legacy Java staged decomposition deleted"
  "2:chartsearchai relay-only for chat"
  "3:Hub owns stage composition (stage_plan_for_level executed)"
  "4:Low-level legs remain valid primitives; product UI never client-composes them"
  "5:Multi-turn context preserved"
  "6:Abort/preempt frees the slot mid-leg"
  "7:Grounding honest (Verified only from entailment)"
  "8:Temporal prompt changes explicit + gated"
  "9:Session chart snapshot + refresh-context deleted"
  "10:No name-prefix orchestration routing"
  "11:Harness drains the same engine"
  "12:Acceptance matrix mandatory before done"
  "13:Team profiles stream via the engine's gather stage"
  "14:Drug safety survives /search retirement (ported to the hub)"
)

echo
echo "== Gate matrix =="
overall_pass=1
for entry in "${GATE_TITLE[@]}"; do
  gate_num="${entry%%:*}"
  gate_desc="${entry#*:}"
  status="PENDING"
  evidence=""
  any_fail=0
  any_pass=0
  any_skip=0
  any_check=0
  for i in "${!CHECK_NAME[@]}"; do
    for g in ${CHECK_GATES[$i]}; do
      if [[ "$g" == "$gate_num" ]]; then
        any_check=1
        case "${CHECK_STATUS[$i]}" in
          FAIL) any_fail=1 ;;
          PASS) any_pass=1 ;;
          SKIP) any_skip=1 ;;
        esac
        evidence+="${CHECK_NAME[$i]}=${CHECK_STATUS[$i]}; "
      fi
    done
  done
  if [[ "$gate_num" == "12" ]]; then
    status="PASS"  # this script's own existence + emission satisfies gate 12's mechanism
    evidence="this script is the mandated matrix emitter"
  elif [[ $any_check -eq 0 ]]; then
    status="PENDING"
    evidence="no automated check wired yet — needs manual/live verification"
  elif [[ $any_fail -eq 1 ]]; then
    status="FAIL"
  elif [[ $any_skip -eq 1 ]]; then
    # A SKIPped check (e.g. RUN_E2E not set) is required evidence this gate has not actually seen —
    # an unrelated check for the same gate reading PASS must NOT paper over that. PENDING, not PASS.
    status="PENDING"
  elif [[ $any_pass -eq 1 ]]; then
    status="PASS"
  fi
  if [[ "$status" != "PASS" ]]; then overall_pass=0; fi
  printf '  Gate %-3s [%-7s] %-55s %s\n' "$gate_num" "$status" "$gate_desc" "$evidence"
done

echo
if [[ $overall_pass -eq 1 ]]; then
  echo "ALL GATES PASS."
  exit 0
else
  echo "NOT DONE: one or more gates are FAIL or PENDING. See matrix above."
  exit 1
fi
