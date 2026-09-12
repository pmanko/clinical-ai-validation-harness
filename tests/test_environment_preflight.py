"""Ownership checks use Docker's live inventory, not a stale local receipt."""

import json
from pathlib import Path

import pytest

from harness.environment_setup import check_ownership
import harness.environment_setup as setup
from harness.evaluation_setup import SetupError


def definition(root):
    return {
        "name": "compose",
        "services": {
            "db": {"container_name": "harness-openmrs-db"},
            "backend": {"container_name": "harness-openmrs-backend"},
        },
        "volumes": {"db-data": {"name": "compose_db-data"}},
    }


def container(root, name="harness-openmrs-db", service="db"):
    return {
        "Name": "/" + name,
        "Config": {
            "Labels": {
                "com.docker.compose.project": "compose",
                "com.docker.compose.service": service,
                "com.docker.compose.project.working_dir": str(root / "compose"),
                "com.docker.compose.project.config_files": str(
                    root / "compose/openmrs-2.8-refapp.yml"
                ),
            }
        },
        "Mounts": [{"Type": "volume", "Name": "compose_db-data"}],
    }


def test_first_install_has_no_existing_containers_or_volumes(tmp_path):
    assert check_ownership(tmp_path, definition(tmp_path), [], []) == "absent"


def test_leftover_application_container_does_not_prove_database_exists(tmp_path):
    value = container(tmp_path, name="harness-openmrs-backend", service="backend")
    value["Mounts"] = []
    with pytest.raises(SetupError, match="database container"):
        check_ownership(tmp_path, definition(tmp_path), [value], [])


def test_database_container_must_retain_its_expected_data_mount(tmp_path):
    value = container(tmp_path)
    value["Mounts"] = []
    with pytest.raises(SetupError, match="database volume"):
        check_ownership(tmp_path, definition(tmp_path), [value], [])


def test_existing_stack_belongs_to_this_checkout(tmp_path):
    assert (
        check_ownership(
            tmp_path, definition(tmp_path), [container(tmp_path)], ["compose_db-data"]
        )
        == "existing"
    )


def test_other_checkout_is_never_taken_over(tmp_path):
    with pytest.raises(SetupError, match="another checkout"):
        check_ownership(tmp_path, definition(tmp_path), [container(Path("/other"))], [])


def test_unlabeled_container_is_not_assumed_to_be_ours(tmp_path):
    with pytest.raises(SetupError, match="ownership"):
        check_ownership(
            tmp_path,
            definition(tmp_path),
            [{"Name": "/harness-openmrs-db", "Config": {"Labels": {}}}],
            [],
        )


def test_volume_without_owning_container_requires_manual_recovery(tmp_path):
    with pytest.raises(SetupError, match="existing data volume"):
        check_ownership(tmp_path, definition(tmp_path), [], ["compose_db-data"])


def test_unrelated_docker_workloads_do_not_block_setup(tmp_path):
    assert (
        check_ownership(
            tmp_path,
            definition(tmp_path),
            [{"Name": "/another-app", "Config": {"Labels": {}}}],
            ["other_data"],
        )
        == "absent"
    )


def test_same_project_name_is_not_enough_to_own_a_stack(tmp_path):
    value = container(tmp_path)
    value["Config"]["Labels"]["com.docker.compose.project.config_files"] = (
        "/other/compose.yml"
    )
    with pytest.raises(SetupError, match="configuration"):
        check_ownership(tmp_path, definition(tmp_path), [value], [])


def test_existing_volume_mounted_by_other_container_is_not_adopted(tmp_path):
    value = container(tmp_path)
    value["Mounts"] = []
    with pytest.raises(SetupError, match="existing data volume"):
        check_ownership(tmp_path, definition(tmp_path), [value], ["compose_db-data"])


def test_shared_owned_volume_cannot_also_be_mounted_by_foreign_workload(tmp_path):
    foreign = {
        "Name": "/another-app",
        "Mounts": [{"Type": "volume", "Name": "compose_db-data"}],
    }
    with pytest.raises(SetupError, match="shared with"):
        check_ownership(
            tmp_path,
            definition(tmp_path),
            [container(tmp_path), foreign],
            ["compose_db-data"],
        )


@pytest.fixture
def docker_inventory(tmp_path, monkeypatch):
    calls = []
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/" + name)

    def run(root, args, **kwargs):
        calls.append((args, kwargs))
        if args[:3] == ["docker", "context", "inspect"]:
            return json.dumps(
                [{"Endpoints": {"docker": {"Host": "unix:///tmp/docker.sock"}}}]
            )
        if args[0] == "git":
            return "exact-hub-pin\n"
        if args[:2] == ["docker", "compose"]:
            assert kwargs["extra_env"]["HUB_BUILD_REVISION"] == "exact-hub-pin"
            return json.dumps(definition(tmp_path))
        return ""

    monkeypatch.setattr(setup, "command", run)
    return calls


def test_read_only_inventory_includes_exact_hub_revision(tmp_path, docker_inventory):
    result = setup.inspect_environment(tmp_path)
    assert result["deployment"] == "absent"
    assert result["platform"] == "Linux"
    assert result["readiness"] == "not_checked"
    assert not any("up" in args or "start" in args for args, _ in docker_inventory)


def test_remote_docker_host_is_refused_before_inventory(
    tmp_path, docker_inventory, monkeypatch
):
    monkeypatch.setenv("DOCKER_HOST", "ssh://production-host")
    with pytest.raises(SetupError, match="local Docker socket"):
        setup.inspect_environment(tmp_path)
    assert len(docker_inventory) == 1


def test_explicit_remote_context_cannot_hide_behind_a_local_host_variable(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(setup.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setup.shutil, "which", lambda name: name)
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/local.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")

    def remote(*args, **kwargs):
        return json.dumps(
            [{"Endpoints": {"docker": {"Host": "ssh://production-host"}}}]
        )

    monkeypatch.setattr(setup, "command", remote)
    with pytest.raises(SetupError, match="local Docker socket"):
        setup.inspect_environment(tmp_path)


def test_docker_failure_never_becomes_absent_deployment(
    tmp_path, docker_inventory, monkeypatch
):
    def failed(*args, **kwargs):
        raise SetupError("Docker unavailable")

    monkeypatch.setattr(setup, "command", failed)
    with pytest.raises(SetupError, match="unavailable"):
        setup.inspect_environment(tmp_path)


def test_missing_tools_are_reported_before_docker(
    tmp_path, docker_inventory, monkeypatch
):
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: None if name == "docker" else name
    )
    with pytest.raises(SetupError, match="Install required tools first: docker"):
        setup.inspect_environment(tmp_path)
    assert docker_inventory == []


def test_native_windows_has_an_explicit_supported_shell_message(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.platform, "system", lambda: "Windows")
    with pytest.raises(SetupError, match="WSL2"):
        setup.inspect_environment(tmp_path)
