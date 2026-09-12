"""Study provisioning must not take over users or rewrite existing role policy."""

import copy
import json
import stat
from pathlib import Path

import pytest

from harness.evaluation_users import provision_users


class Rest:
    base_url = "http://localhost/openmrs"

    def __init__(self):
        self.records = {"role": {}, "user": {}, "privilege": {}}
        self.writes = []
        self.records["privilege"]["p"] = {"uuid": "p", "name": "AI Query Patient Data"}

    def exact(self, resource, field, value):
        return next(
            (
                copy.deepcopy(r)
                for r in self.records[resource].values()
                if r.get(field) == value
            ),
            None,
        )

    def request(self, method, path, payload=None):
        kind, _, uuid = path.partition("/")
        uuid = uuid.split("?")[0]
        if method == "GET":
            return copy.deepcopy(self.records[kind][uuid])
        assert method == "POST" and not uuid, "Existing objects must not be edited"
        self.writes.append((kind, copy.deepcopy(payload)))
        uuid = f"{kind}-{len(self.records[kind]) + 1}"
        row = {"uuid": uuid, **copy.deepcopy(payload)}
        for field, resource in (
            ("privileges", "privilege"),
            ("inheritedRoles", "role"),
            ("roles", "role"),
        ):
            if field in row:
                row[field] = [
                    {"uuid": key, "name": self.records[resource][key].get("name")}
                    for key in row[field]
                ]
        self.records[kind][uuid] = row
        return copy.deepcopy(row)


@pytest.fixture
def config():
    return {
        "access_role": "Application: Uses ChartSearchAI (Research)",
        "required_privileges": ["AI Query Patient Data"],
        "accounts": [
            {"username": "eval-peer", "role": "Organizational: Peer Educator"}
        ],
    }


def test_repeat_provisioning_preserves_credentials_and_ids(tmp_path, config):
    client = Rest()
    path = tmp_path / "private.json"
    first = provision_users(client, config, path)
    saved = json.loads(path.read_text())
    writes = len(client.writes)

    second = provision_users(client, config, path)

    assert first == second
    assert len(client.writes) == writes
    assert json.loads(path.read_text()) == saved
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert saved["accounts"]["eval-peer"]["password"] not in json.dumps(first)
    org = client.exact("role", "name", "Organizational: Peer Educator")
    shared = client.exact("role", "name", config["access_role"])
    assert org["inheritedRoles"][0]["uuid"] == shared["uuid"]
    assert not shared["inheritedRoles"]


def test_existing_user_without_ownership_receipt_is_not_taken_over(tmp_path, config):
    client = Rest()
    client.records["user"]["other"] = {"uuid": "other", "username": "eval-peer"}
    with pytest.raises(RuntimeError, match="existing user"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_missing_privilege_prevents_all_mutations(tmp_path, config):
    client = Rest()
    config["required_privileges"].append("Get Missing Test Resource")
    with pytest.raises(RuntimeError, match="Get Missing Test Resource"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_existing_occupational_role_is_not_rewritten(tmp_path, config):
    client = Rest()
    client.records["role"]["doctor"] = {
        "uuid": "doctor",
        "name": "Organizational: Doctor",
        "privileges": [{"name": "Get Orders"}],
        "inheritedRoles": [],
    }
    config["accounts"][0]["role"] = "Organizational: Doctor"
    config["accounts"][0]["require_existing_role"] = True
    original = copy.deepcopy(client.records["role"]["doctor"])

    result = provision_users(client, config, tmp_path / "private.json")

    assert client.records["role"]["doctor"] == original
    assert result["accounts"][0]["additional_inherited_privileges"] == ["Get Orders"]


def test_missing_required_existing_role_prevents_all_mutations(tmp_path, config):
    client = Rest()
    config["accounts"][0]["require_existing_role"] = True
    with pytest.raises(RuntimeError, match="Required existing role"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_shared_role_with_extra_privileges_is_not_silently_modified(tmp_path, config):
    client = Rest()
    client.records["role"]["shared"] = {
        "uuid": "shared",
        "name": config["access_role"],
        "privileges": [{"name": "Manage Users"}],
        "inheritedRoles": [],
    }
    with pytest.raises(RuntimeError, match="access role"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_receipt_is_bound_to_instance(tmp_path, config):
    client = Rest()
    path = tmp_path / "private.json"
    provision_users(client, config, path)
    client.base_url = "http://different-host/openmrs"
    with pytest.raises(RuntimeError, match="different OpenMRS"):
        provision_users(client, config, path)


def test_superuser_parent_is_rejected(tmp_path, config):
    client = Rest()
    client.records["role"]["super"] = {"uuid": "super", "name": "System Developer"}
    client.records["role"]["peer"] = {
        "uuid": "peer",
        "name": "Organizational: Peer Educator",
        "inheritedRoles": [{"uuid": "super"}],
    }
    with pytest.raises(RuntimeError, match="superuser"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_interrupted_user_creation_recovers_only_with_saved_credential(
    tmp_path, config
):
    class InterruptedRest(Rest):
        def request(self, method, path, payload=None):
            result = super().request(method, path, payload)
            if method == "POST" and path == "user":
                raise ConnectionError("response lost after server created the user")
            return result

    client = InterruptedRest()
    path = tmp_path / "private.json"
    with pytest.raises(ConnectionError):
        provision_users(client, config, path)
    saved = json.loads(path.read_text())["accounts"]["eval-peer"]
    user = client.exact("user", "username", "eval-peer")
    assert saved["user_uuid"] is None
    calls = []

    def authenticate(base_url, username, password):
        calls.append((username, password))
        return {"authenticated": True, "user": {"uuid": user["uuid"]}}

    writes = len(client.writes)
    result = provision_users(client, config, path, authenticate=authenticate)
    assert len(client.writes) == writes
    assert calls == [("eval-peer", saved["password"])]
    assert result["accounts"][0]["user_uuid"] == user["uuid"]


def test_changed_managed_account_roles_are_not_overwritten(tmp_path, config):
    client = Rest()
    path = tmp_path / "private.json"
    provision_users(client, config, path)
    user = next(iter(client.records["user"].values()))
    user["roles"] = []
    writes = len(client.writes)
    with pytest.raises(RuntimeError, match="unexpected roles"):
        provision_users(client, config, path)
    assert len(client.writes) == writes


def test_write_privileges_are_rejected_before_any_mutation(tmp_path, config):
    client = Rest()
    config["required_privileges"].append("Edit Patients")
    with pytest.raises(RuntimeError, match="read privileges"):
        provision_users(client, config, tmp_path / "private.json")
    assert not client.writes


def test_complete_baseline_manifest_provisions_all_planned_accounts(tmp_path):
    config = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "datasets/validation/evaluation-roles.json"
        ).read_text()
    )
    client = Rest()
    for name in config["required_privileges"]:
        client.records["privilege"][name] = {"uuid": name, "name": name}
    for name in ("Organizational: Doctor", "Organizational: Nurse"):
        client.records["role"][name] = {
            "uuid": name,
            "name": name,
            "inheritedRoles": [],
            "privileges": [],
        }
    path = tmp_path / "private.json"
    result = provision_users(client, config, path)
    assert {a["username"] for a in result["accounts"]} == {
        "eval-clinical-officer",
        "eval-nurse",
        "eval-pharmacy",
        "eval-counsellor",
        "eval-records",
        "eval-doctor",
        "eval-peer",
    }
    saved = path.read_bytes()
    writes = len(client.writes)
    assert provision_users(client, config, path) == result
    assert path.read_bytes() == saved
    assert len(client.writes) == writes


def test_explicit_database_reset_recreates_accounts_with_retained_passwords(
    tmp_path, config
):
    path = tmp_path / "private.json"
    provision_users(Rest(), config, path)
    original = json.loads(path.read_text())["accounts"]["eval-peer"]["password"]
    restored = Rest()  # Portable clinical corpus contains no managed study users.
    result = provision_users(restored, config, path)
    assert result["accounts"][0]["username"] == "eval-peer"
    assert json.loads(path.read_text())["accounts"]["eval-peer"]["password"] == original
    user_payload = next(payload for kind, payload in restored.writes if kind == "user")
    assert user_payload["password"] == original
