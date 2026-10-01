"""Arm presentation from supplied experiment metadata, never product source files.

An experiment's optional ``arms`` map contains cards keyed by backend id. Cards
may describe models, roles, stages, sampler settings, prompt text and retrieval
settings. Missing facts remain unknown; model/profile names are not topology.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def arm_card(
    backend_id: str,
    *,
    backend: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a card using only supplied metadata and the selected connection.

    ``metadata`` is this arm's card, not a registry path. Explicit titles are
    preserved. No endpoint, profile-name or model-name heuristics infer roles,
    prompts, safety stages or provider identity.
    """
    supplied = deepcopy(metadata or {})
    label = supplied.get("label") or getattr(backend, "label", None) or backend_id
    model_name = getattr(backend, "model_name", None)
    models = supplied.get("models") or ([{"id": model_name}] if model_name else [])
    roles = supplied.get("roles") or {}
    kind = supplied.get("kind") or getattr(backend, "kind", None) or "unknown"
    title = supplied.get("title") or label
    card = {
        "backend_id": backend_id,
        "label": label,
        "title": title,
        "short_title": supplied.get("short_title") or title,
        "kind": kind,
        "path": supplied.get("path"),
        "models": models,
        "roles": roles,
        "config": supplied.get("config") or {},
        **supplied,
    }
    card["backend_id"] = backend_id
    return card
