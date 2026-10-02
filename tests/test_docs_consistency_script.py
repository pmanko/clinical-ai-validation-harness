import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-docs-consistency.sh"
LINK_SCRIPT = ROOT / "scripts" / "verify-local-markdown-links.py"
TASKS = ROOT / "specs" / "008-catalyst-query-workbench" / "tasks.md"
WORKBENCH_API = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "workbench-api.md"
)


def run_guard(
    extra_environment: dict[str, str] | None = None,
    script: Path = SCRIPT,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(extra_environment or {})
    return subprocess.run(
        ["/bin/bash", str(script)],
        cwd=script.parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_current_documents_pass_the_lightweight_guard() -> None:
    completed = run_guard()

    assert completed.returncode == 0, completed.stderr


def test_missing_current_authority_fails(tmp_path: Path) -> None:
    completed = run_guard(
        {
            "DOCS_PROGRAM_PATH": str(tmp_path / "missing.md"),
            "DOCS_SKIP_LINK_CHECK": "1",
        }
    )

    assert completed.returncode != 0
    assert "missing current Catalyst document" in completed.stderr


def test_lowercase_completed_task_marker_fails(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.md"
    tasks.write_text(
        TASKS.read_text(encoding="utf-8") + "\n- [x] accidental marker\n",
        encoding="utf-8",
    )

    completed = run_guard(
        {
            "DOCS_TASKS_PATH": str(tasks),
            "DOCS_SKIP_LINK_CHECK": "1",
        }
    )

    assert completed.returncode != 0
    assert "task checkboxes must use uppercase [X]" in completed.stderr


def test_infrastructure_identifier_fails(tmp_path: Path) -> None:
    document = tmp_path / "leak.md"
    document.write_text("Temporary rule sgr-deadbeef\n", encoding="utf-8")

    completed = run_guard(
        {
            "DOCS_SECRET_SCAN_PATH": str(document),
            "DOCS_SKIP_LINK_CHECK": "1",
        }
    )

    assert completed.returncode != 0
    assert "security-group rule id" in completed.stderr


def test_discarded_architecture_term_fails(tmp_path: Path) -> None:
    contract = tmp_path / "workbench-api.md"
    contract.write_text(
        WORKBENCH_API.read_text(encoding="utf-8")
        + "\nThe application uses an approved catalog.\n",
        encoding="utf-8",
    )

    completed = run_guard(
        {
            "DOCS_WORKBENCH_API_PATH": str(contract),
            "DOCS_SKIP_LINK_CHECK": "1",
        }
    )

    assert completed.returncode != 0
    assert "restores discarded architecture" in completed.stderr


def test_missing_local_markdown_link_fails(tmp_path: Path) -> None:
    document = tmp_path / "broken.md"
    document.write_text("[missing](does-not-exist.md)\n", encoding="utf-8")

    completed = subprocess.run(
        ["python3", str(LINK_SCRIPT), str(document)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "missing does-not-exist.md" in completed.stderr


def test_consistency_guard_checks_harness_content_without_product_checkouts() -> None:
    completed = run_guard({"DOCS_SKIP_LINK_CHECK": "1"})

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "No such file or directory" not in completed.stderr


def test_consistency_guard_propagates_link_failure(tmp_path: Path) -> None:
    document = tmp_path / "broken.md"
    document.write_text("[missing](does-not-exist.md)\n", encoding="utf-8")
    completed = run_guard({"DOCS_LINK_FILES": str(document)})

    assert completed.returncode != 0
    assert "missing does-not-exist.md" in completed.stderr


def test_missing_secret_scan_source_fails_closed(tmp_path: Path) -> None:
    completed = run_guard({
        "DOCS_SECRET_SCAN_PATH": str(tmp_path / "missing.md"),
        "DOCS_SKIP_LINK_CHECK": "1",
    })

    assert completed.returncode != 0
    assert "could not scan harness documentation" in completed.stderr


def test_consistency_guard_runs_in_a_source_archive_without_git(tmp_path: Path) -> None:
    for relative in (
        "scripts/verify-docs-consistency.sh", "scripts/verify-local-markdown-links.py",
        "README.md", "AGENTS.md", ".specify/memory/constitution.md",
        "specs/001-harness-control-plane-foundation/spec.md",
        "specs/006-validation-harness-mvp/spec.md",
        "specs/006-validation-harness-mvp/plan.md",
        "specs/artifacts/planning/metadata-schema.md",
        "specs/catalyst-program-roadmap.md",
        "specs/openelis-reporting-catalyst-integration.md",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    shutil.copytree(
        ROOT / "specs/008-catalyst-query-workbench",
        tmp_path / "specs/008-catalyst-query-workbench",
        ignore=shutil.ignore_patterns("dashboard-mvp-delivery-goal.md"),
    )
    (tmp_path / ".claude").mkdir()
    (tmp_path / "catalyst-sources").mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("dirname", "python3", "grep", "tr"):
        executable = shutil.which(name)
        assert executable
        (tools / name).symlink_to(executable)

    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / "targets").exists()
    completed = run_guard({
        "PATH": str(tools),
        "DOCS_LINK_FILES": "README.md:AGENTS.md",
    }, script=tmp_path / "scripts" / SCRIPT.name)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "markdown links: OK (2 files)" in completed.stdout
    assert "docs consistency: OK" in completed.stdout


def test_reporting_accuracy_gate_is_rejected(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.md"
    tasks.write_text(TASKS.read_text().replace(
        "## Immediate four-pathway test checkpoint",
        "## Immediate four-pathway test checkpoint\n\nResolve query quality and prove question/refinement; manual execution does not complete that journey.",
    ))
    completed = run_guard({"DOCS_TASKS_PATH": str(tasks), "DOCS_SKIP_LINK_CHECK": "1"})
    assert completed.returncode != 0
    assert "restores the rejected AI-only delivery gate" in completed.stderr


def test_reporting_manual_recovery_exclusion_is_rejected(tmp_path: Path) -> None:
    roadmap = tmp_path / "roadmap.md"
    source = ROOT / "specs" / "openelis-reporting-catalyst-integration.md"
    roadmap.write_text(source.read_text() + "\nAPI-only upload checks and manual SQL\nare useful partial evidence, not substitutes for those recorded journeys.\n")
    completed = run_guard({"DOCS_REPORTING_ROADMAP_PATH": str(roadmap), "DOCS_SKIP_LINK_CHECK": "1"})
    assert completed.returncode != 0
    assert "restores the rejected AI-only delivery gate" in completed.stderr
