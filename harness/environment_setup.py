"""Parent-owned environment preparation using the existing component scripts."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from harness.common.openmrs import OpenMrsClient
from harness.environment_assets import prepare_assets
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
    owned_database_volumes: set[str] | None = None
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
        if expected[name] == "db":
            owned_database_volumes = mounted
    unowned = volumes.intersection(volume_names) - owned_volumes
    if unowned:
        raise SetupError(
            "An existing data volume has no verified owning container: "
            + ", ".join(sorted(unowned))
            + ". Recover its original deployment; do not initialize over it."
        )
    if found:
        if owned_database_volumes is None:
            raise SetupError(
                "The database container is missing from this partial deployment; recover it before updating."
            )
        database_volume = compose["volumes"]["db-data"]["name"]
        if (
            database_volume not in owned_database_volumes
            or database_volume not in volume_names
        ):
            raise SetupError(
                "The expected database volume is missing or not mounted; do not create an empty replacement."
            )
    return "existing" if found else "absent"


def command(
    root: Path,
    args: list[str],
    *,
    capture: bool = False,
    extra_env: dict[str, str | None] | None = None,
) -> str:
    env = os.environ.copy()
    for key, value in (extra_env or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    result = subprocess.run(
        args,
        cwd=root,
        text=True,
        capture_output=capture,
        check=False,
        env=env,
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


def prepare_inference(
    root: Path, client: OpenMrsClient, *, restored_baseline: bool = False
) -> dict[str, Any]:
    """Start managed dependencies of saved providers without changing their settings."""
    discovery = client.request("GET", "chartsearchai/providers")
    enabled = {
        item["id"] for item in discovery["providers"] if item.get("enabled") is True
    }
    if not enabled or enabled - {"bundled", "hub"}:
        raise SetupError("No supported configured providers; review OpenMRS settings.")
    if discovery.get("defaultProvider") not in enabled:
        raise SetupError(
            "The saved default provider is not enabled; settings were retained."
        )

    def setting(name: str, default: str = "") -> str:
        row = client.exact("systemsetting", "property", name)
        return str(row.get("value") or default).strip() if row else default

    def uses_local_router(endpoint: str) -> bool:
        parsed = urlsplit(endpoint)
        return (
            parsed.scheme == "http"
            and parsed.hostname == "host.docker.internal"
            and parsed.port == int(os.environ.get("LLAMA_ROUTER_PORT", "8077"))
        )

    local_hub = False
    router_needed = False
    if "hub" in enabled:
        endpoint = setting("chartsearchai.hub.endpointUrl")
        if not endpoint:
            raise SetupError(
                "The enabled Hub has no endpoint; configure it explicitly."
            )
        local_hub = (
            endpoint.rstrip("/") == "http://med-agent-hub:8080/v1/chat/completions"
        )
        router_needed = local_hub and uses_local_router(
            os.environ.get("MED_AGENT_LLM_BASE_URL", "http://host.docker.internal:8077")
        )
    if (
        "bundled" in enabled
        and setting("chartsearchai.llm.engine", "local").lower() == "remote"
    ):
        endpoint = setting("chartsearchai.llm.remote.endpointUrl")
        if not endpoint:
            raise SetupError(
                "The bundled remote engine has no endpoint; settings were retained."
            )
        router_needed = router_needed or uses_local_router(endpoint)

    source_file = root / "artifacts/chartsearchai-local/querystore-service.env"
    provision_source = False
    source_keys = ("QUERYSTORE_BASE_URL", "QUERYSTORE_USERNAME", "QUERYSTORE_PASSWORD")
    if local_hub:
        external = [os.environ.get(name) for name in source_keys]
        if any(external) and not all(external):
            raise SetupError(
                "Set all three QueryStore connection values together; credentials were retained."
            )
        provision_source = not any(external) and (
            restored_baseline or not source_file.is_file()
        )
        if (
            provision_source
            and not restored_baseline
            and (
                client.exact("user", "username", "med-agent-hub")
                or client.exact("role", "name", "Med Agent Hub Patient Reader")
            )
        ):
            raise SetupError(
                "The patient reader already exists but its local credentials are missing. "
                "Restore them or configure the existing credentials; setup will not replace them."
            )

    if router_needed:
        command(root, ["bash", "scripts/llama-router-up.sh", "--daemon"])
    if provision_source:
        command(
            root,
            [
                "python3",
                "scripts/provision-querystore-service-account.py",
                "--base-url",
                client.base_url,
                "--internal-base-url",
                "http://backend:8080/openmrs",
                "--admin-user",
                os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"),
                "--admin-password",
                os.environ.get("CHARTSEARCH_ADMIN_PASSWORD", "Admin123"),
                "--output",
                str(source_file),
            ]
            + (["--restore-credentials"] if restored_baseline else []),
        )
    if local_hub:
        # Empty example values are not overrides of the saved reader credentials.
        # Let the existing Make target load its private service environment file.
        command(
            root,
            ["make", "med-agent-hub-up"],
            extra_env=({} if all(external) else {key: None for key in source_keys}),
        )

    # The bundled provider caches endpoint reachability for ten seconds. Wait
    # for a fresh verdict after starting its dependency, without retrying startup.
    for attempt in range(7):
        final = client.request("GET", "chartsearchai/providers")
        current = {p["id"] for p in final["providers"] if p.get("enabled") is True}
        if current != enabled or final.get("defaultProvider") != discovery.get(
            "defaultProvider"
        ):
            raise SetupError(
                "Provider choices changed during setup; inspect without resetting."
            )
        unavailable = [
            p["id"]
            for p in final["providers"]
            if p["id"] in enabled and p.get("ready") is not True
        ]
        if not unavailable:
            break
        if attempt == 6:
            raise SetupError(
                "Configured providers are unavailable: " + ", ".join(unavailable)
            )
        time.sleep(2)

    result = {
        "providers": sorted(enabled),
        "default_provider": final["defaultProvider"],
        "provider_discovery": "checked",
        "model_response": "not_checked",
    }
    if "hub" in enabled:
        profiles = client.request("GET", "chartsearchai/models")
        defaults = [
            p
            for p in profiles.get("data", [])
            if p.get("visibility") == "product"
            and p.get("available") is True
            and p.get("default") is True
            and p.get("id")
        ]
        if len(defaults) != 1:
            raise SetupError(
                "Hub discovery has no unique available default profile; no profile was substituted."
            )
        result["hub_default_profile"] = defaults[0]["id"]
    return result


def prepare_environment(
    root: Path,
    *,
    data_action: str = "preserve",
    baseline: Path | None = None,
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
    if not check_only and not confirm_demo_data:
        raise SetupError(
            "Evaluation preparation includes the required role accounts. Confirm "
            "synthetic/demo data with --confirm-demo-data before changing this instance."
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
        state["model_asset"] = prepare_assets(root, model="gemma-e4b")["model"]
    state["data_action"] = data_action
    state["evaluation_accounts"] = "required"
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
    if data_action != "preserve":
        command(
            root, ["bash", "scripts/chartsearch-configure.sh", "--local-evaluation"]
        )
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
    try:
        inference = prepare_inference(
            root,
            OpenMrsClient(
                f"http://127.0.0.1:{port}/openmrs",
                os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"),
                os.environ.get("CHARTSEARCH_ADMIN_PASSWORD", "Admin123"),
            ),
            restored_baseline=data_action != "preserve",
        )
    except RuntimeError as error:
        raise SetupError(str(error)) from error
    return {
        **state,
        "status": "prepared",
        "applied": True,
        "readiness": "not_checked",
        "evaluation_accounts": "provisioned",
        "account_context": "not_verified",
        "instruction_policy": "not_implemented",
        "inference": inference,
        "next_checks": [
            "completed model response for each enabled provider",
            "patient retrieval",
            "study-user chart and chat access",
            "authenticated roles and login location reach both providers",
            "real answer and conversation reload",
            "browser workflow",
        ],
    }
