#!/usr/bin/env python3
"""Stage one report family and its evidence under a publish directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _recorded_suite_source_sha256(run_dir: Path) -> str | None:
    index_path = run_dir / "evidence-index.json"
    if not index_path.is_file():
        return None
    entries = _load_json(index_path).get("entries", [])
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path") == "suite.json":
            source = (entry.get("metadata") or {}).get("sourceSha256")
            return str(source) if source else None
    return None


def _catalyst_suite_identity(run_dir: Path) -> tuple[str, str]:
    manifest = _load_json(run_dir / "run_manifest.json")
    suite_path = run_dir / "suite.json"
    suite = _load_json(suite_path)

    declared_id = manifest.get("suite_id")
    if declared_id is not None and str(declared_id) != str(suite.get("id") or ""):
        raise ValueError(
            f"Catalyst run_manifest.json suite_id {str(declared_id)!r} does not "
            f"match suite.json {str(suite.get('id') or '')!r}"
        )
    suite_id = declared_id or suite.get("id")
    if not suite_id:
        raise ValueError("Catalyst run is missing suite_id")

    # run_manifest.suite_sha256 digests the *source* suite definition, while
    # suite.json in the run directory is a re-serialized copy, so the two are
    # never byte-equal. evidence-index.json records the source digest
    # separately; that is the only value the manifest can be checked against.
    recorded_source = _recorded_suite_source_sha256(run_dir)
    declared_sha = manifest.get("suite_sha256")
    if (
        declared_sha is not None
        and recorded_source is not None
        and str(declared_sha) != recorded_source
    ):
        raise ValueError(
            "Catalyst run_manifest.json suite_sha256 does not match the "
            "sourceSha256 recorded for suite.json in evidence-index.json"
        )
    suite_sha256 = (
        declared_sha
        or recorded_source
        or hashlib.sha256(suite_path.read_bytes()).hexdigest()
    )
    if not re.fullmatch(r"[a-f0-9]{64}", str(suite_sha256)):
        raise ValueError("Catalyst suite_sha256 must be a lowercase SHA-256 digest")
    return str(suite_id), str(suite_sha256)


def _assert_no_symlinks(run_dir: Path) -> None:
    """Reject symlinked run content before it is copied into a published report.

    copytree would otherwise dereference links and publish file contents from
    outside the run directory.
    """
    for parent, dir_names, file_names in os.walk(run_dir, followlinks=False):
        for name in sorted(dir_names) + sorted(file_names):
            candidate = Path(parent) / name
            if candidate.is_symlink():
                raise ValueError(
                    "run directory must not contain symlinks: "
                    f"{candidate.relative_to(run_dir)}"
                )


def _upsert_manifest(
    path: Path,
    *,
    slug: str,
    title: str,
    summary: str,
    takeaway: str,
    family: str,
) -> None:
    payload = _load_json(path)
    runs = payload.setdefault("runs", [])
    existing = next((item for item in runs if item.get("slug") == slug), None)
    if existing is None:
        runs.insert(
            0,
            {
                "slug": slug,
                "title": title or f"{slug} (auto-added — edit title)",
                "summary": summary,
                "takeaway": takeaway,
                # The landing page labels and groups runs by family without
                # re-deriving it from the staged files.
                "family": family,
            },
        )
    else:
        if title:
            existing["title"] = title
        existing["summary"] = summary
        existing["takeaway"] = takeaway
        existing["family"] = family
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
    _assert_no_symlinks(run_dir)
    reports_root.mkdir(parents=True, exist_ok=True)
    destination = reports_root / slug
    temporary = reports_root / f".{slug}.staging"
    if temporary.exists():
        shutil.rmtree(temporary)

    # Render from a staged copy so dry-run publishing mutates nothing outside
    # REPORTS_ROOT and every report-relative evidence link remains resolvable.
    # Build a clean replacement so files from an older report using the same
    # slug cannot survive into the new publication.
    shutil.copytree(run_dir, temporary, symlinks=True)
    if family == "chartsearchai":
        comparison_set = _comparison_set(run_dir)
        family_meta = {"comparison_set": comparison_set}
        report_args = ["validate", "report", "--run-dir", str(temporary)]
    else:
        suite_id, suite_sha256 = _catalyst_suite_identity(run_dir)
        family_meta = {"suite_id": suite_id, "suite_sha256": suite_sha256}
        report_args = ["catalyst", "report", str(temporary)]

    from harness.cli import main as harness_main

    if harness_main(report_args, project_root=root) != 0:
        raise RuntimeError(f"{family} report renderer failed")
    rendered = temporary / "report.html"
    index_path = temporary / "index.html"
    rendered.replace(index_path)
    meta = {
        "slug": slug,
        "report_family": family,
        "run_path": run_path,
        **family_meta,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (temporary / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    if destination.exists():
        shutil.rmtree(destination)
    temporary.replace(destination)
    _upsert_manifest(
        manifest_path,
        slug=slug,
        title=title,
        summary=summary,
        takeaway=takeaway,
        family=family,
    )
    return destination / "index.html"


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
