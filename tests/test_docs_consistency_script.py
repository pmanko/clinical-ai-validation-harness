import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-docs-consistency.sh"
TASKS = ROOT / "specs" / "008-catalyst-query-workbench" / "tasks.md"
PROGRAM = ROOT / "specs" / "catalyst-program-roadmap.md"
EXECUTION = ROOT / "specs" / "catalyst-phase1-qualification-remediation-roadmap.md"
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
        "DOCS_EXECUTION_PATH": EXECUTION,
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
    ("environment_key", "marker", "expected_error"),
    [
        (
            "DOCS_PROGRAM_PATH",
            "## Phase 1 comparison and reader review",
            "program roadmap is missing reader-led comparison",
        ),
        (
            "DOCS_PROGRAM_PATH",
            "### 3. Session context and the open guidance question",
            "program roadmap is missing the open guidance question",
        ),
        (
            "DOCS_EXECUTION_PATH",
            "### R4 — Context-rich report and manual rubric review",
            "execution plan is missing manual full-context review",
        ),
        (
            "DOCS_EXECUTION_PATH",
            "### R6 — Honest context evidence and guidance research seam",
            "execution plan is missing guidance research",
        ),
    ],
)
def test_current_roadmap_structure_cannot_silently_disappear(
    tmp_path: Path,
    environment_key: str,
    marker: str,
    expected_error: str,
) -> None:
    environment = _source_overrides(tmp_path)
    source = Path(environment[environment_key])
    source.write_text(
        source.read_text(encoding="utf-8").replace(marker, "removed section", 1),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert expected_error in completed.stderr


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


@pytest.mark.parametrize(
    "stale_rule",
    [
        "The owner records a selected team.",
        "Record `none` or `inconclusive`.",
        "Deploy the selected team.",
        "Use a composer pin.",
    ],
)
def test_superseded_rule_cannot_return_to_an_active_roadmap(
    tmp_path: Path,
    stale_rule: str,
) -> None:
    environment = _source_overrides(tmp_path)
    execution = Path(environment["DOCS_EXECUTION_PATH"])
    execution.write_text(
        execution.read_text(encoding="utf-8") + f"\n{stale_rule}\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "an active roadmap restores a superseded Phase 1 rule" in completed.stderr


def test_negative_team_selection_statement_is_allowed(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    execution = Path(environment["DOCS_EXECUTION_PATH"])
    execution.write_text(
        execution.read_text(encoding="utf-8")
        + "\nA team preference is not required.\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("environment_key", "required_text", "expected_error"),
    [
        (
            "DOCS_FEATURE_SPEC_PATH",
            "include every relation the configured read-only database role can read",
            "Feature 008 does not require the complete role-readable catalog",
        ),
        (
            "DOCS_FEATURE_SPEC_PATH",
            "Users MUST be able to run the exact displayed draft regardless of\n  its validator status",
            "Feature 008 does not preserve advisory exact-SQL execution",
        ),
        (
            "DOCS_WORKBENCH_API_PATH",
            "Workbench validation is advisory",
            "workbench API does not preserve advisory validation",
        ),
    ],
)
def test_durable_product_boundary_cannot_disappear(
    tmp_path: Path,
    environment_key: str,
    required_text: str,
    expected_error: str,
) -> None:
    environment = _source_overrides(tmp_path)
    source = Path(environment[environment_key])
    source.write_text(
        source.read_text(encoding="utf-8").replace(required_text, "removed boundary", 1),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert expected_error in completed.stderr
