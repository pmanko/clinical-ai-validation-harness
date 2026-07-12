"""One readiness policy for Querystore drift in maintenance and run preflight."""

from __future__ import annotations

from typing import Any


def evaluate_drift(
    payload: dict[str, Any], *, percent_threshold: float, absolute_threshold: int
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    for item in payload.get("types") or []:
        resource_type = str(item.get("resourceType") or "?")
        core = int(item.get("coreCount") or 0)
        indexed = int(item.get("indexedCount") or 0)
        drift = int(item.get("drift", core - indexed))
        if drift < 0:
            status = f"FAIL: {-drift} stale extra"
            issues.append(f"{resource_type}: {-drift} stale extra document(s)")
        elif core > 0 and indexed == 0:
            status = "FAIL: indexed=0"
            issues.append(f"{resource_type}: expected {core} document(s), indexed 0")
        elif drift > absolute_threshold and drift > core * percent_threshold / 100.0:
            status = f"FAIL: drift {drift}"
            issues.append(
                f"{resource_type}: under-indexed by {drift} "
                f"(>{percent_threshold:g}% and >{absolute_threshold})"
            )
        else:
            status = "ok (empty)" if core == 0 and indexed == 0 else "ok"
        rows.append(
            {
                "resource_type": resource_type,
                "core": core,
                "indexed": indexed,
                "drift": drift,
                "status": status,
            }
        )
    if not rows:
        issues.append("Querystore drift response contains no resource types")
    return rows, issues


def render_drift(rows: list[dict[str, Any]]) -> str:
    lines = [
        f"    {'resourceType':<20} {'core':>10} {'indexed':>10} {'drift':>9}   status",
        f"    {'-'*20} {'-'*10} {'-'*10} {'-'*9}   ------",
    ]
    lines.extend(
        f"    {row['resource_type']:<20} {row['core']:>10} {row['indexed']:>10} "
        f"{row['drift']:>9}   {row['status']}"
        for row in rows
    )
    return "\n".join(lines)
