#!/usr/bin/env python3
"""Build machine-relative local performance evidence from med-agent-hub traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_provenance(repo: Path) -> dict[str, Any]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repo,
            text=True,
        ).strip()
    )
    return {"commit": commit, "tree_clean": not dirty}


def _router_version() -> str:
    try:
        output = subprocess.check_output(
            ["llama-server", "--version"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return output.splitlines()[0].strip() if output.splitlines() else "unavailable"


def _memory_bytes() -> int | None:
    if platform.system() == "Darwin":
        try:
            return int(
                subprocess.check_output(
                    ["sysctl", "-n", "hw.memsize"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def _series_summary(values: list[float | int]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
    }


def _timing_rows(
    trace_path: Path,
    profile: str,
    limit: int,
    source: str | None,
    question: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("level_id") != profile:
            continue
        if question is not None and entry.get("question") != question:
            continue
        sources = (entry.get("context") or {}).get("sources") or []
        if source and source not in sources:
            continue
        timing = next(
            (step for step in entry.get("steps", []) if step.get("role") == "answer_timing"),
            None,
        )
        if timing is None:
            continue
        rows.append(
            {
                "timestamp": entry.get("ts"),
                "question": entry.get("question"),
                "context_sources": sources,
                "answer_to_done_ms": timing["answer_to_done_ms"],
                "answer_stage_ms": timing["answer_stage_ms"],
                "pipeline_overhead_ms": timing["pipeline_overhead_ms"],
                "pipeline_overhead_ratio": timing["pipeline_overhead_ratio"],
            }
        )
    return rows[-limit:]


def build_proof(
    trace_path: Path,
    profile: str,
    limit: int,
    source: str | None = None,
    *,
    repo_root: Path | None = None,
    model_path: Path | None = None,
    router_version: str | None = None,
    question: str | None = None,
    collection_manifest: Path | None = None,
) -> dict[str, Any]:
    runs = _timing_rows(trace_path, profile, limit, source, question)
    if len(runs) < 2:
        raise ValueError(f"need at least two traced warm runs for {profile!r}; found {len(runs)}")
    fields = (
        "answer_to_done_ms",
        "answer_stage_ms",
        "pipeline_overhead_ms",
        "pipeline_overhead_ratio",
    )
    provenance: dict[str, Any] = {
        "trace_snapshot_sha256": _sha256(trace_path),
        "selected_runs_sha256": _json_sha256(runs),
    }
    if collection_manifest is not None:
        manifest = json.loads(collection_manifest.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != "local_performance_collection.v1":
            raise ValueError("Unsupported performance collection manifest.")
        if manifest.get("selected_trace_sha256") != _sha256(trace_path):
            raise ValueError("Collection manifest does not match the selected trace.")
        if manifest.get("runs") != len(runs):
            raise ValueError("Collection manifest run count does not match selected rows.")
        provenance.update(manifest["runtime_identity"])
        provenance["collection_manifest_sha256"] = _sha256(collection_manifest)
        provenance["warmup"] = manifest["warmup"]
    elif repo_root is not None:
        root = repo_root.resolve()
        hub = root / "targets" / "med-agent-hub"
        levels = hub / "server" / "levels.yaml"
        router = root / "scripts" / "llama-router.ini"
        provenance.update(
            {
                "harness": _git_provenance(root),
                "med_agent_hub": _git_provenance(hub),
                "profile_config_sha256": _sha256(levels),
                "router_config_sha256": _sha256(router),
            }
        )
    if model_path is not None:
        resolved_model = model_path.expanduser().resolve(strict=True)
        provenance["model_artifact"] = {
            "path": str(resolved_model),
            "size_bytes": resolved_model.stat().st_size,
            "sha256": _sha256(resolved_model),
        }
    provenance["router_version"] = router_version or _router_version()

    return {
        "schema_version": "local_performance.v1",
        "status": "observed",
        "acceptance_model": "relative_observation",
        "fixed_latency_threshold": None,
        "measurement_scope": "warm_answer_done",
        "cold_start_measured": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "memory_bytes": _memory_bytes(),
        },
        "runtime": {
            "profile": profile,
            "context_source": source or "any",
            "question_filter": question,
            "trace_path": str(trace_path),
            "state": "warm",
            "notes": (
                "Local timings are observational. Pipeline overhead is answer_to_done minus "
                "the answer synthesis/substance-check stage; no absolute latency threshold applies."
            ),
        },
        "provenance": provenance,
        "runs": runs,
        "summary": {field: _series_summary([run[field] for run in runs]) for field in fields},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--profile", default="single-e4b-checked")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source", default="querystore")
    parser.add_argument("--question")
    parser.add_argument("--collection-manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path.home() / ".cache" / "llama-router-models" / "gemma-e4b.gguf",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    proof = build_proof(
        args.trace,
        args.profile,
        args.limit,
        args.source,
        repo_root=args.repo_root,
        model_path=args.model_path,
        question=args.question,
        collection_manifest=args.collection_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
