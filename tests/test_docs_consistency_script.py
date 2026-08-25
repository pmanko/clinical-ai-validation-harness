import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-docs-consistency.sh"
TASKS = ROOT / "specs" / "008-catalyst-query-workbench" / "tasks.md"
PROGRAM = ROOT / "specs" / "catalyst-program-roadmap.md"
QUALIFICATION = ROOT / "specs" / "catalyst-phase1-qualification-remediation-roadmap.md"
BRIEF = (
    ROOT / "specs" / "artifacts" / "planning" / "phase-1-planning-discussion-brief.md"
)
WRITER_ARTIFACT = (
    ROOT / "specs" / "artifacts" / "planning" / "what-the-writer-sees.html"
)
FEATURE_SPEC = ROOT / "specs" / "008-catalyst-query-workbench" / "spec.md"
WORKBENCH_API = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "workbench-api.md"
)
PHASE1_SUITE = (
    ROOT / "datasets" / "validation" / "catalyst" / "catalyst-phase1-comparison-v1.json"
)
CATALOG_V6_OVERLAY = ROOT / "catalyst-sources" / "openmrs-hiv" / "catalog-overlay.json"
CATALOG_V6_GENERATED = (
    ROOT / "catalyst-sources" / "openmrs-hiv" / "catalog" / "openmrs-hiv-catalog.json"
)


def _run_with_tasks(
    tmp_path: Path,
    content: str,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    tasks_path = tmp_path / "tasks.md"
    tasks_path.write_text(content, encoding="utf-8")
    environment = os.environ.copy()
    environment["DOCS_TASKS_PATH"] = str(tasks_path)
    environment.update(extra_environment or {})
    return subprocess.run(
        [SCRIPT],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_unchecked_task_after_phase_10_does_not_change_its_gate_count(
    tmp_path: Path,
) -> None:
    content = TASKS.read_text(encoding="utf-8")
    content += "\n## Test-only later phase\n\n- [ ] T999 Later work\n"

    completed = _run_with_tasks(tmp_path, content)

    assert completed.returncode == 0, completed.stderr


def test_phase_10_gate_cannot_be_moved_to_a_later_section(tmp_path: Path) -> None:
    content = TASKS.read_text(encoding="utf-8")
    gate_line = next(
        line for line in content.splitlines() if line.startswith("- [ ] T166 ")
    )
    content = content.replace(gate_line + "\n", "", 1)
    content += f"\n## Test-only later phase\n\n{gate_line}\n"

    completed = _run_with_tasks(tmp_path, content)

    assert completed.returncode != 0
    assert "active Phase 10 gate missing or checked: T166" in completed.stderr


def test_missing_status_source_is_a_check_failure(tmp_path: Path) -> None:
    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        {"DOCS_STATUS_EXTRA_PATH": str(tmp_path / "missing-status.md")},
    )

    assert completed.returncode != 0
    assert "unable to inspect every live status source" in completed.stderr


def _source_overrides(tmp_path: Path) -> dict[str, str]:
    sources = {
        "DOCS_PROGRAM_PATH": PROGRAM,
        "DOCS_QUALIFICATION_PATH": QUALIFICATION,
        "DOCS_BRIEF_PATH": BRIEF,
        "DOCS_WRITER_ARTIFACT_PATH": WRITER_ARTIFACT,
        "DOCS_FEATURE_SPEC_PATH": FEATURE_SPEC,
        "DOCS_WORKBENCH_API_PATH": WORKBENCH_API,
        "DOCS_PHASE1_SUITE_PATH": PHASE1_SUITE,
        "DOCS_CATALOG_V6_OVERLAY_PATH": CATALOG_V6_OVERLAY,
        "DOCS_CATALOG_V6_GENERATED_PATH": CATALOG_V6_GENERATED,
    }
    environment: dict[str, str] = {}
    for variable, source in sources.items():
        target = tmp_path / source.name
        target.write_bytes(source.read_bytes())
        environment[variable] = str(target)
    return environment


@pytest.mark.parametrize(
    "decision_phrase",
    [
        "Relation counts are environment snapshots",
        "metadata cannot hide a readable relation",
        "does not by itself stop ordinary startup",
        "the application adds no blanket query bans",
        "The exact selected SQL reaches PostgreSQL",
        "bounded by the configured read-only account, read-only transaction, timeout, and result limit",
        "wrong query, database diagnostic, or wrong answer is a model-quality result",
        "do not have to match",
        "planned run count and decision method are recorded before live work",
        "no universal pass percentage, automatic disqualifier, or fixed tie-break",
        "no fixed retry or failure allowance",
        "no fixed count, physical order, or ranking formula",
        "not rejected merely for sharing a relation or SQL form",
        "not on every ordinary pull request",
        "not Phase 1 product blockers",
    ],
)
def test_current_decision_summary_cannot_be_weakened(
    tmp_path: Path,
    decision_phrase: str,
) -> None:
    environment = _source_overrides(tmp_path)
    program = Path(environment["DOCS_PROGRAM_PATH"])
    program.write_text(
        program.read_text(encoding="utf-8").replace(
            decision_phrase,
            "removed decision",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert f"current program outcome missing: {decision_phrase}" in completed.stderr


def test_phase1_suite_internal_repetitions_must_remain_one(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    suite = Path(environment["DOCS_PHASE1_SUITE_PATH"])
    payload = json.loads(suite.read_text(encoding="utf-8"))

    for invalid_value in (3, 10, "1", True):
        payload["repetitions"] = invalid_value
        suite.write_text(json.dumps(payload), encoding="utf-8")

        completed = _run_with_tasks(
            tmp_path,
            TASKS.read_text(encoding="utf-8"),
            environment,
        )

        assert completed.returncode != 0
        assert "suite repetitions must remain one" in completed.stderr


def test_published_phase1_suite_v1_bytes_are_immutable(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    suite = Path(environment["DOCS_PHASE1_SUITE_PATH"])
    suite.write_text(suite.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "immutable Phase 1 suite v1 bytes changed" in completed.stderr


def test_published_catalog_v6_overlay_bytes_are_immutable(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    overlay = Path(environment["DOCS_CATALOG_V6_OVERLAY_PATH"])
    overlay.write_text(
        overlay.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "immutable catalog v6 overlay bytes changed" in completed.stderr


def test_published_catalog_v6_generated_bytes_are_immutable(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    catalog = Path(environment["DOCS_CATALOG_V6_GENERATED_PATH"])
    catalog.write_text(
        catalog.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "immutable catalog v6 generated file bytes changed" in completed.stderr


def test_interrupted_run_must_use_a_new_linked_identity(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    content = qualification.read_text(encoding="utf-8")
    marker = "## Execution rules inherited from the program roadmap"
    qualification.write_text(
        content.replace(
            marker,
            f"{marker}\n\nResume continues the same run ID after interruption.",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "stale same-run recovery rule" in completed.stderr


def test_superseded_wording_in_the_historical_log_is_not_current(
    tmp_path: Path,
) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8")
        + "\nResume continues the same run ID after interruption.\n"
        + "Branch protection is not a Phase 1 product blocker.\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_owner_approved_m1_rule_cannot_disappear(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "All three M1 ready answers are scored",
            "Only later M1 answers are scored",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "current Phase 1 evidence rule missing" in completed.stderr


def test_m3_semantic_carryover_rule_cannot_disappear(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "carry no irrelevant CD4-specific assumptions into the visit answer",
            "may carry CD4-specific assumptions into the visit answer",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "current Phase 1 evidence rule missing" in completed.stderr


def test_advisory_validation_cannot_become_an_execution_gate(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "Validation is advisory",
            "Validation blocks execution",
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "current Phase 1 evidence rule missing" in completed.stderr


def test_no_selection_must_remain_an_explicit_outcome(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "record `none` or `inconclusive`",
            "select a fallback",
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "current Phase 1 evidence rule missing" in completed.stderr


def test_recovery_cannot_select_cells_by_answer_quality(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "conversation regardless",
            "conversation only",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "current Phase 1 evidence rule missing" in completed.stderr


def test_writer_artifact_must_retain_the_owner_correction_banner(
    tmp_path: Path,
) -> None:
    environment = _source_overrides(tmp_path)
    artifact = Path(environment["DOCS_WRITER_ARTIFACT_PATH"])
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            "run counts, pass percentages, retry budgets, and context caps are not locked here",
            "the old implementation rules remain locked here",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "writer artifact lacks the owner-correction banner" in completed.stderr


def test_program_roadmap_must_name_the_current_component_pins(
    tmp_path: Path,
) -> None:
    environment = _source_overrides(tmp_path)
    program = Path(environment["DOCS_PROGRAM_PATH"])
    current_pin = subprocess.check_output(
        ["git", "ls-tree", "HEAD", "targets/catalyst"],
        cwd=ROOT,
        text=True,
    ).split()[2]
    program.write_text(
        program.read_text(encoding="utf-8").replace(
            current_pin,
            "0000000000000000000000000000000000000000",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "does not name the pinned Catalyst revision" in completed.stderr


def test_program_roadmap_must_name_the_current_hub_pin(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    program = Path(environment["DOCS_PROGRAM_PATH"])
    current_pin = subprocess.check_output(
        ["git", "ls-tree", "HEAD", "targets/med-agent-hub"],
        cwd=ROOT,
        text=True,
    ).split()[2]
    program.write_text(
        program.read_text(encoding="utf-8").replace(
            current_pin,
            "0000000000000000000000000000000000000000",
            1,
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "does not name the pinned Hub revision" in completed.stderr
