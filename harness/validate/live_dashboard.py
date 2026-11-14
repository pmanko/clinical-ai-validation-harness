"""Ensure the local :8099 live validation dashboard is serving when a run starts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _status_alive(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=timeout) as resp:
            return int(getattr(resp, "status", 200)) == 200
    except Exception:
        return False


def _notify_watch_artifacts(port: int, artifacts_dir: Path) -> None:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/watch",
            data=json.dumps({"artifacts_dir": str(artifacts_dir.resolve())}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.0):
            pass
    except Exception:
        pass


def ensure_live_dashboard(
    project_root: Path | None = None,
    *,
    port: int | None = None,
    force: bool = False,
) -> str | None:
    """Start `scripts/validate-dashboard.py` in the background if `:8099` is not already serving."""
    if not force and not _truthy_env("HARNESS_FORCE_DASHBOARD"):
        if (
            _truthy_env("HARNESS_NO_DASHBOARD")
            or _truthy_env("CI")
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        ):
            return None

    eff_port = int(port if port is not None else os.environ.get("DASH_PORT", "8099"))
    url = f"http://localhost:{eff_port}"
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    if _status_alive(eff_port):
        _notify_watch_artifacts(eff_port, root / "artifacts")
        print(f"    live dashboard: {url}", file=sys.stderr)
        return url

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
