import json
import os
import subprocess
from pathlib import Path

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


def test_obsolete_per_cell_repetition_rule_is_rejected(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    program = Path(environment["DOCS_PROGRAM_PATH"])
    program.write_text(
        program.read_text(encoding="utf-8")
        + "\nStart with three repetitions for every profile/scenario pair.\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "obsolete per-cell Phase 1 repetition rule" in completed.stderr


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
    qualification.write_text(
        qualification.read_text(encoding="utf-8")
        + "\nResume continues the same run ID after interruption.\n",
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "stale same-run recovery rule" in completed.stderr


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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_owner_approved_m3_rule_cannot_disappear(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "reuses no",
            "may reuse",
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_unlisted_validation_warning_cannot_pass(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "an unlisted warning fails",
            "an unlisted warning passes",
        ),
        encoding="utf-8",
    )

    completed = _run_with_tasks(
        tmp_path,
        TASKS.read_text(encoding="utf-8"),
        environment,
    )

    assert completed.returncode != 0
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_no_qualifying_team_must_remain_an_explicit_outcome(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "If no team qualifies, record `none`",
            "If no team qualifies, select a fallback",
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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_approved_warm_up_rule_cannot_disappear(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "one excluded, recorded, unscored warm-up must run",
            "warm-ups are optional",
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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_whole_batch_extension_trigger_must_remain_computable(tmp_path: Path) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "answer correctness varies",
            "answer correctness is reviewed",
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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_third_infrastructure_failure_must_invalidate_the_team_run(
    tmp_path: Path,
) -> None:
    environment = _source_overrides(tmp_path)
    qualification = Path(environment["DOCS_QUALIFICATION_PATH"])
    qualification.write_text(
        qualification.read_text(encoding="utf-8").replace(
            "third infrastructure failure",
            "fourth infrastructure failure",
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
    assert "approved Phase 1 adjudication rule missing" in completed.stderr


def test_writer_artifact_must_name_catalog_v7_as_the_corrected_contract(
    tmp_path: Path,
) -> None:
    environment = _source_overrides(tmp_path)
    artifact = Path(environment["DOCS_WRITER_ARTIFACT_PATH"])
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            "Catalog v7 records the corrected 13-relation decision",
            "Catalog v6 records the decision",
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
    assert "writer artifact still assigns the corrected surface" in completed.stderr


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
