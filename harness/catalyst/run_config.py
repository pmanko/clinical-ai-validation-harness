"""The file that seeds a run, and travels with its evidence.

Nothing about a comparison should live in a shell variable that happened to
be set that afternoon: the suite, the gateway, the acceptance gates and the
publication identity are all read from one config file built off a checked-in
template. `run` freezes the resolved copy into the run directory, so a
`finish` months later applies the thresholds the run was seeded with rather
than today's, and a published package carries its own seed.

Secrets are referenced by environment-variable name, never written. The
frozen copy is published, so it must be safe to publish.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

FROZEN_NAME = "run-config.json"


def resolve(path: str | Path, *, require_secrets: bool = True) -> dict[str, Any]:
    """Read a config file and normalize it, resolving secret references.

    `require_secrets=False` is for reading a template without the runtime
    environment (tests, and anything that only wants the gates).
    """
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"cannot read run config {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"run config {source} is not valid JSON: {error}") from error

    postgres = dict(raw.get("postgres") or {})
    password_env = postgres.get("passwordEnv")
    password = os.environ.get(password_env) if password_env else None
    if require_secrets and password_env and not password:
        raise SystemExit(
            f"run config {source} needs the database password in "
            f"${password_env}, which is not set"
        )

    gates = dict(raw.get("gates") or {})
    return {
        "suite": str(raw.get("suite") or ""),
        "gatewayUrl": str(raw.get("gatewayUrl") or ""),
        "outputDir": str(raw.get("outputDir") or ""),
        "postgres": postgres,
        "_password": password,
        # Normalized to the snake_case the report and triage speak.
        "gates": {
            "overall": gates.get("overall"),
            "per_scenario": gates.get("perScenario", gates.get("per_scenario")),
        },
        "publish": dict(raw.get("publish") or {}),
        "source": str(source),
    }


def postgres_dsn(config: dict[str, Any]) -> str:
    """The DSN the runner connects with. Never written to disk."""
    postgres = config.get("postgres") or {}
    password = config.get("_password") or ""
    user = postgres.get("user", "")
    credentials = f"{user}:{password}@" if user else ""
    return (
        f"postgresql://{credentials}{postgres.get('host', '')}:"
        f"{postgres.get('port', '')}/{postgres.get('database', '')}"
    )


def freeze(config: dict[str, Any], run_dir: str | Path) -> Path:
    """Write the publishable copy of the seed beside the run's evidence."""
    publishable = {
        key: value for key, value in config.items() if not key.startswith("_")
    }
    out = Path(run_dir) / FROZEN_NAME
    out.write_text(
        json.dumps(publishable, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
