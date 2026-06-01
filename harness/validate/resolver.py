"""Resolve a comparison set's abstract backend_ids to concrete Backend configs
({endpointUrl, modelName}) via the checked-in backend registry."""

from __future__ import annotations

from pathlib import Path

from .models import Backend, load_backends


def resolve_backends(backend_ids: list[str], registry_path: Path | str) -> list[Backend]:
    registry = load_backends(registry_path)
    missing = [b for b in backend_ids if b not in registry]
    if missing:
        known = ", ".join(sorted(registry)) or "(empty)"
        raise ValueError(
            f"backend id(s) not in registry {registry_path}: {', '.join(missing)}. Known: {known}"
        )
    return [registry[b] for b in backend_ids]
