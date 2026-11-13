"""Enforce the local :8099 live validation dashboard whenever an evaluation run executes."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import quote
import urllib.request


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _status_payload(
    port: int,
    *,
    run: str | None = None,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    suffix = f"?run={quote(run)}" if run else ""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/status{suffix}",
            timeout=timeout,
        ) as resp:
            if int(getattr(resp, "status", 200)) != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _status_alive(port: int, timeout: float = 5.0) -> bool:
    return _status_payload(port, timeout=timeout) is not None


def _register_watch(
    port: int,
    *,
    artifacts_dir: Path,
    output_dir: Path | None = None,
    run_dir: Path | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    body: dict[str, str] = {"artifacts_dir": str(artifacts_dir.resolve())}
    if output_dir is not None:
        body["output_dir"] = str(output_dir.resolve())
    if run_dir is not None:
        body["run_dir"] = str(run_dir.resolve())
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/watch",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(
            f"Live validation dashboard at http://127.0.0.1:{port} failed /api/watch registration: {exc}"
        ) from exc

    if status_code != 200:
        raise RuntimeError(
            f"Live validation dashboard at http://127.0.0.1:{port} returned HTTP {status_code} from /api/watch"
        )
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Live validation dashboard at http://127.0.0.1:{port} returned invalid JSON from /api/watch: {raw!r}"
        ) from exc
    if not isinstance(parsed, dict) or parsed.get("ok") is not True:
        raise RuntimeError(
            f"Live validation dashboard at http://127.0.0.1:{port} rejected /api/watch payload: {parsed!r}"
        )
    return parsed


def _tail_log(log_path: Path, max_chars: int = 800) -> str:
    try:
        if not log_path.is_file():
            return "(no dashboard.log written)"
        text = log_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return "(dashboard.log empty)"
        return text[-max_chars:]
    except OSError as exc:
        return f"(failed to read dashboard.log: {exc})"


def ensure_live_dashboard(
    project_root: Path | None = None,
    *,
    run_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    port: int | None = None,
    force: bool = False,
) -> str | None:
    """Ensure `harness.validate.dashboard_server` is serving on `:8099` and watching `run_dir`."""
    if not force and not _truthy_env("HARNESS_FORCE_DASHBOARD"):
        if _truthy_env("CI") or bool(os.environ.get("PYTEST_CURRENT_TEST")):
            return None

    eff_port = int(port if port is not None else os.environ.get("DASH_PORT", "8099"))
    url = f"http://localhost:{eff_port}"
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    resolved_run_dir = Path(run_dir).resolve() if run_dir is not None else None
    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else (resolved_run_dir.parent if resolved_run_dir is not None else None)
    )

    if not _status_alive(eff_port):
        if importlib.util.find_spec("harness.validate.dashboard_server") is None:
            raise RuntimeError(
                "Live validation dashboard module 'harness.validate.dashboard_server' not found; "
                "evaluation runs cannot execute without a live dashboard."
            )

        if root.is_dir():
            runtime_dir = root / "artifacts" / "validate-dashboard"
            launch_cwd = root
        else:
            runtime_dir = (
                resolved_output_dir or Path(tempfile.gettempdir())
            ) / "validate-dashboard"
            launch_cwd = resolved_output_dir if (resolved_output_dir and resolved_output_dir.is_dir()) else Path.cwd()
        log_path = runtime_dir / "dashboard.log"
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            log_fh = log_path.open("ab")
        except OSError:
            log_fh = open(os.devnull, "ab")

        env = dict(os.environ)
        env["DASH_PORT"] = str(eff_port)
        env.pop("DASH_RUN", None)
        if root.is_dir():
            env["OPENCLINAI_DASHBOARD_ROOT"] = str(root)
        if (root / "harness").is_dir():
            existing_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{root}{os.pathsep}{existing_pp}" if existing_pp else str(root)

        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", "-m", "harness.validate.dashboard_server"],
                cwd=str(launch_cwd),
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
        except OSError as exc:
            log_fh.close()
            raise RuntimeError(
                f"Failed to launch live validation dashboard (harness.validate.dashboard_server): {exc}"
            ) from exc
        finally:
            log_fh.close()

        deadline = time.monotonic() + 8.0
        alive = False
        while time.monotonic() < deadline:
            if _status_alive(eff_port, timeout=2.5):
                alive = True
                break
            if proc.poll() is not None:
                if _status_alive(eff_port, timeout=1.0):
                    alive = True
                break
            time.sleep(0.15)

        if not alive:
            log_tail = _tail_log(log_path)
            raise RuntimeError(
                f"Live validation dashboard failed to bind/respond on {url} within 8.0s. "
                f"Log tail: {log_tail}"
            )

    _register_watch(
        eff_port,
        artifacts_dir=root / "artifacts",
        output_dir=resolved_output_dir,
        run_dir=resolved_run_dir,
    )

    if resolved_run_dir is not None and resolved_run_dir.is_dir():
        payload = _status_payload(eff_port, run=resolved_run_dir.name)
        active_name = payload.get("run") if isinstance(payload, dict) else None
        if active_name != resolved_run_dir.name:
            raise RuntimeError(
                f"Live validation dashboard at {url} reported run={active_name!r} instead of "
                f"{resolved_run_dir.name!r} after registering {resolved_run_dir}; "
                "clear DASH_RUN or restart harness.validate.dashboard_server so the target run is monitored."
            )

    suffix = f" (watching {resolved_run_dir.name})" if resolved_run_dir is not None else ""
    print(f"    live dashboard: {url}{suffix}", file=sys.stderr)
    return url
