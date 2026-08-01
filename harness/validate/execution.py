"""Validate which service owns a comparison run before creating artifacts."""

from __future__ import annotations

from .models import Backend, ComparisonSet


def validate_execution_contract(
    comparison: ComparisonSet, backends: list[Backend]
) -> None:
    if comparison.transport == "med-agent-hub":
        # MedAgentHubClient.chat() has no `provider` kwarg — a provider-pinned backend
        # here would only fail later, inside run_comparison, once the runner's own
        # client-capability check trips. Catch it here so `validate check` (the
        # upfront gate) never reports a misconfigured comparison set as compatible.
        pinned = [backend.id for backend in backends if backend.provider]
        if pinned:
            names = ", ".join(pinned)
            raise ValueError(
                "med-agent-hub transport cannot route a pinned provider (no provider "
                f"kwarg on MedAgentHubClient.chat); use transport=chartsearchai for "
                f"provider_arm backends: {names}"
            )
        return

    if comparison.transport == "catalyst":
        # CatalystClient (feature 011) has no product-profile/provider-arm
        # concept — those are chartsearchai-only (see Backend.kind/provider).
        # A catalyst backend entry only needs endpointUrl/modelName.
        pinned = [backend.id for backend in backends if backend.provider]
        if pinned:
            names = ", ".join(pinned)
            raise ValueError(
                "catalyst transport does not support a pinned provider (a "
                f"chartsearchai-only concept); remove provider from: {names}"
            )
        return

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
