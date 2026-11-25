#!/usr/bin/env python3
"""Run and package CIRG H200 GPU WAHS+ evaluations over Google Sheet scenarios.

Benchmarks the current 4-pathway `wahs-engine` architecture (`note_rag`,
`condensation_kb`, `dynamic_fhir_tools`, `chart_only`) against the frozen
WAHS+ Google Sheet scenarios (`datasets/wahs_demo_patients_25x10_testset.jsonl`)
using a dedicated local `wahs-engine` container backed by the UW CIRG H200
GPU cluster (`https://llm.co.dev.cirg.uw.edu/v1`) and NEVER local Mac `:8077`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

HARNESS_ROOT = Path(__file__).resolve().parents[1]
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

DEFAULT_CASES_PATH = HARNESS_ROOT / "datasets" / "wahs_demo_patients_25x10_testset.jsonl"
DEFAULT_BUNDLES_DIR = Path("/Users/pmanko/code/hq/wahs/bundles")
DEFAULT_ENGINE_DIR = Path("/Users/pmanko/code/worktrees/wahs-engine-s6-12-profiles")
DEFAULT_ENV_FILE = Path("/Users/pmanko/code/hq/wahs/.env")
DEFAULT_HUB_URL = "http://127.0.0.1:18088"
DEFAULT_LLM_BASE_URL = "https://llm.co.dev.cirg.uw.edu/v1"
DEFAULT_CONTAINER_NAME = "wahs-engine-eval"
DEFAULT_IMAGE_NAME = "wahs-engine:dev"

COHORT_PATIENTS: dict[str, tuple[str, ...]] = {
    "core3": (
        "Maurice742_Auer97_set_b",
        "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b",
        "Marcus_Vance_Oncology_Immunotherapy_set_b",
    ),
    "cal2": (
        "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b",
        "Marcus_Vance_Oncology_Immunotherapy_set_b",
    ),
    "all10": (),
}

PATIENT_ALIASES: dict[str, str] = {
    "arthur": "Arthur_Pendelton_Anticoag_set_b",
    "byron": "Byron202_Emard19_set_b",
    "elena": "Elena_Rostova_Cardiorenal_set_b",
    "lamar": "Lamar193_Beer512_set_b",
    "julian": "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b",
    "clara": "MIMIC_10019003_ICU_Hepatopulmonary_set_b",
    "marcus": "Marcus_Vance_Oncology_Immunotherapy_set_b",
    "margaret": "Margaret_Chen_Polypharmacy_set_b",
    "maurice": "Maurice742_Auer97_set_b",
    "sofia": "Sofia_Alvarez_Maternal_Endocrine_set_b",
}

SMOKE_10_CASE_IDS: tuple[str, ...] = (
    "wahs_sheet_q01__maurice_auer",
    "wahs_sheet_q01__julian_mercer",
    "wahs_sheet_q04__marcus_vance",
    "wahs_sheet_p01__maurice_auer",
    "wahs_sheet_p02__maurice_auer",
)

SMOKE_10_PROFILES: tuple[str, ...] = (
    "wahs-engine-rag:ollama/gemma4:26b@16k",
    "wahs-engine-tools:ollama/gemma4:26b@2k",
)

PATHWAY_SPECS: dict[str, tuple[str, str]] = {
    "rag": ("wahs-engine-rag", "16k"),
    "kb": ("wahs-engine-kb", "16k"),
    "tools": ("wahs-engine-tools", "2k"),
    "chart": ("wahs-engine-chart", "16k"),
}

MODEL_ALIASES: dict[str, str] = {
    "26b": "ollama/gemma4:26b",
    "12b": "ollama/gemma4:12b",
    "e4b": "ollama/gemma4:e4b",
    "qwen3-14b": "ollama/qwen3:14b",
    "qwen3-8b": "ollama/qwen3:8b",
    "llama31-8b": "ollama/llama3.1:8b",
}

CIRG_HARDWARE_ENV: dict[str, str] = {
    "VALIDATE_HARDWARE_TIER": "cirg-cobalt-h200",
    "VALIDATE_HARDWARE_GPU": "NVIDIA H200 (141 GB HBM3e)",
    "VALIDATE_HARDWARE_VRAM_GB": "141",
    "VALIDATE_SERVING_ENGINE": "Ollama (UW CIRG cobalt)",
    "VALIDATE_PARALLEL_SLOTS": "1",
    "VALIDATE_INFERENCE_ENDPOINT": DEFAULT_LLM_BASE_URL,
}

DEFAULT_MODEL_MAP: dict[str, str] = {
    "wahs-26b-kb": "ollama/gemma4:26b",
    "wahs-26b-raw": "ollama/gemma4:26b",
    "wahs-12b-kb": "ollama/gemma4:12b",
    "wahs-12b-raw": "ollama/gemma4:12b",
    "wahs-e4b-kb": "ollama/gemma4:e4b",
    "wahs-e4b-raw": "ollama/gemma4:e4b",
    "wahs-qwen3-14b-kb": "ollama/qwen3:14b",
    "wahs-qwen3-8b-kb": "ollama/qwen3:8b",
    "wahs-llama31-8b-kb": "ollama/llama3.1:8b",
    "gemma-4-e4b": "ollama/gemma4:e4b",
    "gemma4:26b": "ollama/gemma4:26b",
    "gemma4:12b": "ollama/gemma4:12b",
    "gemma4:e4b": "ollama/gemma4:e4b",
    "qwen3-14b": "ollama/qwen3:14b",
    "qwen3.5-9b": "ollama/qwen3:8b",
    "llama-3.1-8b": "ollama/llama3.1:8b",
}


def normalize_question_id(raw: str) -> str:
    clean = str(raw or "").strip().upper()
    if not clean:
        return ""
    if clean[0] in ("Q", "P") and clean[1:].isdigit():
        return f"{clean[0]}{int(clean[1:]):02d}"
    return clean


def resolve_patient_id(raw: str) -> str:
    clean = str(raw or "").strip()
    return PATIENT_ALIASES.get(clean.lower(), clean)


def build_profiles(
    *,
    pathways: Sequence[str],
    models: Sequence[str],
    budget_override: str | None = None,
    tools_budget: str = "2k",
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m_raw in models:
        m_clean = str(m_raw or "").strip()
        if not m_clean:
            continue
        model_id = MODEL_ALIASES.get(m_clean.lower(), m_clean)
        for p_raw in pathways:
            p_key = str(p_raw or "").strip().lower()
            if p_key not in PATHWAY_SPECS:
                raise ValueError(f"Unknown WAHS pathway {p_raw!r}; expected {tuple(PATHWAY_SPECS)}")
            prefix, default_budget = PATHWAY_SPECS[p_key]
            budget = tools_budget if p_key == "tools" else (budget_override or default_budget)
            arm = f"{prefix}:{model_id}@{budget}"
            if arm not in seen:
                seen.add(arm)
                out.append(arm)
    return out


def select_cases(
    cases_path: Path,
    *,
    cohort: str = "core3",
    patients: Sequence[str] | None = None,
    questions: Sequence[str] | None = None,
    case_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if case_ids:
        order = {cid: idx for idx, cid in enumerate(case_ids)}
        selected = [r for r in rows if r.get("case_id") in order]
        selected.sort(key=lambda r: order[r["case_id"]])
        return selected

    target_patients: set[str] | None = None
    if patients:
        target_patients = {resolve_patient_id(p) for p in patients if str(p).strip()}
    elif cohort != "all10":
        if cohort not in COHORT_PATIENTS:
            raise ValueError(f"Unknown cohort {cohort!r}; expected {tuple(COHORT_PATIENTS)}")
        target_patients = set(COHORT_PATIENTS[cohort])

    target_questions: set[str] | None = None
    if questions:
        target_questions = {
            normalize_question_id(q) for q in questions if str(q).strip()
        }

    selected = []
    for row in rows:
        if target_patients is not None and row.get("patient_id") not in target_patients:
            continue
        if target_questions is not None:
            rq = normalize_question_id(str(row.get("question_id") or ""))
            if rq not in target_questions:
                continue
        selected.append(row)
    if not selected:
        raise ValueError(
            f"Selection matched 0 cases in {cases_path} "
            f"(cohort={cohort!r}, patients={patients}, questions={questions})"
        )
    return selected


def write_slice_if_needed(
    rows: list[dict[str, Any]],
    *,
    source_cases_path: Path,
    slices_dir: Path,
    tag: str,
) -> Path:
    all_rows = [
        json.loads(line)
        for line in source_cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) == len(all_rows):
        return source_cases_path
    slices_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows).encode("utf-8")
    ).hexdigest()[:10]
    slice_path = slices_dir / f"{source_cases_path.stem}__{tag}__{len(rows)}c_{digest}.jsonl"
    slice_path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    return slice_path


def _read_llm_api_key(env_file: Path) -> str:
    env_key = os.environ.get("LLM_API_KEY", "").strip()
    if env_key:
        return env_key
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LLM_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def probe_engine_health(hub_url: str, *, timeout: float = 4.0) -> dict[str, Any] | None:
    url = f"{hub_url.rstrip('/')}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data if isinstance(data, dict) else None
    except Exception:
        return None
    return None


def assert_gpu_engine_safe(health: dict[str, Any], *, expected_llm_host: str = "llm.co.dev.cirg.uw.edu") -> None:
    llm_url = str(health.get("llm_base_url") or "").strip().lower()
    if not llm_url:
        raise RuntimeError(f"wahs-engine /healthz missing llm_base_url: {health}")
    for forbidden in ("localhost", "127.0.0.1", "host.docker.internal", ":8077"):
        if forbidden in llm_url:
            raise RuntimeError(
                f"Refusing eval run against local Mac router/loopback LLM URL ({llm_url}); "
                f"expected CIRG GPU server ({expected_llm_host})."
            )
    if expected_llm_host not in llm_url:
        raise RuntimeError(
            f"Refusing eval run: expected {expected_llm_host!r} in llm_base_url, got {llm_url!r}."
        )
    if not bool(health.get("allow_local_bundle_mode")):
        raise RuntimeError(
            "wahs-engine must have WAHS_ALLOW_LOCAL_BUNDLE_MODE=true for bundle evaluation "
            f"(got {health.get('allow_local_bundle_mode')!r})."
        )


def ensure_eval_engine(
    *,
    hub_url: str,
    start_engine: bool,
    engine_dir: Path,
    env_file: Path,
    container_name: str = DEFAULT_CONTAINER_NAME,
    image_name: str = DEFAULT_IMAGE_NAME,
    port: int = 18088,
) -> dict[str, Any]:
    health = probe_engine_health(hub_url)
    if health is not None:
        try:
            assert_gpu_engine_safe(health)
            return health
        except RuntimeError:
            if not start_engine:
                raise

    if not start_engine:
        raise RuntimeError(
            f"Eval wahs-engine at {hub_url} is not reachable. Start it or pass --start-engine."
        )

    api_key = _read_llm_api_key(env_file)
    if not api_key:
        raise RuntimeError(
            f"LLM_API_KEY is required in env or {env_file} to start CIRG GPU eval engine."
        )

    img_check = subprocess.run(
        ["docker", "image", "inspect", image_name],
        capture_output=True,
        text=True,
    )
    if img_check.returncode != 0:
        if not engine_dir.is_dir():
            raise RuntimeError(f"Cannot build {image_name}: engine dir missing ({engine_dir})")
        print(f"==> building {image_name} from {engine_dir}", file=sys.stderr)
        subprocess.run(["docker", "build", "-t", image_name, str(engine_dir)], check=True)

    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, prefix="wahs-eval-env-") as tf:
        tmp_env = Path(tf.name)
        tf.write(f"LLM_API_KEY={api_key}\n")
    os.chmod(tmp_env, 0o600)
    try:
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--rm",
            "-p",
            f"127.0.0.1:{port}:8080",
            "--env-file",
            str(tmp_env),
            "-e",
            "PYTHONUNBUFFERED=1",
            "-e",
            "WAHS_ALLOW_LOCAL_BUNDLE_MODE=true",
            "-e",
            f"LLM_BASE_URL={DEFAULT_LLM_BASE_URL}",
            "-e",
            "WAHS_PROVIDER_FLAVOR=litellm",
            "-e",
            "WAHS_DEFAULT_MODEL=wahs-26b-kb",
            "-e",
            "WAHS_LLM_TIMEOUT_SECONDS=180",
            "-e",
            f"WAHS_MODEL_MAP_JSON={json.dumps(DEFAULT_MODEL_MAP, separators=(',', ':'))}",
            "-e",
            "WAHS_CONTEXT_WINDOW=32768",
            "-e",
            "WAHS_CHART_BUDGET_CEILING=16384",
            "-e",
            "WAHS_CACHE_TTL_SECONDS=1800",
            "-e",
            "WAHS_MAX_OVERLAY_BYTES=5120",
            image_name,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    finally:
        tmp_env.unlink(missing_ok=True)

    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        health = probe_engine_health(hub_url, timeout=2.0)
        if health is not None:
            assert_gpu_engine_safe(health)
            return health
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {container_name} at {hub_url}/healthz")


def verify_four_pathway_preflight(
    *,
    hub_url: str,
    bundles_dir: Path,
) -> list[dict[str, Any]]:
    marcus_path = bundles_dir / "Marcus_Vance_Oncology_Immunotherapy.json"
    if not marcus_path.is_file():
        raise RuntimeError(f"Preflight bundle missing: {marcus_path}")
    bundle = json.loads(marcus_path.read_text(encoding="utf-8"))
    checks = [
        ("note_rag", 16384),
        ("condensation_kb", 16384),
        ("dynamic_fhir_tools", 2048),
        ("chart_only", 16384),
    ]
    report: list[dict[str, Any]] = []
    for strategy, target_budget in checks:
        req = urllib.request.Request(
            f"{hub_url.rstrip('/')}/v1/wahs/context/preview",
            data=json.dumps(
                {
                    "model": "wahs-26b-kb",
                    "messages": [{"role": "user", "content": "What medicines am I taking right now?"}],
                    "wahs": {
                        "fhir_bundle": bundle,
                        "target_budget_tokens": target_budget,
                        "sharing_posture": "patient_self",
                        "retrieval_strategy": strategy,
                        "enable_kb": strategy != "chart_only",
                        "enable_overflow_tools": strategy != "chart_only",
                    },
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Preflight {strategy} returned HTTP {resp.status}")
            payload = json.loads(resp.read().decode("utf-8"))
        cond = ((payload.get("x_wahs") or {}).get("condensation")) or {}
        eff_b = int(cond.get("budget_effective") or cond.get("budget_requested") or 0)
        if strategy == "dynamic_fhir_tools" and eff_b > 2048:
            raise RuntimeError(
                f"Preflight dynamic_fhir_tools budget_effective={eff_b} exceeded 2048 cap"
            )
        report.append(
            {
                "retrieval_strategy": strategy,
                "target_budget_tokens": target_budget,
                "budget_effective": eff_b,
                "actual_tokens": int(cond.get("actual_tokens") or 0),
                "tier": cond.get("tier"),
            }
        )
    return report


def _git_sha(repo_dir: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "--short=10", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def build_target_provenance(
    *,
    engine_dir: Path,
    hub_url: str,
    rationale: str,
) -> list[dict[str, Any]]:
    return [
        {
            "target_id": "wahs-engine",
            "target_source": "supplied",
            "target_actual_sha": _git_sha(engine_dir),
            "target_url": hub_url,
            "evidence_status": "verified",
            "decision_rationale": rationale,
        },
        {
            "target_id": "clinical-ai-validation-harness",
            "target_source": "supplied",
            "target_actual_sha": _git_sha(HARNESS_ROOT),
            "evidence_status": "verified",
        },
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    p.add_argument("--bundles-dir", type=Path, default=DEFAULT_BUNDLES_DIR)
    p.add_argument("--output-dir", type=Path, default=HARNESS_ROOT / "artifacts" / "wahs")
    p.add_argument("--hub-url", default=DEFAULT_HUB_URL)
    p.add_argument("--engine-dir", type=Path, default=DEFAULT_ENGINE_DIR)
    p.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    p.add_argument("--start-engine", action="store_true")
    p.add_argument("--smoke-10", action="store_true", help="Run only the 5-scenario x 2-arm (10-cell) GPU smoke slice + 4-pathway preflight")
    p.add_argument("--cohort", choices=tuple(COHORT_PATIENTS), default="core3")
    p.add_argument("--patients", default=None, help="Comma-separated patient IDs or short slugs (e.g. maurice,julian,marcus)")
    p.add_argument("--questions", default=None, help="Comma-separated sheet question IDs (e.g. Q01,Q04,P01)")
    p.add_argument("--pathways", default="rag,kb,tools,chart", help="Comma-separated pathways from {rag,kb,tools,chart}")
    p.add_argument("--models", default="26b,12b,e4b", help="Comma-separated model aliases/IDs (default: 26b,12b,e4b)")
    p.add_argument("--budget", default=None, help="Optional chart budget override for condensed pathways (default: 16k; tools stays @2k)")
    p.add_argument("--seeds", default=None, help="Optional comma-separated seeds (e.g. 42,43,44)")
    p.add_argument("--resume", type=Path, default=None)
    p.add_argument("--judge", action="append", dest="judges", default=None, help="Optional judge spec(s) (opt-in; off by default)")
    p.add_argument("--dry-run", action="store_true", help="Print plan without launching Docker or running inference")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.smoke_10:
        selected_rows = select_cases(args.cases, case_ids=SMOKE_10_CASE_IDS)
        profiles = list(SMOKE_10_PROFILES)
        slice_tag = "smoke10"
        patients_label = "3 complex patients (5 smoke Google Sheet scenarios) · 2 flagship 26B arms"
    else:
        patients_arg = [s for s in (args.patients or "").split(",") if s.strip()] or None
        questions_arg = [s for s in (args.questions or "").split(",") if s.strip()] or None
        selected_rows = select_cases(
            args.cases,
            cohort=args.cohort,
            patients=patients_arg,
            questions=questions_arg,
        )
        profiles = build_profiles(
            pathways=[s for s in args.pathways.split(",") if s.strip()],
            models=[s for s in args.models.split(",") if s.strip()],
            budget_override=args.budget,
        )
        slice_tag = args.cohort if not patients_arg and not questions_arg else "custom"
        unique_patients = len({r.get("patient_id") for r in selected_rows})
        unique_questions = len({r.get("question_id") for r in selected_rows})
        patients_label = (
            f"{unique_patients} patients · {unique_questions} Google Sheet scenarios "
            f"({len(selected_rows)} cases) × {len(profiles)} arms"
        )

    effective_cases = write_slice_if_needed(
        selected_rows,
        source_cases_path=args.cases,
        slices_dir=args.output_dir / "slices",
        tag=slice_tag,
    )
    parsed_seeds = [int(s.strip()) for s in (args.seeds or "").split(",") if s.strip()] or None
    total_cells = len(selected_rows) * len(profiles) * (len(parsed_seeds) if parsed_seeds else 1)

    plan_summary = {
        "mode": "smoke-10" if args.smoke_10 else slice_tag,
        "cases_file": str(effective_cases),
        "cases_count": len(selected_rows),
        "profiles": profiles,
        "seeds": parsed_seeds,
        "total_cells": total_cells,
        "hub_url": args.hub_url,
        "cirg_gpu_endpoint": DEFAULT_LLM_BASE_URL,
        "bundles_dir": str(args.bundles_dir),
    }

    if args.dry_run:
        print(json.dumps(plan_summary, indent=2))
        return 0

    for k, v in CIRG_HARDWARE_ENV.items():
        os.environ[k] = v

    health = ensure_eval_engine(
        hub_url=args.hub_url,
        start_engine=args.start_engine,
        engine_dir=args.engine_dir,
        env_file=args.env_file,
    )
    preflight = verify_four_pathway_preflight(hub_url=args.hub_url, bundles_dir=args.bundles_dir)
    print(f"==> Engine verified ({health.get('llm_base_url')}), 4-pathway preflight OK:", json.dumps(preflight), file=sys.stderr)

    from harness.wahs.evaluator import WahsHubClient, build_wahs_report_packet, run_wahs_suite

    provenance = build_target_provenance(
        engine_dir=args.engine_dir,
        hub_url=args.hub_url,
        rationale=(
            "Google Sheet scenarios CIRG H200 GPU evaluation (10-cell smoke)"
            if args.smoke_10
            else "Google Sheet scenarios CIRG H200 GPU benchmark"
        ),
    )
    client = WahsHubClient(
        base_url=args.hub_url,
        timeout=240.0,
        bundle_dirs=[args.bundles_dir],
    )
    result = run_wahs_suite(
        effective_cases,
        client=client,
        output_dir=args.output_dir,
        profiles=profiles,
        seeds=parsed_seeds,
        git_sha=_git_sha(HARNESS_ROOT),
        target_provenance=provenance,
        resume_from=args.resume,
        bundle_dirs=[args.bundles_dir],
    )
    packet = build_wahs_report_packet(
        result.run_dir,
        patients_summary=patients_label,
        bundle_dirs=[args.bundles_dir],
    )

    if args.judges:
        judge_cmd = [
            sys.executable,
            "-m",
            "harness.cli",
            "wahs",
            "judge",
            str(result.run_dir),
            "--blind",
            "--bundles-dir",
            str(args.bundles_dir),
        ]
        for j in args.judges:
            judge_cmd.extend(["--judge", j])
        subprocess.run(judge_cmd, cwd=HARNESS_ROOT, check=True)
        packet = build_wahs_report_packet(
            result.run_dir,
            patients_summary=patients_label,
            bundle_dirs=[args.bundles_dir],
        )

    out = {
        "plan": plan_summary,
        "preflight": preflight,
        "run_dir": str(result.run_dir),
        "summary": result.summary,
        "report_files": {
            "report_data": str(result.run_dir / "report-data.json"),
            "dashboard_data": str(result.run_dir / "dashboard-data.json"),
            "run_summary": str(result.run_dir / "run-summary.json"),
        },
        "packet_run_id": packet.get("run_id"),
        "full_run_command": (
            f"uv --directory {HARNESS_ROOT} run python scripts/run-wahs-gpu-sheet-eval.py "
            f"--cohort core3 --pathways rag,kb,tools,chart --models 26b,12b,e4b "
            f"--start-engine --bundles-dir {args.bundles_dir}"
        ),
    }
    print(json.dumps(out, indent=2))
    return 0 if result.passed_cells == result.total_cells else 1


if __name__ == "__main__":
    raise SystemExit(main())
