"""Replay a comparison set against each backend and write results over the
run-manifest spine.

Backends are iterated SEQUENTIALLY: the backend is selected per /chat request via
a per-request {endpointUrl, modelName} override, so a run never mutates
chartsearchai's config-controlled global default. Sequencing is for determinism
and session isolation — a chat session is per (patient, user) and opening a new
one closes the prior, so concurrent backends would cross-contaminate sessions.

A result line is a projection referencing run_id — it does NOT re-declare the
manifest's provenance fields (FR-006.3); provenance lives in run_manifest.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from ..metadata import RunManifest, append_event, utc_now_iso, write_manifest
from ..submodules import read_harness_git_sha
from .client import ChatResult
from .metrics import compute_metrics
from .models import load_comparison_set, load_scenario
from .report import build_report
from .repository import JsonlRepository
from .resolver import resolve_backends


def _row_is_good(row: dict[str, Any]) -> bool:
    """A turn counts as completed only if it answered: HTTP 200 with a non-empty
    answer. A status-200-but-empty row (e.g. an upstream blip) is NOT done."""
    if (row.get("metrics") or {}).get("http_status") != 200:
        return False
    return bool(((row.get("response") or {}).get("answer") or "").strip())


def _load_completed(
    resume_from: Path | str, expected_turns: dict[str, set[int]]
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Read a prior run dir and return {(backend_id, scenario_id): good_rows} for every
    scenario×backend whose *every* expected turn has a good row — those are carried over
    on resume. Anything partial/empty/missing is left out, so it gets re-run."""
    path = Path(resume_from) / "results.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        by_pair.setdefault((r.get("backend_id"), r.get("scenario_id")), []).append(r)
    completed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (bid, sid), rs in by_pair.items():
        want = expected_turns.get(sid)
        if not want:
            continue
        good = {r.get("turn"): r for r in rs if _row_is_good(r)}
        if want <= set(good):
            completed[(bid, sid)] = [good[n] for n in sorted(want)]
    return completed


class _Client(Protocol):
    def new_session(self, patient: str) -> str: ...
    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        endpoint_url: str | None = None,
        model_name: str | None = None,
    ) -> ChatResult: ...


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    results_path: Path
    report_path: Path
    result_count: int


def run_comparison(
    *,
    comparison_set_id: str,
    client: _Client,
    data_root: Path | str = "datasets/validation",
    output_dir: Path | str = "artifacts/validate",
    project_root: Path | str = ".",
    git_sha: str | None = None,
    dataset_id: str = "large-demo-data-2-7-0",
    dataset_version: str = "2.7.0",
    schema_mapping_version: str = "openmrs-2.7-to-2.8@v0",
    gen_ai_provider_name: str = "lmstudio",
    resume_from: Path | str | None = None,
) -> RunResult:
    data_root = Path(data_root)
    cset = load_comparison_set(data_root / "comparison_sets" / f"{comparison_set_id}.json")
    scenarios = [load_scenario(data_root / "scenarios" / f"{sid}.json") for sid in cset.scenario_ids]
    backends = resolve_backends(cset.backend_ids, data_root / "backends.json")

    # Capture a rich patient profile (demographics + clinical snapshot) for each unique
    # patient the run touches, so the report grounds the comparison in the real chart.
    # Best-effort + optional: only if the client exposes get_patient_profile; never fatal.
    patients: dict[str, Any] = {}
    get_profile = getattr(client, "get_patient_profile", None)
    if get_profile is not None:
        for patient_uuid in dict.fromkeys(s.patient_ref for s in scenarios):
            try:
                profile = get_profile(patient_uuid)
                if profile:
                    patients[patient_uuid] = profile
            except Exception:
                pass

    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="validate",
        git_sha=git_sha if git_sha is not None else read_harness_git_sha(Path(project_root)),
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_mapping_version=schema_mapping_version,
        gen_ai_provider_name=gen_ai_provider_name,
        patients=patients,
    )
    manifest_path = run_dir / "run_manifest.json"
    events_path = run_dir / "events.jsonl"
    write_manifest(manifest_path, manifest)
    append_event(
        events_path,
        {
            "event_type": "run",
            "run_id": run_id,
            "component": "validate",
            "comparison_set": comparison_set_id,
            "scenario_ids": cset.scenario_ids,
            "backend_ids": cset.backend_ids,
        },
    )

    repo = JsonlRepository(authored_root=data_root, run_dir=run_dir)
    result_count = 0

    # On resume, carry over every scenario×backend that already completed cleanly in a
    # prior run dir; only the missing/partial cells are re-run below.
    expected_turns = {s.id: {t.n for t in s.turns} for s in scenarios}
    completed = _load_completed(resume_from, expected_turns) if resume_from else {}

    # Backends run sequentially because a chat session is per (patient, user) and
    # opening a new one closes the prior — NOT because of any global backend state.
    # The backend is selected per /chat request (a per-request override), so a run
    # never mutates chartsearchai's config-controlled global default.
    for backend in backends:
        append_event(
            events_path,
            {
                "event_type": "backend_selected",
                "run_id": run_id,
                "backend_id": backend.id,
                "label": backend.label,
                "endpointUrl": backend.endpoint_url,
                "modelName": backend.model_name,
            },
        )
        for scenario in scenarios:
            pair = (backend.id, scenario.id)
            if pair in completed:
                # Carry over the prior good rows, re-stamped with this run_id.
                for prior in completed[pair]:
                    row = {**prior, "run_id": run_id}
                    repo.save("results", row)
                    m = row.get("metrics") or {}
                    append_event(events_path, {
                        "event_type": "evaluation", "check": "chat_turn", "run_id": run_id,
                        "scenario_id": scenario.id, "backend_id": backend.id,
                        "turn": row.get("turn"), "http_status": m.get("http_status"),
                        "latency_ms": m.get("latency_ms"),
                        "citation_count": m.get("citation_count", 0), "resumed": True,
                    })
                    result_count += 1
                continue
            try:
                session = client.new_session(scenario.patient_ref)
            except Exception as exc:
                # Couldn't open a session (e.g. backend restarting) even after the
                # client's retries: record each turn as an error and move on — never
                # abort the whole run because one scenario couldn't start.
                for turn in scenario.turns:
                    now = utc_now_iso()
                    metrics = compute_metrics(
                        envelope=None, latency_ms=0, http_status=0, first_turn=(turn.n == 1))
                    repo.save("results", {
                        "run_id": run_id, "scenario_id": scenario.id, "backend_id": backend.id,
                        "turn": turn.n,
                        "request": {"patient": scenario.patient_ref, "session": None,
                                    "question": turn.question},
                        "response": None, "metrics": metrics,
                        "error": f"new_session failed: {type(exc).__name__}: {exc}"[:500],
                        "started_at": now, "ended_at": now,
                    })
                    result_count += 1
                continue
            first_turn = True
            for turn in scenario.turns:
                session_sent = session
                started = utc_now_iso()
                try:
                    res = client.chat(
                        scenario.patient_ref, session_sent, turn.question,
                        endpoint_url=backend.endpoint_url, model_name=backend.model_name,
                    )
                except Exception as exc:
                    # A hung/failed request must NOT abort the whole run — record it
                    # as an error result (like a non-200 response) and continue.
                    res = ChatResult(status=0, envelope=None, latency_ms=0,
                                     raw_text=f"request failed: {type(exc).__name__}: {exc}")
                ended = utc_now_iso()
                if res.envelope and res.envelope.get("session"):
                    session = res.envelope["session"]
                metrics = compute_metrics(
                    envelope=res.envelope,
                    latency_ms=res.latency_ms,
                    http_status=res.status,
                    first_turn=first_turn,
                )
                repo.save(
                    "results",
                    {
                        "run_id": run_id,
                        "scenario_id": scenario.id,
                        "backend_id": backend.id,
                        "turn": turn.n,
                        "request": {
                            "patient": scenario.patient_ref,
                            "session": session_sent,
                            "question": turn.question,
                        },
                        "response": res.envelope,
                        "metrics": metrics,
                        "error": None if res.status == 200 else (res.raw_text or "")[:500],
                        "started_at": started,
                        "ended_at": ended,
                    },
                )
                append_event(
                    events_path,
                    {
                        "event_type": "evaluation",
                        "check": "chat_turn",
                        "run_id": run_id,
                        "scenario_id": scenario.id,
                        "backend_id": backend.id,
                        "turn": turn.n,
                        "http_status": res.status,
                        "latency_ms": res.latency_ms,
                        "citation_count": metrics["citation_count"],
                    },
                )
                result_count += 1
                first_turn = False

    report_path = build_report(run_dir)

    return RunResult(
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        results_path=run_dir / "results.jsonl",
        report_path=report_path,
        result_count=result_count,
    )
