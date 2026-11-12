"""Single-path live dashboard (:8099) lifecycle & cross-worktree active-run registration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def dashboard_port(port: int | None = None) -> int:
    if port is not None:
        return int(port)
    return int(os.environ.get("DASH_PORT", "8099"))


def active_run_pointer_path(port: int | None = None) -> Path:
    override = os.environ.get("OPENCLINAI_ACTIVE_RUN_FILE", "").strip()
    if override:
        return Path(override)
    eff_port = dashboard_port(port)
    return Path(tempfile.gettempdir()) / f"openclinai-validate-dashboard-{eff_port}.active-run"


def register_active_run(run_dir: Path | str, *, port: int | None = None) -> None:
    """Record the active run directory so the :8099 monitor tracks it across worktrees/output-dirs."""
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("OPENCLINAI_ACTIVE_RUN_FILE"):
        return
    try:
        resolved = str(Path(run_dir).resolve())
        ptr = active_run_pointer_path(port)
        ptr.parent.mkdir(parents=True, exist_ok=True)
        tmp = ptr.with_suffix(".tmp")
        tmp.write_text(resolved + "\n", encoding="utf-8")
        tmp.replace(ptr)
    except OSError:
        pass


def read_registered_active_run(port: int | None = None) -> str | None:
    """Return the registered active run directory if it exists on disk."""
    try:
        ptr = active_run_pointer_path(port)
        if not ptr.is_file():
            return None
        val = ptr.read_text(encoding="utf-8").strip()
        if val and os.path.isdir(val):
            return val
    except OSError:
        return None
    return None


def _status_alive(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=timeout) as resp:
            return int(getattr(resp, "status", 200)) == 200
    except Exception:
        return False


def ensure_live_dashboard(
    project_root: Path | None = None,
    *,
    port: int | None = None,
) -> str | None:
    """Ensure the live :8099 validation dashboard is running before any `harness-cli * run`."""
    if not _truthy_env("HARNESS_FORCE_DASHBOARD"):
        if (
            _truthy_env("HARNESS_NO_DASHBOARD")
            or _truthy_env("CI")
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        ):
            return None

    eff_port = dashboard_port(port)
    url = f"http://localhost:{eff_port}"
    if _status_alive(eff_port):
        print(f"    live dashboard: {url}", file=sys.stderr)
        return url

    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    script_path = root / "scripts" / "validate-dashboard.py"
    if not script_path.is_file():
        return None

    runtime_dir = root / "artifacts" / "validate-dashboard"
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        log_fh = (runtime_dir / "dashboard.log").open("ab")
    except OSError:
        log_fh = open(os.devnull, "ab")

    env = dict(os.environ)
    env["DASH_PORT"] = str(eff_port)
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(script_path)],
            cwd=str(root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            (runtime_dir / "dashboard.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
        except OSError:
            pass
    except OSError:
        log_fh.close()
        return None
    finally:
        log_fh.close()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if _status_alive(eff_port, timeout=1.0):
            print(f"    live dashboard: {url}", file=sys.stderr)
            return url
        time.sleep(0.15)
    return None
