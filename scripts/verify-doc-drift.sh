#!/usr/bin/env bash
# Verify that current docs/comments/scripts do not describe removed ChartSearchAI
# architecture as current behavior. Historical planning artifacts may keep old
# details only when they are clearly marked historical/superseded.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

python3 <<'PY'
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()

FORBIDDEN = [
    (re.compile(r"\bLocalLlmEngine\b"), "embedded local LLM engine"),
    (re.compile(r"\bllama-server-natives\b"), "bundled llama-server native module"),
    (re.compile(r"\b(?:embedded|bundled|in-process) llama-server\b", re.I), "bundled llama-server"),
    (re.compile(r"\btoken-by-token\b|\btoken chunks\b", re.I), "token streaming wording"),
    (re.compile(r"\bindepth_token\b|\bonInDepthToken\b|\bonToken\b"), "removed token event/callback"),
    (re.compile(r"(?:ws/rest/v1/)?chartsearchai/warmup\b|value\s*=\s*[\"']/warmup[\"']|\bwarmupEnabled\b", re.I), "removed ChartSearchAI warmup path"),
    (re.compile(r"\bchartSnapshot\b|\bchartMappingsJson\b|\brefresh-chart\b"), "removed session chart snapshot path"),
    (re.compile(r"\bCitationGroundingVerifier\b"), "removed Java citation grounding"),
    (re.compile(r"chartsearchai\.grounding\."), "removed ChartSearchAI grounding GP"),
    (re.compile(r"chartsearchai\.drugReference|chartsearchai\.drugSafety"), "removed ChartSearchAI drug safety GP"),
    (re.compile(r"chartsearchai\.embedding\.preFilter|chartsearchai\.querystore\.topK"), "old ChartSearchAI retrieval ownership"),
    (re.compile(r"chartsearchai\.llm\.systemPrompt|chartsearchai\.llm\.modelFilePath"), "old ChartSearchAI prompt/model ownership"),
    (re.compile(r"chartsearchai\.llm\.(?:remote\.)?(?:endpointUrl|modelName)"), "old direct-provider ChartSearchAI configuration"),
    (re.compile(r"chartsearchai\.hub\.profileId"), "duplicate ChartSearchAI profile default"),
    (re.compile(r"chartsearchai\.cacheTtlMinutes|chartsearchai\.llm\.timeoutSeconds"), "old ChartSearchAI LLM/cache ownership"),
    (re.compile(r"CHARTSEARCH_REMOTE_(?:ENDPOINT_URL|MODEL_NAME|ENDPOINTS)|CHARTSEARCH_LLM_ENGINE"), "old direct-provider ChartSearchAI configuration"),
    (re.compile(r"MED_AGENT_(?:ORCHESTRATOR_MODEL|MED_MODEL)"), "removed environment-driven profile role models"),
    (re.compile(r"single-model path uses chartsearchAI|chartsearchai.*generates cited answers", re.I), "old ChartSearchAI answer ownership"),
    (re.compile(r"LLM inference.*stays in chartsearchai|quality layer stays in chartsearchai|All query-time logic stays where it is", re.I), "old ChartSearchAI inference/context ownership"),
    (re.compile(r"model sees the whole chart|whole chart.*unfiltered", re.I), "stale unbounded full-chart claim"),
    (re.compile(r"whole chart per turn|every query retrieves the patient chart from querystore", re.I), "stale universal Querystore claim"),
    (re.compile(r"per-level [`']?drug_safety[`']? knob|drug_safety.*default off", re.I), "stale product drug-safety policy"),
    (re.compile(r"let the hub manage its llama\.cpp", re.I), "ambiguous local process ownership"),
    (re.compile(r"GCP_FIREWALL_DENY_LMS|GCP_LMS_PORT"), "retired cloud model-server firewall"),
    (re.compile(r"value\s*=\s*\"/search\"|/search/stream|chartsearchai/search/stream"), "removed search stream path"),
    (re.compile(r"\bRemoteLlmEngine\b"), "removed direct-provider Java engine"),
    (re.compile(r"\bLlmProvider\.search\b"), "removed Java answer orchestration"),
    (re.compile(r"\bModelSwitchService\b"), "removed Java model switching"),
    (re.compile(r"\bPROMPT_INJECTION\b"), "removed Java prompt-content blocklist"),
    (re.compile(r"\b(?:ORCHESTRATOR_MODEL|SYNTHESIZER_MODEL|MED_MODEL)\b"), "removed global role-model setting"),
    (re.compile(r"\bbundled-LLM compatibility\b", re.I), "old bundled-LLM compatibility wording"),
    (re.compile(r"\borchestrator-as-validator\b", re.I), "stale role-model label"),
    (re.compile(r"\btemporal_facts\.v\d"), "versioned internal temporal-facts contract"),
]

TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".adoc", ".sh", ".bash", ".zsh", ".py", ".java",
    ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".json", ".properties",
}
TEXT_NAMES = {"README", "README.md", "Makefile", "Dockerfile", "Dockerfile.gateway", "CLAUDE.md", "AGENTS.md", ".env.med-agent-hub.example", ".env.chartsearch.example"}

SKIP_DIR_PARTS = {
    ".git", "node_modules", "target", "dist", "build", ".pytest_cache", ".mypy_cache",
    "__pycache__", ".venv", "venv",
}

ALWAYS_ALLOW = {
    "scripts/verify-doc-drift.sh",
    "scripts/verify-stage-refactor-gates.sh",
    "scripts/verify-hub-consolidation-gates.sh",
    "tests/test_hub_consolidation_gate_script.py",
    "tests/test_chartsearchai_local.py",
    "specs/artifacts/planning/hub-consolidation-roadmap.md",
    "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/ArchitectureGuardTest.java",
}

HISTORICAL_MARKER = re.compile(
    r"^\s*(?:(?:>|//|/\*+|\*)\s*)?(?:#+\s*)?(?:\*\*)?(?:(?:status\s*:\s*)?"
    r"(?:historical|superseded|archived|pre[- ]?refactor))\b",
    re.I | re.M,
)

REQUIRED_CURRENT = {
    "README.md": (
        r"med-agent-hub",
        r"single-e4b-checked",
    ),
    "adapters/chartsearchai/README.md": (
        r"authorization, session, persistence, and streaming",
        r"make chartsearch-test",
    ),
    "adapters/querystore/README.md": (
        r"optional med-agent-hub patient-context source",
        r"make querystore-test-integration",
    ),
    "specs/006-validation-harness-mvp/spec.md": (
        r"hub product `profile` through ChartSearchAI",
        r"low-level leg experiments",
        r"separately attributed Scout judgments",
    ),
    "targets/chartsearchai/README.md": (
        r"authorizes the patient request",
        r"relays exactly one request to med-agent-hub",
    ),
    "targets/chartsearchai-esm/README.md": (
        r"does not choose provider endpoints",
        r"answer_done.*answer_validation.*indepth_pending",
    ),
    "targets/med-agent-hub/README.md": (
        r"client-facing clinical answer service",
        r"Every product Answer receives deterministic",
        r"Every product In-Depth claim receives deterministic",
    ),
    "targets/querystore/docs/rest-api.md": (
        r"GET `/ws/rest/v1/querystore/patientrecord`",
        r"external services such as med-agent-hub",
        r"A Querystore reindex is already running",
        r"use the REST `scope:\"type\"` trigger",
    ),
    "targets/querystore/docs/chartsearchai-port-map.md": (
        r"Status: historical and superseded",
        r"med-agent-hub owns clinical context\s*(?:>\s*)?assembly",
    ),
    "targets/querystore/docs/migration-chartsearchai.md": (
        r"Status: historical and superseded",
        r"ChartSearchAI is a thin OpenMRS",
    ),
    "targets/chartsearchai/docs/embedding-improvement-plan.md": (
        r"complete evidence ledger",
        r"Oversized charts are reduced by the\s+hub's deterministic selector",
    ),
}


def run(args: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True)


def submodule_paths() -> list[Path]:
    try:
        raw = run(["git", "config", "--file", ".gitmodules", "--get-regexp", r"submodule\..*\.path"])
    except subprocess.CalledProcessError:
        return []
    paths = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) == 2:
            paths.append(ROOT / parts[1])
    return paths


def tracked_files(repo: Path) -> list[Path]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo,
    )
    files = []
    for part in raw.split(b"\0"):
        if not part:
            continue
        rel = Path(part.decode())
        if any(p in SKIP_DIR_PARTS for p in rel.parts):
            continue
        files.append(rel)
    return files


def should_scan(rel: Path) -> bool:
    return (
        rel.name in TEXT_NAMES
        or rel.suffix in TEXT_SUFFIXES
        or rel.name.startswith("Dockerfile")
        or (rel.name.startswith(".env.") and rel.name.endswith(".example"))
    )


def header_is_historical(text: str) -> bool:
    return bool(HISTORICAL_MARKER.search("\n".join(text.splitlines()[:12])))


repos = [ROOT] + submodule_paths()
repo_names = [str(p.relative_to(ROOT)) if p != ROOT else "." for p in repos]
print("Scanning repos:")
for name in repo_names:
    print(f"  - {name}")

violations: list[str] = []
historical_hits = 0

for repo in repos:
    repo_prefix = "" if repo == ROOT else str(repo.relative_to(ROOT)) + "/"
    for rel in tracked_files(repo):
        rel_key = repo_prefix + rel.as_posix()
        if rel_key in ALWAYS_ALLOW or not should_scan(rel):
            continue
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            continue

        matches = []
        for pattern, label in FORBIDDEN:
            if pattern.search(text):
                matches.append(label)
        if not matches:
            continue

        if header_is_historical(text):
            historical_hits += 1
            continue

        violations.append(f"{rel_key}: {', '.join(sorted(set(matches)))}")

if violations:
    print("\nDocumentation drift violations:")
    for violation in violations:
        print(f"  - {violation}")
    print("\nFix current-path language, or move/mark genuinely historical material.")
    sys.exit(1)

required_violations = []
for rel_key, patterns in REQUIRED_CURRENT.items():
    path = ROOT / rel_key
    if not path.is_file():
        required_violations.append(f"{rel_key}: required current document is missing")
        continue
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        if not re.search(pattern, text, re.I | re.S):
            required_violations.append(f"{rel_key}: missing current-architecture statement /{pattern}/")

if required_violations:
    print("\nRequired current-architecture statements missing:")
    for violation in required_violations:
        print(f"  - {violation}")
    sys.exit(1)

print(f"PASS: scanned {len(repos)} repos; historical marked files allowed: {historical_hits}")
PY
