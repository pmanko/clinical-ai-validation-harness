"""Validate which service owns a comparison run before creating artifacts."""

from __future__ import annotations

from .models import Backend, ComparisonSet


def validate_execution_contract(
    comparison: ComparisonSet, backends: list[Backend]
) -> None:
    if comparison.transport in {"med-agent-hub", "openai-compatible"}:
        # MedAgentHubClient.chat() and OpenAICompatibleClient.chat() have no `provider`
        # kwarg — a provider-pinned backend here would only fail later, inside
        # run_comparison, once the runner's own client-capability check trips. Catch it
        # here so `validate check` (the upfront gate) never reports a misconfigured
        # comparison set as compatible.
        pinned = [backend.id for backend in backends if backend.provider]
        if pinned:
            names = ", ".join(pinned)
            raise ValueError(
                f"{comparison.transport} transport cannot route a pinned provider (no provider "
                f"kwarg on client.chat); use transport=chartsearchai for "
                f"provider_arm backends: {names}"
            )
        if comparison.transport == "openai-compatible":
            with_exec = [backend.id for backend in backends if backend.execution is not None]
            if with_exec:
                names = ", ".join(with_exec)
                raise ValueError(
                    "openai-compatible transport does not accept hub execution specs; "
                    f"use transport=med-agent-hub: {names}"
                )
        return

    with_exec = [backend.id for backend in backends if backend.execution is not None]
    if with_exec:
        names = ", ".join(with_exec)
        raise ValueError(
            "ChartSearchAI comparisons send OpenMRS preset ids and do not accept raw hub "
            f"execution specs; use transport=med-agent-hub for low-level experiments: {names}"
        )

    invalid = [
        backend.id
        for backend in backends
        if backend.kind not in ("product_profile", "provider_arm")
    ]
    if invalid:
        names = ", ".join(invalid)
        raise ValueError(
            "ChartSearchAI comparisons accept kind=product_profile or kind=provider_arm "
            f"arms only; use transport=med-agent-hub for low-level experiments: {names}"
        )
    unrouted = [
        backend.id
        for backend in backends
        if backend.kind == "provider_arm" and not backend.provider
    ]
    if unrouted:
        names = ", ".join(unrouted)
        raise ValueError(
            f"provider_arm backends must pin a provider (bundled|hub): {names}"
        )
