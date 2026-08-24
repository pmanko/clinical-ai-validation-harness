import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-docs-consistency.sh"
TASKS = ROOT / "specs" / "008-catalyst-query-workbench" / "tasks.md"


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
