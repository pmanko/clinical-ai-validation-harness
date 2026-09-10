"""cloud-sync ships the checkout to the VM with rsync --delete. Two properties keep that from
erasing evidence that only lives on the VM (2026-09-07: a sync from a worktree with an empty
artifacts/reports/ deleted every published report):

1. the shared filter file never lets --delete touch VM-canonical paths, while still deleting a
   genuinely stale tracked file (so the rule is not vacuous);
2. the deletion gate refuses a dry-run that would delete more than the configured maximum unless
   the operator forces it.
"""
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILTER = ROOT / "scripts" / "cloud-sync.filter"
LIB = ROOT / "scripts" / "cloud-sync-lib.sh"

VM_CANONICAL = [
    "artifacts/reports/run-1/index.html",
    "artifacts/reports/reports-index.json",
    "artifacts/validate/run-a/summary.json",
    "data/large-demo-data-2-7-0.sql",
    "logs/harness.log",
    "datasets/validation/comparison_sets/vm-only-set.json",
]
PROTECTED_PREFIXES = (
    "artifacts/reports/",
    "artifacts/validate/",
    "data/",
    "logs/",
    "datasets/validation/comparison_sets/",
)


@pytest.mark.parametrize("entrypoint", [
    "scripts/cloud-sync.sh",
    "scripts/publish-report.sh",
])
def test_cloud_entrypoints_are_executable_in_a_fresh_checkout(tmp_path, entrypoint):
    """Verify executable packaging from Git's index, not a local chmod; no cloud call runs."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(
        ["git", "-C", str(ROOT), "checkout-index", f"--prefix={checkout}/", "--", entrypoint],
        capture_output=True, text=True, check=True,
    )
    assert os.access(checkout / entrypoint, os.X_OK), (
        f"{entrypoint} is not recorded executable in Git; stage its executable mode"
    )


def _dry_run(tmp_path: pathlib.Path) -> tuple[list[str], list[str]]:
    """(deleted, transferred) for `rsync --delete` from a checkout-shaped src into a VM-shaped dst."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    for d in (src, dst):
        (d / "scripts").mkdir(parents=True)
        (d / "scripts" / "keep.sh").write_text("x")
    # code that happens to live in a directory called data/ or logs/ is NOT VM data and must sync
    for rel in ("harness/pkg/data/model.py", "evals/logs/parser.py"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("code")
    # the checkout carries tracked comparison sets, so the directory exists on both sides and only
    # the VM-only file inside it is at stake
    for d in (src, dst):
        (d / "datasets" / "validation" / "comparison_sets").mkdir(parents=True, exist_ok=True)
        (d / "datasets" / "validation" / "comparison_sets" / "tracked.json").write_text("{}")
    (dst / "stale.py").write_text("removed from the checkout, must go")
    for rel in VM_CANONICAL:
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("only on the VM")
    out = subprocess.run(
        ["rsync", "-a", "--delete", "--dry-run", "-v", f"--filter=merge {FILTER}", f"{src}/", f"{dst}/"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    deleted = [line[len("deleting "):] for line in out if line.startswith("deleting ")]
    transferred = [line for line in out if line and not line.startswith(("deleting ", "sending ", "sent ", "total "))]
    return deleted, transferred


def _deletions(tmp_path):
    return _dry_run(tmp_path)[0]


def test_rules_are_anchored_so_code_dirs_named_data_or_logs_still_sync(tmp_path):
    _, transferred = _dry_run(tmp_path)
    assert "harness/pkg/data/model.py" in transferred, transferred
    assert "evals/logs/parser.py" in transferred, transferred


def test_nothing_under_datasets_is_deleted_when_only_a_vm_only_set_differs(tmp_path):
    """The directory holds tracked sets on both sides and one VM-only set; neither the file nor
    the directory may be deleted (GNU rsync reports the directory itself as a deletion when only
    its contents are protected)."""
    deleted, _ = _dry_run(tmp_path)
    assert not any(d.startswith("datasets/") for d in deleted), deleted


def _rsync_args(root="/repo", dest="user@vm:repo/", key="/key"):
    r = subprocess.run(["bash", "-c", f". '{LIB}' && cloud_sync_rsync_args '{root}' '{dest}' '{key}'"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_cloud_sync_rsync_argv_carries_delete_and_the_shared_filter():
    """cloud-sync.sh builds its rsync argv from this one function, so the filter cannot fall off."""
    args = _rsync_args()
    assert "--delete" in args
    assert "--filter=merge /repo/scripts/cloud-sync.filter" in args
    assert args[-2:] == ["/repo/", "user@vm:repo/"]


def test_delete_never_reaches_vm_canonical_paths(tmp_path):
    deleted = _deletions(tmp_path)
    assert "stale.py" in deleted, "vacuous: a genuinely stale file must still be deleted"
    leaked = [d for d in deleted if d.startswith(PROTECTED_PREFIXES)]
    assert leaked == [], f"--delete would erase VM-canonical content: {leaked}"


def _gate(lines, env=None):
    return subprocess.run(
        ["bash", "-c", f". '{LIB}' && rsync_delete_gate"],
        input="".join(f"{line}\n" for line in lines),
        capture_output=True, text=True, env={**os.environ, **(env or {})},
    )


def test_gate_passes_a_small_deletion_set():
    r = _gate([f"deleting old-{i}.py" for i in range(5)] + ["scripts/keep.sh"])
    assert r.returncode == 0, r.stderr


def test_gate_refuses_a_mass_deletion_and_names_the_count():
    r = _gate([f"deleting targets/x/file-{i}" for i in range(60)])
    assert r.returncode != 0
    assert "60" in r.stdout + r.stderr


@pytest.mark.parametrize("env,expect_ok", [
    ({"CLOUD_SYNC_MAX_DELETES": "10"}, False),
    ({"CLOUD_SYNC_MAX_DELETES": "100"}, True),
    ({"CLOUD_SYNC_FORCE_DELETE": "1"}, True),
])
def test_gate_threshold_and_force_are_operator_controls(env, expect_ok):
    r = _gate([f"deleting targets/x/file-{i}" for i in range(20)], env)
    assert (r.returncode == 0) is expect_ok, r.stderr


def test_gate_refuses_any_deletion_under_a_sensitive_path_unless_forced():
    """Removing an OpenMRS module jar from the VM is a deliberate act, never a side effect of a
    checkout that happens to lack it (the 2026-09-07 sync deleted six distribution modules)."""
    lines = ["deleting artifacts/openmrs/modules/fhir2-4.0.0-SNAPSHOT.omod"]
    assert _gate(lines).returncode != 0
    assert _gate(lines, {"CLOUD_SYNC_FORCE_DELETE": "1"}).returncode == 0
