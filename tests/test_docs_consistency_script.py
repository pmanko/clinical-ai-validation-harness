import os
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


def run_guard(extra_environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(extra_environment or {})
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
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
