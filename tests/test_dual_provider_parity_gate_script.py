from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-dual-provider-parity-gates.sh"
EVALUATOR = ROOT / "scripts" / "verify_dual_provider_parity_gates.py"
SPEC = importlib.util.spec_from_file_location("dual_provider_parity_gates", EVALUATOR)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run(root: Path, gate: str, *, evidence: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PARITY_GATE_ROOT": str(root)}
    command = [str(SCRIPT), "--phase", "full", "--gate", gate]
    if evidence is not None:
        command.extend(["--evidence", str(evidence)])
    return subprocess.run(command, text=True, capture_output=True, env=env)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _initialize_repository(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "gate-test@example.test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Parity Gate Test"], check=True)


def _commit_all(root: Path) -> str:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    return _git(root, "rev-parse", "HEAD")


def _conformance_workspace(tmp_path: Path) -> Path:
    fixture = {
        "schema_version": "dual_provider_conformance.v1",
        "provider_lifecycle": [{"id": "provider.lifecycle.accept"}],
        "provider_capabilities": [{"id": "provider.capabilities.default"}],
        "querystore_records": [{"id": "querystore.record.date"}],
        "context_policy": [{"id": "context.mandatory-overflow-abstains"}],
        "temporal_gate": [{"id": "temporal.upcoming"}],
        "drug_safety_status": [{"id": "drug.checked"}],
    }
    canonical = json.dumps(fixture, indent=2) + "\n"
    _write(
        tmp_path,
        "specs/artifacts/planning/openmrs-dual-provider-conformance-contract.md",
        "Red-First Test Procedure\n",
    )
    _write(tmp_path, "datasets/validation/conformance/dual-provider-conformance.v1.json", canonical)
    for relative in (
        "targets/med-agent-hub/tests/conformance/dual-provider-conformance.v1.json",
        "targets/querystore/api/src/test/resources/conformance/dual-provider-conformance.v1.json",
        "targets/chartsearchai/api/src/test/resources/conformance/dual-provider-conformance.v1.json",
        "targets/chartsearchai-esm/src/conformance/dual-provider-conformance.v1.json",
    ):
        _write(tmp_path, relative, canonical)
    _write(
        tmp_path,
        "targets/med-agent-hub/tests/test_dual_provider_conformance_adapter.py",
        '_load_cases("temporal_gate")\n# context.mandatory-overflow-abstains\n',
    )
    _write(
        tmp_path,
        "targets/querystore/api/src/test/java/org/openmrs/module/querystore/api/impl/ContextSliceTest.java",
        "dual-provider-conformance.v1.json context_policy\n",
    )
    _write(
        tmp_path,
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/TurnLifecycleConformanceTest.java",
        "dual-provider-conformance.v1.json provider_lifecycle\n",
    )
    _write(
        tmp_path,
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/ProviderRegistryConformanceTest.java",
        "dual-provider-conformance.v1.json provider_capabilities\n",
    )
    _write(
        tmp_path,
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/api/provider/TemporalGateRelayConformanceTest.java",
        "dual-provider-conformance.v1.json temporal_gate\n",
    )
    _write(
        tmp_path,
        "targets/chartsearchai/api/src/test/java/org/openmrs/module/chartsearchai/reference/DrugSafetyStatusTest.java",
        "dual-provider-conformance.v1.json drug_safety_status\n",
    )
    _write(
        tmp_path,
        "targets/chartsearchai-esm/src/api/chartsearchai.test.ts",
        "dual-provider-conformance.v1.json provider_lifecycle\n",
    )
    return tmp_path


def _live_evidence_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    _initialize_repository(workspace)
    _write(workspace, ".gitignore", "targets/\n")
    _write(workspace, "scripts/probe-chartsearchai-relay.py", "# real-path probe\n")
    _write(workspace, "tests/e2e/specs/chartsearchai-demo.spec.ts", "// demo\n")
    _write(workspace, "tests/e2e/specs/chartsearchai-preempt.spec.ts", "// preempt\n")
    _write(
        workspace,
        "tests/e2e/specs/chartsearchai-low-confidence-review.spec.ts",
        "// Low confidence Needs review; original rejected output remains inspectable\n",
    )
    proof_values = {
        identifier: {"completed": True}
        for identifier in (
            "low_confidence_visible",
            "rejected_output_inspectable",
            "evidence_resolved",
            "no_silent_downgrade",
        )
    }
    artifact = _write(
        workspace,
        "artifacts/proof/live.json",
        json.dumps({"observations": proof_values}) + "\n",
    )
    harness_head = _commit_all(workspace)

    heads = {"harness": harness_head}
    for name, relative in (
        ("med-agent-hub", "targets/med-agent-hub"),
        ("querystore", "targets/querystore"),
        ("chartsearchai", "targets/chartsearchai"),
        ("chartsearchai-esm", "targets/chartsearchai-esm"),
    ):
        repo = workspace / relative
        _initialize_repository(repo)
        _write(repo, "README.md", f"{name}\n")
        heads[name] = _commit_all(repo)

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    observation = lambda identifier: {
        "id": identifier,
        "status": "pass",
        "method": "live browser and API assertion",
        "assertions": [
            {
                "name": f"{identifier} completed",
                "expected": True,
                "evaluator": "json_pointer_equals",
                "artifact_path": "artifacts/proof/live.json",
                "artifact_json_pointer": f"/observations/{identifier}/completed",
            }
        ],
        "artifacts": [{"path": "artifacts/proof/live.json", "sha256": digest}],
    }
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "dual_provider_parity_evidence.v1",
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "heads": heads,
                "gates": {
                    "G19": {
                        "status": "pass",
                        "observations": [
                            observation("low_confidence_visible"),
                            observation("rejected_output_inspectable"),
                            observation("evidence_resolved"),
                            observation("no_silent_downgrade"),
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return workspace, evidence, artifact


def test_full_gate_checks_the_real_conformance_copies(tmp_path: Path) -> None:
    workspace = _conformance_workspace(tmp_path)
    evaluator = MODULE.GateEvaluator(workspace, tmp_path / "unused-evidence.json")

    passing = evaluator.evaluate_gate("G03")
    assert passing.passed is True

    stale_copy = workspace / "targets/chartsearchai-esm/src/conformance/dual-provider-conformance.v1.json"
    stale_copy.write_text('{"schema_version":"stale"}\n', encoding="utf-8")
    failing = evaluator.evaluate_gate("G03")

    assert failing.passed is False
    assert "stale conformance consumer copy" in failing.detail


def test_shell_entrypoint_delegates_full_gate_and_exit_status(tmp_path: Path) -> None:
    workspace = _conformance_workspace(tmp_path)

    result = _run(workspace, "G03")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "G03  PASS" in result.stdout


def test_live_gate_requires_hash_bound_current_head_evidence(tmp_path: Path) -> None:
    workspace, evidence, _artifact = _live_evidence_workspace(tmp_path)
    evaluator = MODULE.GateEvaluator(workspace, evidence)

    passing = evaluator.evaluate_gate("G19")
    assert passing.passed is True

    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["gates"]["G19"]["observations"][0]["artifacts"][0]["sha256"] = "0" * 64
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    failing = MODULE.GateEvaluator(workspace, evidence).evaluate_gate("G19")

    assert failing.passed is False
    assert "artifact checksum mismatch" in failing.detail


def test_live_gate_reads_assertion_value_from_the_artifact(
    tmp_path: Path,
) -> None:
    workspace, evidence, _artifact = _live_evidence_workspace(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assertion = payload["gates"]["G19"]["observations"][0]["assertions"][0]
    assertion["expected"] = {"status": "checked"}
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    result = MODULE.GateEvaluator(workspace, evidence).evaluate_gate("G19")

    assert result.passed is False
    assert "does not match its expected artifact value" in result.detail


def test_assertion_cannot_self_certify_with_actual_and_passed_fields(tmp_path: Path) -> None:
    workspace, evidence, _artifact = _live_evidence_workspace(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assertion = payload["gates"]["G19"]["observations"][0]["assertions"][0]
    assertion.pop("evaluator")
    assertion["actual"] = True
    assertion["passed"] = True
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    result = MODULE.GateEvaluator(workspace, evidence).evaluate_gate("G19")

    assert result.passed is False
    assert "malformed or failing assertion" in result.detail


def test_live_gate_rejects_malformed_or_escaping_assertion_artifact_paths(
    tmp_path: Path,
) -> None:
    workspace, evidence, _artifact = _live_evidence_workspace(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assertion = payload["gates"]["G19"]["observations"][0]["assertions"][0]
    assertion["artifact_path"] = ["not", "a", "path"]
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    malformed = MODULE.GateEvaluator(workspace, evidence).evaluate_gate("G19")

    assert malformed.passed is False
    assert "not bound to a listed JSON artifact" in malformed.detail

    payload = json.loads(evidence.read_text(encoding="utf-8"))
    observation = payload["gates"]["G19"]["observations"][0]
    observation["artifacts"][0]["path"] = "../outside.json"
    observation["assertions"][0]["artifact_path"] = "../outside.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    escaping = MODULE.GateEvaluator(workspace, evidence).evaluate_gate("G19")

    assert escaping.passed is False
    assert "artifact escapes repository" in escaping.detail


def test_live_gate_rejects_absent_and_stale_evidence(tmp_path: Path) -> None:
    workspace, evidence, _artifact = _live_evidence_workspace(tmp_path)

    absent = _run(workspace, "G19", evidence=tmp_path / "missing.json")
    assert absent.returncode == 1
    assert "structured evidence absent" in absent.stdout

    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["generated_at"] = "2000-01-01T00:00:00+00:00"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    stale = _run(workspace, "G19", evidence=evidence)
    assert stale.returncode == 1
    assert "evidence is stale" in stale.stdout


def test_behavioral_gate_fails_when_its_owner_test_command_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    failing = workspace / "fail-owner-test.sh"
    failing.write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8")
    monkeypatch.setitem(
        MODULE.OWNER_TEST_COMMANDS,
        "fixture-owner",
        (".", ("bash", "fail-owner-test.sh")),
    )
    monkeypatch.setitem(MODULE.GATE_OWNER_TESTS, "G11", ("fixture-owner",))
    evaluator = MODULE.GateEvaluator(workspace, tmp_path / "evidence.json")
    errors: list[str] = []

    evaluator._run_owner_tests(errors, "G11")

    assert errors == ["owner test suite fixture-owner failed: no diagnostic"]


def test_cross_repo_owner_commands_use_stable_complete_wrappers() -> None:
    assert MODULE.OWNER_TEST_COMMANDS["openmrs-source-pair"][1] == (
        "bash",
        "scripts/openmrs-source-pair-test.sh",
    )
    assert MODULE.OWNER_TEST_COMMANDS["chartsearchai-esm"][1] == (
        "bash",
        "scripts/test-chartsearchai-esm.sh",
    )
    assert "openmrs-source-pair" in MODULE.GATE_OWNER_TESTS["G10"]


def test_context_parity_artifact_requires_a_nonempty_equal_mandatory_core(
    tmp_path: Path,
) -> None:
    report = _write(
        tmp_path,
        "artifacts/parity-engine/parity-diff.json",
        json.dumps(
            {
                "ledger": {"violations": []},
                "retrieval": {"status": "identical"},
                "mandatory_core": {"equal": True, "core_a": [], "core_b": []},
            }
        ),
    )
    evaluator = MODULE.GateEvaluator(tmp_path, tmp_path / "unused.json")
    errors: list[str] = []

    evaluator._validate_context_policy_parity(
        errors,
        [{"kind": "parity_engine_diff", "path": str(report.relative_to(tmp_path))}],
    )

    assert errors == [
        "context_policy_parity mandatory core must be equal and nonempty in both arms"
    ]

    report.write_text(
        json.dumps(
            {
                "ledger": {"violations": []},
                "retrieval": {"status": "identical"},
                "mandatory_core": {
                    "equal": True,
                    "core_a": ["Allergy: Ibuprofen"],
                    "core_b": ["Allergy: Ibuprofen"],
                },
            }
        ),
        encoding="utf-8",
    )
    errors = []
    evaluator._validate_context_policy_parity(
        errors,
        [{"kind": "parity_engine_diff", "path": str(report.relative_to(tmp_path))}],
    )
    assert errors == []


def test_parity_diff_itself_rejects_an_unexercised_mandatory_core(tmp_path: Path) -> None:
    request_a = _write(tmp_path, "a.json", json.dumps({"messages": []}))
    request_b = _write(tmp_path, "b.json", json.dumps({"messages": []}))
    contract = _write(
        tmp_path,
        "contract.json",
        json.dumps(
            {
                "schema_version": "engine-parity.v1",
                "must_match": [],
                "documented_divergences": [],
            }
        ),
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/parity-engine-diff.py"),
            str(request_a),
            str(request_b),
            "--contract",
            str(contract),
            "--out",
            str(tmp_path / "report.json"),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "mandatory clinical core is empty" in result.stdout


def test_foundation_remains_the_default_and_placeholder_failures_are_gone() -> None:
    shell_source = SCRIPT.read_text(encoding="utf-8")
    evaluator_source = EVALUATOR.read_text(encoding="utf-8")
    args = MODULE.parse_args(["--root", str(ROOT)])

    assert args.phase == "foundation"
    assert len(shell_source.splitlines()) <= 12
    assert "verify_dual_provider_parity_gates.py" in shell_source
    assert "<<'PY'" not in shell_source
    assert "full cross-repository conformance adapters are not implemented yet" not in evaluator_source
    assert "acceptance gate has not been implemented yet" not in evaluator_source
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_foundation_checks_are_directly_testable_and_fail_closed(tmp_path: Path) -> None:
    governance = MODULE.governance_results(tmp_path)
    foundation = MODULE.foundation_results(tmp_path)

    assert any(result.detail == "status is missing G22" for result in governance)
    assert any(
        result.detail == "targets/chartsearchai is not an initialized Git worktree"
        for result in foundation
    )
    assert any(
        result.detail == "targets/chartsearchai HEAD is not contained by an origin branch"
        for result in foundation
    )
