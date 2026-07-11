#!/usr/bin/env python3
"""Collect an isolated, identity-bound local performance trace."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path) -> dict[str, Any]:
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "tree_clean": not bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=repo,
                text=True,
            ).strip()
        ),
    }


def _deployed_hub_identity(container: str = "harness-med-agent-hub") -> dict[str, Any]:
    """Bind measurements to the running container and its `docker inspect` image label."""
    container_data = json.loads(
        subprocess.check_output(["docker", "inspect", container], text=True)
    )[0]
    image_id = container_data["Image"]
    image_data = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image_id], text=True)
    )[0]
    labels = (image_data.get("Config") or {}).get("Labels") or {}
    return {
        "container": container,
        "container_id": container_data["Id"],
        "container_started_at": (container_data.get("State") or {}).get("StartedAt"),
        "image_id": image_id,
        "revision": labels.get("org.opencontainers.image.revision"),
    }


def runtime_identity(root: Path, model_path: Path) -> dict[str, Any]:
    hub = root / "targets" / "med-agent-hub"
    resolved_model = model_path.expanduser().resolve(strict=True)
    router_version = subprocess.check_output(
        ["llama-server", "--version"], text=True, stderr=subprocess.STDOUT
    ).splitlines()[0]
    hub_git = _git(hub)
    deployment = _deployed_hub_identity()
    if deployment["revision"] != hub_git["commit"]:
        raise RuntimeError(
            "deployed hub revision does not match the checked-out med-agent-hub commit: "
            f"{deployment['revision']!r} != {hub_git['commit']!r}"
        )
    return {
        "harness": _git(root),
        "med_agent_hub": hub_git,
        "deployment": deployment,
        "profile_config_sha256": _sha256(hub / "server" / "levels.yaml"),
        "router_config_sha256": _sha256(root / "scripts" / "llama-router.ini"),
        "router_version": router_version,
        "model_artifact": {
            "path": str(resolved_model),
            "size_bytes": resolved_model.stat().st_size,
            "sha256": _sha256(resolved_model),
        },
    }


def _full_product_turn(
    hub_url: str,
    profile: str,
    patient: str,
    question: str,
    timeout: int,
) -> None:
    payload = {
        "model": profile,
        "stream": False,
        "patient": patient,
        "context": {"source": "querystore"},
        "messages": [{"role": "user", "content": question}],
    }
    request = urllib.request.Request(
        hub_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read())
    if not (body.get("choices") or [{}])[0].get("message", {}).get("content"):
        raise RuntimeError("Product turn returned no completion content.")


def select_entries(
    lines: list[str], profile: str, question: str, count: int
) -> list[dict[str, Any]]:
    selected = []
    for line in lines:
        if not line.strip():
            continue
        entry = json.loads(line)
        sources = (entry.get("context") or {}).get("sources") or []
        has_timing = any(
            step.get("role") == "answer_timing" for step in entry.get("steps", [])
        )
        if (
            entry.get("level_id") == profile
            and entry.get("question") == question
            and "querystore" in sources
            and has_timing
        ):
            selected.append(entry)
    if len(selected) != count:
        raise RuntimeError(
            f"Expected {count} new matching trace rows, found {len(selected)}."
        )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--hub-url", default="http://127.0.0.1:18081/v1/chat/completions")
    parser.add_argument("--profile", default="single-e4b-checked")
    parser.add_argument("--patient", required=True)
    parser.add_argument(
        "--question",
        default="In one short sentence, what was the most recent documented clinical visit?",
    )
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path.home() / ".cache" / "llama-router-models" / "gemma-e4b.gguf",
    )
    parser.add_argument(
        "--live-trace", type=Path, default=Path("artifacts/hub-trace/trace.jsonl")
    )
    parser.add_argument(
        "--output-trace",
        type=Path,
        default=Path("artifacts/roadmap/gates/G20-selected-trace.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/roadmap/gates/G20-collection.json"),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    live_trace = (root / args.live_trace).resolve()
    output_trace = (root / args.output_trace).resolve()
    manifest_path = (root / args.manifest).resolve()
    before_lines = live_trace.read_text(encoding="utf-8").splitlines()
    identity_before = runtime_identity(root, args.model_path)
    if not identity_before["med_agent_hub"]["tree_clean"]:
        raise RuntimeError("med-agent-hub must be committed and clean before collection.")

    warmer = _load_module("warm_hub_profile", root / "scripts" / "warm-hub-profile.py")
    warmup = warmer.warm_profile(
        args.hub_url,
        args.profile,
        stop_after_answer=True,
        timeout=args.timeout,
    )
    for index in range(args.runs):
        print(f"product turn {index + 1}/{args.runs}", flush=True)
        _full_product_turn(
            args.hub_url,
            args.profile,
            args.patient,
            args.question,
            args.timeout,
        )

    after_lines = live_trace.read_text(encoding="utf-8").splitlines()
    selected = select_entries(
        after_lines[len(before_lines) :], args.profile, args.question, args.runs
    )
    output_trace.parent.mkdir(parents=True, exist_ok=True)
    output_trace.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in selected),
        encoding="utf-8",
    )
    identity_after = runtime_identity(root, args.model_path)
    if identity_after != identity_before:
        raise RuntimeError("Runtime identity changed during performance collection.")

    manifest = {
        "schema_version": "local_performance_collection.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {"os": platform.platform(), "machine": platform.machine()},
        "profile": args.profile,
        "patient": args.patient,
        "question": args.question,
        "runs": args.runs,
        "warmup": warmup,
        "runtime_identity": identity_before,
        "selected_trace": str(output_trace.relative_to(root)),
        "selected_trace_sha256": _sha256(output_trace),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
