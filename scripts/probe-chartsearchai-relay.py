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


def _terminal_reference_state(reference: dict[str, Any]) -> tuple[int, str, str]:
    index = reference.get("index")
    if type(index) is not int or index <= 0:
        raise RuntimeError("reference does not have a positive integer index")
    resolution = reference.get("resolutionStatus")
    grounding = reference.get("groundingStatus")
    if resolution == "resolved" and grounding not in {
        "verified",
        "unsupported",
        "mixed",
    }:
        raise RuntimeError("resolved reference lacked a terminal grounding verdict")
    if resolution == "unresolved" and grounding != "unchecked":
        raise RuntimeError("unresolved reference lacked terminal unchecked grounding")
    if resolution not in {"resolved", "unresolved"}:
        raise RuntimeError("reference did not have terminal resolution")
    return index, resolution, grounding


def _answer_side(payload: dict[str, Any]) -> dict[str, Any]:
    confidence = payload.get("confidence") or {}
    return {
        "answer": payload.get("answer") or "",
        "blocks": payload.get("blocks") or [],
        "safetyWarnings": payload.get("safetyWarnings") or [],
        "answerValidation": payload.get("answerValidation"),
        "answerConfidence": confidence.get("answer") if isinstance(confidence, dict) else None,
    }


def _answer_reference_states(payload: dict[str, Any]) -> list[tuple[int, str, str]]:
    references = payload.get("references") or []
    has_usage = any(reference.get("usage") for reference in references if isinstance(reference, dict))
    answer_references = (
        [
            reference
            for reference in references
            if any(
                usage.get("location") in {"answer", "block"}
                for usage in (reference.get("usage") or [])
                if isinstance(usage, dict)
            )
        ]
        if has_usage
        else references
    )
    return [_terminal_reference_state(reference) for reference in answer_references]


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
            / "artifacts/chartsearchai-local/module-provenance/"
            "chartsearchai-1.0.0-SNAPSHOT.omod.provenance.json",
        ),
        "querystore_omod": (
            ROOT / "targets/querystore",
            ROOT / "artifacts/openmrs/modules/querystore-1.0.0-SNAPSHOT.omod",
            ROOT
            / "artifacts/chartsearchai-local/module-provenance/"
            "querystore-1.0.0-SNAPSHOT.omod.provenance.json",
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
    module_specs = {
        "chartsearchai_omod": (
            ROOT / "artifacts/chartsearchai-local/deployed-chartsearchai-omod.json",
            "/openmrs/data/modules/chartsearchai-1.0.0-SNAPSHOT.omod",
        ),
        "querystore_omod": (
            ROOT / "artifacts/chartsearchai-local/deployed-querystore-omod.json",
            "/openmrs/data/modules/querystore-1.0.0-SNAPSHOT.omod",
        ),
    }
    for name, (deployed_manifest, mounted_path) in module_specs.items():
        if not deployed_manifest.is_file():
            raise RuntimeError(f"deployed {name} provenance is missing")
        if json.loads(deployed_manifest.read_text()) != artifacts[name]["provenance"]:
            raise RuntimeError(f"deployed {name} provenance is stale")
        mounted_sha256 = subprocess.check_output(
            [
                "docker",
                "exec",
                "harness-openmrs-backend",
                "sha256sum",
                mounted_path,
            ],
            text=True,
        ).split()[0]
        if mounted_sha256 != artifacts[name]["sha256"]:
            raise RuntimeError(f"mounted {name} differs from the staged artifact")
        artifacts[name]["mounted_sha256"] = mounted_sha256
        artifacts[name]["deployed_provenance_path"] = str(
            deployed_manifest.relative_to(ROOT)
        )
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
    artifacts["chartsearchai_esm"]["import_map_target"] = import_target
    artifacts["chartsearchai_esm"]["served_files"] = served_files
    source_revisions = {
        "harness": _git_identity(ROOT),
        "med_agent_hub": _git_identity(ROOT / "targets/med-agent-hub"),
        "chartsearchai": _git_identity(ROOT / "targets/chartsearchai"),
        "chartsearchai_esm": _git_identity(ROOT / "targets/chartsearchai-esm"),
        "querystore": _git_identity(ROOT / "targets/querystore"),
    }
    deployed_hub_revision = labels.get("org.opencontainers.image.revision")
    if deployed_hub_revision != source_revisions["med_agent_hub"]["commit"]:
        raise RuntimeError("running med-agent-hub image does not match the pinned source")
    return {
        **source_revisions,
        "deployment": {
            "container_id": container["Id"],
            "image_id": image_id,
            "revision": deployed_hub_revision,
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
    provider: str = "hub",
    profile: str,
    question: str,
    session: str | None = None,
    username: str,
    password: str,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "patient": patient,
        "provider": provider,
        "profile": profile,
        "question": question,
    }
    if session:
        payload["session"] = session
    request = _request(
        stream_url,
        username=username,
        password=password,
        payload=payload,
        accept="text/event-stream",
    )
    started = time.monotonic()
    event = ""
    data_lines: list[str] = []
    answer_done: dict[str, Any] | None = None
    turn_done: dict[str, Any] | None = None
    event_names: list[str] = []
    phase_payloads: dict[str, dict[str, Any]] = {}
    stream_audit_log_id: int | None = None

    def observe_stream_audit_log_id(payload: dict[str, Any], phase: str) -> None:
        """Accept omitted early audit IDs, but reject malformed or inconsistent ones."""
        nonlocal stream_audit_log_id
        audit_log_id = payload.get("auditLogId")
        if audit_log_id is None:
            return
        if type(audit_log_id) is not int:
            raise RuntimeError(f"{phase} contained a non-numeric auditLogId")
        if stream_audit_log_id is not None and audit_log_id != stream_audit_log_id:
            raise RuntimeError(f"{phase} used a different audit row")
        stream_audit_log_id = audit_log_id

    with urllib.request.urlopen(request, timeout=timeout) as response:
        header_session = response.headers.get("X-ChartSearchAi-Session")
        for raw in response:
            line = raw.decode(errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                value = line.split(":", 1)[1]
                data_lines.append(value[1:] if value.startswith(" ") else value)
            elif line == "" and data_lines:
                data = "\n".join(data_lines)
                if not data.strip():
                    event = ""
                    data_lines = []
                    continue
                if event == "error":
                    raise RuntimeError(f"ChartSearchAI relay returned an error: {data}")
                payload = json.loads(data)
                if event == "turn_error":
                    problem_code = str(payload.get("problemCode") or "unknown_error")
                    message = str(payload.get("error") or payload.get("message") or data)
                    raise RuntimeError(
                        f"ChartSearchAI relay turn_error [{problem_code}]: {message}"
                    )
                event_names.append(event)
                phase_payloads[event] = payload
                if event == "answer_done":
                    if not payload.get("answer"):
                        raise RuntimeError("answer_done did not contain an answer")
                    if not payload.get("messageId"):
                        raise RuntimeError("answer_done did not contain a messageId")
                    if payload.get("provider") != provider:
                        raise RuntimeError("answer_done returned an unexpected provider")
                    observe_stream_audit_log_id(payload, event)
                    returned_profile = payload.get("model") or payload.get("resolvedModel")
                    if returned_profile != profile:
                        raise RuntimeError(
                            "answer_done returned an unexpected profile: "
                            f"{returned_profile!r} != {profile!r}"
                        )
                    resolved_session = payload.get("session") or header_session
                    if not resolved_session:
                        raise RuntimeError("relay did not expose a session id")
                    if session and resolved_session != session:
                        raise RuntimeError("relay used a different session than requested")
                    answer_done = {
                        "session": resolved_session,
                        "message_id": payload["messageId"],
                        "profile": returned_profile,
                        "answer": payload["answer"],
                        "answer_validation": payload.get("answerValidation"),
                        "reference_count": len(payload.get("references") or []),
                        "answer_done_ms": round((time.monotonic() - started) * 1000),
                    }
                elif event == "turn_done":
                    turn_done = payload
                    break
                event = ""
                data_lines = []
    if answer_done is None:
        raise RuntimeError("ChartSearchAI relay ended before answer_done")
    if turn_done is None:
        raise RuntimeError("ChartSearchAI relay ended before turn_done")
    if turn_done.get("messageId") != answer_done["message_id"]:
        raise RuntimeError("answer_done and turn_done used different assistant rows")
    if turn_done.get("provider") != provider:
        raise RuntimeError("turn_done returned an unexpected provider")
    if turn_done.get("session") not in {None, answer_done["session"]}:
        raise RuntimeError("answer_done and turn_done used different sessions")
    observe_stream_audit_log_id(turn_done, "turn_done")
    valid_event_sequences = {
        (
            "turn_started",
            "answer_done",
            "answer_validation",
            "indepth_pending",
            "indepth_done",
            "turn_done",
        ),
        (
            "turn_started",
            "answer_done",
            "answer_validation",
            "indepth_pending",
            "indepth_error",
            "turn_done",
        ),
    }
    if tuple(event_names) not in valid_event_sequences:
        raise RuntimeError(f"reviewed staged lifecycle was incomplete: {event_names!r}")
    terminal_event = event_names[-2]
    final = phase_payloads[terminal_event]
    for phase in ("answer_validation", "indepth_pending", event_names[-2]):
        payload = phase_payloads.get(phase) or {}
        if payload.get("messageId") != answer_done["message_id"]:
            raise RuntimeError(f"{phase} updated a different assistant row")
        observe_stream_audit_log_id(payload, phase)
    validation = final.get("answerValidation") or {}
    validation_status = validation.get("status")
    if validation_status not in {"checked", "edited", "needs_review"}:
        raise RuntimeError("relay proof did not finish with a terminal answer check")
    if validation_status == "needs_review":
        issues = validation.get("issues")
        if (
            not isinstance(issues, list)
            or not issues
            or any(
                not isinstance(issue, dict)
                or not any(
                    str(issue.get(key) or "").strip()
                    for key in ("reason", "wrong", "fix", "claim", "summary")
                )
                for issue in issues
            )
        ):
            raise RuntimeError("needs-review answer did not contain descriptive issues")
    final_answer_side = _answer_side(final)
    final_answer_references = _answer_reference_states(final)
    for phase in ("answer_validation", "indepth_pending"):
        payload = phase_payloads[phase]
        if _answer_side(payload) != final_answer_side:
            raise RuntimeError(f"{phase} did not carry the final Answer-side envelope")
        if _answer_reference_states(payload) != final_answer_references:
            raise RuntimeError(f"{phase} did not carry the final Answer references")
    pending = phase_payloads["indepth_pending"].get("inDepth") or {}
    if pending.get("status") != "pending":
        raise RuntimeError("indepth_pending did not carry pending In-Depth state")
    references = final.get("references") or []
    for reference in references:
        if not isinstance(reference, dict):
            raise RuntimeError("done contained a malformed reference")
        _terminal_reference_state(reference)
    if validation_status in {"checked", "edited"} and any(
        reference.get("resolutionStatus") != "resolved"
        or reference.get("groundingStatus") != "verified"
        for reference in references
    ):
        raise RuntimeError("checked answer retained unresolved or unsupported evidence")
    reference_sources = sorted(
        {
            str(reference.get("source"))
            for reference in references
            if str(reference.get("source") or "").strip()
        }
    )
    querystore_reference_count = sum(
        reference.get("source") == "querystore" for reference in references
    )
    in_depth = final.get("inDepth") or {}
    terminal_payload = phase_payloads[terminal_event]
    if _canonical_sha256(terminal_payload) != _canonical_sha256(final):
        raise RuntimeError(f"{terminal_event} did not carry the final assistant envelope")
    if terminal_event == "indepth_done":
        if in_depth.get("status") != "complete" or not str(
            in_depth.get("answer") or ""
        ).strip():
            raise RuntimeError("indepth_done did not contain complete substantive In-Depth")
    else:
        indepth_validation = in_depth.get("validation") or {}
        if in_depth.get("status") != "needs_review" or not str(
            in_depth.get("error") or ""
        ).strip():
            raise RuntimeError("indepth_error did not contain a reasoned safety withholding")
        if indepth_validation.get("status") != "needs_review":
            raise RuntimeError("indepth_error lost needs-review validation metadata")
        if indepth_validation.get("review_status") == "unavailable":
            raise RuntimeError("In-Depth review was unavailable")
    return {
        **answer_done,
        "stream_audit_log_id": stream_audit_log_id,
        "event_names": event_names,
        "final_answer": final.get("answer") or "",
        "final_answer_validation": validation,
        "final_reference_count": len(references),
        "reference_sources": reference_sources,
        "querystore_reference_count": querystore_reference_count,
        "final_in_depth": in_depth,
        "in_depth_terminal_event": terminal_event,
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


def discover_default_profile(
    openmrs_url: str,
    *,
    username: str,
    password: str,
    timeout: int,
) -> str:
    api = f"{openmrs_url.rstrip('/')}/ws/rest/v1/chartsearchai"
    payload = _get_json(
        f"{api}/models",
        username=username,
        password=password,
        timeout=timeout,
    )
    defaults = [
        item
        for item in payload.get("data", [])
        if item.get("visibility") == "product"
        and item.get("available") is True
        and item.get("default") is True
    ]
    if len(defaults) != 1 or not str(defaults[0].get("id") or "").strip():
        raise RuntimeError(
            "hub must advertise exactly one available default product profile; "
            f"found {defaults!r}"
        )
    return str(defaults[0]["id"])


def probe_relay(
    openmrs_url: str,
    *,
    patient: str,
    provider: str = "hub",
    profile: str,
    question: str,
    username: str,
    password: str,
    timeout: int,
    clear_after: bool,
) -> dict[str, Any]:
    api = f"{openmrs_url.rstrip('/')}/ws/rest/v1/chartsearchai"
    fresh = _post_json(
        f"{api}/chat/new",
        {"patient": patient, "provider": provider},
        username=username,
        password=password,
        timeout=timeout,
    )
    session = str(fresh.get("session") or "").strip()
    if not session or fresh.get("provider") != provider:
        raise RuntimeError("new-session response did not create the requested provider session")
    streamed = _stream_turn(
        f"{api}/chat/stream",
        patient=patient,
        provider=provider,
        profile=profile,
        question=question,
        session=session,
        username=username,
        password=password,
        timeout=timeout,
    )
    if streamed["session"] != session:
        raise RuntimeError("fresh session and streamed turn returned different session ids")
    if streamed["querystore_reference_count"] <= 0:
        raise RuntimeError("relay proof did not use the live Querystore patient source")

    history_url = f"{api}/chat?{urllib.parse.urlencode({'patient': patient, 'session': session})}"
    history: dict[str, Any] | None = None
    hydrated_envelope_sha256 = None
    hydrated_audit_log_id: int | None = None
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
                and type(row.get("auditLogId")) is int
            ),
            None,
        )
        if matching is not None:
            hydrated_audit_log_id = matching["auditLogId"]
            if (
                streamed["stream_audit_log_id"] is not None
                and hydrated_audit_log_id != streamed["stream_audit_log_id"]
            ):
                raise RuntimeError("stream and hydrated response used different audit rows")
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
        "provider": provider,
        "profile": profile,
        "question": question,
        "session": streamed["session"],
        "message_id": streamed["message_id"],
        "audit_log_id": hydrated_audit_log_id,
        "fast_answer_sha256": hashlib.sha256(streamed["answer"].encode()).hexdigest(),
        "answer_sha256": hashlib.sha256(streamed["final_answer"].encode()).hexdigest(),
        "final_envelope_sha256": streamed["final_envelope_sha256"],
        "hydrated_envelope_sha256": hydrated_envelope_sha256,
        "answer_done_ms": streamed["answer_done_ms"],
        "done_ms": streamed["done_ms"],
        "answer_validation": streamed["final_answer_validation"],
        "reference_count": streamed["final_reference_count"],
        "reference_sources": streamed["reference_sources"],
        "querystore_reference_count": streamed["querystore_reference_count"],
        "in_depth_status": streamed["final_in_depth"].get("status"),
        "in_depth_terminal_event": streamed["in_depth_terminal_event"],
        "events": streamed["event_names"],
        "hydrated": True,
        "cleared_after": clear_after,
        "runtime_identity": _runtime_identity(openmrs_url),
    }
    if clear_after:
        cleared = _post_json(
            f"{api}/chat/new",
            {"patient": patient, "provider": provider},
            username=username,
            password=password,
            timeout=timeout,
        )
        cleared_session = str(cleared.get("session") or "").strip()
        if not cleared_session or cleared.get("provider") != provider:
            raise RuntimeError(
                "new-session response did not create the requested provider session"
            )
        cleared_history_url = (
            f"{api}/chat?"
            f"{urllib.parse.urlencode({'patient': patient, 'session': cleared_session})}"
        )
        cleared_history = _get_json(
            cleared_history_url,
            username=username,
            password=password,
            timeout=timeout,
        )
        if cleared_history.get("session") != cleared_session:
            raise RuntimeError("new-session response did not match hydrated session")
        if cleared_history.get("messages"):
            raise RuntimeError("new-session hydration was not empty")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openmrs-url", default="http://127.0.0.1:8088/openmrs")
    parser.add_argument("--patient")
    parser.add_argument(
        "--identity-only",
        action="store_true",
        help="Verify and print deployed source/artifact identity without an LLM request.",
    )
    parser.add_argument(
        "--provider",
        default="hub",
        help="Configured ChartSearchAI provider to prove (default: hub).",
    )
    parser.add_argument("--profile")
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

    if args.identity_only:
        result = {
            "schema_version": "chartsearchai_runtime_identity.v1",
            "runtime_identity": _runtime_identity(args.openmrs_url),
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0
    if not args.patient:
        parser.error("--patient is required unless --identity-only is used")

    profile = args.profile or discover_default_profile(
        args.openmrs_url,
        username=args.username,
        password=args.password,
        timeout=args.timeout,
    )
    result = probe_relay(
        args.openmrs_url,
        patient=args.patient,
        provider=args.provider,
        profile=profile,
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
