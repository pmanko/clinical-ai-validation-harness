from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openmrs-source-pair-test.sh"
LOCAL_SCRIPT = ROOT / "scripts" / "chartsearchai-local.sh"
CHARTSEARCHAI_WORKFLOW = ROOT / "targets" / "chartsearchai" / ".github" / "workflows" / "build.yml"
SUBMODULES = ("querystore", "chartsearchai", "chartsearchai-esm")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, text: str) -> str:
    marker = repo / "marker.txt"
    marker.write_text(text, encoding="utf-8")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", text)
    return _git(repo, "rev-parse", "HEAD")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "harness"
    (root / "scripts").mkdir(parents=True)
    (root / "targets").mkdir()
    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "scripts")
    _git(root, "commit", "-m", "script")

    heads: dict[str, str] = {}
    for name in SUBMODULES:
        repo = root / "targets" / name
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "test@example.test")
        _git(repo, "config", "user.name", "Test")
        heads[name] = _commit(repo, f"{name}-one")
        _git(
            repo,
            "update-ref",
            "refs/remotes/origin/harness-integration",
            heads[name],
        )
        _git(
            root,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{heads[name]},targets/{name}",
        )
    _git(root, "commit", "-m", "pin integration heads")

    log = tmp_path / "maven.log"
    fake_maven = tmp_path / "fake-maven"
    fake_maven.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$PWD\" >> \"$SOURCE_PAIR_TEST_LOG\"\n",
        encoding="utf-8",
    )
    fake_maven.chmod(fake_maven.stat().st_mode | stat.S_IXUSR)
    return root, fake_maven, log


def _run(root: Path, fake_maven: Path, log: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HARNESS_ROOT": str(root),
        "MVN_BIN": str(fake_maven),
        "SOURCE_PAIR_TEST_LOG": str(log),
    }
    return subprocess.run(
        ["bash", str(root / "scripts" / SCRIPT.name)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_source_pair_gate_runs_pinned_sources_in_dependency_order(tmp_path):
    root, fake_maven, log = _fixture(tmp_path)

    result = _run(root, fake_maven, log)

    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        str(root / "targets" / "querystore"),
        str(root / "targets" / "chartsearchai"),
    ]


def test_source_pair_gate_rejects_stale_remote_or_parent_gitlink_before_build(tmp_path):
    root, fake_maven, log = _fixture(tmp_path)
    querystore = root / "targets" / "querystore"

    remote_mismatch = _commit(querystore, "querystore-two")
    result = _run(root, fake_maven, log)
    assert result.returncode != 0
    assert "does not match origin/harness-integration" in result.stderr
    assert not log.exists()

    _git(
        querystore,
        "update-ref",
        "refs/remotes/origin/harness-integration",
        remote_mismatch,
    )
    result = _run(root, fake_maven, log)
    assert result.returncode != 0
    assert "does not match parent gitlink" in result.stderr
    assert not log.exists()


def test_development_pair_build_installs_querystore_before_chartsearchai():
    result = subprocess.run(
        ["make", "--dry-run", "openmrs-source-pair-build"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    querystore = "cd targets/querystore && mvn -DskipTests -B install"
    chartsearchai = "cd targets/chartsearchai && mvn -DskipTests -B package"
    assert querystore in result.stdout
    assert chartsearchai in result.stdout
    assert result.stdout.index(querystore) < result.stdout.index(chartsearchai)


def test_local_entrypoint_builds_the_openmrs_modules_as_one_pair():
    subprocess.run(["bash", "-n", str(LOCAL_SCRIPT)], check=True)
    source = LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert "make openmrs-source-pair-build" in source
    assert '"ChartSearchAI module" \\\n' not in source
    assert '"Querystore module" \\\n' not in source


def test_chartsearchai_integration_ci_builds_the_exact_pinned_querystore_source():
    workflow_text = CHARTSEARCHAI_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)
    querystore_head = _git(ROOT / "targets" / "querystore", "rev-parse", "HEAD")

    assert "github.head_ref != 'harness-integration'" in workflow["jobs"]["build"]["if"]
    paired = workflow["jobs"]["paired-build"]
    assert "github.head_ref == 'harness-integration'" in paired["if"]
    assert paired["strategy"]["matrix"]["java"] == [11, 17, 21]

    checkout = next(
        step for step in paired["steps"] if step["name"] == "Checkout paired QueryStore source"
    )
    assert checkout["with"]["repository"] == "pmanko/openmrs-module-querystore"
    assert checkout["with"]["ref"] == querystore_head

    install = next(
        step for step in paired["steps"] if step["name"] == "Install paired QueryStore source"
    )
    assert "clean install -DskipTests" in install["run"]
