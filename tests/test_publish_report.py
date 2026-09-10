"""Exercise real publication/backup shell control flow, not cloud or report rendering.

The isolated checkout has pre-rendered reports. Only external executables (uv,
gcloud, rsync and ssh) are stubbed; publish-report.sh, reports-backup.sh and their
shared cloud helpers run unchanged. No network service is contacted.
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def publisher(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("publish-report.sh", "reports-backup.sh", "cloud-lib.sh"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)

    reports = tmp_path / "artifacts/reports"
    (reports / "example").mkdir(parents=True)
    (reports / "example/index.html").write_text("Report\n", encoding="utf-8")
    (reports / "index.html").write_text("Index\n", encoding="utf-8")
    (tmp_path / "reports-index.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".env.chartsearch.cloud").write_text(
        "CADDY_SITE_REPORTS=reports.example.invalid\n", encoding="utf-8",
    )
    binaries = tmp_path / "bin"
    binaries.mkdir()
    stubs = {
        "uv": "exit 0\n",
        "ssh": "exit 0\n",
        "rsync": 'echo "trace: publish upload"\nexit "${PUBLISH_EXIT_CODE:-0}"\n',
        "gcloud": '''case "$*" in
  "compute instances describe "*"--format=value(name)") echo test-vm ;;
  "compute instances describe "*"--format=value(status)") echo RUNNING ;;
  "compute instances describe "*"--format=value(networkInterfaces[0].accessConfigs[0].natIP)") echo 192.0.2.1 ;;
  "compute ssh "*) exit 0 ;;
  "storage buckets describe "*"--project test-project"*"--format=value(versioning.enabled)") echo True ;;
  "storage buckets describe "*"--project test-project"*) exit 0 ;;
  "storage rsync "*)
    echo "trace: backup upload"
    exit "${BACKUP_EXIT_CODE:-0}"
    ;;
  "storage ls "*)
    if [[ "${LIST_EXIT_CODE:-0}" != 0 ]]; then
      echo "storage listing unavailable" >&2
      exit "${LIST_EXIT_CODE}"
    fi
    echo gs://test-reports/artifacts/reports/example/index.html
    ;;
  *) echo "unexpected gcloud arguments: $*" >&2; exit 97 ;;
esac
''',
    }
    for name, body in stubs.items():
        executable = binaries / name
        executable.write_text("#!/bin/bash\nset -eu\n" + body, encoding="utf-8")
        executable.chmod(0o755)

    def run(*, backup_exit=0, publish_exit=0, list_exit=0, dry_run=False):
        return subprocess.run(
            ["/bin/bash", str(scripts / "publish-report.sh"),
             "chartsearchai", str(tmp_path / "run"), "example"],
            cwd=tmp_path, capture_output=True, text=True, check=False,
            env={
                **os.environ,
                "PATH": f"{binaries}:/usr/bin:/bin",
                "REPORTS_ROOT": str(reports), "PUBLISH_DRY_RUN": str(int(dry_run)),
                "GCP_PROJECT": "test-project", "GCP_SSH_USER": "test-user",
                "GCP_SSH_KEY": str(tmp_path / "unused-test-key"),
                "REPORTS_BACKUP_BUCKET": "gs://test-reports",
                "BACKUP_EXIT_CODE": str(backup_exit),
                "PUBLISH_EXIT_CODE": str(publish_exit),
                "LIST_EXIT_CODE": str(list_exit),
            },
        )

    return run


def test_success_is_reported_only_after_the_mandatory_backup(publisher):
    result = publisher()
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("trace: publish upload") == 2
    assert "==> objects in gs://test-reports/artifacts/reports: 1" in result.stdout
    success = "==> published: https://reports.example.invalid/example/"
    assert result.stdout.index("trace: backup upload") < result.stdout.index(success)
    assert result.stdout.rstrip().endswith(success)


def test_backup_failure_reports_partial_publication_without_success(publisher):
    result = publisher(backup_exit=23)
    assert result.returncode == 23, result.stdout + result.stderr
    assert result.stdout.count("trace: publish upload") == 2
    assert "trace: backup upload" in result.stdout
    assert "==> published:" not in result.stdout
    assert "already published" in result.stderr
    assert "https://reports.example.invalid/example/" in result.stderr
    assert "backup failed" in result.stderr


def test_publication_failure_does_not_claim_publication_or_attempt_backup(publisher):
    result = publisher(publish_exit=17)
    assert result.returncode == 17, result.stdout + result.stderr
    assert "trace: backup upload" not in result.stdout
    assert "==> published:" not in result.stdout
    assert "already published" not in result.stderr


def test_failed_count_is_unavailable_not_zero_after_a_successful_backup(publisher):
    result = publisher(list_exit=19)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "trace: backup upload" in result.stdout
    assert "==> objects in" not in result.stdout
    assert "backup completed" in result.stderr
    assert "object count unavailable" in result.stderr
    assert result.stdout.rstrip().endswith(
        "==> published: https://reports.example.invalid/example/"
    )


def test_dry_run_only_stages_and_never_publishes_or_backs_up(publisher):
    result = publisher(dry_run=True, publish_exit=17, backup_exit=23)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dry-run staged only" in result.stdout
    assert "trace:" not in result.stdout
    assert "==> published:" not in result.stdout
