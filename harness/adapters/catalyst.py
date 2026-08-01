from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalystAdapter:
    """Project-identity record for the Catalyst target (feature 011).

    Not on the critical path for driving a validate run — that's
    harness/validate/catalyst_client.py's CatalystClient, which implements
    the actual pluggable `_Client` Protocol the runner uses (see
    specs/011-catalyst-fhir-sidecar-poc/research.md item 1 for why). This
    mirrors chartsearchai.py/querystore.py for registry/CI consistency.
    """

    repo_path: Path

    def command_plan(self) -> list[str]:
        return [
            "cd catalyst-mcp && uv run pytest tests/test_fhir_tools.py",
            "cd catalyst-agents && uv run pytest tests/test_fhir_grounding.py",
            "cd catalyst-gateway && uv run pytest tests/test_sidecar_response_contract.py tests/test_sidecar_ui.py",
        ]
