#!/usr/bin/env python3
"""Stage one report family and its evidence under a publish directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAMILIES = {"chartsearchai", "catalyst"}
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_relative(root: Path, path: Path) -> str:
    root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"run directory must be inside repository root: {resolved}")
    return resolved.relative_to(root).as_posix()


def _comparison_set(run_dir: Path) -> str:
    events = run_dir / "events.jsonl"
    if events.is_file():
        for line in events.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_type") == "run" and event.get("comparison_set"):
                return str(event["comparison_set"])
    raise ValueError("ChartSearchAI run event is missing comparison_set")


def _catalyst_suite_identity(run_dir: Path) -> tuple[str, str]:
    manifest = _load_json(run_dir / "run_manifest.json")
    suite_path = run_dir / "suite.json"
    suite = _load_json(suite_path)
    suite_id = manifest.get("suite_id") or suite.get("id")
    suite_sha256 = manifest.get("suite_sha256") or hashlib.sha256(
        suite_path.read_bytes()
    ).hexdigest()
    if not suite_id:
        raise ValueError("Catalyst run is missing suite_id")
    if not re.fullmatch(r"[a-f0-9]{64}", str(suite_sha256)):
        raise ValueError("Catalyst suite_sha256 must be a lowercase SHA-256 digest")
    return str(suite_id), str(suite_sha256)


def _upsert_manifest(
    path: Path,
    *,
    slug: str,
    title: str,
    summary: str,
    takeaway: str,
) -> None:
    payload = _load_json(path)
    runs = payload.setdefault("runs", [])
    if not any(item.get("slug") == slug for item in runs):
        runs.insert(
            0,
            {
                "slug": slug,
                "title": title or f"{slug} (auto-added — edit title)",
                "summary": summary,
                "takeaway": takeaway,
            },
        )
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def stage_report(
    *,
    family: str,
    run_dir: Path,
    slug: str,
    reports_root: Path,
    manifest_path: Path,
    root: Path = ROOT,
    title: str = "",
    summary: str = "",
    takeaway: str = "",
) -> Path:
    if family not in FAMILIES:
        raise ValueError(f"unsupported report family: {family}")
    if not SAFE_SLUG.fullmatch(slug):
        raise ValueError("slug must contain only lowercase letters, digits, '.', '_' or '-'")
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")
    run_path = _root_relative(root, run_dir)
    reports_root.mkdir(parents=True, exist_ok=True)
    destination = reports_root / slug
    destination.mkdir(parents=True, exist_ok=True)

    # Render from a staged copy so dry-run publishing mutates nothing outside
    # REPORTS_ROOT and every report-relative evidence link remains resolvable.
    shutil.copytree(run_dir, destination, dirs_exist_ok=True)
    if family == "chartsearchai":
        comparison_set = _comparison_set(run_dir)
        family_meta = {"comparison_set": comparison_set}
        report_args = ["validate", "report", "--run-dir", str(destination)]
    else:
        suite_id, suite_sha256 = _catalyst_suite_identity(run_dir)
        family_meta = {"suite_id": suite_id, "suite_sha256": suite_sha256}
        report_args = ["catalyst", "report", str(destination)]

    from harness.cli import main as harness_main

    if harness_main(report_args, project_root=root) != 0:
        raise RuntimeError(f"{family} report renderer failed")
    rendered = destination / "report.html"
    index_path = destination / "index.html"
    rendered.replace(index_path)
    meta = {
        "slug": slug,
        "report_family": family,
        "run_path": run_path,
        **family_meta,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (destination / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    _upsert_manifest(
        manifest_path,
        slug=slug,
        title=title,
        summary=summary,
        takeaway=takeaway,
    )
    return index_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("slug")
    parser.add_argument("title", nargs="?", default="")
    parser.add_argument("summary", nargs="?", default="")
    parser.add_argument("takeaway", nargs="?", default="")
    parser.add_argument("--reports-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        path = stage_report(
            family=args.family,
            run_dir=args.run_dir,
            slug=args.slug,
            reports_root=args.reports_root,
            manifest_path=args.manifest,
            root=args.root,
            title=args.title,
            summary=args.summary,
            takeaway=args.takeaway,
        )
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"staged {args.family} report -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
