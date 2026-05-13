from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import yaml


def _parse_ports(ports_raw: Any) -> tuple[str, ...]:
    if ports_raw is None:
        return ()
    if not isinstance(ports_raw, list):
        return (str(ports_raw),)
    out: list[str] = []
    for p in ports_raw:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            out.append(str(p))
        else:
            out.append(str(p))
    return tuple(out)


def parse_compose_services(compose_path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, spec in services.items():
        if not isinstance(spec, dict):
            continue
        out[str(name)] = {
            "image": str(spec.get("image", "")),
            "ports": _parse_ports(spec.get("ports")),
            "source": str(compose_path),
        }
    return out


def detect_compose_conflicts(
    harness_compose_files: Sequence[Path],
    target_compose_files: Sequence[tuple[str, Path]],
) -> list[str]:
    harness_svc: dict[str, list[dict[str, Any]]] = {}
    for path in harness_compose_files:
        if not path.is_file():
            continue
        for svc, meta in parse_compose_services(path).items():
            harness_svc.setdefault(svc, []).append(meta)

    target_svc: dict[str, list[dict[str, Any]]] = {}
    for target_id, path in target_compose_files:
        if not path.is_file():
            continue
        for svc, meta in parse_compose_services(path).items():
            meta = dict(meta)
            meta["target_id"] = target_id
            target_svc.setdefault(svc, []).append(meta)

    messages: list[str] = []
    for name in set(harness_svc) & set(target_svc):
        for hm in harness_svc[name]:
            for tm in target_svc[name]:
                hi, ti = hm.get("image", ""), tm.get("image", "")
                if hi and ti and hi != ti:
                    messages.append(
                        f"service {name!r}: harness image {hi!r} vs "
                        f"target {tm['target_id']} image {ti!r}"
                    )
                hp, tp = hm.get("ports") or (), tm.get("ports") or ()
                if hp and tp and hp != tp:
                    messages.append(
                        f"service {name!r}: harness ports {hp!r} vs "
                        f"target {tm['target_id']} ports {tp!r}"
                    )
    return messages
