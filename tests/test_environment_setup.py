"""The parent workflow must not turn startup trouble into a data reset."""

import pytest

import harness.environment_setup as setup
from harness.evaluation_setup import SetupError


@pytest.fixture
def actions(monkeypatch):
    calls = []
    monkeypatch.setattr(
        setup, "inspect_environment", lambda root: {"deployment": "existing"}
    )
    monkeypatch.setattr(setup, "command", lambda root, args: calls.append(args))
    monkeypatch.setattr(
        setup, "verify_baseline", lambda path: {"output_sha256": "verified"}
    )
    return calls


def test_evaluation_preparation_includes_required_accounts_without_settings_or_reset(
    tmp_path, actions
):
    report = setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert actions == [
        ["bash", "scripts/chartsearchai-local.sh", "--prepare-core", "--check"],
        ["bash", "scripts/chartsearchai-local.sh", "--prepare-core"],
        [
            "python3",
            "scripts/provision-evaluation-users.py",
            "--confirm-demo-data",
            "--base-url",
            "http://127.0.0.1:8088/openmrs",
        ],
    ]
    assert report["data_action"] == "preserve"
    assert report["evaluation_accounts"] == "provisioned"
    assert report["readiness"] == "not_checked"
    assert report["account_context"] == "not_verified"
    assert report["instruction_policy"] == "not_implemented"
    assert not any("role-to-instruction" in check for check in report["next_checks"])


def test_check_stops_before_mutation(tmp_path, actions):
    report = setup.prepare_environment(tmp_path, check_only=True)
    assert len(actions) == 1 and actions[0][-1] == "--check"
    assert report["applied"] is False


def test_initialize_refuses_any_existing_deployment(tmp_path, actions):
    with pytest.raises(SetupError, match="new deployment"):
        setup.prepare_environment(
            tmp_path, data_action="initialize", confirm_demo_data=True
        )
    assert actions == []


def test_missing_deployment_is_not_interpreted_as_permission_to_seed(
    tmp_path, actions, monkeypatch
):
    monkeypatch.setattr(
        setup, "inspect_environment", lambda root: {"deployment": "absent"}
    )
    with pytest.raises(SetupError, match="Choose initialize"):
        setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert actions == []


def test_initialize_has_to_pass_baseline_verification_before_build(
    tmp_path, actions, monkeypatch
):
    monkeypatch.setattr(
        setup, "inspect_environment", lambda root: {"deployment": "absent"}
    )

    def invalid(path):
        raise SetupError("corrupt baseline")

    monkeypatch.setattr(setup, "verify_baseline", invalid)
    with pytest.raises(SetupError, match="corrupt"):
        setup.prepare_environment(
            tmp_path, data_action="initialize", confirm_demo_data=True
        )
    assert actions == []


def test_explicit_initialize_restores_verified_package_and_materializes_index(
    tmp_path, actions, monkeypatch
):
    monkeypatch.setattr(
        setup, "inspect_environment", lambda root: {"deployment": "absent"}
    )
    baseline = tmp_path / "baseline.sql.gz"
    report = setup.prepare_environment(
        tmp_path, data_action="initialize", baseline=baseline, confirm_demo_data=True
    )
    assert actions[2] == [
        "bash",
        "scripts/seed-local.sh",
        "--dump",
        str(baseline),
        "--target",
        "openmrs",
    ]
    assert actions[3] == ["bash", "scripts/querystore-configure.sh"]
    assert actions[4] == [
        "make",
        "querystore-recreate-index",
        "ALLOW_QUERYSTORE_INDEX_RESET=1",
    ]
    assert report["baseline_sha256"] == "verified"
    assert "scripts/provision-evaluation-users.py" in actions[-1]


def test_reset_backups_precede_any_application_upgrade(tmp_path, actions, monkeypatch):
    def reset(root, **kwargs):
        assert kwargs["reset"] is True
        actions.append(["verified-backup-and-reset"])
        return {"backup": "private-backup.sql.gz"}

    monkeypatch.setattr(setup, "prepare_data", reset)
    report = setup.prepare_environment(
        tmp_path, data_action="reset", confirm_demo_data=True
    )
    assert actions[1] == ["verified-backup-and-reset"]
    assert actions[2] == ["bash", "scripts/chartsearchai-local.sh", "--prepare-core"]
    assert report["data"]["backup"] == "private-backup.sql.gz"
    assert "scripts/provision-evaluation-users.py" in actions[-1]


def test_startup_error_does_not_trigger_seed_or_retry(tmp_path, actions, monkeypatch):
    def fail(root, args):
        actions.append(args)
        if "--check" not in args:
            raise SetupError("Docker startup failed")

    monkeypatch.setattr(setup, "command", fail)
    with pytest.raises(SetupError, match="Docker startup failed"):
        setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert len(actions) == 2
    assert not any("scripts/seed-local.sh" in call for call in actions)


def test_preparation_requires_synthetic_data_confirmation_but_accounts_are_not_optional(
    tmp_path, actions
):
    with pytest.raises(SetupError, match="synthetic/demo"):
        setup.prepare_environment(tmp_path)
    assert actions == []
    setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert actions[-1] == [
        "python3",
        "scripts/provision-evaluation-users.py",
        "--confirm-demo-data",
        "--base-url",
        "http://127.0.0.1:8088/openmrs",
    ]


def test_changed_deployment_between_inspections_stops_before_mutation(
    tmp_path, actions, monkeypatch
):
    values = iter(["existing", "absent"])
    monkeypatch.setattr(
        setup, "inspect_environment", lambda root: {"deployment": next(values)}
    )
    with pytest.raises(SetupError, match="changed during preflight"):
        setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert len(actions) == 1 and "--check" in actions[0]


def test_account_provision_failure_cannot_report_prepared(
    tmp_path, actions, monkeypatch
):
    def fail(root, args):
        actions.append(args)
        if "scripts/provision-evaluation-users.py" in args:
            raise SetupError("Account setup failed")

    monkeypatch.setattr(setup, "command", fail)
    with pytest.raises(SetupError, match="Account setup failed"):
        setup.prepare_environment(tmp_path, confirm_demo_data=True)
    assert len(actions) == 3


def test_invalid_data_action_is_rejected_before_any_inspection(tmp_path, actions):
    with pytest.raises(SetupError, match="Data action"):
        setup.prepare_environment(tmp_path, data_action="guess")
    assert actions == []
