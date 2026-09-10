"""The file that seeds a run, and travels with its evidence.

Nothing about a comparison should live in a shell variable that happened to
be set that afternoon: the suite, rubric, gateway, database identity, and
publication identity are all read from one checked-in config file. `run`
freezes the resolved copy into the run directory, so the published evidence
states exactly what was used.

Secrets are referenced by environment-variable name, never written. The
frozen copy is published, so it must be safe to publish.
"""

from __future__ import annotations

import json
import os
import re
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FROZEN_NAME = "run-config.json"
_SECURITY_RULE = re.compile(r"\bsgr-[0-9a-f]+\b", re.IGNORECASE)
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def resolve(path: str | Path, *, require_secrets: bool = True) -> dict[str, Any]:
    """Read a config file and normalize it.

    The runner reaches its data only through Catalyst, so a run config carries
    no database credential to resolve. ``require_secrets`` is retained as an
    accepted no-op so existing callers and templates keep working.
    """
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"cannot read run config {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"run config {source} is not valid JSON: {error}") from error

    invocation = raw.get("invocation", {})
    if invocation is None:
        invocation = {}
    if not isinstance(invocation, dict):
        raise SystemExit(f"run config {source} invocation must be an object")
    scenarios = invocation.get("scenarios") or []
    if not isinstance(scenarios, list) or any(
        not isinstance(item, str) or not item for item in scenarios
    ):
        raise SystemExit(
            f"run config {source} invocation.scenarios must be a list of IDs"
        )
    repetitions = invocation.get("repetitions")
    if repetitions is not None and (
        not isinstance(repetitions, int)
        or isinstance(repetitions, bool)
        or repetitions < 1
    ):
        raise SystemExit(
            f"run config {source} invocation.repetitions must be a positive integer"
        )
    timeout_seconds = invocation.get("timeoutSeconds", 900)
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds < 1
    ):
        raise SystemExit(
            f"run config {source} invocation.timeoutSeconds must be a positive integer"
        )
    for field in ("includeManual",):
        if field in invocation and not isinstance(invocation[field], bool):
            raise SystemExit(
                f"run config {source} invocation.{field} must be boolean"
            )
    resolved = {
        "suite": str(raw.get("suite") or ""),
        "readerRubric": str(raw.get("readerRubric") or ""),
        "readerRubricSha256": str(raw.get("readerRubricSha256") or ""),
        "gatewayUrl": str(raw.get("gatewayUrl") or ""),
        "outputDir": str(raw.get("outputDir") or ""),
        "warmupQuestion": str(raw.get("warmupQuestion") or ""),
        "invocation": {
            "scenarios": list(dict.fromkeys(scenarios)),
            "repetitions": repetitions,
            "includeManual": invocation.get("includeManual", False),
            "timeoutSeconds": timeout_seconds,
        },
        "publish": dict(raw.get("publish") or {}),
        "source": str(source),
    }
    # Older frozen runs may still be reproduced with their historical report.
    # The active reader-led comparison does not declare or consume gates.
    if "gates" in raw:
        gates = dict(raw.get("gates") or {})
        resolved["gates"] = {
            "overall": gates.get("overall"),
            "per_scenario": gates.get("perScenario", gates.get("per_scenario")),
        }
    return resolved


def _unsafe_public_value(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered == "password" or lowered.endswith("dsn"):
                return f"{path}.{key} contains a secret-bearing field"
            problem = _unsafe_public_value(child, f"{path}.{key}")
            if problem:
                return problem
        return None
    if isinstance(value, list):
        for index, child in enumerate(value):
            problem = _unsafe_public_value(child, f"{path}[{index}]")
            if problem:
                return problem
        return None
    if not isinstance(value, str):
        return None
    if _SECURITY_RULE.search(value):
        return f"{path} contains a security-group rule identifier"
    if value.startswith("/") or value.startswith("~/"):
        return f"{path} contains an absolute workstation path"
    parsed = urlparse(value) if "://" in value else None
    if parsed is not None and parsed.password is not None:
        return f"{path} contains a password-bearing URL"
    candidates = _IPV4.findall(value)
    if parsed is not None and parsed.hostname:
        candidates.append(parsed.hostname)
    for candidate in set(candidates or [value]):
        try:
            address = ip_address(candidate)
        except ValueError:
            continue
        # Loopback identifies the isolated stack without publishing a
        # workstation or deployment address. Other non-public addresses do
        # not belong in a report artifact.
        if not address.is_global and not address.is_loopback:
            return f"{path} contains a non-public network address"
    return None


def publishable(config: dict[str, Any]) -> dict[str, Any]:
    """Return and validate the exact public seed used for a run.

    Runtime-only keys begin with ``_``. ``source`` is also runtime-only: it is
    the absolute path from which the seed was read and would disclose a local
    workstation path without adding reproducibility.
    """
    public = {
        key: value
        for key, value in config.items()
        if not key.startswith("_") and key != "source"
    }
    problem = _unsafe_public_value(public)
    if problem:
        raise ValueError(f"run config is not safe to publish: {problem}")
    return public


def freeze(config: dict[str, Any], run_dir: str | Path) -> Path:
    """Write the publishable copy of the seed beside the run's evidence."""
    public = publishable(config)
    out = Path(run_dir) / FROZEN_NAME
    out.write_text(
        json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


def load_frozen(run_dir: str | Path) -> dict[str, Any]:
    """The seed a finished run was started with, or {} for older runs."""
    path = Path(run_dir) / FROZEN_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
