"""Small OpenMRS REST client shared by local provisioning tools."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class OpenMrsClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}/ws/rest/v1/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            # Response bodies can echo credentials or clinical data. Keep these
            # out of setup receipts and console output.
            raise RuntimeError(
                f"OpenMRS {method} {path} failed: HTTP {error.code}"
            ) from error
        return json.loads(body) if body else {}

    def exact(self, resource: str, field: str, value: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode({"q": value, "v": "full", "limit": 100})
        payload = self.request("GET", f"{resource}?{query}")
        match = next(
            (item for item in payload.get("results", []) if item.get(field) == value),
            None,
        )
        if match is not None:
            return match
        # Some REST resources ignore q. Page their collection, never fall back to SQL.
        start = 0
        while True:
            query = urllib.parse.urlencode(
                {"v": "full", "limit": 100, "startIndex": start}
            )
            page = self.request("GET", f"{resource}?{query}")
            rows = page.get("results", [])
            match = next((item for item in rows if item.get(field) == value), None)
            if match is not None:
                return match
            if len(rows) < 100:
                return None
            start += len(rows)


def effective_privileges(
    client: OpenMrsClient, role: dict[str, Any], *, seen=None
) -> set[str]:
    visited = seen if seen is not None else set()
    uuid = str(role.get("uuid") or "")
    if uuid in visited:
        return set()
    visited.add(uuid)
    privileges = {
        str(item["name"]) for item in role.get("privileges", []) if item.get("name")
    }
    if role.get("name") == "System Developer":
        privileges.add("*ALL*")
    for parent in role.get("inheritedRoles", []):
        parent_uuid = parent.get("uuid")
        if parent_uuid and parent_uuid not in visited:
            privileges.update(
                effective_privileges(
                    client,
                    client.request("GET", f"role/{parent_uuid}?v=full"),
                    seen=visited,
                )
            )
    return privileges
