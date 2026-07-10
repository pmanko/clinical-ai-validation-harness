"""Local llama-router process policy for validation runs.

The harness selects the logical backend per request, but llama.cpp's router-mode
residency cap is a process-level startup flag. This module reconciles that local
process setting at backend boundaries so high-memory arms can run with
``--models-max 1`` while normal arms keep the warm-cache default.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .models import Backend

_DEFAULT_PORT = 8077
_DEFAULT_MODELS_MAX = 4
_FALSEY = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class RouterPolicyResult:
    schema_version: str
    action: str
    status: str
    requested_models_max: int
    current_models_max: int | None = None
    pid: int | None = None
    detail: str = ""


def effective_llama_router_models_max(backend: Backend) -> int | None:
    """Return the arm's requested llama-router residency cap.

    Backends can opt in explicitly with ``llamaRouterModelsMax``. Llama-backed
    arms without an explicit value use the local default of 4, which matters when
    a normal arm follows a high-memory arm in the same sequential run.
    """
    if not _uses_local_llama_router(backend):
        return None
    if backend.llama_router_models_max is not None:
        return backend.llama_router_models_max
    return _DEFAULT_MODELS_MAX


def reconcile_llama_router_for_backend(
    backend: Backend,
    *,
    project_root: Path | str = ".",
    port: int = _DEFAULT_PORT,
    startup_timeout_s: float = 90.0,
) -> dict[str, Any] | None:
    requested = effective_llama_router_models_max(backend)
    if requested is None:
        return None

    if os.environ.get("VALIDATE_MANAGE_LLAMA_ROUTER", "1").strip().lower() in _FALSEY:
        return asdict(RouterPolicyResult(
            schema_version="llama_router_policy.v1",
            action="skipped",
            status="disabled",
            requested_models_max=requested,
            detail="VALIDATE_MANAGE_LLAMA_ROUTER disabled local router reconciliation.",
        ))

    root = Path(project_root).resolve()
    parents = _router_parent_processes(root, port)
    current = _current_models_max(root, parents)
    reachable = _router_reachable(port)

    if reachable and current == requested:
        return asdict(RouterPolicyResult(
            schema_version="llama_router_policy.v1",
            action="noop",
            status="ready",
            requested_models_max=requested,
            current_models_max=current,
            pid=parents[0]["pid"] if parents else None,
        ))

    if reachable or parents:
        if not parents:
            raise RuntimeError(
                f"llama-router is reachable on :{port}, but no local llama-server "
                "process for the canonical router was found; stop it manually or set "
                "VALIDATE_MANAGE_LLAMA_ROUTER=0."
            )
        _stop_router_tree(parents)

    pid = _start_router(root, requested)
    _wait_for_router(port, startup_timeout_s)
    _write_marker(root, requested, pid)
    return asdict(RouterPolicyResult(
        schema_version="llama_router_policy.v1",
        action="restarted" if reachable or parents else "started",
        status="ready",
        requested_models_max=requested,
        current_models_max=current,
        pid=pid,
    ))


def _uses_local_llama_router(backend: Backend) -> bool:
    local_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    for endpoint in (backend.endpoint_url, backend.indepth_endpoint or ""):
        if not endpoint:
            continue
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            continue
        if host == "med-agent-hub":
            return True
        if host in local_hosts and port in {_DEFAULT_PORT, 8080}:
            return True
    return False


def _router_reachable(port: int) -> bool:
    try:
        resp = requests.get(f"http://localhost:{port}/v1/models", timeout=4)
        return resp.ok
    except requests.RequestException:
        return False


def _ps_rows() -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)$", line)
        if not m:
            continue
        rows.append({"pid": int(m.group(1)), "ppid": int(m.group(2)), "command": m.group(3)})
    return rows


def _router_parent_processes(root: Path, port: int) -> list[dict[str, Any]]:
    preset = str(root / "scripts" / "llama-router.ini")
    out = []
    for row in _ps_rows():
        cmd = row["command"]
        if "llama-server" not in cmd:
            continue
        has_port = re.search(rf"--port(?:=|\s+){port}\b", cmd) is not None
        has_preset = preset in cmd and "--models-preset" in cmd
        if has_port or has_preset:
            out.append(row)
    return out


def _current_models_max(root: Path, parents: list[dict[str, Any]]) -> int | None:
    for row in parents:
        m = re.search(r"--models-max(?:=|\s+)(\d+)\b", row["command"])
        if m:
            return int(m.group(1))
    marker = root / "artifacts" / "llama-router.models-max"
    try:
        return int(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _descendant_pids(root_pids: set[int]) -> set[int]:
    by_parent: dict[int, list[int]] = {}
    for row in _ps_rows():
        by_parent.setdefault(row["ppid"], []).append(row["pid"])
    found: set[int] = set()
    stack = list(root_pids)
    while stack:
        pid = stack.pop()
        for child in by_parent.get(pid, []):
            if child not in found:
                found.add(child)
                stack.append(child)
    return found


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _stop_router_tree(parents: list[dict[str, Any]]) -> None:
    roots = {row["pid"] for row in parents}
    pids = roots | _descendant_pids(roots)
    if not pids:
        return
    for sig, wait_s in ((signal.SIGTERM, 8.0), (signal.SIGKILL, 3.0)):
        for pid in sorted(pids, reverse=True):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if not any(_pid_alive(pid) for pid in pids):
                return
            time.sleep(0.2)


def _start_router(root: Path, models_max: int) -> int:
    log_dir = root / "artifacts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"llama-router-models-max-{models_max}.log"
    env = os.environ.copy()
    env["LLAMA_ROUTER_MODELS_MAX"] = str(models_max)
    log = log_path.open("ab")
    try:
        proc = subprocess.Popen(
            ["bash", str(root / "scripts" / "llama-router-up.sh")],
            cwd=root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()
    return proc.pid


def _wait_for_router(port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error = ""
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"http://localhost:{port}/v1/models", timeout=4)
            if resp.ok:
                return
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"llama-router did not become ready on :{port}: {last_error}")


def _write_marker(root: Path, models_max: int, pid: int) -> None:
    marker = root / "artifacts" / "llama-router.models-max"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{models_max}\n", encoding="utf-8")
    (root / "artifacts" / "llama-router.pid").write_text(f"{pid}\n", encoding="utf-8")
