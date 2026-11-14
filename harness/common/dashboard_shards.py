"""Shared per-arm sharding writer for `openclinai.dashboard.v2` packets."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


def shard_rel_path(idx: int, backend_id: str) -> str:
    """Return the deterministic relative path for an arm detail shard."""
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(backend_id or "arm")).strip("-")[:48] or "arm"
    digest = hashlib.sha1(str(backend_id).encode("utf-8")).hexdigest()[:8]
    return f"dashboard-details/{idx:02d}-{safe}-{digest}.json"


def write_sharded_dashboard_packet(run_dir: Path | str, data: dict[str, Any]) -> Path:
    """Write `dashboard-data.json` and per-arm `dashboard-details/` shards into `run_dir`."""
    run_path = Path(run_dir)
    details = data.get("details") or {}
    shards_dir = run_path / "dashboard-details"

    by_backend: dict[str, dict[str, Any]] = {}
    for cell_key, cell_obj in details.items():
        _, _, backend_id = cell_key.partition("|")
        by_backend.setdefault(backend_id, {})[cell_key] = cell_obj

    ordered_backends = list((data.get("status") or {}).get("backends") or [])
    for b in sorted(by_backend):
        if b not in ordered_backends:
            ordered_backends.append(b)

    if shards_dir.exists():
        shutil.rmtree(shards_dir)

    detail_shards: dict[str, str] = {}
    if by_backend:
        shards_dir.mkdir(parents=True, exist_ok=True)
        for idx, backend_id in enumerate(ordered_backends):
            shard_cells = by_backend.get(backend_id)
            if not shard_cells:
                continue
            rel_path = shard_rel_path(idx, backend_id)
            (run_path / rel_path).write_text(
                json.dumps(shard_cells, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            detail_shards[backend_id] = rel_path

    out_data = {
        **data,
        "details": {},
        "detail_shards": detail_shards,
    }
    out = run_path / "dashboard-data.json"
    out.write_text(json.dumps(out_data, ensure_ascii=False), encoding="utf-8")
    return out
