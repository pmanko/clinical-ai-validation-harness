"""Content-addressed context normalization for evaluation run artifacts.

Large chart payloads (`mappings`, `condensed_text`, `valid_uuids`, `retained_uuids`,
and `x_wahs.citation_map`) are identical across arms, prompts, and seeds sharing
the same condensed patient chart. This module deduplicates those payloads into
``<run_dir>/inputs/contexts/<sha256_16>.json`` while eagerly materializing
``<run_dir>/inputs/charts/<scenario_id>.json`` so live detail views resolve `[N]`
citations immediately during execution and ``results.jsonl`` stays compact (~2-4 KB/row).

Older runs with inline payloads ("legacy fat rows") continue to work transparently
with zero migration required.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


CONTEXT_SCHEMA = "openclinai.context.v1"
_CONTEXT_REF_RE = re.compile(r"^[0-9a-f]{16}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validated_safe_id(value: str, label: str = "scenario_id") -> str:
    if value in {".", ".."} or not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def _validated_context_ref(ctx_id: Any) -> str:
    ctx_key = str(ctx_id)
    if not _CONTEXT_REF_RE.fullmatch(ctx_key):
        raise ValueError(f"invalid context_ref: {ctx_key!r}")
    return ctx_key


def _safe_child_json(base_dir: Path, stem: str, *, label: str) -> Path:
    resolved_base = base_dir.resolve()
    resolved_target = (resolved_base / f"{stem}.json").resolve()
    if not resolved_target.is_relative_to(resolved_base):
        raise ValueError(f"{label} escapes {base_dir}: {stem!r}")
    return resolved_target


def _atomic_write_json(path: Path, payload: dict[str, Any], *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"ensure_ascii": False}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    data = json.dumps(payload, **kwargs) + ("\n" if indent is not None else "")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _collect_valid_uuids(
    mappings: list[Any],
    *,
    extra_valid_uuids: list[str] | tuple[str, ...] = (),
    valid_uuids: list[Any] = (),
    retained_uuids: list[Any] = (),
) -> list[str]:
    valid_set: set[str] = set()
    for src in (extra_valid_uuids, valid_uuids, retained_uuids):
        for u in src or ():
            if u:
                valid_set.add(str(u).replace("urn:uuid:", ""))
    for m in mappings or ():
        if not isinstance(m, dict):
            continue
        ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
        if ru:
            valid_set.add(ru)
        for mu in m.get("memberUuids") or ():
            if mu:
                valid_set.add(str(mu).replace("urn:uuid:", ""))
    return sorted(valid_set)


def ensure_scenario_chart_input(
    run_dir: Path | str,
    scenario_id: str,
    *,
    patient_id: str | None = None,
    response: dict[str, Any] | None = None,
    extra_valid_uuids: list[str] | tuple[str, ...] = (),
) -> Path | None:
    """Eagerly write or enrich ``inputs/charts/<scenario_id>.json`` during execution."""
    if not scenario_id:
        return None
    safe_sid = _validated_safe_id(scenario_id, "scenario_id")
    env = response if isinstance(response, dict) else {}
    mappings = list(env.get("mappings") or [])
    condensed_text = str(env.get("condensed_text") or "").strip()
    valid_list = _collect_valid_uuids(
        mappings,
        extra_valid_uuids=extra_valid_uuids,
        valid_uuids=env.get("valid_uuids") or (),
        retained_uuids=env.get("retained_uuids") or (),
    )
    if not mappings and not condensed_text and not valid_list:
        return None

    charts_dir = Path(run_dir) / "inputs" / "charts"
    chart_path = _safe_child_json(charts_dir, safe_sid, label="scenario_id")

    existing: dict[str, Any] = {}
    if chart_path.is_file():
        try:
            loaded = json.loads(chart_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}

    if existing:
        old_maps = existing.get("mappings") or []
        old_snap = str(existing.get("chart_snapshot") or "").strip()
        old_valid = set(existing.get("valid_uuids") or [])
        new_valid = old_valid | set(valid_list)
        # Keep the richer chart representation across arms; avoid pointless rewrites when unchanged.
        keep_old = len(old_snap) >= len(condensed_text) and len(old_maps) >= len(mappings)
        merged_maps = old_maps if keep_old else mappings
        merged_snap = old_snap if keep_old else condensed_text
        if keep_old and new_valid == old_valid:
            return chart_path
        valid_list = sorted(new_valid)
        mappings = list(merged_maps)
        condensed_text = merged_snap

    chart_obj = {
        "patient": {
            "uuid": scenario_id,
            "name": str(patient_id or scenario_id),
            "gender": "unknown",
            "birthdate": "",
            "slug": scenario_id,
        },
        "valid_uuids": valid_list,
        "mappings": mappings,
        "chart_snapshot": condensed_text,
    }
    _atomic_write_json(chart_path, chart_obj, indent=2)
    return chart_path


def slim_response_envelope(
    run_dir: Path | str,
    scenario_id: str | None,
    patient_id: str | None,
    response: dict[str, Any] | None,
    *,
    extra_valid_uuids: list[str] | tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Normalize heavy chart context into ``inputs/contexts/<sha256_16>.json``.

    Also eagerly populates ``inputs/charts/<scenario_id>.json`` so live `/api/detail`
    requests resolve `[N]` source cards cleanly mid-run.
    """
    if not isinstance(response, dict):
        return response
    if scenario_id:
        _validated_safe_id(scenario_id, "scenario_id")
    existing_ref = response.get("context_ref")
    if existing_ref is not None and existing_ref != "":
        _validated_context_ref(existing_ref)

    x_wahs = response.get("x_wahs")
    has_x_cit = isinstance(x_wahs, dict) and "citation_map" in x_wahs
    heavy_keys = ("mappings", "condensed_text", "valid_uuids", "retained_uuids")
    has_heavy = any(k in response and response.get(k) not in (None, "", []) for k in heavy_keys)

    if existing_ref and not has_heavy and not has_x_cit:
        return dict(response)
    if not has_heavy and not has_x_cit:
        if scenario_id and extra_valid_uuids:
            ensure_scenario_chart_input(
                run_dir,
                scenario_id,
                patient_id=patient_id,
                response=response,
                extra_valid_uuids=extra_valid_uuids,
            )
        return dict(response)

    ctx_payload: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "condensed_text": str(response.get("condensed_text") or ""),
        "mappings": list(response.get("mappings") or []),
        "valid_uuids": list(response.get("valid_uuids") or []),
        "retained_uuids": list(response.get("retained_uuids") or []),
    }
    if has_x_cit:
        ctx_payload["x_wahs_citation_map"] = x_wahs.get("citation_map")

    digest_bytes = json.dumps(
        ctx_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    ctx_id = _validated_context_ref(hashlib.sha256(digest_bytes).hexdigest()[:16])

    ctx_path = _safe_child_json(Path(run_dir) / "inputs" / "contexts", ctx_id, label="context_ref")
    if not ctx_path.is_file():
        _atomic_write_json(ctx_path, ctx_payload)

    if scenario_id:
        ensure_scenario_chart_input(
            run_dir,
            scenario_id,
            patient_id=patient_id,
            response=response,
            extra_valid_uuids=extra_valid_uuids,
        )

    slim = dict(response)
    slim["context_ref"] = ctx_id
    for k in heavy_keys:
        slim.pop(k, None)
    if has_x_cit:
        xw_copy = dict(x_wahs)
        xw_copy.pop("citation_map", None)
        slim["x_wahs"] = xw_copy
    return slim


def rehydrate_response_envelope(
    run_dir: Path | str,
    response: dict[str, Any] | None,
    *,
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Restore context fields from ``inputs/contexts/<context_ref>.json`` if needed."""
    if not isinstance(response, dict):
        return response
    ctx_id = response.get("context_ref")
    if not ctx_id:
        return response
    ctx_key = _validated_context_ref(ctx_id)
    ctx_data = cache.get(ctx_key) if cache is not None else None
    if ctx_data is None:
        ctx_path = _safe_child_json(Path(run_dir) / "inputs" / "contexts", ctx_key, label="context_ref")
        if not ctx_path.is_file():
            return response
        try:
            loaded = json.loads(ctx_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return response
        if not isinstance(loaded, dict):
            return response
        ctx_data = loaded
        if cache is not None:
            cache[ctx_key] = ctx_data

    out = dict(response)
    if "mappings" not in out and ctx_data.get("mappings") is not None:
        out["mappings"] = ctx_data["mappings"]
    if "condensed_text" not in out and ctx_data.get("condensed_text") is not None:
        out["condensed_text"] = ctx_data["condensed_text"]
    if "valid_uuids" not in out and ctx_data.get("valid_uuids"):
        out["valid_uuids"] = ctx_data["valid_uuids"]
    if "retained_uuids" not in out and ctx_data.get("retained_uuids"):
        out["retained_uuids"] = ctx_data["retained_uuids"]
    if "x_wahs_citation_map" in ctx_data and isinstance(out.get("x_wahs"), dict):
        xw = dict(out["x_wahs"])
        xw.setdefault("citation_map", ctx_data["x_wahs_citation_map"])
        out["x_wahs"] = xw
    return out
