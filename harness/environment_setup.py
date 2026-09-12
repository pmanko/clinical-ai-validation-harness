"""Parent-owned environment preparation using the existing component scripts."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from harness.evaluation_setup import SetupError, prepare_data, verify_baseline


def check_ownership(
    root: Path,
    compose: dict[str, Any],
    containers: list[dict[str, Any]],
    volume_names: list[str],
) -> str:
    """Refuse ambiguous persistent data or containers from another checkout."""
    root = root.resolve()
    expected = {
        value["container_name"]: name
        for name, value in compose["services"].items()
        if value.get("container_name")
    }
    volumes = {value["name"] for value in compose.get("volumes", {}).values()}
    owned_volumes: set[str] = set()
    found = False
    for item in containers:
        name = item.get("Name", "").removeprefix("/")
        mounted = {
            mount["Name"]
            for mount in item.get("Mounts", [])
            if mount.get("Type") == "volume"
        }
        if name not in expected:
            if mounted & volumes:
                raise SetupError(
                    f"Project data is shared with container {name}; inspect before proceeding."
                )
            continue
        labels = item.get("Config", {}).get("Labels") or {}
        workdir = labels.get("com.docker.compose.project.working_dir")
        if not workdir:
            raise SetupError(
                f"Cannot establish ownership of {name}; no deployment changed."
            )
        if Path(workdir).resolve() not in {root, root / "compose"}:
            raise SetupError(
                f"{name} belongs to another checkout at {workdir}; use that checkout."
            )
        configs = labels.get("com.docker.compose.project.config_files", "").split(",")
        if configs != [str(root / "compose/openmrs-2.8-refapp.yml")]:
            raise SetupError(
                f"{name} uses a different Compose configuration; inspect before proceeding."
            )
        if (
            labels.get("com.docker.compose.project") != compose["name"]
            or labels.get("com.docker.compose.service") != expected[name]
        ):
            raise SetupError(f"Container ownership labels do not match for {name}.")
        found = True
        owned_volumes.update(mounted)
    unowned = volumes.intersection(volume_names) - owned_volumes
    if unowned:
        raise SetupError(
            "An existing data volume has no verified owning container: "
            + ", ".join(sorted(unowned))
            + ". Recover its original deployment; do not initialize over it."
        )
    return "existing" if found else "absent"


def command(
    root: Path,
    args: list[str],
    *,
    capture: bool = False,
    extra_env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        args,
        cwd=root,
        text=True,
        capture_output=capture,
        check=False,
        env={**os.environ, **(extra_env or {})},
    )
    if result.returncode:
        # Command output can contain local credentials. It is not copied into
        # the shareable receipt; interactive scripts report their own diagnostics.
        operation = " ".join(args[:3])
        raise SetupError(
            f"{operation} failed (exit {result.returncode}); setup is incomplete."
        )
    return result.stdout if capture else ""


def inspect_environment(root: Path) -> dict[str, Any]:
    """Read-only inspection. Docker errors are never interpreted as empty data."""
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        raise SetupError(
            "Use macOS, Linux, or a Linux WSL2 shell; native Windows startup is not verified."
        )
    missing = [
        name
        for name in ("git", "bash", "docker", "python3", "make", "curl")
        if not shutil.which(name)
    ]
    if missing:
        raise SetupError("Install required tools first: " + ", ".join(missing))
    context = json.loads(command(root, ["docker", "context", "inspect"], capture=True))
    endpoint = context[0]["Endpoints"]["docker"]["Host"]
    # Docker's explicit context selection overrides DOCKER_HOST.
    if not os.environ.get("DOCKER_CONTEXT"):
        endpoint = os.environ.get("DOCKER_HOST") or endpoint
    if not endpoint.startswith("unix://"):
        raise SetupError(
            "Local setup requires a local Docker socket, not a remote Docker endpoint."
        )
    revision = command(
        root, ["git", "-C", "targets/med-agent-hub", "rev-parse", "HEAD"], capture=True
    ).strip()
    compose = json.loads(
        command(
            root,
            [
                "docker",
                "compose",
                "-f",
                "compose/openmrs-2.8-refapp.yml",
                "config",
                "--format",
                "json",
            ],
            capture=True,
            extra_env={"HUB_BUILD_REVISION": revision},
        )
    )
    ids = command(root, ["docker", "ps", "-aq"], capture=True).split()
    containers = (
        json.loads(command(root, ["docker", "inspect", *ids], capture=True))
        if ids
        else []
    )
    volumes = command(
        root, ["docker", "volume", "ls", "--format", "{{.Name}}"], capture=True
    ).splitlines()
    state = check_ownership(root, compose, containers, volumes)
    by_name = {c.get("Name", "").removeprefix("/"): c for c in containers}
    for service in compose["services"].values():
        existing = by_name.get(service.get("container_name"), {})
        if existing.get("State", {}).get("Running"):
            continue
        for port in service.get("ports", []):
            if port.get("protocol", "tcp") != "tcp" or not port.get("published"):
                continue
            try:
                with socket.socket() as probe:
                    probe.bind(
                        (port.get("host_ip") or "0.0.0.0", int(port["published"]))
                    )
            except OSError as error:
                raise SetupError(
                    f"Host port {port['published']} is already in use; no services changed."
                ) from error
    return {
        "platform": system,
        "processor": platform.machine(),
        "deployment": state,
        "data_action": "preserve",
        "readiness": "not_checked",
    }


def prepare_environment(
    root: Path,
    *,
    data_action: str = "preserve",
    baseline: Path | None = None,
    study: bool = False,
    confirm_demo_data: bool = False,
    check_only: bool = False,
) -> dict[str, Any]:
    """Prepare the selected ChartSearchAI environment, not certify its UI/model.

    Source updating is separate so the caller can reload the new instructions
    before executing them. Reset happens before application upgrades so its
    backup contains the original database, not a partially migrated one.
    """
    if data_action not in {"preserve", "initialize", "reset"}:
        raise SetupError("Data action must be preserve, initialize, or reset.")
    if study and not confirm_demo_data:
        raise SetupError(
            "Role-study accounts require explicit confirmation of synthetic/demo data."
        )
    state = inspect_environment(root)
    if data_action == "initialize" and state["deployment"] != "absent":
        raise SetupError(
            "Initialize is only for a new deployment without existing volumes. Preserve or explicitly reset instead."
        )
    if data_action in {"preserve", "reset"} and state["deployment"] == "absent":
        raise SetupError(
            "No existing deployment. Choose initialize with a verified baseline; no data was created or reset."
        )
    if data_action != "preserve":
        baseline = (
            baseline or root / "artifacts/demo-data/refapp_28_demo.sql.gz"
        ).resolve()
        source = verify_baseline(baseline)
        state["baseline_sha256"] = source["output_sha256"]
    state["data_action"] = data_action
    state["study_accounts"] = "requested" if study else "not_requested"
    command(
        root, ["bash", "scripts/chartsearchai-local.sh", "--prepare-core", "--check"]
    )
    if check_only:
        return {**state, "status": "preflight_passed", "applied": False}

    # Re-read ownership immediately before mutations; a saved receipt does not
    # authorize reuse of containers that have since changed hands.
    if inspect_environment(root)["deployment"] != state["deployment"]:
        raise SetupError(
            "Deployment changed during preflight; inspect and rerun without resetting."
        )
    if data_action == "reset":
        state["data"] = prepare_data(
            root,
            reset=True,
            baseline=baseline,
            database=os.environ.get("OMRS_DB_NAME", "openmrs"),
            run=lambda args: command(root, args),
        )
    command(root, ["bash", "scripts/chartsearchai-local.sh", "--prepare-core"])
    if data_action == "initialize":
        command(
            root,
            [
                "bash",
                "scripts/seed-local.sh",
                "--dump",
                str(baseline),
                "--target",
                os.environ.get("OMRS_DB_NAME", "openmrs"),
            ],
        )
        command(root, ["bash", "scripts/querystore-configure.sh"])
        command(
            root,
            ["make", "querystore-recreate-index", "ALLOW_QUERYSTORE_INDEX_RESET=1"],
        )
    if study:
        port = os.environ.get("HARNESS_PROXY_HTTP_PORT", "8088")
        command(
            root,
            [
                "python3",
                "scripts/provision-evaluation-users.py",
                "--confirm-demo-data",
                "--base-url",
                f"http://127.0.0.1:{port}/openmrs",
            ],
        )
    return {
        **state,
        "status": "prepared",
        "applied": True,
        "readiness": "not_checked",
        "next_checks": [
            "provider and model readiness",
            "patient retrieval",
            "study logins",
            "real answer and conversation reload",
            "browser workflow",
        ],
    }
