import fcntl
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from harness.evaluation_setup import SetupError


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli(tmp_path, monkeypatch):
    module = load("setup-environment")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["setup-environment.py", "check"])
    return module


def test_check_receipt_is_not_a_ready_receipt(cli, tmp_path, monkeypatch, capsys):
    def check(root, **kwargs):
        assert root == tmp_path and kwargs["check_only"] is True
        assert kwargs["data_action"] == "preserve"
        assert kwargs["study"] is False
        return {"status": "preflight_passed", "applied": False}

    monkeypatch.setattr(cli, "prepare_environment", check)
    assert cli.main() == 0
    receipt = json.loads(
        next(
            (tmp_path / "artifacts/evaluation-setup").glob("environment-*.json")
        ).read_text()
    )
    assert receipt["readiness"] == "not_checked"
    assert receipt["applied"] is False
    assert "not application acceptance" in capsys.readouterr().out


def test_failure_keeps_older_receipts_and_returns_nonzero(cli, tmp_path, monkeypatch):
    directory = tmp_path / "artifacts/evaluation-setup"
    directory.mkdir(parents=True)
    previous = directory / "environment-previous.json"
    previous.write_text('{"status":"prepared"}')

    def fail(*args, **kwargs):
        raise SetupError("Deployment belongs to another checkout")

    monkeypatch.setattr(cli, "prepare_environment", fail)
    assert cli.main() == 1
    assert json.loads(previous.read_text())["status"] == "prepared"
    receipts = [json.loads(p.read_text()) for p in directory.glob("environment-*.json")]
    failure = next(r for r in receipts if r["status"] == "failed")
    assert "another checkout" in failure["error"]
    assert failure["readiness"] == "not_checked"


@pytest.mark.parametrize("script", ["setup-environment", "update-evaluation-checkout"])
def test_source_update_and_preparation_share_a_real_process_lock(
    tmp_path, monkeypatch, script
):
    module = load(script)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [f"{script}.py", "check"]
        if script == "setup-environment"
        else [f"{script}.py"],
    )

    def must_not_run(*args, **kwargs):
        pytest.fail("A conflicting operation must not start")

    monkeypatch.setattr(
        module,
        "prepare_environment" if script == "setup-environment" else "update_checkout",
        must_not_run,
    )
    directory = tmp_path / "artifacts/evaluation-setup"
    directory.mkdir(parents=True)
    with (directory / "operation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert module.main() == 1
    assert not list(directory.glob("*.json"))


def test_unsupported_environment_is_not_guessed(cli, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["setup-environment.py", "prepare", "--environment", "anything"]
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
