#!/usr/bin/env python3
"""Run and package CIRG H200 GPU WAHS+ evaluations over Google Sheet scenarios.

Benchmarks declarative `wahs-engine` profiles (`configs/wahs/profiles.yaml`:
`baseline`, `temporal`, `terminology`, `temporal-terminology`, `rag-overflow`,
`core-enriched`, `full-enriched`, ad-hoc `wahs+<enricher>`, and `raw-fhir`)
against the frozen WAHS+ Google Sheet scenarios
(`datasets/wahs_demo_patients_25x10_testset.jsonl`) using a dedicated local
`wahs-engine` container backed by the UW CIRG H200 GPU cluster
(`https://llm.co.dev.cirg.uw.edu/v1`) and NEVER local Mac `:8077`.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.request

HARNESS_ROOT = Path(__file__).resolve().parents[1]
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from harness.wahs.evaluator import (  # noqa: E402
    load_wahs_profiles_config,
    parse_wahs_profile_spec,
)

DEFAULT_CASES_PATH = HARNESS_ROOT / "datasets" / "wahs_demo_patients_25x10_testset.jsonl"
DEFAULT_BUNDLES_DIR = Path("/Users/pmanko/code/hq/wahs/bundles")
DEFAULT_ENGINE_DIR = Path("/Users/pmanko/code/wahs-engine")
DEFAULT_ENV_FILE = Path("/Users/pmanko/code/hq/wahs/.env")
DEFAULT_HUB_URL = "http://127.0.0.1:18088"
DEFAULT_LLM_BASE_URL = "https://llm.co.dev.cirg.uw.edu/v1"
DEFAULT_CONTAINER_NAME = "wahs-engine-eval"
DEFAULT_IMAGE_NAME = "wahs-engine:modular-eval"

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

SMOKE_CASE_IDS: tuple[str, ...] = (
    "wahs_sheet_q01__maurice_auer",
    "wahs_sheet_q03__margaret_chen",
    "wahs_sheet_q10__marcus_vance",
    "wahs_sheet_q12__maurice_auer",
)

SMOKE_MODULAR_PROFILES: tuple[str, ...] = (
    "wahs:baseline:ollama/gemma4:26b@32k",
    "wahs:core-enriched:ollama/gemma4:26b@32k",
    "wahs:full-enriched:ollama/gemma4:26b@32k",
)

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
    "wahs-26b": "ollama/gemma4:26b",
    "wahs-12b": "ollama/gemma4:12b",
    "wahs-e4b": "ollama/gemma4:e4b",
    "gemma-4-e4b": "ollama/gemma4:e4b",
    "gemma4:26b": "ollama/gemma4:26b",
    "gemma4:12b": "ollama/gemma4:12b",
    "gemma4:e4b": "ollama/gemma4:e4b",
    "ollama/gemma4:26b": "ollama/gemma4:26b",
    "ollama/gemma4:12b": "ollama/gemma4:12b",
    "ollama/gemma4:e4b": "ollama/gemma4:e4b",
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


def _resolve_pathway_prefix(
    pathway: str,
    *,
    configured_profiles: dict[str, dict[str, Any]],
    prompt_override: str | None = None,
) -> tuple[str, str]:
    """Return `(arm_prefix, default_budget)` for a pathway / profile name."""
    raw = str(pathway or "").strip()
    low = raw.lower()
    prompt_suffix = f"[prompt={prompt_override}]" if prompt_override else ""
    if low in {"direct", "raw-fhir"}:
        return "raw-fhir", "auto"
    if low == "engine":
        return f"wahs:baseline{prompt_suffix}", "auto"
    if low.startswith("wahs+"):
        base_lhs = raw[:-len(raw[raw.index("["):])] if "[" in raw else raw
        suffix = "" if "[" in raw else prompt_suffix
        return f"{base_lhs}{suffix}", "32k"
    prof_lookup = {k.lower(): k for k in configured_profiles}
    if low in prof_lookup:
        canon = prof_lookup[low]
        default_b = "auto" if canon == "baseline" else "32k"
        return f"wahs:{canon}{prompt_suffix}", default_b
    raise ValueError(
        f"Unknown WAHS pathway/profile {pathway!r}; expected one of "
        f"{('engine', 'direct', 'raw-fhir', *sorted(configured_profiles))} or 'wahs+<enricher>'"
    )


def build_profiles(
    *,
    pathways: Sequence[str],
    models: Sequence[str],
    budget_override: str | None = None,
    prompt_override: str | None = None,
    profiles_config_path: Path | str | None = None,
) -> list[str]:
    cfg = load_wahs_profiles_config(profiles_config_path)
    configured_profiles = cfg["profiles"]
    out: list[str] = []
    seen: set[str] = set()
    override_budgets = (
        [b.strip() for b in str(budget_override).split(",") if b.strip()]
        if budget_override
        else []
    )
    clean_prompt = str(prompt_override or "").strip() or None

    # Allow full profile specs (e.g. `wahs:baseline:ollama/gemma4:26b@32k`) directly in `pathways`.
    expanded_pathways: list[str] = []
    for p_raw in pathways:
        p_clean = str(p_raw or "").strip()
        if not p_clean:
            continue
        if ":" in p_clean and p_clean.lower().startswith(("wahs:", "wahs+", "wahs-engine-baseline:", "raw-fhir:")):
            parse_wahs_profile_spec(
                p_clean,
                config_path=profiles_config_path,
                default_prompt=clean_prompt,
                strict=True,
            )
            if p_clean not in seen:
                seen.add(p_clean)
                out.append(p_clean)
        else:
            expanded_pathways.append(p_clean)

    if not expanded_pathways:
        return out

    for m_raw in models:
        m_clean = str(m_raw or "").strip()
        if not m_clean:
            continue
        model_id = MODEL_ALIASES.get(m_clean.lower(), m_clean)
        for p_raw in expanded_pathways:
            prefix, default_budget = _resolve_pathway_prefix(
                p_raw,
                configured_profiles=configured_profiles,
                prompt_override=clean_prompt,
            )
            is_raw = prefix == "raw-fhir"
            if is_raw and len(override_budgets) > 1:
                budgets_for_arm = [default_budget]
            else:
                budgets_for_arm = override_budgets or [default_budget]
            for budget in budgets_for_arm:
                arm = (
                    f"{prefix}:{model_id}"
                    if str(budget).lower() == "auto"
                    else f"{prefix}:{model_id}@{budget}"
                )
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


def probe_engine_profiles(hub_url: str, *, timeout: float = 4.0) -> dict[str, Any] | None:
    """Query `GET /v1/wahs/profiles` when supported by `wahs-engine`."""
    url = f"{hub_url.rstrip('/')}/v1/wahs/profiles"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"wahs-engine /v1/wahs/profiles failed with HTTP {exc.code}") from exc
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
    context_window: int = 32768,
    llm_timeout_seconds: int = 300,
) -> dict[str, Any]:
    health = probe_engine_health(hub_url)
    if health is not None and not start_engine:
        assert_gpu_engine_safe(health)
        return health

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
            "WAHS_DEFAULT_MODEL=wahs-26b",
            "-e",
            "WAHS_ENABLED_ENRICHERS=",
            "-e",
            f"WAHS_LLM_TIMEOUT_SECONDS={int(llm_timeout_seconds)}",
            "-e",
            f"WAHS_MODEL_MAP_JSON={json.dumps(DEFAULT_MODEL_MAP, separators=(',', ':'))}",
            "-e",
            f"WAHS_CONTEXT_WINDOW={int(context_window)}",
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


def verify_modular_preflight(
    *,
    hub_url: str,
    bundles_dir: Path,
    requested_profiles: Sequence[str],
    llm_base_url: str = DEFAULT_LLM_BASE_URL,
    api_key: str = "",
    prompt_override: str | None = None,
    profiles_config_path: Path | str | None = None,
    default_budget: int = 32768,
) -> list[dict[str, Any]]:
    """Verify `/v1/wahs/profiles` (when available), `/v1/wahs/context/preview` for each requested
    WAHS profile configuration, and `/models` for `raw-fhir` direct LLM baselines.
    """
    parsed_list = [
        parse_wahs_profile_spec(
            p,
            default_budget,
            config_path=profiles_config_path,
            default_prompt=prompt_override,
            strict=True,
        )
        for p in requested_profiles
    ]
    engine_specs = [p for p in parsed_list if p.kind == "wahs"]
    has_raw_fhir = any(p.kind == "raw-fhir" for p in parsed_list)
    report: list[dict[str, Any]] = []

    if engine_specs:
        marcus_path = bundles_dir / "Marcus_Vance_Oncology_Immunotherapy.json"
        if not marcus_path.is_file():
            raise RuntimeError(f"Preflight bundle missing: {marcus_path}")
        bundle = json.loads(marcus_path.read_text(encoding="utf-8"))

        adv_profiles = probe_engine_profiles(hub_url)
        if adv_profiles is not None:
            prof_entries = adv_profiles.get("profiles")
            adv_names = (
                sorted(prof_entries.keys())
                if isinstance(prof_entries, dict)
                else [str(x.get("id") or x) for x in (prof_entries or []) if isinstance(x, (dict, str))]
            )
            report.append(
                {
                    "mode": "engine_profiles_catalog",
                    "default_profile": adv_profiles.get("default_profile"),
                    "available_profiles": adv_names,
                }
            )

        seen_preview_keys: set[tuple[Any, ...]] = set()
        for spec in engine_specs:
            pkey = (
                spec.wahs_profile,
                spec.engine_profile,
                tuple(spec.explicit_enrichers or ()),
                spec.prompt_override or "",
                spec.budget_tokens if spec.explicit_budget else "auto",
            )
            if pkey in seen_preview_keys:
                continue
            seen_preview_keys.add(pkey)

            wahs_opts: dict[str, Any] = {
                "fhir_bundle": bundle,
                "profile": spec.engine_profile,
                **({"prompt": spec.prompt_override} if spec.prompt_override else {}),
                **({"enrichers": spec.explicit_enrichers} if spec.explicit_enrichers is not None else {}),
                **({"target_budget_tokens": int(spec.budget_tokens)} if spec.explicit_budget else {}),
            }
            req = urllib.request.Request(
                f"{hub_url.rstrip('/')}/v1/wahs/context/preview",
                data=json.dumps(
                    {
                        "model": spec.model_id,
                        "messages": [{"role": "user", "content": "What medicines am I taking right now?"}],
                        "wahs": wahs_opts,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Preflight {spec.wahs_profile} returned HTTP {resp.status}")
                payload = json.loads(resp.read().decode("utf-8"))
            x_wahs = payload.get("x_wahs") if isinstance(payload.get("x_wahs"), dict) else {}
            cond = x_wahs.get("condensation") if isinstance(x_wahs.get("condensation"), dict) else {}
            actual_tok = int(cond.get("actual_tokens") or 0)
            if actual_tok <= 0:
                raise RuntimeError(
                    f"Preflight {spec.wahs_profile} returned invalid actual_tokens={actual_tok}"
                )
            if spec.explicit_budget and actual_tok > int(spec.budget_tokens):
                raise RuntimeError(
                    f"Preflight {spec.wahs_profile} actual_tokens={actual_tok} exceeded budget={spec.budget_tokens}"
                )
            report.append(
                {
                    "mode": "wahs_preview",
                    "wahs_profile": spec.wahs_profile,
                    "engine_profile": spec.engine_profile,
                    "prompt_id": cond.get("prompt_id") or spec.prompt_override,
                    "prompt_sha256": cond.get("prompt_sha256"),
                    "budget_effective": int(cond.get("budget_effective") or 0),
                    "actual_tokens": actual_tok,
                    "tier": cond.get("tier"),
                    "enrichers_count": len(x_wahs.get("enrichers") or []),
                }
            )

    if has_raw_fhir and api_key:
        m_req = urllib.request.Request(
            f"{llm_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(m_req, timeout=20) as m_resp:
            if m_resp.status != 200:
                raise RuntimeError(f"Preflight direct LLM returned HTTP {m_resp.status}")
            m_payload = json.loads(m_resp.read().decode("utf-8"))
        report.append(
            {
                "mode": "direct_llm",
                "models_count": len(m_payload.get("data") or []),
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
    p.add_argument(
        "--smoke",
        "--smoke-12",
        dest="smoke",
        action="store_true",
        help="Run the 4-scenario x 3-arm (12-cell) modular GPU smoke gate + preflight",
    )
    p.add_argument("--cohort", choices=tuple(COHORT_PATIENTS), default="core3")
    p.add_argument("--patients", default=None, help="Comma-separated patient IDs or short slugs (e.g. maurice,julian,marcus,margaret)")
    p.add_argument("--questions", default=None, help="Comma-separated sheet question IDs (e.g. Q01,Q03,Q10,Q12)")
    p.add_argument(
        "--pathways",
        default="baseline,raw-fhir",
        help="Comma-separated profile names from configs/wahs/profiles.yaml (baseline/engine, temporal, terminology, temporal-terminology, rag-overflow, core-enriched, full-enriched, direct/raw-fhir, or wahs+<enricher>)",
    )
    p.add_argument(
        "--profiles",
        default=None,
        help="Optional comma-separated profile names or full profile specs overriding --pathways",
    )
    p.add_argument("--models", default="26b,12b,e4b", help="Comma-separated model aliases/IDs (default: 26b,12b,e4b)")
    p.add_argument("--budget", default=None, help="Optional chart budget override or comma-separated sweep (e.g. 32k or auto,64k,32k,16k)")
    p.add_argument("--prompt", default=None, help="Optional prompt template ID override")
    p.add_argument("--profiles-config", type=Path, default=None, help="Optional path to custom profiles.yaml")
    p.add_argument("--context-window", type=int, default=32768, help="Model context window tokens for both wahs-engine and raw-fhir (e.g. 32768 or 131072)")
    p.add_argument("--seeds", default=None, help="Optional comma-separated seeds (e.g. 42,43,44)")
    p.add_argument("--resume", type=Path, default=None)
    p.add_argument("--judge", action="append", dest="judges", default=None, help="Optional judge spec(s) (opt-in; off by default)")
    p.add_argument("--dry-run", action="store_true", help="Print plan without launching Docker or running inference")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.smoke:
        selected_rows = select_cases(args.cases, case_ids=SMOKE_CASE_IDS)
        if args.prompt:
            profiles = build_profiles(
                pathways=["baseline", "core-enriched", "full-enriched"],
                models=["26b"],
                budget_override="32k",
                prompt_override=args.prompt,
                profiles_config_path=args.profiles_config,
            )
        else:
            profiles = list(SMOKE_MODULAR_PROFILES)
        slice_tag = "smoke12"
        patients_label = "3 complex patients (4 smoke Google Sheet scenarios) · 3 modular 26B@32k arms"
    else:
        patients_arg = [s for s in (args.patients or "").split(",") if s.strip()] or None
        questions_arg = [s for s in (args.questions or "").split(",") if s.strip()] or None
        selected_rows = select_cases(
            args.cases,
            cohort=args.cohort,
            patients=patients_arg,
            questions=questions_arg,
        )
        raw_pathway_str = args.profiles if args.profiles else args.pathways
        profiles = build_profiles(
            pathways=[s for s in raw_pathway_str.split(",") if s.strip()],
            models=[s for s in args.models.split(",") if s.strip()],
            budget_override=args.budget,
            prompt_override=args.prompt,
            profiles_config_path=args.profiles_config,
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
        "mode": "smoke-12" if args.smoke else slice_tag,
        "cases_file": str(effective_cases),
        "cases_count": len(selected_rows),
        "profiles": profiles,
        "prompt_override": args.prompt,
        "context_window": int(args.context_window),
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

    need_engine = any(not p.lower().startswith("raw-fhir:") for p in profiles)
    api_key = _read_llm_api_key(args.env_file)
    llm_timeout_s = 300

    if need_engine or args.start_engine:
        health = ensure_eval_engine(
            hub_url=args.hub_url,
            start_engine=args.start_engine,
            engine_dir=args.engine_dir,
            env_file=args.env_file,
            context_window=int(args.context_window),
            llm_timeout_seconds=llm_timeout_s,
        )
    else:
        health = {"llm_base_url": DEFAULT_LLM_BASE_URL}

    preflight = verify_modular_preflight(
        hub_url=args.hub_url,
        bundles_dir=args.bundles_dir,
        requested_profiles=profiles,
        llm_base_url=DEFAULT_LLM_BASE_URL,
        api_key=api_key,
        prompt_override=args.prompt,
        profiles_config_path=args.profiles_config,
        default_budget=int(args.context_window),
    )
    print(
        f"==> Modular preflight OK ({health.get('llm_base_url')}):",
        json.dumps(preflight),
        file=sys.stderr,
    )

    from harness.wahs.evaluator import WahsHubClient, build_wahs_report_packet, run_wahs_suite

    provenance = build_target_provenance(
        engine_dir=args.engine_dir,
        hub_url=args.hub_url,
        rationale=(
            "Google Sheet scenarios CIRG H200 GPU evaluation (12-cell modular smoke)"
            if args.smoke
            else "Google Sheet scenarios CIRG H200 GPU modular benchmark"
        ),
    )
    client = WahsHubClient(
        base_url=args.hub_url,
        direct_llm_base_url=DEFAULT_LLM_BASE_URL,
        direct_llm_api_key=api_key or None,
        direct_provider_flavor="litellm",
        direct_context_window=int(args.context_window),
        timeout=float(llm_timeout_s),
        bundle_dirs=[args.bundles_dir],
        profiles_config_path=args.profiles_config,
        prompt_override=args.prompt,
    )
    suite_budgets = [int(args.context_window)]
    result = run_wahs_suite(
        effective_cases,
        client=client,
        output_dir=args.output_dir,
        budgets=suite_budgets,
        profiles=profiles,
        seeds=parsed_seeds,
        git_sha=_git_sha(HARNESS_ROOT),
        target_provenance=provenance,
        resume_from=args.resume,
        bundle_dirs=[args.bundles_dir],
        profiles_config_path=args.profiles_config,
        prompt_override=args.prompt,
    )
    packet = build_wahs_report_packet(
        result.run_dir,
        patients_summary=patients_label,
        bundle_dirs=[args.bundles_dir],
        profiles_config_path=args.profiles_config,
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
        if args.profiles_config:
            judge_cmd.extend(["--profiles-config", str(args.profiles_config)])
        for j in args.judges:
            judge_cmd.extend(["--judge", j])
        subprocess.run(judge_cmd, cwd=HARNESS_ROOT, check=True)
        packet = build_wahs_report_packet(
            result.run_dir,
            patients_summary=patients_label,
            bundle_dirs=[args.bundles_dir],
            profiles_config_path=args.profiles_config,
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
            f"--cohort core3 --pathways baseline,core-enriched,full-enriched --budget 32k "
            f"--models 26b,12b,e4b --start-engine --bundles-dir {args.bundles_dir}"
        ),
    }
    print(json.dumps(out, indent=2))
    return 0 if result.passed_cells == result.total_cells else 1


if __name__ == "__main__":
    raise SystemExit(main())
