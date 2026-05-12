from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImportSmokeResult:
    startup_ok: bool
    api_read_ok: bool
    table_checks: dict[str, bool]

    def to_event(self) -> dict[str, Any]:
        return {
            "event_type": "evaluation",
            "check": "import_smoke",
            "startup_ok": self.startup_ok,
            "api_read_ok": self.api_read_ok,
            "table_checks": self.table_checks,
            "pass": self.startup_ok and self.api_read_ok and all(self.table_checks.values()),
        }


def run_import_smoke_stub() -> ImportSmokeResult:
    """Placeholder for real OpenMRS startup/API/table smoke checks."""
    checks = {
        "patient": True,
        "person": True,
        "encounter": True,
        "obs": True,
        "concept": True,
    }
    return ImportSmokeResult(startup_ok=True, api_read_ok=True, table_checks=checks)
