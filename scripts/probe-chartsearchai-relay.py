#!/usr/bin/env python3
"""Prove the configured OpenMRS -> med-agent-hub staged relay path."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_content(path: Path) -> dict[str, Any]:
    if path.is_file():
        return {"kind": "file", "sha256": _sha256(path), "size_bytes": path.stat().st_size}
    if not path.is_dir():
        raise RuntimeError(f"artifact does not exist: {path}")
    files = [
        {
            "path": str(item.relative_to(path)),
            "sha256": _sha256(item),
            "size_bytes": item.stat().st_size,
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "kind": "directory",
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }


def _canonical_envelope(payload: dict[str, Any], *, hydrated: bool = False) -> dict[str, Any]:
    answer = payload.get("content") if hydrated else payload.get("answer")
    return {
        "answer": answer or "",
        "blocks": payload.get("blocks") or [],
        "references": payload.get("references") or [],
        "safetyWarnings": payload.get("safetyWarnings") or [],
        "confidence": payload.get("confidence"),
        "answerValidation": payload.get("answerValidation"),
        "inDepth": payload.get("inDepth"),
    }


def _canonical_sha256(payload: dict[str, Any], *, hydrated: bool = False) -> str:
    encoded = json.dumps(
        _canonical_envelope(payload, hydrated=hydrated),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git_identity(path: Path) -> dict[str, Any]:
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip(),
        "tree_clean": not bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=path,
                text=True,
            ).strip()
        ),
    }


def _artifact_identity(
    name: str,
    repo: Path,
    artifact: Path,
    manifest: Path,
) -> dict[str, Any]:
    if not artifact.exists() or not manifest.is_file():
        raise RuntimeError(f"{name} artifact or provenance is missing")
    provenance = json.loads(manifest.read_text(encoding="utf-8"))
    identity = _git_identity(repo)
    content = _artifact_content(artifact)
    source_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=repo, text=True
    ).strip()
    if provenance.get("source_commit") != identity["commit"]:
        raise RuntimeError(f"{name} provenance does not match the current commit")
    if provenance.get("source_tree") != source_tree:
        raise RuntimeError(f"{name} provenance does not match the current source tree")
    if provenance.get("artifact_kind") != content["kind"]:
        raise RuntimeError(f"{name} provenance has the wrong artifact kind")
    if provenance.get("artifact_sha256") != content["sha256"]:
        raise RuntimeError(f"{name} provenance does not match the staged artifact")
    if provenance.get("artifact_size_bytes") != content["size_bytes"]:
        raise RuntimeError(f"{name} provenance has the wrong artifact size")
    if provenance.get("artifact_files") != content.get("files"):
        raise RuntimeError(f"{name} provenance does not match the staged artifact files")
    return {
        "path": str(artifact.relative_to(ROOT)),
        "kind": content["kind"],
        "sha256": content["sha256"],
        "size_bytes": content["size_bytes"],
        **({"files": content["files"]} if content["kind"] == "directory" else {}),
        "provenance_path": str(manifest.relative_to(ROOT)),
        "provenance": provenance,
    }


def _runtime_identity(openmrs_url: str) -> dict[str, Any]:
    container = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "harness-med-agent-hub"], text=True
        )
    )[0]
    image_id = container["Image"]
    image = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image_id], text=True)
    )[0]
    labels = (image.get("Config") or {}).get("Labels") or {}
    artifact_specs = {
        "chartsearchai_omod": (
            ROOT / "targets/chartsearchai",
            ROOT / "artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod",
            ROOT
            / "artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod.provenance.json",
        ),
        "chartsearchai_esm": (
            ROOT / "targets/chartsearchai-esm",
            ROOT / "artifacts/openmrs/spa-custom",
            ROOT / "artifacts/openmrs/chartsearchai-esm.provenance.json",
        ),
    }
    artifacts = {
        name: _artifact_identity(name, repo, artifact, manifest)
        for name, (repo, artifact, manifest) in artifact_specs.items()
    }
    deployed_manifest = ROOT / "artifacts/chartsearchai-local/deployed-chartsearchai-omod.json"
    if not deployed_manifest.is_file():
        raise RuntimeError("deployed ChartSearchAI module provenance is missing")
    if json.loads(deployed_manifest.read_text()) != artifacts["chartsearchai_omod"][
        "provenance"
    ]:
        raise RuntimeError("deployed ChartSearchAI module provenance is stale")
    mounted_omod_sha256 = subprocess.check_output(
        [
            "docker",
            "exec",
            "harness-openmrs-backend",
            "sha256sum",
            "/openmrs/data/modules/chartsearchai-1.0.0-SNAPSHOT.omod",
        ],
        text=True,
    ).split()[0]
    esm = artifacts["chartsearchai_esm"]
    served_files: dict[str, str] = {}
    for item in esm.get("files") or []:
        relative = item["path"]
        served_url = f"{openmrs_url.rstrip('/')}/spa/{urllib.parse.quote(relative)}"
        with urllib.request.urlopen(served_url, timeout=30) as response:
            served_sha256 = hashlib.sha256(response.read()).hexdigest()
        if served_sha256 != item["sha256"]:
            raise RuntimeError(f"served ChartSearchAI ESM asset differs: {relative}")
        served_files[relative] = served_sha256
    importmap_path = ROOT / "artifacts/openmrs/spa-custom/importmap.json"
    importmap = json.loads(importmap_path.read_text(encoding="utf-8"))
    import_target = (importmap.get("imports") or {}).get("@openmrs/esm-chartsearchai-app")
    expected_target = "./openmrs-esm-chartsearchai-app-multiturn/openmrs-esm-chartsearchai-app.js"
    if import_target != expected_target:
        raise RuntimeError("served ChartSearchAI import-map target is not the staged bundle")
    if mounted_omod_sha256 != artifacts["chartsearchai_omod"]["sha256"]:
        raise RuntimeError("mounted ChartSearchAI module differs from the staged artifact")
    artifacts["chartsearchai_omod"]["mounted_sha256"] = mounted_omod_sha256
    artifacts["chartsearchai_omod"]["deployed_provenance_path"] = str(
        deployed_manifest.relative_to(ROOT)
    )
    artifacts["chartsearchai_esm"]["import_map_target"] = import_target
    artifacts["chartsearchai_esm"]["served_files"] = served_files
    return {
        "harness": _git_identity(ROOT),
        "med_agent_hub": _git_identity(ROOT / "targets/med-agent-hub"),
        "chartsearchai": _git_identity(ROOT / "targets/chartsearchai"),
        "chartsearchai_esm": _git_identity(ROOT / "targets/chartsearchai-esm"),
        "deployment": {
            "container_id": container["Id"],
            "image_id": image_id,
            "revision": labels.get("org.opencontainers.image.revision"),
        },
        "artifacts": artifacts,
        "configuration": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": _sha256(path)}
            for name, path in {
                "hub_profiles": ROOT / "targets/med-agent-hub/server/levels.yaml",
                "compose": ROOT / "compose/openmrs-2.8-refapp.yml",
                "relay_configuration": ROOT / "scripts/chartsearch-configure.sh",
            }.items()
        },
    }


def _request(
    url: str,
    *,
    username: str,
    password: str,
    payload: dict[str, Any] | None = None,
    accept: str = "application/json",
) -> urllib.request.Request:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Accept": accept, "Authorization": f"Basic {token}"}
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
        method = "POST"
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def _stream_turn(
    stream_url: str,
    *,
    patient: str,
    profile: str,
    question: str,
    username: str,
    password: str,
    timeout: int,
) -> dict[str, Any]:
    request = _request(
        stream_url,
        username=username,
        password=password,
        payload={"patient": patient, "profile": profile, "question": question},
        accept="text/event-stream",
    )
    started = time.monotonic()
    event = ""
    data_lines: list[str] = []
    answer_done: dict[str, Any] | None = None
    final: dict[str, Any] | None = None
    event_names: list[str] = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        session = response.headers.get("X-ChartSearchAi-Session")
        for raw in response:
            line = raw.decode(errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                value = line.split(":", 1)[1]
                data_lines.append(value[1:] if value.startswith(" ") else value)
            elif line == "" and data_lines:
                data = "\n".join(data_lines)
                if event == "error":
                    raise RuntimeError(f"ChartSearchAI relay returned an error: {data}")
                payload = json.loads(data)
                event_names.append(event)
                if event == "answer_done":
                    if not payload.get("answer"):
                        raise RuntimeError("answer_done did not contain an answer")
                    if not payload.get("messageId"):
                        raise RuntimeError("answer_done did not contain a messageId")
                    if not isinstance(payload.get("auditLogId"), int):
                        raise RuntimeError("answer_done did not contain a numeric auditLogId")
                    returned_profile = payload.get("model") or payload.get("resolvedModel")
                    if returned_profile != profile:
                        raise RuntimeError(
                            "answer_done returned an unexpected profile: "
                            f"{returned_profile!r} != {profile!r}"
                        )
                    resolved_session = payload.get("session") or session
                    if not resolved_session:
                        raise RuntimeError("relay did not expose a session id")
                    answer_done = {
                        "session": resolved_session,
                        "message_id": payload["messageId"],
                        "audit_log_id": payload["auditLogId"],
                        "profile": returned_profile,
                        "answer": payload["answer"],
                        "answer_validation": payload.get("answerValidation"),
                        "reference_count": len(payload.get("references") or []),
                        "answer_done_ms": round((time.monotonic() - started) * 1000),
                    }
                elif event == "done":
                    final = payload
                    break
                event = ""
                data_lines = []
    if answer_done is None:
        raise RuntimeError("ChartSearchAI relay ended before answer_done")
    if final is None:
        raise RuntimeError("ChartSearchAI relay ended before done")
    if final.get("messageId") != answer_done["message_id"]:
        raise RuntimeError("answer_done and done used different assistant rows")
    if final.get("auditLogId") != answer_done["audit_log_id"]:
        raise RuntimeError("answer_done and done used different audit rows")
    expected_events = [
        "answer_done",
        "answer_validation",
        "indepth_pending",
        "indepth_done",
        "done",
    ]
    if event_names != expected_events:
        raise RuntimeError(f"reviewed staged lifecycle was incomplete: {event_names!r}")
    validation = final.get("answerValidation") or {}
    if validation.get("status") not in {"checked", "edited"}:
        raise RuntimeError("healthy proof did not finish with a checked or edited answer")
    references = final.get("references") or []
    for reference in references:
        if not isinstance(reference, dict):
            raise RuntimeError("done contained a malformed reference")
        resolution = reference.get("resolutionStatus")
        if resolution not in {"resolved", "unresolved"}:
            raise RuntimeError("done contained a reference without terminal resolution")
        if resolution == "resolved" and reference.get("groundingStatus") not in {
            "verified",
            "unsupported",
        }:
            raise RuntimeError("resolved reference lacked a terminal grounding verdict")
    in_depth = final.get("inDepth") or {}
    if in_depth.get("status") != "complete" or not str(in_depth.get("answer") or "").strip():
        raise RuntimeError("healthy proof did not finish with complete substantive In-Depth")
    return {
        **answer_done,
        "event_names": event_names,
        "final_answer": final.get("answer") or "",
        "final_answer_validation": validation,
        "final_reference_count": len(references),
        "final_in_depth": in_depth,
        "final_envelope_sha256": _canonical_sha256(final),
        "done_ms": round((time.monotonic() - started) * 1000),
    }


def _get_json(
    url: str, *, username: str, password: str, timeout: int
) -> dict[str, Any]:
    request = _request(url, username=username, password=password)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    username: str,
    password: str,
    timeout: int,
) -> dict[str, Any]:
    request = _request(
        url, username=username, password=password, payload=payload
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else {}


def probe_relay(
    openmrs_url: str,
    *,
    patient: str,
    profile: str,
    question: str,
    username: str,
    password: str,
    timeout: int,
    clear_after: bool,
) -> dict[str, Any]:
    api = f"{openmrs_url.rstrip('/')}/ws/rest/v1/chartsearchai"
    streamed = _stream_turn(
        f"{api}/chat/stream",
        patient=patient,
        profile=profile,
        question=question,
        username=username,
        password=password,
        timeout=timeout,
    )

    history_url = f"{api}/chat?{urllib.parse.urlencode({'patient': patient})}"
    history: dict[str, Any] | None = None
    hydrated_envelope_sha256 = None
    for attempt in range(10):
        history = _get_json(
            history_url, username=username, password=password, timeout=timeout
        )
        matching = next(
            (
                row
                for row in history.get("messages") or []
                if row.get("messageId") == streamed["message_id"]
                and row.get("role") == "assistant"
                and row.get("auditLogId") == streamed["audit_log_id"]
            ),
            None,
        )
        if matching is not None:
            hydrated_envelope_sha256 = _canonical_sha256(matching, hydrated=True)
        if hydrated_envelope_sha256 == streamed["final_envelope_sha256"]:
            break
        if attempt < 9:
            time.sleep(0.25)
    else:
        raise RuntimeError("the final staged turn was not persisted in the hydrated chat session")

    if history.get("session") != streamed["session"]:
        raise RuntimeError("stream and hydration returned different session ids")

    result = {
        "schema_version": "chartsearchai_relay_probe.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "openmrs_url": openmrs_url,
        "patient": patient,
        "profile": profile,
        "question": question,
        "session": streamed["session"],
        "message_id": streamed["message_id"],
        "audit_log_id": streamed["audit_log_id"],
        "fast_answer_sha256": hashlib.sha256(streamed["answer"].encode()).hexdigest(),
        "answer_sha256": hashlib.sha256(streamed["final_answer"].encode()).hexdigest(),
        "final_envelope_sha256": streamed["final_envelope_sha256"],
        "hydrated_envelope_sha256": hydrated_envelope_sha256,
        "answer_done_ms": streamed["answer_done_ms"],
        "done_ms": streamed["done_ms"],
        "answer_validation": streamed["final_answer_validation"],
        "reference_count": streamed["final_reference_count"],
        "in_depth_status": streamed["final_in_depth"].get("status"),
        "events": streamed["event_names"],
        "hydrated": True,
        "cleared_after": clear_after,
        "runtime_identity": _runtime_identity(openmrs_url),
    }
    if clear_after:
        cleared = _post_json(
            f"{api}/chat/new",
            {"patient": patient},
            username=username,
            password=password,
            timeout=timeout,
        )
        cleared_history = _get_json(
            history_url, username=username, password=password, timeout=timeout
        )
        if not cleared.get("session") or cleared_history.get("session") != cleared.get("session"):
            raise RuntimeError("new-session response did not match hydrated session")
        if cleared_history.get("messages"):
            raise RuntimeError("new-session hydration was not empty")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openmrs-url", default="http://127.0.0.1:8088/openmrs")
    parser.add_argument("--patient", required=True)
    parser.add_argument("--profile", default="single-e4b-checked")
    parser.add_argument(
        "--question",
        default="In one short sentence, what was the most recent documented clinical visit?",
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin123")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--clear-after", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = probe_relay(
        args.openmrs_url,
        patient=args.patient,
        profile=args.profile,
        question=args.question,
        username=args.username,
        password=args.password,
        timeout=args.timeout,
        clear_after=args.clear_after,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
