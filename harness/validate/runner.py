"""Replay a comparison set against each backend and write results over the
run-manifest spine.

Backends are iterated STRICTLY SEQUENTIALLY: POST /endpoint mutates global
active-backend state, so two backends must never run concurrently or their turns
cross-contaminate (spec 006 risk note).

A result line is a projection referencing run_id — it does NOT re-declare the
manifest's provenance fields (FR-006.3); provenance lives in run_manifest.json.
"""

from __future__ import annotations

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
) -> RunResult:
    data_root = Path(data_root)
    cset = load_comparison_set(data_root / "comparison_sets" / f"{comparison_set_id}.json")
    scenarios = [load_scenario(data_root / "scenarios" / f"{sid}.json") for sid in cset.scenario_ids]
    backends = resolve_backends(cset.backend_ids, data_root / "backends.json")

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
            session = client.new_session(scenario.patient_ref)
            first_turn = True
            for turn in scenario.turns:
                session_sent = session
                started = utc_now_iso()
                res = client.chat(
                    scenario.patient_ref, session_sent, turn.question,
                    endpoint_url=backend.endpoint_url, model_name=backend.model_name,
                )
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
