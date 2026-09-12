"""Idempotent synthetic-data study accounts, without editing existing role policy."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Callable

from harness.common.openmrs import OpenMrsClient, effective_privileges


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(state, stream, indent=2)
        stream.write("\n")
    temporary.replace(path)


def _authenticate(base_url: str, username: str, password: str) -> dict[str, Any]:
    return OpenMrsClient(base_url, username, password).request("GET", "session")


def provision_users(
    client: OpenMrsClient,
    config: dict[str, Any],
    credentials: Path,
    *,
    authenticate: Callable = _authenticate,
) -> dict[str, Any]:
    accounts = config["accounts"]
    names = [a["username"] for a in accounts]
    if len(set(names)) != len(names) or any(
        not re.fullmatch(r"eval-[a-z0-9-]+", n) for n in names
    ):
        raise RuntimeError("Study usernames must be unique and start with eval-.")
    required = set(config["required_privileges"])
    if not required or any(
        not (p.startswith("Get ") or p == "AI Query Patient Data") for p in required
    ):
        raise RuntimeError(
            "Study access may contain only existing read privileges and AI Query Patient Data."
        )
    state = (
        json.loads(credentials.read_text())
        if credentials.exists()
        else {
            "schema_version": "evaluation_credentials.v1",
            "base_url": client.base_url,
            "accounts": {},
        }
    )
    if state.get("base_url") != client.base_url:
        raise RuntimeError(
            "Credentials belong to a different OpenMRS instance; do not reuse them."
        )
    privileges = {}
    for name in sorted(required):
        value = client.exact("privilege", "name", name)
        if value is None:
            raise RuntimeError(f"Required privilege is unavailable: {name}")
        privileges[name] = value["uuid"]

    access_name = config["access_role"]
    access = client.exact("role", "name", access_name)
    if access and (
        effective_privileges(client, access) != required or access.get("inheritedRoles")
    ):
        raise RuntimeError(
            "Existing study access role differs from the manifest; review it without overwriting it."
        )

    # Inspect every account before creating anything. A collision must not leave
    # half the study provisioned or take over a real user's login.
    existing = {}
    roles = {}
    for account in accounts:
        username, role_name = account["username"], account["role"]
        role = client.exact("role", "name", role_name)
        if not role and account.get("require_existing_role"):
            raise RuntimeError(f"Required existing role is missing: {role_name}")
        if role and "*ALL*" in effective_privileges(client, role):
            raise RuntimeError(f"Study role grants superuser access: {role_name}")
        roles[role_name] = role
        user = client.exact("user", "username", username)
        saved = state["accounts"].get(username)
        if user and not saved:
            raise RuntimeError(
                f"Refusing to take over existing user {username}; no ownership receipt exists."
            )
        if user and saved.get("user_uuid") != user["uuid"]:
            if saved.get("user_uuid"):
                raise RuntimeError(
                    f"Existing user identity changed for {username}; manual review required."
                )
            # A prior request may have succeeded just before the client lost its
            # connection. Only the saved random credential can establish ownership.
            session = authenticate(client.base_url, username, saved["password"])
            if (
                not session.get("authenticated")
                or session.get("user", {}).get("uuid") != user["uuid"]
            ):
                raise RuntimeError(
                    f"Cannot verify ownership of existing user {username}."
                )
        existing[username] = user

    if access is None:
        access = client.request(
            "POST",
            "role",
            {
                "name": access_name,
                "description": "ChartSearchAI synthetic-data research access; not production role isolation.",
                "privileges": list(privileges.values()),
                "inheritedRoles": [],
            },
        )
    report = []
    for account in accounts:
        username, role_name = account["username"], account["role"]
        role = roles[role_name]
        if role is None:
            role = client.request(
                "POST",
                "role",
                {
                    "name": role_name,
                    "description": "Research occupational label; does not establish clinical credentials or data restrictions.",
                    "privileges": [],
                    "inheritedRoles": [access["uuid"]],
                },
            )
            roles[role_name] = role
        role_privileges = effective_privileges(client, role)
        if "*ALL*" in role_privileges:
            raise RuntimeError(f"Study role grants superuser access: {role_name}")
        # Existing occupational roles are immutable here. Assign the study access
        # separately when necessary rather than broadening the role for all users.
        role_ids = [role["uuid"]]
        if not required.issubset(role_privileges):
            role_ids.append(access["uuid"])
        saved = state["accounts"].setdefault(
            username,
            {
                "password": f"Eval{secrets.token_urlsafe(24)}9a",
                "user_uuid": None,
            },
        )
        _save(credentials, state)
        user = existing[username]
        if user is None:
            user = client.request(
                "POST",
                "user",
                {
                    "username": username,
                    "systemId": username,
                    "password": saved["password"],
                    "roles": role_ids,
                    "person": {
                        "names": [
                            {
                                "givenName": "Evaluation",
                                "familyName": username.removeprefix("eval-"),
                            }
                        ],
                        "gender": "U",
                    },
                },
            )
        saved["user_uuid"] = user["uuid"]
        _save(credentials, state)
        verified = client.request("GET", f"user/{user['uuid']}?v=full")
        assigned = {r["uuid"] for r in verified.get("roles", [])}
        if assigned != set(role_ids) or verified.get("retired"):
            raise RuntimeError(
                f"Study account {username} has unexpected roles or is retired; no automatic rewrite performed."
            )
        current_access = client.request("GET", f"role/{access['uuid']}?v=full")
        if effective_privileges(
            client, current_access
        ) != required or current_access.get("inheritedRoles"):
            raise RuntimeError("Server did not retain the requested study access role.")
        report.append(
            {
                "username": username,
                "user_uuid": user["uuid"],
                "role": role_name,
                "additional_inherited_privileges": sorted(role_privileges - required),
            }
        )
    return {
        "schema_version": "evaluation_accounts.v1",
        "accounts": report,
        "credentials_file": str(credentials),
        "login_and_ui_access": "not_yet_verified",
        "role_context_status": "not_verified_by_setup",
    }
