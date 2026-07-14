"""Validate which service owns a comparison run before creating artifacts."""

from __future__ import annotations

from .models import Backend, ComparisonSet


def validate_execution_contract(
    comparison: ComparisonSet, backends: list[Backend]
) -> None:
    if comparison.transport == "med-agent-hub":
        return

    invalid = [backend.id for backend in backends if backend.kind != "product_profile"]
    if invalid:
        names = ", ".join(invalid)
        raise ValueError(
            "ChartSearchAI comparisons accept kind=product_profile arms only; "
            f"use transport=med-agent-hub for low-level experiments: {names}"
        )
