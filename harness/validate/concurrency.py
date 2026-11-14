"""Multi-clinician concurrency benchmark for OpenMRS ChartSearchAI.

OpenMRS ChartSearchAI scopes active conversations per ``(patient, user)`` and
enforces ``chartsearchai.rateLimitPerMinute`` per user. To measure true
multi-session clinical concurrency (``N=1, 2, 4`` simultaneous clinicians)
without conversation preemption or artificial single-account rate-limit
throttling, each concurrent worker uses a distinct provisioned OpenMRS clinical
account (``eval-doctor``, ``eval-nurse``, ``eval-pharmacy``,
``eval-clinical-officer``, ``eval-counsellor``, ``eval-records``, ``eval-peer``,
``admin``) and scenario patient.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import inspect
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Sequence
from uuid import uuid4

from ..metadata import utc_now_iso
from ..common.stats import avg, percentile
from .client import (
    ChartSearchAiClient,
    ChatResult,
    MedAgentHubClient,
    OpenAICompatibleClient,
)
from .metrics import compute_metrics
from .models import load_comparison_set, load_scenario
from .resolver import resolve_backends
from .runner import resolve_hardware_metadata

DEFAULT_CLINICAL_ACCOUNTS: tuple[tuple[str, str], ...] = (
    ("eval-doctor", "Admin123"),
    ("eval-nurse", "Admin123"),
    ("eval-pharmacy", "Admin123"),
    ("eval-clinical-officer", "Admin123"),
    ("eval-counsellor", "Admin123"),
    ("eval-records", "Admin123"),
    ("eval-peer", "Admin123"),
    ("admin", "Admin123"),
)


@dataclass(frozen=True)
class ConcurrencyRunResult:
    run_id: str
    run_dir: Path
    summary_path: Path
    results_path: Path
    summary: dict[str, Any]


def _p50(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(percentile(sorted(vals), 0.50), 1)


def _p95(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(percentile(sorted(vals), 0.95), 1)


def _default_client_factory(user: str, password: str) -> ChartSearchAiClient:
    eff_password = os.environ.get("EVALUATION_PASSWORD") or password
    return ChartSearchAiClient(user=user, password=eff_password, min_interval_s=0.0)


def _make_transport_client_factory(
    transport: str, endpoint_url: str | None = None
) -> Callable[[str, str], Any]:
    if transport == "med-agent-hub":
        return lambda _user, _password: MedAgentHubClient(
            base_url=endpoint_url, min_interval_s=0.0
        )
    if transport == "openai-compatible":
        return lambda _user, _password: OpenAICompatibleClient(
            base_url=endpoint_url, min_interval_s=0.0
        )
    return _default_client_factory


DEFAULT_TTFT_SLO_MS = 3000.0
DEFAULT_ANSWER_DONE_SLO_MS = 10000.0
DEFAULT_TPOT_SLO_MS = 50.0


def _meets_slo(
    metrics: dict[str, Any],
    *,
    ttft_slo_ms: float,
    answer_done_slo_ms: float,
    tpot_slo_ms: float,
) -> bool:
    ttft = metrics.get("ttft_ms")
    if isinstance(ttft, (int, float)) and ttft > ttft_slo_ms:
        return False
    ans_done = metrics.get("answer_done_ms")
    if isinstance(ans_done, (int, float)) and ans_done > answer_done_slo_ms:
        return False
    tpot = metrics.get("tpot_ms")
    if isinstance(tpot, (int, float)) and tpot > tpot_slo_ms:
        return False
    return True


def summarize_concurrency_rows(
    rows: Sequence[dict[str, Any]],
    *,
    run_id: str,
    comparison_set_id: str,
    backend_id: str,
    n_users: int,
    turns_per_user: int,
    wall_clock_s: float,
    hardware: dict[str, Any] | None = None,
    ttft_slo_ms: float = DEFAULT_TTFT_SLO_MS,
    answer_done_slo_ms: float = DEFAULT_ANSWER_DONE_SLO_MS,
    tpot_slo_ms: float = DEFAULT_TPOT_SLO_MS,
) -> dict[str, Any]:
    ok_rows = [
        r for r in rows if (r.get("metrics") or {}).get("http_status") == 200 and not r.get("error")
    ]
    goodput_rows = [
        r
        for r in ok_rows
        if _meets_slo(
            r.get("metrics") or {},
            ttft_slo_ms=ttft_slo_ms,
            answer_done_slo_ms=answer_done_slo_ms,
            tpot_slo_ms=tpot_slo_ms,
        )
    ]
    ttft_vals = [
        float(r["metrics"]["ttft_ms"])
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("ttft_ms"), (int, float))
    ]
    turn1_ttft_vals = [
        float(r["metrics"]["ttft_ms"])
        for r in ok_rows
        if r.get("turn") == 1 and isinstance((r.get("metrics") or {}).get("ttft_ms"), (int, float))
    ]
    turn2plus_ttft_vals = [
        float(r["metrics"]["ttft_ms"])
        for r in ok_rows
        if (r.get("turn") or 0) > 1
        and isinstance((r.get("metrics") or {}).get("ttft_ms"), (int, float))
    ]
    ans_vals = [
        float(r["metrics"]["answer_done_ms"])
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("answer_done_ms"), (int, float))
    ]
    turn_vals = [
        float(
            r["metrics"].get("turn_done_ms")
            if isinstance(r["metrics"].get("turn_done_ms"), (int, float))
            else r["metrics"]["latency_ms"]
        )
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("latency_ms"), (int, float))
    ]
    tpot_vals = [
        float(r["metrics"]["tpot_ms"])
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("tpot_ms"), (int, float))
    ]
    cached_vals = [
        float(r["metrics"]["cached_tokens"])
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("cached_tokens"), (int, float))
    ]
    cache_ratios = [
        float(r["metrics"]["cache_hit_ratio"])
        for r in ok_rows
        if isinstance((r.get("metrics") or {}).get("cache_hit_ratio"), (int, float))
    ]
    total_turns = len(rows)
    ok_turns = len(ok_rows)
    goodput_turns = len(goodput_rows)
    error_turns = total_turns - ok_turns
    throughput = round((ok_turns / wall_clock_s) * 60.0, 2) if wall_clock_s > 0 else 0.0
    goodput_tpm = round((goodput_turns / wall_clock_s) * 60.0, 2) if wall_clock_s > 0 else 0.0
    summary: dict[str, Any] = {
        "run_id": run_id,
        "comparison_set": comparison_set_id,
        "backend_id": backend_id,
        "n_users": n_users,
        "turns_per_user": turns_per_user,
        "total_turns": total_turns,
        "ok_turns": ok_turns,
        "error_turns": error_turns,
        "error_rate": round(error_turns / total_turns, 4) if total_turns else 0.0,
        "wall_clock_s": round(wall_clock_s, 3),
        "throughput_turns_per_min": throughput,
        "slo_thresholds_ms": {
            "ttft_ms": ttft_slo_ms,
            "answer_done_ms": answer_done_slo_ms,
            "tpot_ms": tpot_slo_ms,
        },
        "goodput_turns": goodput_turns,
        "goodput_rate": round(goodput_turns / total_turns, 4) if total_turns else 0.0,
        "goodput_turns_per_min": goodput_tpm,
        "ttft_avg_ms": avg(ttft_vals) if ttft_vals else None,
        "ttft_p50_ms": _p50(ttft_vals),
        "ttft_p95_ms": _p95(ttft_vals),
        "turn_1_ttft_p50_ms": _p50(turn1_ttft_vals),
        "turn_2plus_ttft_p50_ms": _p50(turn2plus_ttft_vals),
        "answer_done_avg_ms": avg(ans_vals) if ans_vals else None,
        "answer_done_p50_ms": _p50(ans_vals),
        "answer_done_p95_ms": _p95(ans_vals),
        "turn_done_avg_ms": avg(turn_vals) if turn_vals else None,
        "turn_done_p50_ms": _p50(turn_vals),
        "turn_done_p95_ms": _p95(turn_vals),
        "tpot_avg_ms": round(sum(tpot_vals) / len(tpot_vals), 2) if tpot_vals else None,
        "tpot_p50_ms": _p50(tpot_vals),
        "cached_tokens_avg": avg(cached_vals) if cached_vals else None,
        "cache_hit_ratio_avg": (
            round(sum(cache_ratios) / len(cache_ratios), 4) if cache_ratios else None
        ),
        "users": [r.get("user") for r in rows if r.get("turn") == 1],
    }
    if hardware:
        summary["hardware"] = hardware
    return summary


def run_concurrency_benchmark(
    *,
    comparison_set_id: str,
    n_users: int = 1,
    turns_per_user: int = 1,
    backend_id: str | None = None,
    data_root: Path | str = "datasets/validation",
    output_dir: Path | str = "artifacts/concurrency",
    accounts: Sequence[tuple[str, str]] = DEFAULT_CLINICAL_ACCOUNTS,
    client_factory: Callable[[str, str], Any] | None = None,
    reference_date: str | None = None,
    hardware_metadata: dict[str, Any] | None = None,
    ttft_slo_ms: float = DEFAULT_TTFT_SLO_MS,
    answer_done_slo_ms: float = DEFAULT_ANSWER_DONE_SLO_MS,
    tpot_slo_ms: float = DEFAULT_TPOT_SLO_MS,
) -> ConcurrencyRunResult:
    if n_users < 1:
        raise ValueError("n_users must be >= 1")
    if turns_per_user < 1:
        raise ValueError("turns_per_user must be >= 1")
    if not accounts:
        raise ValueError("accounts must be non-empty")

    data_root = Path(data_root)
    cset = load_comparison_set(data_root / "comparison_sets" / f"{comparison_set_id}.json")
    scenarios = [load_scenario(data_root / "scenarios" / f"{sid}.json") for sid in cset.scenario_ids]
    if not scenarios:
        raise ValueError(f"comparison set {comparison_set_id} has no scenarios")
    backends = resolve_backends(cset.backend_ids, data_root / "backends.json")
    if backend_id is not None:
        matched = [b for b in backends if b.id == backend_id]
        if not matched:
            raise ValueError(f"backend_id {backend_id!r} not in comparison set {comparison_set_id}")
        backend = matched[0]
    else:
        backend = backends[0]

    factory = client_factory or _make_transport_client_factory(
        cset.transport, backend.endpoint_url
    )
    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    barrier = threading.Barrier(n_users)

    def _worker(worker_idx: int) -> list[dict[str, Any]]:
        user, password = accounts[worker_idx % len(accounts)]
        scenario = scenarios[worker_idx % len(scenarios)]
        client = factory(user, password)
        try:
            chat_params = inspect.signature(client.chat).parameters
            takes_provider = "provider" in chat_params
            takes_request_id = "request_id" in chat_params
            takes_ref_date = "reference_date" in chat_params
            takes_endpoint_url = "endpoint_url" in chat_params
            takes_execution = "execution" in chat_params
        except (ValueError, TypeError):
            takes_provider = False
            takes_request_id = False
            takes_ref_date = False
            takes_endpoint_url = False
            takes_execution = False
        try:
            session_takes_provider = "provider" in inspect.signature(client.new_session).parameters
        except (ValueError, TypeError):
            session_takes_provider = False

        try:
            if backend.provider and session_takes_provider:
                session: str | None = client.new_session(
                    scenario.patient_ref, provider=backend.provider
                )
            else:
                session = client.new_session(scenario.patient_ref)
            session_err: str | None = None
        except Exception as exc:
            session = None
            session_err = f"new_session failed: {type(exc).__name__}: {exc}"[:500]

        # Synchronize all workers after session creation so turn 1 fires concurrently.
        try:
            barrier.wait(timeout=30.0)
        except threading.BrokenBarrierError:
            pass

        worker_rows: list[dict[str, Any]] = []
        for turn_idx in range(turns_per_user):
            turn_obj = scenario.turns[turn_idx % len(scenario.turns)]
            turn_num = turn_idx + 1
            started = utc_now_iso()
            if session_err is not None:
                metrics = compute_metrics(
                    envelope=None, latency_ms=0, http_status=0, first_turn=(turn_num == 1)
                )
                worker_rows.append(
                    {
                        "run_id": run_id,
                        "worker_id": worker_idx,
                        "user": user,
                        "scenario_id": scenario.id,
                        "backend_id": backend.id,
                        "turn": turn_num,
                        "request": {
                            "patient": scenario.patient_ref,
                            "session": None,
                            "question": turn_obj.question,
                        },
                        "response": None,
                        "metrics": metrics,
                        "error": session_err,
                        "started_at": started,
                        "ended_at": started,
                    }
                )
                continue

            request_id = str(uuid4()) if takes_request_id else None
            chat_kwargs: dict[str, Any] = (
                {} if backend.provider == "bundled" else {"profile": backend.model_name}
            )
            if backend.provider and takes_provider:
                chat_kwargs["provider"] = backend.provider
            if takes_ref_date:
                chat_kwargs["reference_date"] = reference_date
            if takes_request_id:
                chat_kwargs["request_id"] = request_id
            if takes_endpoint_url and backend.endpoint_url:
                chat_kwargs["endpoint_url"] = backend.endpoint_url
            if takes_execution and backend.execution is not None:
                chat_kwargs["execution"] = dict(backend.execution)

            try:
                res = client.chat(
                    scenario.patient_ref, session, turn_obj.question, **chat_kwargs
                )
            except Exception as exc:
                res = ChatResult(
                    status=0,
                    envelope=None,
                    latency_ms=0,
                    raw_text=f"request failed: {type(exc).__name__}: {exc}",
                )
            ended = utc_now_iso()
            if res.envelope and res.envelope.get("session"):
                session = res.envelope["session"]
            metrics = compute_metrics(
                envelope=res.envelope,
                latency_ms=res.latency_ms,
                http_status=res.status,
                first_turn=(turn_num == 1),
            )
            worker_rows.append(
                {
                    "run_id": run_id,
                    "worker_id": worker_idx,
                    "user": user,
                    "scenario_id": scenario.id,
                    "backend_id": backend.id,
                    "turn": turn_num,
                    "request": {
                        "patient": scenario.patient_ref,
                        "session": session,
                        "question": turn_obj.question,
                        "profile": chat_kwargs.get("profile"),
                        "provider": backend.provider or None,
                        **({"execution": dict(chat_kwargs["execution"])} if "execution" in chat_kwargs else {}),
                        **({"request_id": request_id} if request_id else {}),
                    },
                    "response": res.envelope,
                    "metrics": metrics,
                    "error": None if res.status == 200 else (res.raw_text or "")[:500],
                    "started_at": started,
                    "ended_at": ended,
                }
            )
        return worker_rows

    t0 = time.perf_counter()
    all_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = [pool.submit(_worker, i) for i in range(n_users)]
        for fut in futures:
            all_rows.extend(fut.result())
    wall_clock_s = time.perf_counter() - t0

    results_path = run_dir / "concurrency_results.jsonl"
    with results_path.open("w", encoding="utf-8") as handle:
        for row in all_rows:
            handle.write(json.dumps(row) + "\n")

    hw = resolve_hardware_metadata(hardware_metadata)
    summary = summarize_concurrency_rows(
        all_rows,
        run_id=run_id,
        comparison_set_id=comparison_set_id,
        backend_id=backend.id,
        n_users=n_users,
        turns_per_user=turns_per_user,
        wall_clock_s=wall_clock_s,
        hardware=hw,
        ttft_slo_ms=ttft_slo_ms,
        answer_done_slo_ms=answer_done_slo_ms,
        tpot_slo_ms=tpot_slo_ms,
    )
    summary_path = run_dir / "concurrency_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return ConcurrencyRunResult(
        run_id=run_id,
        run_dir=run_dir,
        summary_path=summary_path,
        results_path=results_path,
        summary=summary,
    )
