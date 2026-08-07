#!/usr/bin/env python3
"""Evaluate the full dual-provider parity acceptance contract.

Static requirements are checked against source and owner tests. Claims that need a
running stack require a fresh, exact-head evidence manifest with gate-evaluated
assertions and hash-bound artifacts. This module owns both foundation and full
evaluation; the shell file is only the stable command-line entrypoint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


GATES = tuple(f"G{number:02d}" for number in range(3, 23))
EVIDENCE_SCHEMA = "dual_provider_parity_evidence.v1"
CONFORMANCE_SCHEMA = "dual_provider_conformance.v1"

REPOSITORY_PATHS = {
    "harness": ".",
    "med-agent-hub": "targets/med-agent-hub",
    "querystore": "targets/querystore",
    "chartsearchai": "targets/chartsearchai",
    "chartsearchai-esm": "targets/chartsearchai-esm",
}

LIVE_OBSERVATIONS = {
    "G04": ("bundled_without_hub", "hub_without_bundled_model", "no_silent_fallback"),
    "G05": (
        "single_provider_picker_hidden",
        "multi_provider_picker_visible",
        "provider_switch_new_conversation",
    ),
    "G06": (
        "bundled_local_turn",
        "bundled_remote_turn",
        "bundled_query_scoped",
        "bundled_full_chart",
        "bundled_stream",
        "bundled_warmup_cache",
    ),
    "G07": ("full_and_ranked_read_semantics",),
    "G08": ("etag_304", "chart_change_new_snapshot", "mixed_snapshot_rejected"),
    "G09": ("hub_without_querystore", "alternate_source_contract"),
    "G10": ("context_policy_parity",),
    "G12": ("cache_scope_isolation", "failed_revalidation_no_stale_serve"),
    "G14": ("temporal_gate_relay",),
    "G15": (
        "review_rewrite_regated",
        "final_answer_grounded",
        "prior_turn_citation_isolation",
    ),
    "G16": ("drug_safety_checked", "drug_safety_limited", "drug_safety_unavailable"),
    "G17": ("provider_picker", "validation_and_evidence_visible", "reload_hydration"),
    "G18": ("new_turn_preemption", "disconnect_cancellation", "single_row_settled"),
    "G19": (
        "low_confidence_visible",
        "rejected_output_inspectable",
        "evidence_resolved",
        "no_silent_downgrade",
    ),
    "G20": ("pr_descriptions_aligned",),
    "G21": ("required_ci", "real_path_smoke", "code_qa", "publication_prs"),
    "G22": ("evaluation_metadata_complete",),
}

REQUIRED_FILES = {
    "G04": (
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/BundledClinicalAnswerProvider.java",
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/HubClinicalAnswerProvider.java",
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/ClinicalAnswerProviderRegistry.java",
    ),
    "G06": (
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/LocalLlmEngine.java",
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/RemoteLlmEngine.java",
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/LocalLlmEngineTest.java",
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/LlmInferenceServiceWarmupIntegrationTest.java",
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/QueryStoreChartBuilderScopedTest.java",
        "targets/chartsearchai/omod/src/test/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestControllerTest.java",
    ),
    "G07": (
        "targets/querystore/api/src/test/java/org/openmrs/module/querystore/serialization/DateFixtures.java",
        "targets/querystore/api/src/test/java/org/openmrs/module/querystore/serialization/PatientRecordSerializerTest.java",
        "targets/querystore/omod/src/test/java/org/openmrs/module/querystore/web/rest/PatientRecordEndpointTest.java",
    ),
    "G10": (
        "scripts/parity-engine-diff.py",
        "targets/querystore/api/src/test/java/org/openmrs/module/querystore/api/impl/ContextSliceTest.java",
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/QueryStoreChartBuilderScopedTest.java",
        "targets/med-agent-hub/tests/test_context_sources.py",
    ),
    "G11": (
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/ChartTooLargeException.java",
        "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/InsufficientContextException.java",
    ),
    "G19": (
        "scripts/probe-chartsearchai-relay.py",
        "tests/e2e/specs/chartsearchai-demo.spec.ts",
        "tests/e2e/specs/chartsearchai-low-confidence-review.spec.ts",
        "tests/e2e/specs/chartsearchai-preempt.spec.ts",
    ),
    "G21": (
        "scripts/verify-stage-refactor-gates.sh",
        "scripts/verify-hub-consolidation-gates.sh",
        "tests/test_dual_provider_conformance_contract.py",
    ),
    "G22": (
        "harness/validate/runner.py",
        "harness/validate/hub_trace.py",
        "harness/validate/stage_timings.py",
        "scripts/build-product-evaluation-evidence.py",
        "tests/test_run_meta.py",
        "tests/test_stage_timings.py",
        "tests/test_product_evaluation_evidence.py",
    ),
}

# Each tuple is (path, required regexes). These assertions intentionally point to
# owner tests as well as implementation so a class name alone cannot satisfy a gate.
REQUIRED_PATTERNS = {
    "G04": ((
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/ProviderRegistryConformanceTest.java",
        (r"provider_not_ready", r"provider_not_enabled"),
    ),),
    "G05": (
        (
            "targets/chartsearchai/omod/src/test/java/org/openmrs/module/chartsearchai/web/rest/ProviderRestContractTest.java",
            (r"defaultProvider", r"pickerVisible", r"startNew"),
        ),
        (
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/conversation/ConversationServicePersistenceTest.java",
            (r"provider switching must start a new conversation",),
        ),
        (
            "targets/chartsearchai-esm/src/components/provider-picker.test.tsx",
            (
                r"renders nothing when only one provider",
                r"starts a new conversation on switch",
                r"never a silent fallback",
            ),
        ),
    ),
    "G07": (
        (
            "targets/querystore/api/src/main/java/org/openmrs/module/querystore/serialization/PatientRecordSerializer.java",
            (r"getClinicalDate", r"getDateKind"),
        ),
        (
            "targets/querystore/api/src/main/java/org/openmrs/module/querystore/serialization/AbstractRecordSerializer.java",
            (r"getLastModified", r"setLastModified"),
        ),
        (
            "targets/querystore/api/src/test/java/org/openmrs/module/querystore/backend/mysql/MysqlBackendStoreIntegrationTest.java",
            (r"findPatientChart_marksAHandledPerTableFailureIncomplete", r"isTruncated"),
        ),
    ),
    "G08": (
        (
            "targets/querystore/omod/src/test/java/org/openmrs/module/querystore/web/rest/PatientRecordEndpointTest.java",
            (r"getETag", r"snapshotChanges"),
        ),
        (
            "targets/med-agent-hub/tests/test_querystore_client.py",
            (r"rejects_a_snapshot_id_that_changes_mid_page", r"InconsistentSnapshotError"),
        ),
    ),
    "G09": (
        (
            "targets/med-agent-hub/server/context_sources.py",
            (r"class InlineChartSource", r"class StaticKnowledgeSource", r"class QueryStoreSource"),
        ),
        (
            "targets/med-agent-hub/tests/test_context_sources.py",
            (r"InlineChartSource", r"StaticKnowledgeSource", r"querystore.*unavailable|without_querystore"),
        ),
    ),
    "G10": (("scripts/parity-engine-diff.py", (r"mandatory_core_parity", r"retrieval")),),
    "G11": (
        (
            "targets/med-agent-hub/tests/test_context_budget.py",
            (r"mandatory_overflow_returns_insufficient_context", r"token"),
        ),
        (
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/impl/QueryStoreChartBuilderBudgetTest.java",
            (r"mandatory", r"InsufficientContext"),
        ),
    ),
    "G12": (
        (
            "targets/med-agent-hub/server/context_sources.py",
            (r"cache_key = \(self\.client\.base_url, self\.client\.username, request\.patient\)",),
        ),
        (
            "targets/med-agent-hub/server/patient_ledger_cache.py",
            (r"snapshot_id", r"Never serves a cached ledger after a failed fetch"),
        ),
        (
            "targets/med-agent-hub/tests/test_patient_ledger_cache.py",
            (r"every_call_revalidates", r"failure_propagates_without_serving_a_stale_ledger"),
        ),
        (
            "targets/querystore/omod/src/test/java/org/openmrs/module/querystore/web/rest/PatientRecordEndpointTest.java",
            (r"snapshot", r"ETag|etag"),
        ),
    ),
    "G13": ((
        "specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md",
        (r"G13 Prefix proof \| Deferred \(user-directed", r"Does not block Signoff 2"),
    ),),
    "G14": (
        (
            "targets/med-agent-hub/tests/test_dual_provider_conformance_adapter.py",
            (r'_load_cases\("temporal_gate"\)', r"run_temporal_gate"),
        ),
        (
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/TemporalGateRelayConformanceTest.java",
            (r"temporal_gate", r"temporalGate"),
        ),
    ),
    "G15": (
        (
            "targets/med-agent-hub/tests/test_staged_stream.py",
            (r"final grounding", r"answer_validation", r"originalReferences"),
        ),
        (
            "targets/med-agent-hub/tests/test_validator_rewrite.py",
            (r"temporal|gate", r"original"),
        ),
    ),
    "G16": (
        (
            "targets/med-agent-hub/tests/test_drug_safety_status.py",
            (r"checked", r"limited", r"unavailable"),
        ),
        (
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/reference/DrugSafetyStatusTest.java",
            (r"checked", r"limited", r"unavailable"),
        ),
        (
            "targets/chartsearchai-esm/src/components/ai-response-panel.test.tsx",
            (r"safety", r"limited|unavailable"),
        ),
    ),
    "G17": (
        (
            "targets/chartsearchai-esm/src/hooks/useChartSearchAi.test.ts",
            (r"hydrates.*answer", r"hydrates.*safety", r"inDepth"),
        ),
        (
            "targets/chartsearchai-esm/src/components/ai-response-panel.test.tsx",
            (r"original", r"evidence", r"needs.review"),
        ),
    ),
    "G18": (
        (
            "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/TurnCancellation.java",
            (r"cancel",),
        ),
        (
            "targets/chartsearchai/omod/src/test/java/org/openmrs/module/chartsearchai/web/rest/ProviderRestContractTest.java",
            (r"preempt|cancel",),
        ),
        (
            "targets/med-agent-hub/tests/test_staged_stream.py",
            (r"cancelled.*frees the router lock",),
        ),
    ),
    "G19": ((
        "tests/e2e/specs/chartsearchai-low-confidence-review.spec.ts",
        (r"low.confidence|Needs review", r"original|rejected"),
    ),),
}

HELPERS = {
    "G20": ("scripts/verify-doc-drift.sh", ()),
    "G21": ("scripts/verify-repository-lines.sh", ("--allow-harness-branch",)),
}

# Behavioral gates execute the owning repositories' tests. A full gate run caches each command,
# so sharing one suite across several requirements does not multiply build time.
OWNER_TEST_COMMANDS = {
    "querystore": (
        ".",
        ("bash", "scripts/test-querystore.sh", "unit"),
    ),
    "querystore-mysql-integration": (
        ".",
        ("bash", "scripts/test-querystore.sh", "mysql-integration"),
    ),
    "openmrs-source-pair": (
        ".",
        ("bash", "scripts/openmrs-source-pair-test.sh"),
    ),
    "med-agent-hub": (
        "targets/med-agent-hub",
        ("uv", "run", "pytest", "-q"),
    ),
    "chartsearchai-esm": (
        ".",
        ("bash", "scripts/test-chartsearchai-esm.sh"),
    ),
    "evaluation-metadata": (
        ".",
        (
            "uv",
            "run",
            "pytest",
            "-q",
            "tests/test_run_meta.py",
            "tests/test_stage_timings.py",
            "tests/test_product_evaluation_evidence.py",
        ),
    ),
}

GATE_OWNER_TESTS = {
    "G04": ("openmrs-source-pair",),
    "G05": ("openmrs-source-pair", "chartsearchai-esm"),
    "G06": ("openmrs-source-pair",),
    "G07": ("querystore", "querystore-mysql-integration"),
    "G08": ("querystore", "med-agent-hub"),
    "G09": ("med-agent-hub",),
    "G10": ("openmrs-source-pair", "med-agent-hub"),
    "G11": ("openmrs-source-pair", "med-agent-hub"),
    "G12": ("querystore", "med-agent-hub"),
    "G14": ("openmrs-source-pair", "med-agent-hub"),
    "G15": ("openmrs-source-pair", "med-agent-hub"),
    "G16": ("openmrs-source-pair", "med-agent-hub", "chartsearchai-esm"),
    "G17": ("openmrs-source-pair", "chartsearchai-esm"),
    "G18": ("openmrs-source-pair", "med-agent-hub", "chartsearchai-esm"),
    "G22": ("evaluation-metadata",),
}


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    detail: str

    def render(self) -> str:
        return f"{self.gate:<4} {'PASS' if self.passed else 'FAIL':<4} {self.detail}"


def _result(gate: str, passed: bool, success: str, failure: str) -> GateResult:
    return GateResult(gate, passed, success if passed else failure)


def governance_results(root: Path) -> list[GateResult]:
    """Check the immutable roadmap/index contract shared by both phases."""
    results: list[GateResult] = []
    paths = {
        "roadmap": root / "specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md",
        "status": root / "specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md",
        "old_roadmap": root / "specs/artifacts/planning/hub-consolidation-roadmap.md",
        "old_status": root / "specs/artifacts/planning/hub-consolidation-roadmap-status.md",
        "index": root / "specs/artifacts/README.md",
    }
    for path in paths.values():
        if not path.is_file():
            results.append(GateResult("G01", False, f"missing {path.relative_to(root)}"))

    status_text = paths["status"].read_text(encoding="utf-8") if paths["status"].is_file() else ""
    if paths["roadmap"].is_file() and paths["status"].is_file():
        match = re.search(r"\| Approved roadmap SHA-256 \| `([^`]*)`", status_text)
        expected = match.group(1) if match else ""
        actual = hashlib.sha256(paths["roadmap"].read_bytes()).hexdigest()
        valid = bool(expected and expected != "PENDING_INITIAL_HASH" and expected == actual)
        results.append(
            _result(
                "G01",
                valid,
                "roadmap SHA-256 matches status record",
                "roadmap SHA-256 is missing or mismatched",
            )
        )
    for number in range(1, 23):
        gate = f"G{number:02d}"
        if f"| {gate} " not in status_text:
            results.append(GateResult("G01", False, f"status is missing {gate}"))

    supersession = "Status: Historical and superseded by `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`"
    superseded = all(
        path.is_file() and supersession in path.read_text(encoding="utf-8")
        for path in (paths["old_roadmap"], paths["old_status"])
    )
    results.append(
        _result(
            "G01",
            superseded,
            "prior roadmap and status are explicitly superseded",
            "prior roadmap supersession marker missing",
        )
    )
    index_text = paths["index"].read_text(encoding="utf-8") if paths["index"].is_file() else ""
    index_linked = all(
        value in index_text
        for value in (
            "planning/openmrs-dual-provider-parity-roadmap.md",
            "planning/openmrs-dual-provider-parity-roadmap-status.md",
        )
    )
    results.append(
        _result(
            "G01",
            index_linked,
            "artifact index links canonical roadmap and status",
            "artifact index does not link canonical roadmap and status",
        )
    )
    obsolete = root / "specs/artifacts/planning/openmrs-dual-runtime-pivot-audit-roadmap-2026-07-20.md"
    results.append(
        _result(
            "G01",
            not obsolete.exists(),
            "obsolete dual-runtime draft removed",
            "obsolete dual-runtime draft remains active",
        )
    )
    return results


def foundation_results(root: Path) -> list[GateResult]:
    """Preserve the original Signoff-1 worktree and red-first checks."""
    results: list[GateResult] = []
    repositories = (
        ("harness", root),
        ("targets/chartsearchai", root / "targets/chartsearchai"),
        ("targets/chartsearchai-esm", root / "targets/chartsearchai-esm"),
        ("targets/med-agent-hub", root / "targets/med-agent-hub"),
        ("targets/querystore", root / "targets/querystore"),
        ("targets/catalyst", root / "targets/catalyst"),
        ("targets/openmrs_chatbot", root / "targets/openmrs_chatbot"),
    )
    for label, repo in repositories:
        if not (repo / ".git").exists():
            results.append(GateResult("G02", False, f"{label} is not an initialized Git worktree"))
            results.append(GateResult("G02", False, f"{label} HEAD is not contained by an origin branch"))
            continue
        dirty = GateEvaluator._git(repo, "status", "--porcelain")
        results.append(
            _result(
                "G02",
                not dirty,
                f"{label} worktree is clean",
                f"{label} worktree is not clean",
            )
        )
        remote_branches = GateEvaluator._git(repo, "branch", "-r", "--contains", "HEAD")
        results.append(
            _result(
                "G02",
                "origin/" in remote_branches,
                f"{label} HEAD is remote-reachable",
                f"{label} HEAD is not contained by an origin branch",
            )
        )

    for label, repo, reference in (
        (
            "ChartSearchAI PR #26",
            root / "targets/chartsearchai",
            "refs/heads/codex/backup/chartsearchai-pr-26-20260720",
        ),
        (
            "ChartSearchAI ESM PR #12",
            root / "targets/chartsearchai-esm",
            "refs/heads/codex/backup/chartsearchai-esm-pr-12-20260720",
        ),
    ):
        exists = subprocess.run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", reference],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        results.append(
            _result(
                "G02",
                exists,
                f"{label} rollback ref exists",
                f"{label} rollback ref missing",
            )
        )

    inventory = root / "specs/artifacts/planning/openmrs-dual-provider-upstream-inventory.md"
    inventory_text = inventory.read_text(encoding="utf-8") if inventory.is_file() else ""
    inventory_ready = all(
        value in inventory_text
        for value in ("Upstream commit", "Current ChartSearchAI PR #26 Replay Inventory")
    )
    results.append(
        _result(
            "G02",
            inventory_ready,
            "upstream and replay dispositions are recorded",
            "upstream/replay disposition inventory missing or incomplete",
        )
    )

    contract = root / "specs/artifacts/planning/openmrs-dual-provider-conformance-contract.md"
    fixture = root / "datasets/validation/conformance/dual-provider-conformance.v1.json"
    ready = (
        contract.is_file()
        and fixture.is_file()
        and "Red-First Test Procedure" in contract.read_text(encoding="utf-8")
        and '"schema_version": "dual_provider_conformance.v1"'
        in fixture.read_text(encoding="utf-8")
    )
    results.append(
        _result(
            "G03",
            ready,
            "versioned conformance contract and fixture manifest are ready for red-first adapters",
            "conformance contract or versioned fixtures missing",
        )
    )
    return results


class GateEvaluator:
    def __init__(self, root: Path, evidence: Path, max_evidence_age_days: int = 14) -> None:
        self.root = root.resolve()
        self.evidence = evidence.resolve()
        self.max_evidence_age_days = max_evidence_age_days
        self._evidence_common: tuple[dict[str, Any] | None, tuple[str, ...]] | None = None
        self._owner_test_results: dict[str, tuple[bool, str]] = {}

    def evaluate(self, only_gate: str | None = None) -> list[GateResult]:
        gates = (only_gate,) if only_gate else GATES
        return [self.evaluate_gate(gate) for gate in gates]

    def evaluate_gate(self, gate: str) -> GateResult:
        if gate not in GATES:
            raise ValueError(f"unknown gate: {gate}")
        errors: list[str] = []
        if gate == "G03":
            self._check_conformance_contract(errors)
        self._require_files(errors, *REQUIRED_FILES.get(gate, ()))
        for relative, patterns in REQUIRED_PATTERNS.get(gate, ()):
            self._require_patterns(errors, relative, *patterns)
        if gate in HELPERS:
            relative, arguments = HELPERS[gate]
            self._run_helper(errors, relative, *arguments)
        self._run_owner_tests(errors, gate)
        if gate in LIVE_OBSERVATIONS:
            self._validate_evidence(errors, gate, LIVE_OBSERVATIONS[gate])

        if errors:
            return GateResult(gate, False, "; ".join(errors))
        if gate == "G13":
            detail = "explicit user deferral remains recorded; no runtime prefix-reuse claim made"
        elif gate in LIVE_OBSERVATIONS:
            detail = "source/test contract and exact-head structured evidence pass"
        else:
            detail = "source/test contract passes"
        return GateResult(gate, True, detail)

    def _require_files(self, errors: list[str], *relative_paths: str) -> None:
        for relative in relative_paths:
            if not (self.root / relative).is_file():
                errors.append(f"missing {relative}")

    def _require_patterns(self, errors: list[str], relative: str, *patterns: str) -> None:
        path = self.root / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if re.search(pattern, content, re.MULTILINE | re.DOTALL) is None:
                errors.append(f"{relative} lacks /{pattern}/")

    def _run_helper(self, errors: list[str], relative: str, *arguments: str) -> None:
        path = self.root / relative
        if not path.is_file():
            errors.append(f"missing helper {relative}")
            return
        completed = subprocess.run(
            ["bash", str(path), *arguments], cwd=self.root, text=True, capture_output=True
        )
        if completed.returncode:
            output = (completed.stderr or completed.stdout).strip().splitlines()
            errors.append(f"{relative} failed: {output[-1] if output else 'no diagnostic'}")

    def _run_owner_tests(self, errors: list[str], gate: str) -> None:
        for name in GATE_OWNER_TESTS.get(gate, ()):
            cached = self._owner_test_results.get(name)
            if cached is None:
                relative_cwd, command = OWNER_TEST_COMMANDS[name]
                try:
                    completed = subprocess.run(
                        list(command),
                        cwd=self.root / relative_cwd,
                        text=True,
                        capture_output=True,
                    )
                    output = (completed.stderr or completed.stdout).strip().splitlines()
                    cached = (
                        completed.returncode == 0,
                        output[-1] if output else "no diagnostic",
                    )
                except OSError as exc:
                    cached = (False, str(exc))
                self._owner_test_results[name] = cached
            passed, diagnostic = cached
            if not passed:
                errors.append(f"owner test suite {name} failed: {diagnostic}")

    def _check_conformance_contract(self, errors: list[str]) -> None:
        fixture_rel = "datasets/validation/conformance/dual-provider-conformance.v1.json"
        contract_rel = "specs/artifacts/planning/openmrs-dual-provider-conformance-contract.md"
        fixture = self.root / fixture_rel
        self._require_files(errors, fixture_rel, contract_rel)
        if not fixture.is_file() or not (self.root / contract_rel).is_file():
            return
        try:
            payload = json.loads(fixture.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid {fixture_rel}: {exc}")
            return

        families = {
            "provider_lifecycle",
            "provider_capabilities",
            "querystore_records",
            "context_policy",
            "temporal_gate",
            "drug_safety_status",
        }
        if payload.get("schema_version") != CONFORMANCE_SCHEMA:
            errors.append(f"conformance fixture schema_version is not {CONFORMANCE_SCHEMA}")
        missing = sorted(families - payload.keys())
        if missing:
            errors.append(f"conformance fixture missing families: {','.join(missing)}")
        identifiers = [
            case.get("id")
            for family in families
            for case in payload.get(family, [])
            if isinstance(case, dict)
        ]
        if (
            not identifiers
            or len(identifiers) != len(set(identifiers))
            or any(not value for value in identifiers)
        ):
            errors.append("conformance case IDs are missing or duplicated")

        canonical = fixture.read_bytes()
        for relative in (
            "targets/med-agent-hub/tests/conformance/dual-provider-conformance.v1.json",
            "targets/querystore/api/src/test/resources/conformance/dual-provider-conformance.v1.json",
            "targets/chartsearchai/api/src/test/resources/conformance/dual-provider-conformance.v1.json",
            "targets/chartsearchai-esm/src/conformance/dual-provider-conformance.v1.json",
        ):
            copy = self.root / relative
            if not copy.is_file():
                errors.append(f"missing conformance consumer copy {relative}")
            elif copy.read_bytes() != canonical:
                errors.append(f"stale conformance consumer copy {relative}")

        owner_patterns = {
            "targets/med-agent-hub/tests/test_dual_provider_conformance_adapter.py": (
                r'_load_cases\("temporal_gate"\)',
                r"mandatory-overflow-abstains",
            ),
            "targets/querystore/api/src/test/java/org/openmrs/module/querystore/api/impl/ContextSliceTest.java": (
                r"dual-provider-conformance\.v1\.json",
                r"context_policy",
            ),
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/TurnLifecycleConformanceTest.java": (
                r"dual-provider-conformance\.v1\.json",
                r"provider_lifecycle",
            ),
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/ProviderRegistryConformanceTest.java": (
                r"dual-provider-conformance\.v1\.json",
                r"provider_capabilities",
            ),
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/TemporalGateRelayConformanceTest.java": (
                r"dual-provider-conformance\.v1\.json",
                r"temporal_gate",
            ),
            "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/reference/DrugSafetyStatusTest.java": (
                r"dual-provider-conformance\.v1\.json",
                r"drug_safety_status",
            ),
            "targets/chartsearchai-esm/src/api/chartsearchai.test.ts": (
                r"dual-provider-conformance\.v1\.json",
                r"provider_lifecycle",
            ),
        }
        for relative, patterns in owner_patterns.items():
            self._require_patterns(errors, relative, *patterns)

    def _load_evidence(self) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
        if self._evidence_common is not None:
            return self._evidence_common
        errors: list[str] = []
        if not self.evidence.is_file():
            self._evidence_common = (None, (f"structured evidence absent: {self.evidence}",))
            return self._evidence_common
        try:
            payload = json.loads(self.evidence.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._evidence_common = (None, (f"structured evidence is invalid JSON: {exc}",))
            return self._evidence_common
        if payload.get("schema_version") != EVIDENCE_SCHEMA:
            errors.append(f"evidence schema_version must be {EVIDENCE_SCHEMA}")
        self._validate_evidence_time(errors, payload.get("generated_at"))
        self._validate_evidence_heads(errors, payload.get("heads"))
        self._evidence_common = (payload, tuple(errors))
        return self._evidence_common

    def _validate_evidence_time(self, errors: list[str], raw_time: Any) -> None:
        try:
            generated = dt.datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            if generated.tzinfo is None:
                raise ValueError("timezone is required")
            age = dt.datetime.now(dt.timezone.utc) - generated.astimezone(dt.timezone.utc)
            if age < dt.timedelta(minutes=-5):
                errors.append("evidence generated_at is in the future")
            elif age > dt.timedelta(days=self.max_evidence_age_days):
                errors.append(
                    f"evidence is stale ({age.days} days old; max {self.max_evidence_age_days})"
                )
        except (TypeError, ValueError):
            errors.append("evidence generated_at must be a timezone-aware ISO-8601 timestamp")

    def _validate_evidence_heads(self, errors: list[str], heads: Any) -> None:
        if not isinstance(heads, dict):
            errors.append("evidence heads must be an object")
            heads = {}
        for name, relative in REPOSITORY_PATHS.items():
            repo = (self.root / relative).resolve()
            try:
                actual = self._git(repo, "rev-parse", "HEAD")
                dirty = self._git(repo, "status", "--porcelain", "--untracked-files=all")
            except (OSError, subprocess.CalledProcessError):
                errors.append(f"cannot resolve {name} Git head")
                continue
            if heads.get(name) != actual:
                errors.append(
                    f"evidence head mismatch for {name}: expected {actual}, got {heads.get(name)!r}"
                )
            if dirty:
                errors.append(f"{name} worktree is dirty; evidence cannot cover uncommitted content")

    @staticmethod
    def _git(repo: Path, *arguments: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), *arguments],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    def _validate_evidence(
        self, errors: list[str], gate: str, required_observations: Sequence[str]
    ) -> None:
        payload, common_errors = self._load_evidence()
        errors.extend(common_errors)
        if payload is None:
            return
        gates = payload.get("gates")
        entry = gates.get(gate) if isinstance(gates, dict) else None
        if not isinstance(entry, dict) or entry.get("status") != "pass":
            errors.append(f"evidence {gate} entry is absent or not pass")
            return
        observations = entry.get("observations")
        if not isinstance(observations, list):
            errors.append(f"evidence {gate}.observations must be a list")
            return
        by_id = {
            item.get("id"): item
            for item in observations
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for identifier in required_observations:
            self._validate_observation(errors, gate, identifier, by_id.get(identifier))

    def _validate_observation(
        self, errors: list[str], gate: str, identifier: str, item: Any
    ) -> None:
        if not isinstance(item, dict) or item.get("status") != "pass":
            errors.append(f"evidence {gate} missing passing observation {identifier}")
            return
        if not isinstance(item.get("method"), str) or not item["method"].strip():
            errors.append(f"evidence observation {gate}/{identifier} lacks method")
        assertions = item.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append(f"evidence observation {gate}/{identifier} has no structured assertions")
        else:
            for assertion in assertions:
                if not self._valid_assertion(assertion):
                    errors.append(
                        f"evidence observation {gate}/{identifier} has a malformed or failing assertion"
                    )
        artifacts = item.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"evidence observation {gate}/{identifier} has no artifacts")
            return
        for artifact in artifacts:
            self._validate_artifact(errors, gate, identifier, artifact)
        if isinstance(assertions, list):
            artifact_paths = {
                artifact.get("path")
                for artifact in artifacts
                if isinstance(artifact, dict) and isinstance(artifact.get("path"), str)
            }
            for assertion in assertions:
                self._validate_assertion_artifact(
                    errors, gate, identifier, assertion, artifact_paths
                )
        if gate == "G10" and identifier == "context_policy_parity":
            self._validate_context_policy_parity(errors, artifacts)

    @staticmethod
    def _valid_assertion(assertion: Any) -> bool:
        if not isinstance(assertion, dict):
            return False
        return (
            isinstance(assertion.get("name"), str)
            and bool(assertion["name"].strip())
            and "expected" in assertion
            and assertion.get("evaluator") == "json_pointer_equals"
        )

    def _validate_artifact(
        self, errors: list[str], gate: str, identifier: str, artifact: Any
    ) -> None:
        if not isinstance(artifact, dict):
            errors.append(f"evidence observation {gate}/{identifier} has malformed artifact")
            return
        relative = artifact.get("path")
        expected_digest = artifact.get("sha256")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            errors.append(f"evidence observation {gate}/{identifier} artifact path must be relative")
            return
        resolved = (self.root / relative).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            errors.append(f"evidence artifact escapes repository: {relative}")
            return
        if not resolved.is_file():
            errors.append(f"evidence artifact missing: {relative}")
            return
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if not isinstance(expected_digest, str) or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
            errors.append(f"evidence artifact has invalid sha256: {relative}")
        elif digest != expected_digest:
            errors.append(f"evidence artifact checksum mismatch: {relative}")

    def _validate_assertion_artifact(
        self,
        errors: list[str],
        gate: str,
        identifier: str,
        assertion: Any,
        artifact_paths: set[Any],
    ) -> None:
        if not isinstance(assertion, dict):
            return
        relative = assertion.get("artifact_path")
        pointer = assertion.get("artifact_json_pointer")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or relative not in artifact_paths
            or not isinstance(pointer, str)
        ):
            errors.append(
                f"evidence assertion {gate}/{identifier} is not bound to a listed JSON artifact"
            )
            return
        resolved = (self.root / relative).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            errors.append(
                f"evidence assertion {gate}/{identifier} artifact escapes repository: {relative}"
            )
            return
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
            actual = self._resolve_json_pointer(payload, pointer)
            encoded_actual = json.dumps(actual, sort_keys=True, separators=(",", ":"))
            encoded_expected = json.dumps(
                assertion.get("expected"), sort_keys=True, separators=(",", ":")
            )
        except (OSError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
            errors.append(
                f"evidence assertion {gate}/{identifier} cannot be resolved from {relative}{pointer}"
            )
            return
        if encoded_actual != encoded_expected:
            errors.append(
                f"evidence assertion {gate}/{identifier} does not match its expected artifact value"
            )

    def _validate_context_policy_parity(
        self, errors: list[str], artifacts: Sequence[Any]
    ) -> None:
        reports: list[Path] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict) or artifact.get("kind") != "parity_engine_diff":
                continue
            relative = artifact.get("path")
            if isinstance(relative, str) and relative and not Path(relative).is_absolute():
                reports.append((self.root / relative).resolve())
        if len(reports) != 1:
            errors.append(
                "context_policy_parity requires exactly one parity_engine_diff artifact"
            )
            return
        try:
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            core = report["mandatory_core"]
            retrieval = report["retrieval"]
            ledger = report["ledger"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            errors.append("context_policy_parity artifact is not a valid parity-engine report")
            return
        if ledger.get("violations"):
            errors.append("context_policy_parity artifact reports engine-request violations")
        if retrieval.get("status") not in {"identical", "documented_divergence"}:
            errors.append("context_policy_parity artifact reports an unapproved retrieval difference")
        core_a = core.get("core_a")
        core_b = core.get("core_b")
        if core.get("equal") is not True or not core_a or not core_b:
            errors.append(
                "context_policy_parity mandatory core must be equal and nonempty in both arms"
            )

    @staticmethod
    def _resolve_json_pointer(payload: Any, pointer: str) -> Any:
        if pointer == "":
            return payload
        if not pointer.startswith("/"):
            raise ValueError("JSON pointer must start with /")
        current = payload
        for raw_token in pointer[1:].split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, list):
                current = current[int(token)]
            elif isinstance(current, dict):
                current = current[token]
            else:
                raise KeyError(token)
        return current


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("PARITY_GATE_ROOT", Path(__file__).resolve().parents[1])),
    )
    parser.add_argument("--phase", choices=("foundation", "full"), default="foundation")
    parser.add_argument("--evidence", type=Path, default=os.environ.get("PARITY_GATE_EVIDENCE"))
    parser.add_argument(
        "--max-evidence-age-days",
        type=int,
        default=int(os.environ.get("PARITY_GATE_MAX_EVIDENCE_AGE_DAYS", "14")),
    )
    parser.add_argument("--gate", choices=GATES)
    args = parser.parse_args(argv)
    if args.gate and args.phase != "full":
        parser.error("--gate requires --phase full")
    if args.max_evidence_age_days < 0:
        parser.error("--max-evidence-age-days must be non-negative")
    args.root = args.root.resolve()
    if args.evidence is None:
        args.evidence = args.root / "artifacts/dual-provider-parity/evidence.json"
    else:
        args.evidence = args.evidence.resolve()
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    results = [] if args.gate else governance_results(args.root)
    if args.phase == "foundation":
        results.extend(foundation_results(args.root))
    else:
        evaluator = GateEvaluator(args.root, args.evidence, args.max_evidence_age_days)
        results.extend(evaluator.evaluate(args.gate))
    for result in results:
        print(result.render())
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
