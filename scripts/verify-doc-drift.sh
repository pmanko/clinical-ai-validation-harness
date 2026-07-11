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
    (re.compile(r"chartsearchai\.cacheTtlMinutes|chartsearchai\.llm\.timeoutSeconds"), "old ChartSearchAI LLM/cache ownership"),
    (re.compile(r"CHARTSEARCH_REMOTE_(?:ENDPOINT_URL|MODEL_NAME|ENDPOINTS)|CHARTSEARCH_LLM_ENGINE"), "old direct-provider ChartSearchAI configuration"),
    (re.compile(r"GCP_FIREWALL_DENY_LMS|GCP_LMS_PORT"), "retired cloud model-server firewall"),
    (re.compile(r"value\s*=\s*\"/search\"|/search/stream|chartsearchai/search/stream"), "removed search stream path"),
]

TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".adoc", ".sh", ".bash", ".zsh", ".py", ".java",
    ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".json", ".properties",
}
TEXT_NAMES = {"README", "README.md", "Makefile", "Dockerfile", "Dockerfile.gateway", "CLAUDE.md", "AGENTS.md"}

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
    "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/ArchitectureGuardTest.java",
}

HISTORICAL_PATH_HINTS = (
    "docs/adr.md",
    "docs/migration-querystore-plan.md",
    "specs/artifacts/",
    "specs/research/",
    "specs/004-real-adapter-entrypoints/",
    "specs/007-llm-config-overrides/",
    ".env.chartsearch.cloud.example",
    "scripts/cloud-up.sh",
)
HISTORICAL_MARKER = re.compile(
    r"historical|superseded|pre[- ]?refactor|predates|archive|snapshot",
    re.I,
)


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


def is_historical(rel_key: str) -> bool:
    return any(hint in rel_key for hint in HISTORICAL_PATH_HINTS)


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

        if is_historical(rel_key) and HISTORICAL_MARKER.search(text):
            historical_hits += 1
            continue

        violations.append(f"{rel_key}: {', '.join(sorted(set(matches)))}")

if violations:
    print("\nDocumentation drift violations:")
    for violation in violations:
        print(f"  - {violation}")
    print("\nFix current-path language, or move/mark genuinely historical material.")
    sys.exit(1)

print(f"PASS: scanned {len(repos)} repos; historical marked files allowed: {historical_hits}")
PY
