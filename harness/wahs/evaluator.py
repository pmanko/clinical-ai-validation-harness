"""Evaluation runner and mechanical scorer for standalone `wahs-engine` and `raw-fhir` benchmarks.

Executes declarative WAHS profile suites (`wahs:<profile>:<model>[@<budget>]`,
`wahs+<enricher>[+<enricher>...]:<model>[@<budget>]`, backwards-compatible
`wahs-engine-baseline:<model>[@<budget>]`, and `raw-fhir:<model>[@<budget>]`)
against a caller-supplied endpoint, freezes all artifacts (`inputs/cases.jsonl`, lossless
Stage-A chart snapshots, blinded judge scenarios, `results.jsonl`, `domain_guardrails.json`,
and OpenClinAI v2 report packets), and applies strictly mechanical checks (token-budget
compliance and inline `[N]` / `[K1]..[KM]` citation resolution against trusted evidence).
Clinical accuracy, completeness, grounding, abstention, and privacy are evaluated by blind
multi-judge panels via `harness.validate.judge_runner`.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import inspect
import json
import math
import os
from pathlib import Path
import random
import re
import threading
import time
from typing import Any
from uuid import uuid4

import requests
import yaml

from ..metadata import RunManifest, append_event, copy_target_provenance

_CITATION_RE = re.compile(r"\[((?:K)?\d+)\]", re.IGNORECASE)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_CITE_TOKEN_PAT = r"(?:K)?\d+"
_MULTI_BRACKET_RE = re.compile(
    rf"\[({_CITE_TOKEN_PAT}(?:\s*(?:,|;|/|-|\band\b)\s*{_CITE_TOKEN_PAT})+)\]",
    re.IGNORECASE,
)
_LOWER_K_CITE_RE = re.compile(r"\[k(\d+)\]")
_SAFE_PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_PROFILE_SEG_RE = re.compile(r"^([A-Za-z0-9._-]+)(?:\[prompt=([A-Za-z0-9._-]+)\])?$")
_ADHOC_LHS_RE = re.compile(
    r"^wahs\+([A-Za-z0-9._+-]+)(?:\[prompt=([A-Za-z0-9._-]+)\])?$",
    re.IGNORECASE,
)
_BASELINE_ALIAS_RE = re.compile(
    r"^wahs-engine-baseline(?:\[prompt=([A-Za-z0-9._-]+)\])?:(.*)$",
    re.IGNORECASE,
)
_RAW_FHIR_RE = re.compile(
    r"^raw-fhir(?:\[prompt=([A-Za-z0-9._-]+)\])?:(.*)$",
    re.IGNORECASE,
)
_WAHS_CASE_Q_RE = re.compile(r"^(?:wahs_sheet_)?([qp]\d{2})(?:__|$)", re.IGNORECASE)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAHS_PROFILES_PATH = _REPO_ROOT / "configs" / "wahs" / "profiles.yaml"
DEFAULT_WAHS_PROMPTS_DIR = _REPO_ROOT / "configs" / "wahs" / "prompts"
DEFAULT_TOKEN_BUDGETS = (8192, 4096, 2048, 1024, 512)
MAX_TOKEN_BUDGET = 262144


def load_wahs_profiles_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load declarative WAHS harness profiles and scenario categories from YAML."""
    raw_override = str(config_path or os.environ.get("WAHS_HARNESS_PROFILES_PATH") or "").strip()
    resolved_path = Path(raw_override).expanduser() if raw_override else DEFAULT_WAHS_PROFILES_PATH
    if not resolved_path.is_file():
        raise FileNotFoundError(f"WAHS profiles config not found: {resolved_path}")
    loaded = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid WAHS profiles YAML in {resolved_path}: expected mapping")
    raw_profiles = loaded.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError(f"Invalid WAHS profiles YAML in {resolved_path}: missing non-empty 'profiles'")
    profiles: dict[str, dict[str, Any]] = {}
    for k, v in raw_profiles.items():
        if isinstance(v, dict) and str(k).strip():
            profiles[str(k).strip()] = dict(v)
    raw_cats = loaded.get("scenario_categories")
    scenario_categories = (
        {
            str(k).strip().lower(): str(v).strip()
            for k, v in raw_cats.items()
            if str(k).strip() and str(v).strip()
        }
        if isinstance(raw_cats, dict)
        else {}
    )
    return {
        "config_path": resolved_path,
        "default_profile": str(loaded.get("default_profile") or "baseline").strip(),
        "raw_fhir_prompt": str(loaded.get("raw_fhir_prompt") or "raw-fhir-default").strip(),
        "profiles": profiles,
        "scenario_categories": scenario_categories,
    }


def _candidate_prompt_dirs(
    prompts_dir: Path | str | None = None,
    config_path: Path | str | None = None,
) -> list[Path]:
    dirs: list[Path] = []
    for raw in (prompts_dir, os.environ.get("WAHS_HARNESS_PROMPTS_DIR")):
        clean = str(raw or "").strip()
        if clean:
            cand = Path(clean).expanduser()
            if cand not in dirs:
                dirs.append(cand)
    if config_path:
        sibling = Path(config_path).expanduser().parent / "prompts"
        if sibling.is_dir() and sibling not in dirs:
            dirs.append(sibling)
    env_cfg = os.environ.get("WAHS_HARNESS_PROFILES_PATH", "").strip()
    if env_cfg:
        env_sibling = Path(env_cfg).expanduser().parent / "prompts"
        if env_sibling.is_dir() and env_sibling not in dirs:
            dirs.append(env_sibling)
    if DEFAULT_WAHS_PROMPTS_DIR not in dirs:
        dirs.append(DEFAULT_WAHS_PROMPTS_DIR)
    return dirs


def load_raw_fhir_prompt_template(
    prompt_id: str | None = None,
    *,
    prompts_dir: Path | str | None = None,
    config_path: Path | str | None = None,
    fallback_to_default: bool = False,
) -> tuple[str, str, str]:
    """Load `<prompt_id>.txt` for `raw-fhir` evaluation and return `(prompt_id, template, sha256)`."""
    cfg = load_wahs_profiles_config(config_path)
    default_id = cfg["raw_fhir_prompt"]
    requested_id = str(prompt_id or default_id).strip()
    if requested_id in {".", ".."} or not _SAFE_PROMPT_ID_RE.fullmatch(requested_id):
        raise ValueError(f"Invalid WAHS prompt ID: {requested_id!r}")
    search_dirs = _candidate_prompt_dirs(prompts_dir=prompts_dir, config_path=cfg["config_path"])
    for d in search_dirs:
        cand = d / f"{requested_id}.txt"
        if cand.is_file():
            raw_bytes = cand.read_bytes()
            return requested_id, raw_bytes.decode("utf-8"), hashlib.sha256(raw_bytes).hexdigest()
    if fallback_to_default and requested_id != default_id:
        for d in search_dirs:
            cand = d / f"{default_id}.txt"
            if cand.is_file():
                raw_bytes = cand.read_bytes()
                return default_id, raw_bytes.decode("utf-8"), hashlib.sha256(raw_bytes).hexdigest()
    raise FileNotFoundError(
        f"Prompt template {requested_id + '.txt'!r} not found in {[str(d) for d in search_dirs]}"
    )


def render_raw_fhir_prompt(
    template: str,
    *,
    header_line: str,
    raw_fhir_slice: str,
    question: str,
) -> str:
    """Substitute `{header_line}`, `{raw_fhir_slice}`, and `{question}` in a single pass."""
    replacements = {
        "header_line": header_line,
        "raw_fhir_slice": raw_fhir_slice,
        "question": question,
    }
    return re.sub(
        r"\{(header_line|raw_fhir_slice|question)\}",
        lambda m: replacements[m.group(1)],
        template,
    ).strip()


def wilson_ci_95(successes: int, total: int, z: float = 1.959964) -> dict[str, Any]:
    """Compute exact 95% Wilson score confidence interval for a binomial proportion."""
    n = int(total)
    k = max(0, min(int(successes), n))
    if n <= 0:
        return {"rate": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "successes": 0, "n": 0}
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return {
        "rate": round(p, 4),
        "ci95_low": round(max(0.0, center - half), 4),
        "ci95_high": round(min(1.0, center + half), 4),
        "successes": k,
        "n": n,
    }


def bootstrap_mean_ci_95(
    values: list[float],
    *,
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute deterministic percentile bootstrap 95% CI and SD for a continuous metric."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "sd": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}
    mean_val = sum(values) / n
    if n == 1:
        v = round(float(values[0]), 4)
        return {"mean": v, "sd": 0.0, "ci95_low": v, "ci95_high": v, "n": 1}
    variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
    sd_val = math.sqrt(max(0.0, variance))
    rng = random.Random(seed)
    boot_means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(max(100, n_boot))
    )
    lo_idx = max(0, min(len(boot_means) - 1, int(0.025 * len(boot_means))))
    hi_idx = max(0, min(len(boot_means) - 1, int(0.975 * len(boot_means))))
    return {
        "mean": round(mean_val, 4),
        "sd": round(sd_val, 4),
        "ci95_low": round(boot_means[lo_idx], 4),
        "ci95_high": round(boot_means[hi_idx], 4),
        "n": n,
    }


def latency_percentiles(values: list[float]) -> dict[str, Any]:
    """Compute p50, p95, mean, min, max over non-negative latency samples (ms)."""
    clean = sorted(float(v) for v in values if v is not None and float(v) >= 0.0)
    n = len(clean)
    if n == 0:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "n": 0}

    def _pct(p: float) -> float:
        pos = (n - 1) * p
        lo = int(math.floor(pos))
        hi = min(n - 1, lo + 1)
        frac = pos - lo
        return clean[lo] * (1.0 - frac) + clean[hi] * frac

    return {
        "mean_ms": round(sum(clean) / n, 2),
        "p50_ms": round(_pct(0.50), 2),
        "p95_ms": round(_pct(0.95), 2),
        "min_ms": round(clean[0], 2),
        "max_ms": round(clean[-1], 2),
        "n": n,
    }


@dataclass(frozen=True)
class WahsEvalCase:
    case_id: str
    patient_id: str
    use_case: str
    prompt: str
    target_token_budgets: list[int] = field(default_factory=lambda: list(DEFAULT_TOKEN_BUDGETS))
    valid_uuids: list[str] = field(default_factory=list)
    must_abstain: bool = False
    question_horizon: str = "current_active_state"
    patient_category: str = "medication_reconciliation"
    question_id: str = ""
    category: str = ""
    patient_label: str = ""
    what_it_tests: str = ""
    expected_answer: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WahsEvalCase":
        case_id = data.get("case_id")
        patient_id = data.get("patient_id")
        if not patient_id and data.get("patient_bundle"):
            patient_id = Path(str(data["patient_bundle"])).stem
        use_case = data.get("use_case")
        prompt = data.get("prompt") or data.get("question")
        if not case_id or not patient_id or not use_case or not prompt:
            raise ValueError(
                "WAHS eval case requires case_id, patient_id/patient_bundle, use_case, and prompt/question"
            )
        budgets = [int(b) for b in (data.get("target_token_budgets") or DEFAULT_TOKEN_BUDGETS)]
        seen_uuids: set[str] = set()
        valid_uuids: list[str] = []
        for key in (
            "valid_uuids",
            "chart_uuids",
            "expected_target_uuids",
            "expected_resource_uuids",
            "expected_uuids",
        ):
            for raw_u in data.get(key) or ():
                clean_u = str(raw_u).strip()
                if clean_u and clean_u not in seen_uuids:
                    seen_uuids.add(clean_u)
                    valid_uuids.append(clean_u)
        must_abstain = (
            bool(data.get("must_abstain", False))
            or bool(data.get("expect_abstention", False))
            or data.get("expected_answer_type") == "abstain_not_in_chart"
            or str(use_case).endswith("abstention")
        )
        smeta = (
            data.get("spreadsheet_meta")
            if isinstance(data.get("spreadsheet_meta"), dict)
            else {}
        )
        return cls(
            case_id=str(case_id),
            patient_id=str(patient_id),
            use_case=str(use_case),
            prompt=str(prompt),
            target_token_budgets=budgets,
            valid_uuids=valid_uuids,
            must_abstain=must_abstain,
            question_horizon=str(data.get("question_horizon") or "current_active_state"),
            patient_category=str(data.get("patient_category") or "medication_reconciliation"),
            question_id=str(data.get("question_id") or smeta.get("question_id") or ""),
            category=str(data.get("category") or smeta.get("category") or ""),
            patient_label=str(data.get("patient_label") or smeta.get("patient_label") or ""),
            what_it_tests=str(data.get("what_it_tests") or smeta.get("what_it_tests") or ""),
            expected_answer=str(data.get("expected_answer") or smeta.get("expected_answer") or ""),
        )


def load_wahs_cases(path: Path | str) -> list[WahsEvalCase]:
    p = Path(path)
    cases: list[WahsEvalCase] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(WahsEvalCase.from_dict(json.loads(line)))
    if not cases:
        raise ValueError(f"No WAHS evaluation cases found in {p}")
    return cases


@dataclass(frozen=True)
class WahsCaseScore:
    case_id: str
    patient_id: str
    use_case: str
    budget_tokens: int
    actual_tokens: int
    token_budget_ok: bool
    citation_count: int
    resolved_citation_count: int
    fabricated_citation_count: int
    unresolved_citations: list[str]
    citation_resolution_rate: float
    question_horizon: str
    patient_category: str
    passed: bool
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "patient_id": self.patient_id,
            "use_case": self.use_case,
            "budget_tokens": self.budget_tokens,
            "actual_tokens": self.actual_tokens,
            "token_budget_ok": self.token_budget_ok,
            "citation_count": self.citation_count,
            "resolved_citation_count": self.resolved_citation_count,
            "fabricated_citation_count": self.fabricated_citation_count,
            "unresolved_citations": list(self.unresolved_citations),
            "citation_resolution_rate": round(self.citation_resolution_rate, 4),
            "question_horizon": self.question_horizon,
            "patient_category": self.patient_category,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def _normalize_cite_key(raw_key: Any) -> str:
    return str(raw_key or "").strip("[] ").upper()


def _extract_known_uuids(
    envelope: dict[str, Any],
) -> tuple[set[str], dict[str, str], dict[str, set[str]]]:
    """Return `(all_uuid_set, index_to_primary_id_map, index_to_all_ids_map)` from a WAHS response envelope."""
    uuids: set[str] = set()
    idx_map: dict[str, str] = {}
    idx_all_uuids: dict[str, set[str]] = {}

    for u in envelope.get("retained_uuids") or []:
        if isinstance(u, str) and u:
            uuids.add(u.replace("urn:uuid:", ""))

    x_wahs = envelope.get("x_wahs") if isinstance(envelope.get("x_wahs"), dict) else {}
    for cmap in (envelope.get("citation_map"), x_wahs.get("citation_map")):
        if not isinstance(cmap, dict):
            continue
        for k, v in cmap.items():
            key_num = _normalize_cite_key(k)
            if not key_num:
                continue
            if isinstance(v, str) and v:
                clean = v.replace("urn:uuid:", "")
                uuids.add(clean)
                idx_map[key_num] = clean
                idx_all_uuids.setdefault(key_num, set()).add(clean)
            elif isinstance(v, dict):
                raw_u = str(
                    v.get("resourceUuid")
                    or v.get("resource_uuid")
                    or v.get("uuid")
                    or v.get("id")
                    or ""
                )
                bucket = idx_all_uuids.setdefault(key_num, set())
                if raw_u:
                    clean = raw_u.replace("urn:uuid:", "")
                    uuids.add(clean)
                    idx_map[key_num] = clean
                    bucket.add(clean)
                for mu in (
                    v.get("member_uuids")
                    or v.get("memberUuids")
                    or v.get("memberIds")
                    or []
                ):
                    if isinstance(mu, str) and mu:
                        clean_m = mu.replace("urn:uuid:", "")
                        uuids.add(clean_m)
                        bucket.add(clean_m)

    cond = envelope.get("condensation") if isinstance(envelope.get("condensation"), dict) else {}
    ref_lists: list[tuple[str, Any]] = [
        ("mappings", envelope.get("mappings")),
        ("mappings", cond.get("mappings")),
        ("references", envelope.get("references")),
        ("citations", envelope.get("citations")),
    ]
    for ref_key, refs in ref_lists:
        if not isinstance(refs, list):
            continue
        for idx, ref in enumerate(refs, start=1):
            if not isinstance(ref, dict):
                continue
            raw_u = str(
                ref.get("resourceUuid")
                or ref.get("resource_uuid")
                or ref.get("uuid")
                or ref.get("id")
                or ""
            )
            raw_idx = ref.get("index")
            if raw_idx is not None:
                c_idx: str | None = _normalize_cite_key(raw_idx)
            elif ref_key == "mappings":
                c_idx = None
            else:
                c_idx = str(idx)
            bucket = idx_all_uuids.setdefault(c_idx, set()) if c_idx else None
            if raw_u:
                clean = raw_u.replace("urn:uuid:", "")
                uuids.add(clean)
                if c_idx is not None and bucket is not None:
                    idx_map[c_idx] = clean
                    bucket.add(clean)
            for mu in (
                ref.get("member_uuids")
                or ref.get("memberUuids")
                or ref.get("memberIds")
                or []
            ):
                if isinstance(mu, str) and mu:
                    clean_m = mu.replace("urn:uuid:", "")
                    uuids.add(clean_m)
                    if bucket is not None:
                        bucket.add(clean_m)

    for c_idx in list(idx_all_uuids.keys()):
        idx_all_uuids[c_idx] = idx_all_uuids[c_idx] & uuids

    return uuids, idx_map, idx_all_uuids


def _extract_trusted_uuids(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    valid_uuids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> set[str]:
    """Collect trusted record UUIDs from caller/case/chart expectations, condensation mappings,
    or engine `x_wahs.citation_map` `KnowledgeReference` (`[K1]..[KM]`) entries.

    Never trusts self-declared model `references`, `citations`, `valid_uuids`, or `retained_uuids`
    from the response alone.
    """
    trusted: set[str] = set()
    for source in (valid_uuids or (), case.valid_uuids):
        for u in source:
            if isinstance(u, str) and u.strip():
                trusted.add(u.strip().replace("urn:uuid:", ""))

    mappings = (
        envelope.get("mappings")
        or (envelope.get("condensation") or {}).get("mappings")
        or []
    )
    if isinstance(mappings, list):
        for m in mappings:
            if not isinstance(m, dict):
                continue
            ru = str(
                m.get("resourceUuid")
                or m.get("resource_uuid")
                or m.get("uuid")
                or m.get("id")
                or ""
            ).strip().replace("urn:uuid:", "")
            if ru:
                trusted.add(ru)
            for mu in (
                m.get("memberUuids")
                or m.get("member_uuids")
                or m.get("memberIds")
                or []
            ):
                if isinstance(mu, str) and mu.strip():
                    trusted.add(mu.strip().replace("urn:uuid:", ""))

    x_wahs = envelope.get("x_wahs") if isinstance(envelope.get("x_wahs"), dict) else {}
    for cmap in (x_wahs.get("citation_map"), envelope.get("citation_map")):
        if not isinstance(cmap, dict):
            continue
        for k, v in cmap.items():
            key_norm = _normalize_cite_key(k)
            if (
                key_norm.startswith("K")
                and key_norm[1:].isdigit()
                and isinstance(v, dict)
                and str(v.get("resourceType") or "") == "KnowledgeReference"
            ):
                kid = str(
                    v.get("resourceUuid")
                    or v.get("resource_uuid")
                    or v.get("uuid")
                    or v.get("id")
                    or ""
                ).strip().replace("urn:uuid:", "")
                if kid:
                    trusted.add(kid)

    condensed_text = str(envelope.get("condensed_text") or "")
    if condensed_text:
        for cand in _extract_known_uuids(envelope)[0]:
            if len(cand) >= 4 and cand in condensed_text:
                trusted.add(cand)

    return trusted


def _normalize_bracket_citations(text: str) -> str:
    """Expand multi-index bracket citations like `[48, 56]` or `[K1, K2]` into `[48] [56]` / `[K1] [K2]`."""
    def _repl(match: re.Match[str]) -> str:
        raw_inner = match.group(1)
        tokens = [t.upper() for t in re.findall(_CITE_TOKEN_PAT, raw_inner, flags=re.IGNORECASE)]
        return " ".join(f"[{t}]" for t in tokens)

    expanded = _MULTI_BRACKET_RE.sub(_repl, text or "")
    return _LOWER_K_CITE_RE.sub(r"[K\1]", expanded)


def score_wahs_case(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    *,
    budget_tokens: int = 8192,
    valid_uuids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> WahsCaseScore:
    """Mechanically check token-budget compliance, non-empty output, and inline `[N]` / `[K1]` resolution."""
    failures: list[str] = []
    tier_info = envelope.get("tier_info") if isinstance(envelope.get("tier_info"), dict) else {}
    condense_stats = (
        envelope.get("condense_stats")
        if isinstance(envelope.get("condense_stats"), dict)
        else {}
    )
    raw_tokens = None
    for candidate in (
        envelope.get("condensed_chart_tokens"),
        tier_info.get("actual_tokens"),
        envelope.get("actual_tokens"),
        condense_stats.get("approx_tokens"),
    ):
        if candidate is not None:
            raw_tokens = candidate
            break

    has_valid_tokens = (
        raw_tokens is not None
        and not isinstance(raw_tokens, bool)
        and isinstance(raw_tokens, int)
        and raw_tokens > 0
    )
    actual_tokens = int(raw_tokens) if has_valid_tokens else 0
    if raw_tokens is None:
        failures.append("missing actual token count")
    elif not has_valid_tokens:
        failures.append(f"invalid actual token count: {raw_tokens!r}")
    token_budget_ok = has_valid_tokens and 0 < budget_tokens and actual_tokens <= budget_tokens
    if has_valid_tokens and not token_budget_ok:
        failures.append(
            f"token budget exceeded: actual_tokens={actual_tokens} > budget_tokens={budget_tokens}"
        )

    answer = _normalize_bracket_citations(str(envelope.get("answer") or ""))
    if not answer.strip():
        failures.append("empty model answer")

    known_uuids, idx_map, idx_all_uuids = _extract_known_uuids(envelope)
    trusted_uuids = _extract_trusted_uuids(case, envelope, valid_uuids=valid_uuids)
    trusted_idx_map: dict[str, str] = {}
    for k, primary_u in idx_map.items():
        cand_set = set(idx_all_uuids.get(k, set()))
        if primary_u in known_uuids:
            cand_set.add(primary_u)
        matched_trusted = cand_set & trusted_uuids
        if matched_trusted:
            trusted_idx_map[k] = (
                primary_u if primary_u in matched_trusted else sorted(matched_trusted)[0]
            )

    inline_tokens = [tok.upper() for tok in _CITATION_RE.findall(answer)]
    citation_count = len(inline_tokens)
    if inline_tokens:
        resolved_citation_count = sum(
            1 for tok in inline_tokens if tok in trusted_idx_map and trusted_idx_map[tok]
        )
        fabricated_citation_count = citation_count - resolved_citation_count
        citation_resolution_rate = resolved_citation_count / citation_count
        unresolved_citations = sorted(
            {f"[{tok}]" for tok in inline_tokens if tok not in trusted_idx_map}
        )
        if fabricated_citation_count > 0:
            failures.append(f"unresolved inline citation(s): {', '.join(unresolved_citations)}")
    else:
        resolved_citation_count = 0
        fabricated_citation_count = 0
        citation_resolution_rate = 1.0
        unresolved_citations = []

    return WahsCaseScore(
        case_id=case.case_id,
        patient_id=case.patient_id,
        use_case=case.use_case,
        budget_tokens=budget_tokens,
        actual_tokens=actual_tokens,
        token_budget_ok=token_budget_ok,
        citation_count=citation_count,
        resolved_citation_count=resolved_citation_count,
        fabricated_citation_count=fabricated_citation_count,
        unresolved_citations=unresolved_citations,
        citation_resolution_rate=citation_resolution_rate,
        question_horizon=case.question_horizon,
        patient_category=case.patient_category,
        passed=len(failures) == 0,
        failures=failures,
    )


def _split_profile_budget(
    profile_spec: str,
    fallback_budget: int = 8192,
) -> tuple[str, str, int, str | None]:
    """Parse an optional `@<budget>` suffix on a WAHS profile spec (e.g. `wahs:baseline:gemma@32k`).

    Returns `(backend_id, api_profile_id, budget_tokens, budget_tag)`.
    """
    spec = str(profile_spec or "").strip()
    if "@" not in spec:
        return spec, spec, int(fallback_budget), None
    api_prof, raw_b = spec.split("@", 1)
    api_prof = api_prof.strip()
    raw_b_low = raw_b.strip().lower()
    if raw_b_low.endswith("k") and raw_b_low[:-1].isdigit():
        eff_b = int(raw_b_low[:-1]) * 1024
        b_tag = raw_b_low
    elif raw_b_low.isdigit():
        eff_b = int(raw_b_low)
        b_tag = f"{eff_b // 1024}k" if eff_b >= 1024 and eff_b % 1024 == 0 else str(eff_b)
    else:
        raise ValueError(f"Invalid profile budget suffix in {profile_spec!r}")
    if eff_b <= 0 or eff_b > MAX_TOKEN_BUDGET:
        raise ValueError(
            f"Invalid profile budget {eff_b} in {profile_spec!r}: expected int in [1, {MAX_TOKEN_BUDGET}]"
        )
    return f"{api_prof}@{b_tag}", api_prof, eff_b, b_tag


@dataclass(frozen=True)
class ParsedWahsProfile:
    backend_id: str
    api_profile_id: str
    kind: str
    wahs_profile: str
    engine_profile: str
    model_id: str
    budget_tokens: int
    budget_tag: str | None
    explicit_budget: bool
    prompt_override: str | None
    inline_prompt: str | None
    explicit_enrichers: list[str] | None
    configured_enrichers: list[str]
    profile_config: dict[str, Any]


def parse_wahs_profile_spec(
    profile_spec: str | None,
    fallback_budget: int = 8192,
    *,
    config_path: Path | str | None = None,
    default_prompt: str | None = None,
    strict: bool = True,
) -> ParsedWahsProfile:
    """Resolve a declarative `wahs:*`, `wahs+*`, `wahs-engine-baseline:*`, or `raw-fhir:*` profile spec."""
    raw_spec = str(profile_spec or "").strip()
    if not raw_spec:
        if strict:
            raise ValueError(
                "profile_id is required; expected wahs:<profile>:<model>[@<budget>], "
                "wahs+<enricher>:<model>[@<budget>], or raw-fhir:<model>[@<budget>]"
            )
        return ParsedWahsProfile(
            backend_id="",
            api_profile_id="",
            kind="wahs",
            wahs_profile="baseline",
            engine_profile="baseline",
            model_id="",
            budget_tokens=int(fallback_budget),
            budget_tag=None,
            explicit_budget=False,
            prompt_override=default_prompt,
            inline_prompt=None,
            explicit_enrichers=None,
            configured_enrichers=[],
            profile_config={},
        )

    explicit_budget = "@" in raw_spec
    backend_id, api_profile_id, eff_budget, b_tag = _split_profile_budget(raw_spec, fallback_budget)
    cfg = load_wahs_profiles_config(config_path)
    profiles_map = cfg["profiles"]
    default_eng_profile = cfg["default_profile"]
    clean_default_prompt = str(default_prompt or "").strip() or None

    m_base = _BASELINE_ALIAS_RE.match(api_profile_id)
    if m_base:
        inline_prompt = m_base.group(1)
        model_id = m_base.group(2).strip()
        if not model_id:
            raise ValueError(f"Missing model ID in WAHS profile {profile_spec!r}")
        prof_cfg = dict(profiles_map.get("baseline") or {})
        cfg_prompt = str(prof_cfg.get("prompt") or "").strip() or None
        return ParsedWahsProfile(
            backend_id=backend_id,
            api_profile_id=api_profile_id,
            kind="wahs",
            wahs_profile="baseline",
            engine_profile=str(prof_cfg.get("engine_profile") or "baseline"),
            model_id=model_id,
            budget_tokens=eff_budget,
            budget_tag=b_tag,
            explicit_budget=explicit_budget,
            prompt_override=inline_prompt or clean_default_prompt or cfg_prompt,
            inline_prompt=inline_prompt,
            explicit_enrichers=None,
            configured_enrichers=[str(e) for e in (prof_cfg.get("enrichers") or [])],
            profile_config=prof_cfg,
        )

    if api_profile_id.lower().startswith("wahs:"):
        rem = api_profile_id[5:]
        prof_seg, sep, raw_model = rem.partition(":")
        model_id = raw_model.strip()
        if not sep or not prof_seg.strip() or not model_id:
            raise ValueError(
                f"Invalid WAHS profile {profile_spec!r}: expected wahs:<profile_name>:<model>[@<budget>]"
            )
        m_seg = _PROFILE_SEG_RE.fullmatch(prof_seg.strip())
        if not m_seg:
            raise ValueError(f"Invalid WAHS profile segment {prof_seg!r} in {profile_spec!r}")
        prof_name = m_seg.group(1)
        inline_prompt = m_seg.group(2)
        prof_cfg = profiles_map.get(prof_name)
        if prof_cfg is None:
            lower_lookup = {k.lower(): (k, v) for k, v in profiles_map.items()}
            if prof_name.lower() in lower_lookup:
                prof_name, prof_cfg = lower_lookup[prof_name.lower()]
        if prof_cfg is None:
            if strict:
                raise ValueError(
                    f"Unknown WAHS profile {prof_name!r} in {profile_spec!r}; "
                    f"available profiles: {sorted(profiles_map)}"
                )
            prof_cfg = {}
        prof_cfg = dict(prof_cfg)
        cfg_enrichers = [str(e) for e in (prof_cfg.get("enrichers") or [])]
        if prof_cfg.get("engine_profile") and not prof_cfg.get("override_enrichers"):
            engine_profile = str(prof_cfg["engine_profile"])
            explicit_enrichers: list[str] | None = None
        else:
            engine_profile = str(prof_cfg.get("engine_profile") or default_eng_profile)
            explicit_enrichers = list(cfg_enrichers) if prof_cfg else None
        cfg_prompt = str(prof_cfg.get("prompt") or "").strip() or None
        return ParsedWahsProfile(
            backend_id=backend_id,
            api_profile_id=api_profile_id,
            kind="wahs",
            wahs_profile=prof_name,
            engine_profile=engine_profile,
            model_id=model_id,
            budget_tokens=eff_budget,
            budget_tag=b_tag,
            explicit_budget=explicit_budget,
            prompt_override=inline_prompt or clean_default_prompt or cfg_prompt,
            inline_prompt=inline_prompt,
            explicit_enrichers=explicit_enrichers,
            configured_enrichers=cfg_enrichers,
            profile_config=prof_cfg,
        )

    if api_profile_id.lower().startswith("wahs+"):
        lhs, sep, raw_model = api_profile_id.partition(":")
        model_id = raw_model.strip()
        if not sep or not model_id:
            raise ValueError(
                f"Invalid ad-hoc WAHS profile {profile_spec!r}: expected wahs+<mod1>[+<mod2>...]:<model>[@<budget>]"
            )
        m_adhoc = _ADHOC_LHS_RE.fullmatch(lhs.strip())
        if not m_adhoc:
            raise ValueError(f"Invalid ad-hoc WAHS enricher spec {lhs!r} in {profile_spec!r}")
        mods = [tok.strip() for tok in m_adhoc.group(1).split("+") if tok.strip()]
        if not mods:
            raise ValueError(f"Empty ad-hoc enricher list in {profile_spec!r}")
        inline_prompt = m_adhoc.group(2)
        return ParsedWahsProfile(
            backend_id=backend_id,
            api_profile_id=api_profile_id,
            kind="wahs",
            wahs_profile="ad-hoc+" + "+".join(mods),
            engine_profile=default_eng_profile,
            model_id=model_id,
            budget_tokens=eff_budget,
            budget_tag=b_tag,
            explicit_budget=explicit_budget,
            prompt_override=inline_prompt or clean_default_prompt,
            inline_prompt=inline_prompt,
            explicit_enrichers=mods,
            configured_enrichers=list(mods),
            profile_config={},
        )

    m_raw = _RAW_FHIR_RE.match(api_profile_id)
    if m_raw:
        inline_prompt = m_raw.group(1)
        model_id = m_raw.group(2).strip()
        if not model_id:
            raise ValueError(f"Missing model ID in raw-fhir profile {profile_spec!r}")
        return ParsedWahsProfile(
            backend_id=backend_id,
            api_profile_id=api_profile_id,
            kind="raw-fhir",
            wahs_profile="raw-fhir",
            engine_profile="",
            model_id=model_id,
            budget_tokens=eff_budget,
            budget_tag=b_tag,
            explicit_budget=explicit_budget,
            prompt_override=inline_prompt or clean_default_prompt,
            inline_prompt=inline_prompt,
            explicit_enrichers=None,
            configured_enrichers=[],
            profile_config={},
        )

    if not strict:
        underlying = api_profile_id.split(":", 1)[1].strip() if ":" in api_profile_id else api_profile_id
        return ParsedWahsProfile(
            backend_id=backend_id,
            api_profile_id=api_profile_id,
            kind="custom",
            wahs_profile=api_profile_id.split(":", 1)[0].strip() or "custom",
            engine_profile="baseline",
            model_id=underlying,
            budget_tokens=eff_budget,
            budget_tag=b_tag,
            explicit_budget=explicit_budget,
            prompt_override=clean_default_prompt,
            inline_prompt=None,
            explicit_enrichers=None,
            configured_enrichers=[],
            profile_config={},
        )

    raise ValueError(
        f"Unsupported WAHS profile {profile_spec!r}: expected wahs:<profile>:<model>[@<budget>], "
        "wahs+<enricher>:<model>[@<budget>], wahs-engine-baseline:<model>[@<budget>], or raw-fhir:<model>[@<budget>]"
    )


def _decode_b64_utf8_text(raw_b64: str) -> str | None:
    """Decode Base64 attachment text if it is valid UTF-8 with >=90% printable characters."""
    cleaned = raw_b64.strip()
    if not cleaned:
        return None
    try:
        raw_bytes = base64.b64decode(cleaned, validate=True)
        decoded = raw_bytes.decode("utf-8")
    except Exception:
        return None
    if not decoded:
        return ""
    printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\n\r\t")
    if printable / len(decoded) >= 0.9:
        return decoded
    return None


def _decode_raw_fhir_entry_attachments(resource: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `resource` with Base64 text attachments decoded to UTF-8 strings."""
    content = resource.get("content")
    presented = resource.get("presentedForm")
    has_content = isinstance(content, list) and bool(content)
    has_presented = isinstance(presented, list) and bool(presented)
    if not has_content and not has_presented:
        return resource

    out = dict(resource)
    if has_content:
        new_content: list[Any] = []
        changed_c = False
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("attachment"), dict):
                att = item["attachment"]
                raw_data = att.get("data")
                if isinstance(raw_data, str):
                    dec = _decode_b64_utf8_text(raw_data)
                    if dec is not None:
                        new_att = {**att, "data": dec}
                        new_content.append({**item, "attachment": new_att})
                        changed_c = True
                        continue
            new_content.append(item)
        if changed_c:
            out["content"] = new_content

    if has_presented:
        new_pf: list[Any] = []
        changed_p = False
        for pf in presented:
            if isinstance(pf, dict) and isinstance(pf.get("data"), str):
                dec = _decode_b64_utf8_text(pf["data"])
                if dec is not None:
                    new_pf.append({**pf, "data": dec})
                    changed_p = True
                    continue
            new_pf.append(pf)
        if changed_p:
            out["presentedForm"] = new_pf

    return out


def _extract_provenance_and_enrichment(
    x_wahs: dict[str, Any],
    *,
    fallback_profile: str,
    fallback_prompt_id: str | None = None,
    fallback_enrichers: Sequence[str] = (),
) -> tuple[str, str | None, str | None, list[str], int]:
    """Extract `(wahs_profile, prompt_id, prompt_sha256, active_enrichers, enrichment_tokens)` from `x_wahs`."""
    cond = x_wahs.get("condensation") if isinstance(x_wahs.get("condensation"), dict) else {}
    ai_prov = x_wahs.get("ai_provenance") if isinstance(x_wahs.get("ai_provenance"), dict) else {}

    wahs_profile = str(
        cond.get("profile_id")
        or ai_prov.get("profile_id")
        or x_wahs.get("profile_id")
        or fallback_profile
    ).strip()
    raw_pid = cond.get("prompt_id") or ai_prov.get("prompt_id") or x_wahs.get("prompt_id") or fallback_prompt_id
    prompt_id = str(raw_pid).strip() if raw_pid else None
    raw_sha = cond.get("prompt_sha256") or ai_prov.get("prompt_sha256") or x_wahs.get("prompt_sha256")
    prompt_sha256 = str(raw_sha).strip() if raw_sha else None

    active_enrichers: list[str] = []
    enricher_sum = 0
    raw_enrichers = x_wahs.get("enrichers")
    if isinstance(raw_enrichers, list):
        for item in raw_enrichers:
            if isinstance(item, str) and item.strip():
                eid = item.strip()
                if eid not in active_enrichers:
                    active_enrichers.append(eid)
            elif isinstance(item, dict):
                raw_eid = item.get("id") or item.get("enricher_id") or item.get("name")
                if raw_eid and str(raw_eid).strip():
                    eid = str(raw_eid).strip()
                    if eid not in active_enrichers:
                        active_enrichers.append(eid)
                for tk in ("tokens", "actual_tokens", "enrichment_tokens", "token_count"):
                    tval = item.get(tk)
                    if isinstance(tval, int) and not isinstance(tval, bool) and tval > 0:
                        enricher_sum += tval
                        break
    else:
        for e in fallback_enrichers:
            if str(e).strip() and str(e).strip() not in active_enrichers:
                active_enrichers.append(str(e).strip())

    raw_enr_toks = cond.get("enrichment_tokens")
    if raw_enr_toks is None:
        raw_enr_toks = x_wahs.get("enrichment_tokens")
    if isinstance(raw_enr_toks, int) and not isinstance(raw_enr_toks, bool) and raw_enr_toks >= 0:
        enrichment_tokens = int(raw_enr_toks)
    else:
        enrichment_tokens = enricher_sum

    return wahs_profile, prompt_id, prompt_sha256, active_enrichers, enrichment_tokens


class WahsHubClient:
    """HTTP client for standalone `wahs-engine` (`/v1/chat/completions`, `/v1/wahs/context/preview`) and `raw-fhir` baselines."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 180.0,
        session: requests.Session | None = None,
        max_retries: int = 1,
        retry_backoff_s: float = 0.0,
        bundle_dirs: Sequence[Path | str] | None = None,
        direct_llm_base_url: str | None = None,
        direct_llm_api_key: str | None = None,
        direct_provider_flavor: str | None = None,
        direct_context_window: int = 32768,
        decode_raw_fhir_attachments: bool = True,
        profiles_config_path: Path | str | None = None,
        prompts_dir: Path | str | None = None,
        prompt_override: str | None = None,
    ) -> None:
        raw_base = (
            base_url or os.environ.get("MED_AGENT_HUB_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.base_url = re.sub(r"/v1$", "", raw_base)
        raw_direct = (
            direct_llm_base_url
            or os.environ.get("DIRECT_LLM_BASE_URL")
            or self.base_url
        ).rstrip("/")
        self.direct_llm_base_url = re.sub(r"/v1$", "", raw_direct)
        self._direct_llm_api_key = (
            direct_llm_api_key
            if direct_llm_api_key is not None
            else os.environ.get("DIRECT_LLM_API_KEY", "")
        ).strip()
        self.direct_provider_flavor = (
            direct_provider_flavor
            or os.environ.get("DIRECT_LLM_PROVIDER_FLAVOR")
            or ""
        ).strip().lower()
        self.direct_context_window = int(direct_context_window)
        self.decode_raw_fhir_attachments = bool(decode_raw_fhir_attachments)
        self.profiles_config_path = Path(profiles_config_path).expanduser() if profiles_config_path else None
        self.prompts_dir = Path(prompts_dir).expanduser() if prompts_dir else None
        self.prompt_override = str(prompt_override or "").strip() or None
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = max(0.0, float(retry_backoff_s))
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._engine_preview_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._bundle_cache: dict[str, dict[str, Any] | None] = {}
        self.bundle_dirs: list[Path] = []
        seen_dirs: set[Path] = set()

        def _append_bundle_dir(raw_dir: Path | str) -> None:
            raw_str = str(raw_dir or "").strip()
            if not raw_str:
                return
            cand = Path(raw_str).expanduser()
            if cand not in seen_dirs:
                seen_dirs.add(cand)
                self.bundle_dirs.append(cand)

        for d in bundle_dirs or ():
            _append_bundle_dir(d)
        env_bdirs = os.environ.get("WAHS_BUNDLES_DIR", "").strip()
        if env_bdirs:
            for seg in env_bdirs.split(os.pathsep):
                _append_bundle_dir(seg)
        env_bdir = os.environ.get("WAHS_BUNDLE_DIR", "").strip()
        if env_bdir:
            _append_bundle_dir(env_bdir)
        repo_bundles = _REPO_ROOT / "datasets" / "bundles"
        if repo_bundles.is_dir():
            _append_bundle_dir(repo_bundles)

    def _resolve_local_bundle(self, patient_id: str) -> dict[str, Any] | None:
        if patient_id in self._bundle_cache:
            return self._bundle_cache[patient_id]
        stem = patient_id[:-5] if patient_id.endswith(".json") else patient_id
        stems = [stem]
        for suffix in ("_set_b", "_set_a", "_set_c", "_multisource"):
            if stem.endswith(suffix) and stem[: -len(suffix)] not in stems:
                stems.append(stem[: -len(suffix)])
        for bdir in self.bundle_dirs:
            for st in stems:
                for candidate in (bdir / f"{st}.json", bdir / "eval" / f"{st}.json"):
                    if candidate.is_file():
                        try:
                            data = json.loads(candidate.read_text(encoding="utf-8"))
                            if isinstance(data, dict) and data.get("resourceType") == "Bundle":
                                self._bundle_cache[patient_id] = data
                                return data
                        except Exception:
                            continue
        self._bundle_cache[patient_id] = None
        return None

    @staticmethod
    def _build_wahs_wire_options(
        *,
        local_bundle: dict[str, Any],
        engine_profile: str,
        prompt_override: str | None,
        explicit_enrichers: list[str] | None,
        budget_tokens: int,
        explicit_budget: bool,
    ) -> dict[str, Any]:
        return {
            "fhir_bundle": local_bundle,
            "profile": engine_profile,
            **({"prompt": prompt_override} if prompt_override else {}),
            **({"enrichers": explicit_enrichers} if explicit_enrichers is not None else {}),
            **({"target_budget_tokens": int(budget_tokens)} if explicit_budget else {}),
        }

    def _preview_wahs_engine_context(
        self,
        case: WahsEvalCase,
        *,
        local_bundle: dict[str, Any],
        parsed: ParsedWahsProfile,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        query_dependent = bool(parsed.configured_enrichers or parsed.explicit_enrichers or not parsed.explicit_budget)
        cache_key: tuple[Any, ...] = (
            case.patient_id,
            parsed.engine_profile,
            tuple(parsed.explicit_enrichers or ()),
            str(parsed.prompt_override or ""),
            int(parsed.budget_tokens) if parsed.explicit_budget else "auto",
            case.case_id if query_dependent else "*",
            parsed.model_id,
        )
        if cache_key in self._engine_preview_cache:
            return self._engine_preview_cache[cache_key]

        wahs_opts = self._build_wahs_wire_options(
            local_bundle=local_bundle,
            engine_profile=parsed.engine_profile,
            prompt_override=parsed.prompt_override,
            explicit_enrichers=parsed.explicit_enrichers,
            budget_tokens=parsed.budget_tokens,
            explicit_budget=parsed.explicit_budget,
        )
        req_body: dict[str, Any] = {
            "model": parsed.model_id,
            "messages": [{"role": "user", "content": case.prompt}],
            "wahs": wahs_opts,
        }
        if max_tokens is not None:
            req_body["max_tokens"] = int(max_tokens)

        try:
            resp = self._session.post(
                f"{self.base_url}/v1/wahs/context/preview",
                json=req_body,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = dict(resp.json())
                self._engine_preview_cache[cache_key] = data
                return data
        except Exception:
            pass
        return {}

    def _evaluate_wahs_engine_case(
        self,
        case: WahsEvalCase,
        *,
        profile_id: str,
        parsed: ParsedWahsProfile,
        seed: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate standalone `wahs-engine` OpenAI `/v1/chat/completions` + `/v1/wahs/context/preview`."""
        local_bundle = self._resolve_local_bundle(case.patient_id)
        if local_bundle is None:
            raise ValueError(
                f"Local FHIR bundle not found for patient_id={case.patient_id!r} in {self.bundle_dirs}"
            )
        eff_temp = (
            float(temperature)
            if temperature is not None
            else (0.2 if seed is not None else 0.1)
        )
        max_tok = int(os.environ.get("WAHS_EVAL_MAX_TOKENS", "900") or "900")
        preview = self._preview_wahs_engine_context(
            case,
            local_bundle=local_bundle,
            parsed=parsed,
            max_tokens=max_tok,
        )
        wahs_opts = self._build_wahs_wire_options(
            local_bundle=local_bundle,
            engine_profile=parsed.engine_profile,
            prompt_override=parsed.prompt_override,
            explicit_enrichers=parsed.explicit_enrichers,
            budget_tokens=parsed.budget_tokens,
            explicit_budget=parsed.explicit_budget,
        )
        chat_req: dict[str, Any] = {
            "model": parsed.model_id,
            "messages": [{"role": "user", "content": case.prompt}],
            "stream": False,
            "temperature": eff_temp,
            "max_tokens": max_tok,
            "wahs": wahs_opts,
        }
        if seed is not None:
            chat_req["seed"] = int(seed)

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self._session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=chat_req,
                    timeout=self.timeout,
                )
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries:
                    if self.retry_backoff_s > 0:
                        time.sleep(self.retry_backoff_s)
                    continue
                raise RuntimeError(
                    f"wahs-engine {profile_id} transport failure for {case.case_id}: {exc}"
                ) from exc

            wall_latency_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code == 200:
                chat_json = dict(resp.json())
                choices = chat_json.get("choices") or []
                msg = (choices[0].get("message") if choices and isinstance(choices[0], dict) else {}) or {}
                raw_content = str(msg.get("content") or "")
                cleaned_answer = _normalize_bracket_citations(
                    _THINK_RE.sub("", raw_content).strip()
                )
                x_wahs = chat_json.get("x_wahs") if isinstance(chat_json.get("x_wahs"), dict) else {}
                citation_map = x_wahs.get("citation_map") if isinstance(x_wahs.get("citation_map"), dict) else {}
                cond_meta = x_wahs.get("condensation") if isinstance(x_wahs.get("condensation"), dict) else {}
                timings = x_wahs.get("timings") if isinstance(x_wahs.get("timings"), dict) else {}

                sortable_mappings: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
                mapping_by_key: dict[str, dict[str, Any]] = {}
                for k_str, v_obj in citation_map.items():
                    if not isinstance(v_obj, dict):
                        continue
                    norm_key = _normalize_cite_key(k_str)
                    if norm_key.isdigit():
                        idx_val: int | str = int(norm_key)
                        sort_key = (0, int(norm_key), "")
                    elif norm_key.startswith("K") and norm_key[1:].isdigit():
                        idx_val = norm_key
                        sort_key = (1, int(norm_key[1:]), norm_key)
                    else:
                        continue
                    norm_m = {
                        "index": idx_val,
                        "resourceType": v_obj.get("resourceType") or "Resource",
                        "resourceUuid": v_obj.get("id") or v_obj.get("resourceUuid"),
                        "date": v_obj.get("date") or "",
                        "display": v_obj.get("display") or "",
                        "source": v_obj.get("source") or "",
                        "memberUuids": list(v_obj.get("memberIds") or v_obj.get("memberUuids") or []),
                    }
                    sortable_mappings.append((sort_key, norm_m))
                    mapping_by_key[norm_key] = norm_m
                sortable_mappings.sort(key=lambda item: item[0])
                mappings = [m for _, m in sortable_mappings]

                cited_keys: list[str] = []
                for raw_tok in _CITATION_RE.findall(cleaned_answer):
                    tok_up = raw_tok.upper()
                    if tok_up not in cited_keys:
                        cited_keys.append(tok_up)

                references: list[dict[str, Any]] = []
                for c_key in cited_keys:
                    m_obj = mapping_by_key.get(c_key)
                    if m_obj is not None:
                        ref_entry: dict[str, Any] = {
                            "index": m_obj["index"],
                            "resourceType": m_obj.get("resourceType"),
                            "resourceUuid": m_obj.get("resourceUuid"),
                        }
                        if m_obj.get("date"):
                            ref_entry["date"] = m_obj["date"]
                        if m_obj.get("display"):
                            ref_entry["display"] = m_obj["display"]
                        if m_obj.get("memberUuids"):
                            ref_entry["memberUuids"] = list(m_obj["memberUuids"])
                        references.append(ref_entry)

                actual_tokens = int(cond_meta.get("actual_tokens") or 0)
                eff_chart_budget = (
                    cond_meta.get("effective_chart_budget")
                    if cond_meta.get("effective_chart_budget") is not None
                    else cond_meta.get("budget_effective")
                )
                eff_latency = int(round(float(timings.get("total_latency_ms") or wall_latency_ms)))
                base_chart_text = str(preview.get("chart_text") or "")
                extra_lines = [
                    f"[{m['index']}] {m.get('date') or ''} {m.get('resourceType')}: {m.get('display')}".strip()
                    for m in mappings
                    if f"[{m['index']}]" not in base_chart_text and m.get("display")
                ]
                full_chart_text = (
                    f"{base_chart_text}\n\n# Enricher & Knowledge Evidence\n" + "\n".join(extra_lines)
                    if extra_lines and base_chart_text
                    else (base_chart_text or "\n".join(extra_lines))
                )
                (
                    wahs_profile,
                    prompt_id,
                    prompt_sha256,
                    active_enrichers,
                    enrichment_tokens,
                ) = _extract_provenance_and_enrichment(
                    x_wahs,
                    fallback_profile=parsed.wahs_profile,
                    fallback_prompt_id=parsed.prompt_override,
                    fallback_enrichers=parsed.explicit_enrichers or parsed.configured_enrichers,
                )
                return {
                    "answer": cleaned_answer,
                    "references": references,
                    "citations": references,
                    "mappings": mappings,
                    "actual_tokens": actual_tokens,
                    "budget_tokens": int(parsed.budget_tokens),
                    "tier_info": {
                        "tier_used": cond_meta.get("tier"),
                        "tier_name": cond_meta.get("tier_name"),
                        "actual_tokens": actual_tokens,
                        "condense_mode": "lossless_structural",
                    },
                    "condensed_text": full_chart_text,
                    "latency_ms": eff_latency,
                    "timings": {
                        "engine_prep_ms": float(timings.get("engine_prep_ms") or 0.0),
                        "upstream_llm_ms": float(timings.get("upstream_llm_ms") or eff_latency),
                        "total_latency_ms": float(timings.get("total_latency_ms") or eff_latency),
                        "prompt_ms": float(timings.get("prompt_ms") or 0.0),
                        "predicted_ms": float(timings.get("predicted_ms") or 0.0),
                        "prompt_n": int(timings.get("prompt_n") or 0),
                        "predicted_n": int(timings.get("predicted_n") or 0),
                        "prompt_per_second": float(timings.get("prompt_per_second") or 0.0),
                        "predicted_per_second": float(timings.get("predicted_per_second") or 0.0),
                        "llm_rounds": int(timings.get("llm_rounds") or 1),
                    },
                    "usage": chat_json.get("usage") or {},
                    "x_wahs": x_wahs,
                    "effective_chart_budget": eff_chart_budget,
                    "wahs_profile": wahs_profile,
                    "prompt_id": prompt_id,
                    "prompt_sha256": prompt_sha256,
                    "active_enrichers": active_enrichers,
                    "enrichment_tokens": enrichment_tokens,
                    "seed": seed,
                    "profile_id": profile_id,
                    "api_profile_id": parsed.api_profile_id,
                }

            err_text = getattr(resp, "text", "")[:300]
            last_err = RuntimeError(
                f"wahs-engine {profile_id} failed [{resp.status_code}] for {case.case_id}: {err_text}"
            )
            if resp.status_code in {500, 502, 503, 504} and attempt < self.max_retries:
                if self.retry_backoff_s > 0:
                    time.sleep(self.retry_backoff_s)
                continue
            raise last_err
        assert last_err is not None
        raise last_err

    def _evaluate_raw_fhir_ablation_case(
        self,
        case: WahsEvalCase,
        *,
        profile_id: str,
        parsed: ParsedWahsProfile,
        seed: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Offline Raw Chart Baseline (`raw-fhir`): raw uncondensed/truncated FHIR JSON without `wahs-engine`."""
        local_bundle = self._resolve_local_bundle(case.patient_id)
        if local_bundle is None:
            raise ValueError(
                f"Local FHIR bundle not found for patient_id={case.patient_id!r} in {self.bundle_dirs}"
            )
        budget_tokens = int(parsed.budget_tokens)
        max_tok = int(os.environ.get("WAHS_EVAL_MAX_TOKENS", "900") or "900")
        if budget_tokens > 4096:
            effective_slice_budget = min(
                budget_tokens,
                max(256, self.direct_context_window - max_tok - 320),
            )
            chars_per_tok = 2.15
        else:
            effective_slice_budget = budget_tokens
            chars_per_tok = 3.6
        max_chars = max(256, int(effective_slice_budget * chars_per_tok))
        wrapper_overhead = 128
        entry_budget = max(128, max_chars - wrapper_overhead)
        entries = list(local_bundle.get("entry") or [])
        kept_entries: list[dict[str, Any]] = []
        used_chars = wrapper_overhead
        retained_uuids: list[str] = []
        for entry in entries:
            res = entry.get("resource") if isinstance(entry, dict) else None
            if not isinstance(res, dict):
                continue
            if self.decode_raw_fhir_attachments:
                res = _decode_raw_fhir_entry_attachments(res)
            serialized = json.dumps(res, separators=(",", ":"))
            if used_chars + len(serialized) + 2 > max_chars:
                if kept_entries:
                    break
                slice_cap = max(48, entry_budget - 110)
                kept_entries.append(
                    {
                        "resource": {
                            "resourceType": str(res.get("resourceType") or "Resource"),
                            "id": str(res.get("id") or ""),
                            "_truncated_raw_json": serialized[:slice_cap],
                        }
                    }
                )
                rid = str(res.get("id") or "").strip()
                if rid:
                    retained_uuids.append(rid)
                break
            kept_entries.append({"resource": res})
            used_chars += len(serialized) + 2
            rid = str(res.get("id") or "").strip()
            if rid:
                retained_uuids.append(rid)

        def _bundle_json(entries_slice: list[dict[str, Any]]) -> str:
            return json.dumps(
                {
                    "resourceType": "Bundle",
                    "type": "collection",
                    "total_entries_in_bundle": len(entries),
                    "included_entries": len(entries_slice),
                    "entry": entries_slice,
                },
                separators=(",", ":"),
            )

        raw_fhir_slice = _bundle_json(kept_entries)
        if kept_entries and "_truncated_raw_json" in kept_entries[0].get("resource", {}):
            while len(raw_fhir_slice) > max_chars:
                cur = kept_entries[0]["resource"]["_truncated_raw_json"]
                if not cur:
                    break
                excess = len(raw_fhir_slice) - max_chars
                new_cap = max(0, len(cur) - max(excess, 16))
                kept_entries[0]["resource"]["_truncated_raw_json"] = cur[:new_cap]
                raw_fhir_slice = _bundle_json(kept_entries)
        approx_tokens = (
            max(1, min(budget_tokens, math.ceil(len(raw_fhir_slice) / chars_per_tok)))
            if budget_tokens > 4096
            else max(1, (len(raw_fhir_slice) + 3) // 4)
        )
        is_full_bundle = (len(kept_entries) == len(entries)) and not (
            kept_entries and "_truncated_raw_json" in kept_entries[0].get("resource", {})
        )
        if is_full_bundle:
            header_line = (
                f"Raw FHIR R4 Bundle (complete uncondensed chart: all {len(kept_entries)}/{len(entries)} entries included"
                + ("; clinical note attachments decoded to UTF-8" if self.decode_raw_fhir_attachments else "")
                + "):"
            )
        else:
            header_line = (
                f"Raw FHIR R4 Bundle Slice (uncondensed, truncated to <= {budget_tokens} tokens; "
                f"{len(kept_entries)}/{len(entries)} entries fit):"
            )

        resolved_prompt_id, prompt_tpl, prompt_sha256 = load_raw_fhir_prompt_template(
            parsed.inline_prompt or parsed.prompt_override,
            prompts_dir=self.prompts_dir,
            config_path=self.profiles_config_path,
            fallback_to_default=(parsed.inline_prompt is None),
        )
        user_prompt = render_raw_fhir_prompt(
            prompt_tpl,
            header_line=header_line,
            raw_fhir_slice=raw_fhir_slice,
            question=case.prompt,
        )
        eff_temp = (
            float(temperature)
            if temperature is not None
            else (0.2 if seed is not None else 0.1)
        )
        chat_req: dict[str, Any] = {
            "model": parsed.model_id,
            "messages": [{"role": "user", "content": user_prompt}],
            "stream": False,
            "temperature": eff_temp,
            "max_tokens": max_tok,
        }
        use_litellm_ollama = (
            self.direct_provider_flavor in {"litellm", "ollama"}
            or "llm.co.dev.cirg.uw.edu" in self.direct_llm_base_url
        )
        if use_litellm_ollama:
            chat_req["num_ctx"] = int(self.direct_context_window)
            chat_req["reasoning_effort"] = "none"
        else:
            chat_req["chat_template_kwargs"] = {"enable_thinking": False}
        if seed is not None:
            chat_req["seed"] = int(seed)

        post_kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self._direct_llm_api_key:
            post_kwargs["headers"] = {"Authorization": f"Bearer {self._direct_llm_api_key}"}

        started = time.monotonic()
        resp = self._session.post(
            f"{self.direct_llm_base_url}/v1/chat/completions",
            json=chat_req,
            **post_kwargs,
        )
        if resp.status_code in {400, 422}:
            chat_req.pop("chat_template_kwargs", None)
            chat_req.pop("reasoning_effort", None)
            resp = self._session.post(
                f"{self.direct_llm_base_url}/v1/chat/completions",
                json=chat_req,
                **post_kwargs,
            )
        wall_latency_ms = int((time.monotonic() - started) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(
                f"raw-fhir {profile_id} failed [{resp.status_code}] for {case.case_id}: {resp.text[:300]}"
            )
        body = dict(resp.json())
        choices = body.get("choices") or []
        msg = (choices[0].get("message") if choices and isinstance(choices[0], dict) else {}) or {}
        cleaned_answer = _normalize_bracket_citations(
            _THINK_RE.sub("", str(msg.get("content") or "")).strip()
        )
        usage_obj = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        prompt_tok = usage_obj.get("prompt_tokens")
        eff_actual_tokens = (
            int(prompt_tok)
            if isinstance(prompt_tok, int) and not isinstance(prompt_tok, bool) and 0 < prompt_tok <= budget_tokens
            else approx_tokens
        )
        t_obj = body.get("timings") if isinstance(body.get("timings"), dict) else {}
        return {
            "answer": cleaned_answer,
            "references": [],
            "citations": [],
            "mappings": [],
            "prompt_retained_uuids": retained_uuids,
            "valid_uuids": retained_uuids,
            "actual_tokens": eff_actual_tokens,
            "budget_tokens": budget_tokens,
            "tier_info": {
                "actual_tokens": eff_actual_tokens,
                "condense_mode": "raw_fhir_full" if is_full_bundle else "raw_fhir_truncated",
                "attachments_decoded": self.decode_raw_fhir_attachments,
                "included_entries": len(kept_entries),
                "total_entries": len(entries),
            },
            "condensed_text": raw_fhir_slice,
            "latency_ms": wall_latency_ms,
            "timings": {
                "engine_prep_ms": 0.0,
                "upstream_llm_ms": float(wall_latency_ms),
                "total_latency_ms": float(wall_latency_ms),
                "prompt_ms": float(t_obj.get("prompt_ms") or 0.0),
                "predicted_ms": float(t_obj.get("predicted_ms") or 0.0),
                "prompt_n": int(t_obj.get("prompt_n") or 0),
                "predicted_n": int(t_obj.get("predicted_n") or 0),
                "prompt_per_second": float(t_obj.get("prompt_per_second") or 0.0),
                "predicted_per_second": float(t_obj.get("predicted_per_second") or 0.0),
                "llm_rounds": 1,
            },
            "usage": body.get("usage") or {},
            "wahs_profile": "raw-fhir",
            "prompt_id": resolved_prompt_id,
            "prompt_sha256": prompt_sha256,
            "active_enrichers": [],
            "enrichment_tokens": 0,
            "seed": seed,
            "profile_id": profile_id,
            "api_profile_id": parsed.api_profile_id,
        }

    def warmup_model(self, model_id: str) -> bool:
        """Issue a tiny unrecorded 4-token completion to warm GPU weights on model switch."""
        if not model_id:
            return False
        post_fn = getattr(self._session, "post", None)
        if not callable(post_fn):
            return False
        try:
            target_url = f"{self.base_url}/v1/chat/completions"
            post_kwargs: dict[str, Any] = {"timeout": min(self.timeout, 240.0)}
            warmup_body: dict[str, Any] = {
                "model": model_id,
                "messages": [{"role": "user", "content": "ok"}],
                "max_tokens": 4,
                "stream": False,
            }
            if self._direct_llm_api_key and self.direct_llm_base_url != self.base_url:
                target_url = f"{self.direct_llm_base_url}/v1/chat/completions"
                post_kwargs["headers"] = {"Authorization": f"Bearer {self._direct_llm_api_key}"}
                use_litellm_ollama = (
                    self.direct_provider_flavor in {"litellm", "ollama"}
                    or "llm.co.dev.cirg.uw.edu" in self.direct_llm_base_url
                )
                if use_litellm_ollama:
                    warmup_body["num_ctx"] = int(self.direct_context_window)
                    warmup_body["reasoning_effort"] = "none"
            resp = post_fn(
                target_url,
                json=warmup_body,
                **post_kwargs,
            )
            return getattr(resp, "status_code", 0) == 200
        except Exception:
            return False

    def evaluate_case(
        self,
        case: WahsEvalCase,
        *,
        budget_tokens: int,
        profile_id: str | None = None,
        seed: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate a case under a declarative `wahs:*`, `wahs+*`, `wahs-engine-baseline:*`, or `raw-fhir:*` profile."""
        parsed = parse_wahs_profile_spec(
            profile_id,
            budget_tokens,
            config_path=self.profiles_config_path,
            default_prompt=self.prompt_override,
            strict=True,
        )
        if parsed.kind == "raw-fhir":
            return self._evaluate_raw_fhir_ablation_case(
                case,
                profile_id=str(profile_id),
                parsed=parsed,
                seed=seed,
                temperature=temperature,
            )
        return self._evaluate_wahs_engine_case(
            case,
            profile_id=str(profile_id),
            parsed=parsed,
            seed=seed,
            temperature=temperature,
        )


@dataclass(frozen=True)
class WahsRunResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    results_path: Path
    summary_path: Path
    total_cells: int
    passed_cells: int
    summary: dict[str, Any]


def _missing_cell_score(
    case: WahsEvalCase, budget_tokens: int, reason: str | None = None
) -> WahsCaseScore:
    msg = reason or f"missing or incomplete evaluation result for cell ({case.case_id}, {budget_tokens})"
    return WahsCaseScore(
        case_id=case.case_id,
        patient_id=case.patient_id,
        use_case=case.use_case,
        budget_tokens=budget_tokens,
        actual_tokens=0,
        token_budget_ok=False,
        citation_count=0,
        resolved_citation_count=0,
        fabricated_citation_count=0,
        unresolved_citations=[],
        citation_resolution_rate=0.0,
        question_horizon=case.question_horizon,
        patient_category=case.patient_category,
        passed=False,
        failures=[msg],
    )


def _infer_wahs_profile(
    profile_id: str | None,
    *,
    config_path: Path | str | None = None,
) -> str:
    """Return canonical `wahs_profile` identifier for a profile spec."""
    if not profile_id:
        return "baseline"
    parsed = parse_wahs_profile_spec(profile_id, config_path=config_path, strict=False)
    return parsed.wahs_profile


def _infer_model_family_and_id(
    profile_id: str,
    *,
    config_path: Path | str | None = None,
) -> tuple[str, str]:
    """Return `(model_family, underlying_model_id)` for a WAHS profile."""
    parsed = parse_wahs_profile_spec(profile_id, config_path=config_path, strict=False)
    underlying = parsed.model_id or parsed.api_profile_id
    api_low = parsed.api_profile_id.lower()
    u_low = underlying.lower()
    if "medgemma" in u_low or "medgemma" in api_low:
        fam = "medgemma"
    elif "gemma" in u_low or "gemma" in api_low:
        fam = "gemma-4"
    elif "qwen" in u_low or "qwen" in api_low:
        fam = "qwen"
    elif "llama" in u_low or "llama" in api_low or "hermes3" in u_low or "hermes3" in api_low:
        fam = "llama"
    elif "mistral" in u_low or "mistral" in api_low:
        fam = "mistral"
    elif "granite" in u_low or "granite" in api_low:
        fam = "granite"
    elif "lfm2" in u_low or "lfm2" in api_low:
        fam = "lfm2"
    elif "gemini" in u_low or "gemini" in api_low:
        fam = "gemini"
    elif "claude" in u_low or "claude" in api_low:
        fam = "claude"
    else:
        fam = "other"
    return fam, underlying


def _finalize_stat_bucket(pb: dict[str, Any]) -> dict[str, Any]:
    n = pb["total"] or 1
    skip_keys = {
        "token_budget_ok_sum",
        "citation_clean_sum",
        "citation_rate_sum",
        "latency_ms_sum",
        "enrichment_tokens_sum",
        "lat_vals",
        "prompt_ms_vals",
        "predicted_ms_vals",
        "engine_prep_ms_vals",
        "prompt_tps_vals",
        "predicted_tps_vals",
        "seeds_seen",
        "prompt_ids_seen",
        "prompt_sha256s_seen",
        "active_enrichers_seen",
    }
    out: dict[str, Any] = {k: v for k, v in pb.items() if k not in skip_keys}
    prompt_ids = sorted(pb["prompt_ids_seen"])
    prompt_shas = sorted(pb["prompt_sha256s_seen"])
    out.update(
        {
            "total": pb["total"],
            "passed": pb["passed"],
            "pass_rate": round(pb["passed"] / n, 4),
            "pass_rate_wilson_ci_95": wilson_ci_95(pb["passed"], pb["total"]),
            "token_budget_compliance_rate": round(pb["token_budget_ok_sum"] / n, 4),
            "citation_clean_rate": round(pb["citation_clean_sum"] / n, 4),
            "mean_citation_resolution_rate": round(pb["citation_rate_sum"] / n, 4),
            "total_citations": int(pb["total_citations"]),
            "resolved_citations": int(pb["resolved_citations"]),
            "fabricated_citation_count": int(pb["fabricated_citation_count"]),
            "mean_latency_ms": round(pb["latency_ms_sum"] / n, 1),
            "prompt_id": prompt_ids[0] if len(prompt_ids) == 1 else None,
            "prompt_ids": prompt_ids,
            "prompt_sha256": prompt_shas[0] if len(prompt_shas) == 1 else None,
            "prompt_sha256s": prompt_shas,
            "active_enrichers": list(pb["active_enrichers_seen"]),
            "enrichment_tokens": int(pb["enrichment_tokens_sum"]),
            "mean_enrichment_tokens": round(pb["enrichment_tokens_sum"] / n, 1),
            "latency_stats": {
                "total_ms": latency_percentiles(pb["lat_vals"]),
                "prefill_prompt_ms": latency_percentiles(pb["prompt_ms_vals"]),
                "decode_predicted_ms": latency_percentiles(pb["predicted_ms_vals"]),
                "engine_prep_ms": latency_percentiles(pb["engine_prep_ms_vals"]),
                "mean_prompt_per_second": round(
                    sum(pb["prompt_tps_vals"]) / (len(pb["prompt_tps_vals"]) or 1), 1
                ),
                "mean_predicted_per_second": round(
                    sum(pb["predicted_tps_vals"]) / (len(pb["predicted_tps_vals"]) or 1), 1
                ),
            },
            "seeds": sorted(pb["seeds_seen"]),
        }
    )
    return out


def _summarize_scores(
    scores: list[WahsCaseScore],
    *,
    missing_cells: list[dict[str, Any]] | None = None,
    cell_meta_list: list[dict[str, Any]] | None = None,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    by_use_case: dict[str, dict[str, Any]] = {}
    by_horizon: dict[str, dict[str, Any]] = {}
    by_profile: dict[str, dict[str, Any]] = {}
    by_wahs_profile: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_family: dict[str, dict[str, Any]] = {}
    all_seeds_seen: set[int] = set()
    all_wahs_profiles: set[str] = set()
    all_prompts: dict[str, str | None] = {}
    all_enrichers: list[str] = []
    total_enrichment_tokens = 0

    for idx, s in enumerate(scores):
        bucket = by_use_case.setdefault(
            s.use_case,
            {
                "total": 0,
                "passed": 0,
                "token_budget_ok_sum": 0,
                "citation_clean_sum": 0,
                "citation_rate_sum": 0.0,
                "total_citations": 0,
                "resolved_citations": 0,
                "fabricated_citation_count": 0,
            },
        )
        bucket["total"] += 1
        bucket["passed"] += int(s.passed)
        bucket["token_budget_ok_sum"] += int(s.token_budget_ok)
        bucket["citation_clean_sum"] += int(s.fabricated_citation_count == 0)
        bucket["citation_rate_sum"] += s.citation_resolution_rate
        bucket["total_citations"] += s.citation_count
        bucket["resolved_citations"] += s.resolved_citation_count
        bucket["fabricated_citation_count"] += s.fabricated_citation_count

        h_bucket = by_horizon.setdefault(
            s.question_horizon,
            {
                "total": 0,
                "passed": 0,
                "token_budget_ok_sum": 0,
                "citation_rate_sum": 0.0,
                "fabricated_citation_count": 0,
            },
        )
        h_bucket["total"] += 1
        h_bucket["passed"] += int(s.passed)
        h_bucket["token_budget_ok_sum"] += int(s.token_budget_ok)
        h_bucket["citation_rate_sum"] += s.citation_resolution_rate
        h_bucket["fabricated_citation_count"] += s.fabricated_citation_count

        c_meta = (
            cell_meta_list[idx]
            if cell_meta_list and idx < len(cell_meta_list)
            else {}
        ) or {}
        if c_meta.get("seed") is not None:
            all_seeds_seen.add(int(c_meta["seed"]))
        prof_id = c_meta.get("profile_id")
        enr_toks = int(c_meta.get("enrichment_tokens") or 0)
        total_enrichment_tokens += enr_toks
        cell_prompt_id = str(c_meta.get("prompt_id") or "").strip() or None
        cell_prompt_sha = str(c_meta.get("prompt_sha256") or "").strip() or None
        if cell_prompt_id:
            all_prompts.setdefault(cell_prompt_id, cell_prompt_sha)
        cell_enrichers = [str(x).strip() for x in (c_meta.get("active_enrichers") or []) if str(x).strip()]
        for eid in cell_enrichers:
            if eid not in all_enrichers:
                all_enrichers.append(eid)

        if prof_id:
            m_fam = str(c_meta.get("model_family") or "other")
            u_mod = str(c_meta.get("underlying_model") or prof_id)
            w_prof = str(
                c_meta.get("wahs_profile")
                or _infer_wahs_profile(str(prof_id), config_path=config_path)
            )
            all_wahs_profiles.add(w_prof)
            lat_ms = float(c_meta.get("latency_ms") or 0.0)
            timings = c_meta.get("timings") if isinstance(c_meta.get("timings"), dict) else {}
            for target_map, group_key, extra_info in (
                (
                    by_profile,
                    str(prof_id),
                    {
                        "model_family": m_fam,
                        "underlying_model": u_mod,
                        "wahs_profile": w_prof,
                    },
                ),
                (
                    by_wahs_profile,
                    w_prof,
                    {"wahs_profile": w_prof},
                ),
                (
                    by_model,
                    u_mod,
                    {"model_family": m_fam, "underlying_model": u_mod},
                ),
                (by_family, m_fam, {}),
            ):
                p_bucket = target_map.setdefault(
                    group_key,
                    {
                        **extra_info,
                        "total": 0,
                        "passed": 0,
                        "token_budget_ok_sum": 0,
                        "citation_clean_sum": 0,
                        "citation_rate_sum": 0.0,
                        "total_citations": 0,
                        "resolved_citations": 0,
                        "fabricated_citation_count": 0,
                        "latency_ms_sum": 0.0,
                        "enrichment_tokens_sum": 0,
                        "lat_vals": [],
                        "prompt_ms_vals": [],
                        "predicted_ms_vals": [],
                        "engine_prep_ms_vals": [],
                        "prompt_tps_vals": [],
                        "predicted_tps_vals": [],
                        "seeds_seen": set(),
                        "prompt_ids_seen": set(),
                        "prompt_sha256s_seen": set(),
                        "active_enrichers_seen": [],
                    },
                )
                p_bucket["total"] += 1
                p_bucket["passed"] += int(s.passed)
                p_bucket["token_budget_ok_sum"] += int(s.token_budget_ok)
                p_bucket["citation_clean_sum"] += int(s.fabricated_citation_count == 0)
                p_bucket["citation_rate_sum"] += s.citation_resolution_rate
                p_bucket["total_citations"] += s.citation_count
                p_bucket["resolved_citations"] += s.resolved_citation_count
                p_bucket["fabricated_citation_count"] += s.fabricated_citation_count
                p_bucket["latency_ms_sum"] += lat_ms
                p_bucket["enrichment_tokens_sum"] += enr_toks
                if cell_prompt_id:
                    p_bucket["prompt_ids_seen"].add(cell_prompt_id)
                if cell_prompt_sha:
                    p_bucket["prompt_sha256s_seen"].add(cell_prompt_sha)
                for eid in cell_enrichers:
                    if eid not in p_bucket["active_enrichers_seen"]:
                        p_bucket["active_enrichers_seen"].append(eid)
                if lat_ms > 0:
                    p_bucket["lat_vals"].append(lat_ms)
                if float(timings.get("prompt_ms") or 0.0) > 0:
                    p_bucket["prompt_ms_vals"].append(float(timings["prompt_ms"]))
                if float(timings.get("predicted_ms") or 0.0) > 0:
                    p_bucket["predicted_ms_vals"].append(float(timings["predicted_ms"]))
                if "engine_prep_ms" in timings:
                    p_bucket["engine_prep_ms_vals"].append(float(timings.get("engine_prep_ms") or 0.0))
                if float(timings.get("prompt_per_second") or 0.0) > 0:
                    p_bucket["prompt_tps_vals"].append(float(timings["prompt_per_second"]))
                if float(timings.get("predicted_per_second") or 0.0) > 0:
                    p_bucket["predicted_tps_vals"].append(float(timings["predicted_per_second"]))
                if c_meta.get("seed") is not None:
                    p_bucket["seeds_seen"].add(int(c_meta["seed"]))

    use_case_summary = {}
    for uc, b in sorted(by_use_case.items()):
        n = b["total"] or 1
        use_case_summary[uc] = {
            "total": b["total"],
            "passed": b["passed"],
            "pass_rate": round(b["passed"] / n, 4),
            "pass_rate_wilson_ci_95": wilson_ci_95(b["passed"], b["total"]),
            "token_budget_compliance_rate": round(b["token_budget_ok_sum"] / n, 4),
            "citation_clean_rate": round(b["citation_clean_sum"] / n, 4),
            "mean_citation_resolution_rate": round(b["citation_rate_sum"] / n, 4),
            "total_citations": b["total_citations"],
            "resolved_citations": b["resolved_citations"],
            "fabricated_citation_count": b["fabricated_citation_count"],
        }

    horizon_summary = {}
    for hz, hb in sorted(by_horizon.items()):
        n = hb["total"] or 1
        horizon_summary[hz] = {
            "total": hb["total"],
            "passed": hb["passed"],
            "pass_rate": round(hb["passed"] / n, 4),
            "pass_rate_wilson_ci_95": wilson_ci_95(hb["passed"], hb["total"]),
            "token_budget_compliance_rate": round(hb["token_budget_ok_sum"] / n, 4),
            "mean_citation_resolution_rate": round(hb["citation_rate_sum"] / n, 4),
            "fabricated_citation_count": hb["fabricated_citation_count"],
        }

    prompt_ids_sorted = sorted(all_prompts.keys())
    prompt_shas_sorted = sorted({v for v in all_prompts.values() if v})
    summary: dict[str, Any] = {
        "incomplete": bool(missing_cells),
        "missing_cells": list(missing_cells or []),
        "seeds": sorted(all_seeds_seen),
        "wahs_profiles": sorted(all_wahs_profiles),
        "wahs_profile": sorted(all_wahs_profiles)[0] if len(all_wahs_profiles) == 1 else None,
        "prompt_id": prompt_ids_sorted[0] if len(prompt_ids_sorted) == 1 else None,
        "prompt_sha256": prompt_shas_sorted[0] if len(prompt_shas_sorted) == 1 else None,
        "prompts": {k: all_prompts[k] for k in prompt_ids_sorted},
        "active_enrichers": all_enrichers,
        "enrichment_tokens": total_enrichment_tokens,
        "mean_enrichment_tokens": round(total_enrichment_tokens / (total or 1), 1),
        "total_cells": total,
        "passed_cells": passed,
        "pass_rate": round(passed / (total or 1), 4),
        "pass_rate_wilson_ci_95": wilson_ci_95(passed, total),
        "token_budget_compliance_rate": round(
            sum(1 for s in scores if s.token_budget_ok) / (total or 1), 4
        ),
        "citation_clean_rate": round(
            sum(1 for s in scores if s.fabricated_citation_count == 0) / (total or 1), 4
        ),
        "mean_citation_resolution_rate": round(
            sum(s.citation_resolution_rate for s in scores) / (total or 1), 4
        ),
        "total_citations": sum(s.citation_count for s in scores),
        "resolved_citations": sum(s.resolved_citation_count for s in scores),
        "fabricated_citation_count": sum(s.fabricated_citation_count for s in scores),
        "by_use_case": use_case_summary,
        "by_question_horizon": horizon_summary,
    }
    if by_profile:
        summary["by_profile"] = {
            pid: _finalize_stat_bucket(pb) for pid, pb in sorted(by_profile.items())
        }
    if by_wahs_profile:
        summary["by_wahs_profile"] = {
            wp: _finalize_stat_bucket(wb) for wp, wb in sorted(by_wahs_profile.items())
        }
    if by_model:
        summary["by_underlying_model"] = {
            mid: _finalize_stat_bucket(mb) for mid, mb in sorted(by_model.items())
        }
    if by_family:
        summary["by_model_family"] = {
            fid: _finalize_stat_bucket(fb) for fid, fb in sorted(by_family.items())
        }
    return summary


def _invoke_client_evaluate_case(
    client: Any,
    case: WahsEvalCase,
    *,
    budget_tokens: int,
    profile_id: str,
    seed: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    fn = client.evaluate_case
    try:
        sig = inspect.signature(fn)
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        accepts_profile_id = "profile_id" in sig.parameters or has_var_kw
        accepts_seed = "seed" in sig.parameters or has_var_kw
        accepts_temperature = "temperature" in sig.parameters or has_var_kw
    except (TypeError, ValueError):
        accepts_profile_id = False
        accepts_seed = False
        accepts_temperature = False
    kwargs: dict[str, Any] = {"budget_tokens": budget_tokens}
    if accepts_profile_id:
        kwargs["profile_id"] = profile_id
    if seed is not None and accepts_seed:
        kwargs["seed"] = seed
    if temperature is not None and accepts_temperature:
        kwargs["temperature"] = temperature
    return fn(case, **kwargs)


def _cell_dict(
    case_id: str,
    budget_tokens: int,
    profile_id: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    cell: dict[str, Any] = {"case_id": case_id, "budget_tokens": int(budget_tokens)}
    if profile_id is not None:
        cell["profile_id"] = profile_id
    if seed is not None:
        cell["seed"] = int(seed)
    return cell


def _profile_display_label(pid: str, *, config_path: Path | str | None = None) -> str:
    return str(_wahs_arm_card(pid, config_path=config_path).get("title") or pid)


def _write_judge_prep_artifacts(
    run_dir: Path,
    cases: list[WahsEvalCase],
    profiles: list[str],
    client: Any,
    observed_envelopes: dict[str, dict[str, Any]],
    *,
    config_path: Path | str | None = None,
) -> None:
    """Write `inputs/scenarios/`, `inputs/charts/`, and `run_meta.json` for blind judging."""
    scenarios_dir = run_dir / "inputs" / "scenarios"
    charts_dir = run_dir / "inputs" / "charts"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    backends_meta: dict[str, dict[str, Any]] = {}
    arm_cards_meta: dict[str, dict[str, Any]] = {}
    for pid in profiles:
        parsed = parse_wahs_profile_spec(pid, config_path=config_path, strict=False)
        fam, underlying = _infer_model_family_and_id(pid, config_path=config_path)
        provider_kind = "raw-fhir" if parsed.kind == "raw-fhir" else "wahs-engine"
        label = _profile_display_label(pid, config_path=config_path)
        backends_meta[pid] = {
            "label": label,
            "kind": "provider_arm",
            "provider": provider_kind,
            "modelName": underlying,
            "profile": parsed.api_profile_id,
            "wahs_profile": parsed.wahs_profile,
            "budget_tokens": parsed.budget_tokens,
            "answer_model": underlying,
        }
        arm_cards_meta[pid] = {
            "id": pid,
            "label": label,
            "kind": "single",
            "models": [{"id": underlying, "family": fam}],
            "roles": {"synthesizer": {"id": underlying, "family": fam}},
            "answer_model": underlying,
            "wahs_profile": parsed.wahs_profile,
            "budget_tokens": parsed.budget_tokens,
        }

    _write_run_meta_preserving_hardware(
        run_dir,
        {
            "reference_date": "2026-11-11",
            "backends": backends_meta,
            "arm_cards": arm_cards_meta,
        },
        client=client,
    )
    _write_scenario_and_chart_inputs(
        run_dir,
        cases,
        observed_envelopes,
        client=client,
        config_path=config_path,
    )


def _merge_scenario_envelopes(
    existing_env: dict[str, Any] | None,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    if existing_env is None:
        merged = dict(envelope)
    else:
        merged = dict(existing_env)
        cur_text = str(merged.get("condensed_text") or "")
        new_text = str(envelope.get("condensed_text") or "")
        cur_is_raw = str((merged.get("tier_info") or {}).get("condense_mode") or "") == "raw_fhir_truncated"
        new_is_raw = str((envelope.get("tier_info") or {}).get("condense_mode") or "") == "raw_fhir_truncated"
        new_is_better = (cur_is_raw and not new_is_raw and bool(new_text)) or (
            cur_is_raw == new_is_raw and len(new_text) > len(cur_text)
        )
        if new_is_better:
            merged["condensed_text"] = envelope.get("condensed_text")
            merged["tier_info"] = envelope.get("tier_info")

        primary_maps = (envelope.get("mappings") or []) if new_is_better else (merged.get("mappings") or [])
        secondary_maps = (merged.get("mappings") or []) if new_is_better else (envelope.get("mappings") or [])
        by_idx: dict[Any, dict[str, Any]] = {}
        seen_uuids: set[str] = set()
        extra_maps: list[dict[str, Any]] = []
        for m in primary_maps:
            if isinstance(m, dict):
                idx = m.get("index")
                if idx is not None and idx not in by_idx:
                    by_idx[idx] = m
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if ru:
                    seen_uuids.add(ru)
        for m in secondary_maps:
            if isinstance(m, dict):
                idx = m.get("index")
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if idx is not None and idx not in by_idx:
                    by_idx[idx] = m
                    if ru:
                        seen_uuids.add(ru)
                elif ru and ru not in seen_uuids:
                    seen_uuids.add(ru)
                    extra_maps.append(m)
        int_keys = sorted(k for k in by_idx if isinstance(k, int))
        str_keys = sorted((k for k in by_idx if not isinstance(k, int)), key=str)
        merged["mappings"] = [by_idx[k] for k in [*int_keys, *str_keys]] + extra_maps

    vset: set[str] = set()
    for src in (existing_env or {}, envelope):
        for key in ("valid_uuids", "retained_uuids"):
            for u in src.get(key) or []:
                if u:
                    vset.add(str(u).replace("urn:uuid:", ""))
        for m in src.get("mappings") or []:
            if isinstance(m, dict):
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if ru:
                    vset.add(ru)
                for mu in m.get("memberUuids") or []:
                    if mu:
                        vset.add(str(mu).replace("urn:uuid:", ""))
    merged["valid_uuids"] = sorted(vset)
    return merged


def _scenario_category_for_case(
    case: WahsEvalCase,
    *,
    config_path: Path | str | None = None,
) -> str:
    cfg = load_wahs_profiles_config(config_path)
    cat_map = cfg["scenario_categories"]
    for cand in (case.case_id, case.question_id):
        m = _WAHS_CASE_Q_RE.match(str(cand or "").strip())
        if m:
            mapped = cat_map.get(m.group(1).lower())
            if mapped:
                return mapped
        low_cand = str(cand or "").strip().lower()
        if low_cand in cat_map:
            return cat_map[low_cand]
    raw_cat = str(case.category or case.patient_category or case.use_case or "").strip()
    return raw_cat or "Clinical Q&A"


def _probe_live_hardware(client: Any) -> dict[str, Any] | None:
    """Best-effort probe of upstream Ollama/serving hardware when using a real HTTP session."""
    if client is None:
        return None
    sess = getattr(client, "_session", None)
    if type(sess) is not requests.Session:
        return None
    base = str(getattr(client, "direct_llm_base_url", None) or getattr(client, "base_url", "") or "").rstrip("/")
    if not base:
        return None
    hw: dict[str, Any] = {"inference_endpoint": base}
    try:
        resp = sess.get(f"{base}/api/ps", timeout=0.5)
        if getattr(resp, "status_code", 0) == 200:
            models = (resp.json() or {}).get("models") or []
            if models and isinstance(models[0], dict):
                det = models[0].get("details") or {}
                if det.get("quantization_level"):
                    hw["quantization"] = str(det["quantization_level"])
                if models[0].get("context_length"):
                    hw["context_window"] = int(models[0]["context_length"])
                hw["serving_engine"] = "Ollama"
    except Exception:
        pass
    return hw or None


def _write_run_meta_preserving_hardware(
    run_dir: Path,
    updates: dict[str, Any],
    *,
    client: Any = None,
) -> dict[str, Any]:
    """Update `run_meta.json` without discarding existing or env-resolved `hardware` metadata."""
    from harness.validate.runner import resolve_hardware_metadata

    run_meta_path = run_dir / "run_meta.json"
    existing: dict[str, Any] = {}
    if run_meta_path.is_file():
        try:
            loaded = json.loads(run_meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception:
            existing = {}

    merged = {**existing, **updates}
    hw_merged: dict[str, Any] = {}
    if isinstance(existing.get("hardware"), dict):
        hw_merged.update(existing["hardware"])
    env_hw = resolve_hardware_metadata()
    if env_hw:
        for k, v in env_hw.items():
            hw_merged.setdefault(k, v)
    probed = _probe_live_hardware(client)
    if probed and not hw_merged:
        hw_merged.update(probed)
    if hw_merged:
        merged["hardware"] = hw_merged
    run_meta_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


_FHIR_BOILERPLATE_KEYS = frozenset({"resourceType", "id", "meta", "implicitRules", "language"})


def _fhir_code_text(obj: Any) -> str:
    if isinstance(obj, dict):
        if obj.get("text"):
            return str(obj["text"]).strip()
        codings = obj.get("coding")
        if isinstance(codings, list):
            for c in codings:
                if isinstance(c, dict) and (c.get("display") or c.get("code")):
                    return str(c.get("display") or c.get("code")).strip()
        return ""
    if isinstance(obj, list):
        return "; ".join(p for p in (_fhir_code_text(item) for item in obj) if p)
    return str(obj or "").strip()


def _strip_fhir_narrative(div: Any) -> str:
    raw = str(div or "").strip()
    if not raw:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _decode_attachment_text(att: dict[str, Any]) -> str:
    meta_bits = [str(att.get(k)).strip() for k in ("title", "contentType", "url") if att.get(k)]
    raw_b64 = att.get("data")
    if isinstance(raw_b64, str) and raw_b64.strip():
        try:
            raw_bytes = base64.b64decode(raw_b64, validate=True)
        except Exception:
            meta_bits.append(f"raw_b64_len={len(raw_b64)}")
        else:
            try:
                decoded = raw_bytes.decode("utf-8")
                printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\n\r\t")
                if decoded and printable / len(decoded) >= 0.9:
                    meta_bits.append(decoded.strip())
                else:
                    meta_bits.append(f"binary_bytes={len(raw_bytes)}")
            except UnicodeDecodeError:
                meta_bits.append(f"binary_bytes={len(raw_bytes)}")
    return " ".join(b for b in meta_bits if b)


def _format_obs_value(res: dict[str, Any], handled: set[str]) -> str | None:
    if isinstance(res.get("valueQuantity"), dict):
        vq = res["valueQuantity"]
        handled.add("valueQuantity")
        if vq.get("value") is not None:
            return f"value={vq['value']} {vq.get('unit') or ''}".strip()
    for vk in ("valueString", "valueBoolean", "valueInteger"):
        if res.get(vk) is not None and res.get(vk) != "":
            handled.add(vk)
            return f"value={res[vk]}"
    if isinstance(res.get("valueCodeableConcept"), dict):
        handled.add("valueCodeableConcept")
        txt = _fhir_code_text(res["valueCodeableConcept"])
        if txt:
            return f"value={txt}"
    for comp_k in ("valueRatio", "valueRange"):
        if isinstance(res.get(comp_k), dict):
            handled.add(comp_k)
            return f"{comp_k}={json.dumps(res[comp_k], sort_keys=True, separators=(',', ':'), ensure_ascii=False)}"
    return None


def _collect_composition_sections(sections: list[Any]) -> list[str]:
    out: list[str] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or _fhir_code_text(sec.get("code")) or "").strip()
        narrative = _strip_fhir_narrative((sec.get("text") or {}).get("div") if isinstance(sec.get("text"), dict) else "")
        sec_str = ": ".join(p for p in (title, narrative) if p)
        if sec_str:
            out.append(sec_str)
        if isinstance(sec.get("section"), list):
            out.extend(_collect_composition_sections(sec["section"]))
    return out


def _serialize_bundle_lossless(bundle: dict[str, Any]) -> dict[str, Any]:
    """Pure-stdlib lossless Stage-A serialization for raw FHIR R4 bundles."""
    lines: list[str] = []
    mappings: list[dict[str, Any]] = []
    uuids: set[str] = set()
    idx = 1
    for entry in bundle.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        res = entry.get("resource") if isinstance(entry.get("resource"), dict) else None
        if not res:
            continue
        rtype = str(res.get("resourceType") or "Resource")
        rid = str(res.get("id") or entry.get("fullUrl") or "").replace("urn:uuid:", "")
        if rid:
            uuids.add(rid)
        date = ""
        for dk in (
            "effectiveDateTime",
            "recordedDate",
            "onsetDateTime",
            "authoredOn",
            "occurrenceDateTime",
            "performedDateTime",
            "date",
        ):
            if res.get(dk):
                date = str(res[dk])[:10]
                break
        if not date and isinstance(res.get("period"), dict) and res["period"].get("start"):
            date = str(res["period"]["start"])[:10]
        if not date and isinstance(res.get("meta"), dict) and res["meta"].get("lastUpdated"):
            date = str(res["meta"]["lastUpdated"])[:10]

        code_obj = res.get("code") or res.get("medicationCodeableConcept") or res.get("vaccineCode")
        label = (
            _fhir_code_text(code_obj)
            or str(res.get("title") or res.get("description") or "").strip()
            or _fhir_code_text(res.get("type"))
            or str(res.get("status") or rtype)
        )
        handled: set[str] = set(_FHIR_BOILERPLATE_KEYS) | {
            "code",
            "medicationCodeableConcept",
            "vaccineCode",
            "title",
            "description",
        }
        parts = [label]
        for sk in ("status", "clinicalStatus", "verificationStatus", "criticality", "intent"):
            if res.get(sk):
                handled.add(sk)
                sval = _fhir_code_text(res[sk]) if isinstance(res[sk], dict) else str(res[sk])
                if sval:
                    parts.append(f"{sk}={sval}")
        val_str = _format_obs_value(res, handled)
        if val_str:
            parts.append(val_str)
        if res.get("interpretation"):
            handled.add("interpretation")
            interp = _fhir_code_text(res["interpretation"])
            if interp:
                parts.append(f"interpretation={interp}")
        if isinstance(res.get("referenceRange"), list) and res["referenceRange"]:
            handled.add("referenceRange")
            rr_bits = []
            for rr in res["referenceRange"]:
                if not isinstance(rr, dict):
                    continue
                if rr.get("text"):
                    rr_bits.append(str(rr["text"]))
                else:
                    lo = (rr.get("low") or {}).get("value") if isinstance(rr.get("low"), dict) else None
                    hi = (rr.get("high") or {}).get("value") if isinstance(rr.get("high"), dict) else None
                    unit = (rr.get("low") or rr.get("high") or {}).get("unit") if isinstance(rr.get("low") or rr.get("high"), dict) else ""
                    if lo is not None or hi is not None:
                        rr_bits.append(f"{lo or ''}..{hi or ''} {unit or ''}".strip())
            if rr_bits:
                parts.append(f"refRange={'; '.join(rr_bits)}")
        if isinstance(res.get("component"), list) and res["component"]:
            handled.add("component")
            comp_bits = []
            for comp in res["component"]:
                if not isinstance(comp, dict):
                    continue
                clabel = _fhir_code_text(comp.get("code")) or "component"
                cval = _format_obs_value(comp, set()) or ""
                comp_bits.append(f"{clabel}:{cval}".strip(":"))
            if comp_bits:
                parts.append("components=[" + "; ".join(comp_bits) + "]")
        for dk in ("dosageInstruction", "dosage"):
            if isinstance(res.get(dk), list) and res[dk]:
                handled.add(dk)
                dosages = []
                for d in res[dk]:
                    if not isinstance(d, dict):
                        continue
                    d_str = str(d.get("text") or "").strip() or json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    dosages.append(d_str)
                if dosages:
                    parts.append(f"dosage={'; '.join(dosages)}")
        if isinstance(res.get("reaction"), list) and res["reaction"]:
            handled.add("reaction")
            rx_bits = []
            for rx in res["reaction"]:
                if not isinstance(rx, dict):
                    continue
                manif = _fhir_code_text(rx.get("manifestation"))
                sev = str(rx.get("severity") or "").strip()
                desc = str(rx.get("description") or "").strip()
                rx_bits.append(" ".join(x for x in (manif, f"({sev})" if sev else "", desc) if x))
            if any(rx_bits):
                parts.append("reaction=" + "; ".join(b for b in rx_bits if b))
        if isinstance(res.get("content"), list) and res["content"]:
            handled.add("content")
            att_bits = []
            for c_item in res["content"]:
                if isinstance(c_item, dict) and isinstance(c_item.get("attachment"), dict):
                    att_txt = _decode_attachment_text(c_item["attachment"])
                    if att_txt:
                        att_bits.append(att_txt)
            if att_bits:
                parts.append("attachment=" + " | ".join(att_bits))
        if isinstance(res.get("presentedForm"), list) and res["presentedForm"]:
            handled.add("presentedForm")
            pf_bits = [_decode_attachment_text(pf) for pf in res["presentedForm"] if isinstance(pf, dict)]
            if any(pf_bits):
                parts.append("presentedForm=" + " | ".join(b for b in pf_bits if b))
        if res.get("conclusion"):
            handled.add("conclusion")
            parts.append(f"conclusion={res['conclusion']}")
        if isinstance(res.get("section"), list) and res["section"]:
            handled.add("section")
            secs = _collect_composition_sections(res["section"])
            if secs:
                parts.append("sections=[" + " | ".join(secs) + "]")
        if isinstance(res.get("note"), list) and res["note"]:
            handled.add("note")
            notes = [str(n.get("text") or "").strip() for n in res["note"] if isinstance(n, dict) and n.get("text")]
            if notes:
                parts.append("note=" + " | ".join(notes))
        if isinstance(res.get("text"), dict) and res["text"].get("div"):
            handled.add("text")
            narr = _strip_fhir_narrative(res["text"]["div"])
            if narr:
                parts.append(f"narrative={narr}")

        extra = {k: v for k, v in res.items() if k not in handled and v not in (None, "", [], {})}
        if extra:
            parts.append("extra=" + json.dumps(extra, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

        disp = " | ".join(p for p in parts if p)
        lines.append(f"[{idx}] {date} {rtype}: {disp}".strip())
        mappings.append(
            {
                "index": idx,
                "resourceType": rtype,
                "resourceUuid": rid,
                "date": date,
                "display": disp,
            }
        )
        idx += 1
    return {
        "condensed_text": "\n".join(lines),
        "mappings": mappings,
        "valid_uuids": sorted(uuids),
        "lossless_stage_a": True,
    }


def _lossless_stage_a_chart_envelope(
    bundle: dict[str, Any],
) -> dict[str, Any]:
    """Produce a Stage-A lossless chart snapshot (0 omitted clinical items) for blind judges."""
    return _serialize_bundle_lossless(bundle)


def _write_scenario_input_file(
    scenarios_dir: Path,
    case: WahsEvalCase,
    scenario_id: str,
    *,
    config_path: Path | str | None = None,
) -> None:
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    _, _, seed_part = scenario_id.partition("__s")
    scen_path = scenarios_dir / f"{scenario_id}.json"
    existing_scen: dict[str, Any] = {}
    if scen_path.is_file():
        try:
            existing_scen = json.loads(scen_path.read_text(encoding="utf-8"))
        except Exception:
            existing_scen = {}
    default_title = (
        f"{case.use_case}: {case.case_id} (seed {seed_part})"
        if seed_part
        else f"{case.use_case}: {case.case_id}"
    )
    rubric_bits: list[str] = [f"Use case: {case.use_case}."]
    if case.what_it_tests.strip():
        rubric_bits.append(case.what_it_tests.strip())
    if case.expected_answer.strip():
        rubric_bits.append(f"Reference expected answer: {case.expected_answer.strip()}")
    if case.must_abstain:
        rubric_bits.append(
            "GROUNDED ABSTENTION: The requested test/finding is absent from the patient chart; "
            "the answer must state it is not documented without fabricating values or unrelated citations."
        )
    what_it_tests_str = " ".join(rubric_bits)
    existing_exp = (
        existing_scen.get("expectations")
        if isinstance(existing_scen.get("expectations"), dict)
        else {}
    )
    expectations_payload: dict[str, Any] = {
        **existing_exp,
        "should_abstain": case.must_abstain,
        "what_it_tests": what_it_tests_str,
    }
    if case.expected_answer.strip():
        expectations_payload["expected_answer"] = case.expected_answer.strip()
    resolved_category = str(
        existing_scen.get("category")
        or _scenario_category_for_case(case, config_path=config_path)
    )
    scen_obj = {
        **existing_scen,
        "id": scenario_id,
        "title": str(existing_scen.get("title") or default_title),
        "category": resolved_category,
        "patient_ref": scenario_id,
        "should_abstain": case.must_abstain,
        "what_it_tests": what_it_tests_str,
        "expectations": expectations_payload,
        "turns": existing_scen.get("turns") or [{"n": 1, "question": case.prompt}],
    }
    scen_path.write_text(json.dumps(scen_obj, indent=2) + "\n", encoding="utf-8")


def _write_scenario_and_chart_inputs(
    run_dir: Path,
    cases: list[WahsEvalCase],
    observed_envelopes: dict[str, dict[str, Any]],
    *,
    client: Any = None,
    scenario_ids: list[str] | None = None,
    config_path: Path | str | None = None,
) -> None:
    from harness.validate.context_store import ensure_scenario_chart_input

    scenarios_dir = run_dir / "inputs" / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    cases_by_id = {c.case_id: c for c in cases}
    lossless_by_patient: dict[str, dict[str, Any] | None] = {}

    def _lossless_for_case(c: WahsEvalCase) -> dict[str, Any] | None:
        if c.patient_id in lossless_by_patient:
            return lossless_by_patient[c.patient_id]
        resolver = getattr(client, "_resolve_local_bundle", None)
        bundle = resolver(c.patient_id) if callable(resolver) else None
        env_out = _lossless_stage_a_chart_envelope(bundle) if isinstance(bundle, dict) else None
        lossless_by_patient[c.patient_id] = env_out
        return env_out

    all_sids: list[str] = list(dict.fromkeys([*(scenario_ids or ()), *observed_envelopes.keys()]))
    for scenario_id in all_sids:
        no_seed_part, _, _ = scenario_id.partition("__s")
        base_cid = no_seed_part.split("__b", 1)[0]
        case = cases_by_id.get(base_cid)
        if case is None:
            continue
        _write_scenario_input_file(scenarios_dir, case, scenario_id, config_path=config_path)
        lossless_env = _lossless_for_case(case)
        target_env = lossless_env or observed_envelopes.get(scenario_id)
        if target_env is not None:
            ensure_scenario_chart_input(
                run_dir,
                scenario_id,
                patient_id=case.patient_id,
                response=target_env,
                extra_valid_uuids=list(case.valid_uuids),
                lossless_stage_a=bool(lossless_env is not None),
            )


def run_wahs_suite(
    cases_path: Path | str,
    *,
    client: Any,
    output_dir: Path | str = "artifacts/wahs",
    budgets: tuple[int, ...] | list[int] | None = None,
    profiles: tuple[str, ...] | list[str] | None = None,
    seeds: tuple[int, ...] | list[int] | None = None,
    temperature: float | None = None,
    git_sha: str | None = None,
    target_provenance: list[dict[str, Any]] | None = None,
    dataset_id: str = "wahs-synthetic-r4",
    dataset_version: str = "2026.11",
    resume_from: Path | str | None = None,
    bundle_dirs: Sequence[Path | str] | None = None,
    profiles_config_path: Path | str | None = None,
    prompt_override: str | None = None,
) -> WahsRunResult:
    """Execute a WAHS profile suite against `client` and freeze all artifacts in `<output_dir>/<run_id>`."""
    from harness.validate.context_store import (
        rehydrate_response_envelope,
        slim_response_envelope,
    )
    from harness.validate.runner import CellPlanItem, execute_cell_matrix

    active_profiles = [str(p).strip() for p in (profiles or ()) if str(p).strip()]
    if not active_profiles:
        raise ValueError("profiles must contain at least one non-empty WAHS profile ID")

    eff_config_path = profiles_config_path or getattr(client, "profiles_config_path", None)
    eff_prompt_override = prompt_override or getattr(client, "prompt_override", None)
    if eff_config_path and hasattr(client, "profiles_config_path") and getattr(client, "profiles_config_path") is None:
        client.profiles_config_path = Path(eff_config_path).expanduser()
    if eff_prompt_override and hasattr(client, "prompt_override") and getattr(client, "prompt_override") is None:
        client.prompt_override = str(eff_prompt_override)

    if budgets is not None:
        for b in budgets:
            if isinstance(b, bool) or not isinstance(b, int) or b <= 0 or b > MAX_TOKEN_BUDGET:
                raise ValueError(
                    f"Invalid token budget {b!r}: expected int in [1, {MAX_TOKEN_BUDGET}]"
                )

    cases_file = Path(cases_path)
    cases_bytes = cases_file.read_bytes()
    suite_sha256 = hashlib.sha256(cases_bytes).hexdigest()
    cases = load_wahs_cases(cases_file)
    if bundle_dirs and hasattr(client, "bundle_dirs") and isinstance(getattr(client, "bundle_dirs"), list):
        existing_bundle_dirs = list(client.bundle_dirs)
        explicit_dirs = [Path(d).expanduser() for d in bundle_dirs if str(d or "").strip()]
        client.bundle_dirs = list(dict.fromkeys([*explicit_dirs, *existing_bundle_dirs]))

    active_seeds: list[int | None] = (
        [int(s) for s in seeds] if seeds else [None]
    )
    multi_seed_mode = len(active_seeds) > 1

    def _budgets_for_profile_case(prof_spec: str, case_obj: WahsEvalCase) -> list[int]:
        if "@" in prof_spec:
            _, _, pinned_b, _ = _split_profile_budget(prof_spec)
            return [int(pinned_b)]
        if budgets:
            return [int(b) for b in budgets]
        return [int(b) for b in (case_obj.target_token_budgets or DEFAULT_TOKEN_BUDGETS)]

    expected_cells: list[dict[str, Any]] = []
    max_budgets_per_profile = 1
    for prof_id in active_profiles:
        for seed_val in active_seeds:
            for case in cases:
                active_budgets = _budgets_for_profile_case(prof_id, case)
                max_budgets_per_profile = max(max_budgets_per_profile, len(active_budgets))
                for b_tokens in active_budgets:
                    expected_cells.append(
                        _cell_dict(
                            case.case_id,
                            int(b_tokens),
                            profile_id=prof_id,
                            seed=seed_val,
                        )
                    )

    norm_temp = float(temperature) if temperature is not None else None
    prior_rows: dict[tuple[str, int, str, int | None], dict[str, Any]] = {}
    resumed_run_id: str | None = None
    resume_ancestry: list[str] = []
    if resume_from is not None:
        r_dir = Path(resume_from)
        r_manifest_path = r_dir / "run_manifest.json"
        if not r_manifest_path.is_file():
            raise ValueError(f"Cannot resume from {r_dir}: missing run_manifest.json")
        r_manifest = json.loads(r_manifest_path.read_text(encoding="utf-8"))
        prior_suite_sha = r_manifest.get("suite_sha256")
        if prior_suite_sha != suite_sha256:
            raise ValueError(
                f"Cannot resume from {r_dir}: suite_sha256 mismatch "
                f"(prior={prior_suite_sha!r}, current={suite_sha256!r})"
            )
        prior_expected_cells = r_manifest.get("expected_cells")
        if isinstance(prior_expected_cells, list) and prior_expected_cells != expected_cells:
            raise ValueError(
                f"Cannot resume from {r_dir}: expected_cells mismatch "
                f"(prior has {len(prior_expected_cells)} cells, current has {len(expected_cells)} cells)"
            )
        prior_temp_raw = r_manifest.get("temperature")
        prior_temp = float(prior_temp_raw) if prior_temp_raw is not None else None
        if prior_temp != norm_temp:
            raise ValueError(
                f"Cannot resume from {r_dir}: temperature mismatch "
                f"(prior={prior_temp!r}, current={norm_temp!r})"
            )
        resumed_run_id = str(r_manifest.get("run_id") or r_dir.name)
        resume_ancestry = list(r_manifest.get("resumeAncestry") or [])
        if resumed_run_id and resumed_run_id not in resume_ancestry:
            resume_ancestry.append(resumed_run_id)
        r_results_path = r_dir / "results.jsonl"
        if r_results_path.is_file():
            resume_ctx_cache: dict[str, dict[str, Any]] = {}
            with r_results_path.open("r", encoding="utf-8") as rfh:
                for line in rfh:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cid = str(row.get("case_id") or "")
                    btok = int(row.get("budget_tokens") or 8192)
                    prof_id = str(row.get("profile_id") or "")
                    r_seed = int(row["seed"]) if row.get("seed") is not None else None
                    http_st = (row.get("metrics") or {}).get("http_status")
                    if (
                        cid
                        and prof_id
                        and isinstance(row.get("response"), dict)
                        and not row.get("error")
                        and http_st in (None, 200)
                    ):
                        row["response"] = rehydrate_response_envelope(
                            r_dir, row["response"], cache=resume_ctx_cache
                        )
                        prior_rows[(cid, btok, prof_id, r_seed)] = row

    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    frozen_cases_path = inputs_dir / "cases.jsonl"
    frozen_cases_path.write_bytes(cases_bytes)

    uses_wahs_engine = any(
        not p.lower().startswith("raw-fhir:") for p in active_profiles
    )
    frozen_provenance = copy_target_provenance(target_provenance)
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="wahs-evaluation",
        git_sha=git_sha,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_mapping_version="fhir-r4-uscore-ips@v1",
        gen_ai_provider_name="wahs-engine" if uses_wahs_engine else "raw-fhir",
        gen_ai_operation_name="wahs_condense_and_qa",
        evidence_status="development",
        target_provenance=frozen_provenance,
        report_family="wahs",
        suite_id=cases_file.stem,
        suite_sha256=suite_sha256,
        resumed_from=resumed_run_id,
        resume_ancestry=resume_ancestry,
    )
    manifest_path = run_dir / "run_manifest.json"
    events_path = run_dir / "events.jsonl"
    manifest_payload = manifest.to_dict()
    manifest_payload["expected_cells"] = expected_cells
    manifest_payload["temperature"] = norm_temp
    if budgets is not None:
        manifest_payload["budgets"] = [int(b) for b in budgets]
    manifest_payload["profiles"] = active_profiles
    if eff_prompt_override:
        manifest_payload["prompt_override"] = eff_prompt_override
    if seeds is not None:
        manifest_payload["seeds"] = [int(s) for s in seeds]
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    single_budget_mode = max_budgets_per_profile == 1

    def _format_scenario_id(case_id: str, b_tokens: int, seed_val: int | None) -> str:
        base_s = case_id if single_budget_mode else f"{case_id}__b{int(b_tokens)}"
        if multi_seed_mode and seed_val is not None:
            return f"{base_s}__s{int(seed_val)}"
        return base_s

    plan_items: list[CellPlanItem] = []
    scen_case_by_sid: dict[str, WahsEvalCase] = {}
    planned_cells_meta: list[dict[str, Any]] = []
    for prof_id in active_profiles:
        for seed_val in active_seeds:
            for case in cases:
                active_budgets = _budgets_for_profile_case(prof_id, case)
                for b_tokens in active_budgets:
                    scenario_id = _format_scenario_id(case.case_id, b_tokens, seed_val)
                    scen_case_by_sid.setdefault(scenario_id, case)
                    ck = (case.case_id, b_tokens, prof_id, seed_val)
                    plan_items.append(
                        CellPlanItem(
                            cell_key=ck,
                            scenario_id=scenario_id,
                            backend_id=prof_id,
                            turn=1,
                            seed=seed_val,
                            payload=(case, b_tokens, prof_id, seed_val, scenario_id),
                        )
                    )
                    planned_cells_meta.append(
                        {
                            "scenario_id": scenario_id,
                            "backend_id": prof_id,
                            "turns": 1,
                        }
                    )

    run_event_payload: dict[str, Any] = {
        "event_type": "run",
        "run_id": run_id,
        "component": "wahs-evaluation",
        "suite_sha256": suite_sha256,
        "expected_cells": len(expected_cells),
        "reference_date": "2026-11-11",
        "comparison_set": cases_file.stem,
        "scenario_ids": list(scen_case_by_sid.keys()),
        "backend_ids": active_profiles,
        "cells": planned_cells_meta,
    }
    if norm_temp is not None:
        run_event_payload["temperature"] = norm_temp
    if seeds is not None:
        run_event_payload["seeds"] = [int(s) for s in seeds]
    append_event(events_path, run_event_payload)

    scenarios_dir = inputs_dir / "scenarios"
    for sid, case_obj in scen_case_by_sid.items():
        _write_scenario_input_file(scenarios_dir, case_obj, sid, config_path=eff_config_path)
    _write_scenario_and_chart_inputs(
        run_dir,
        cases,
        {},
        client=client,
        scenario_ids=list(scen_case_by_sid.keys()),
        config_path=eff_config_path,
    )
    for prof_id in active_profiles:
        label = _profile_display_label(prof_id, config_path=eff_config_path)
        append_event(
            events_path,
            {
                "event_type": "backend_selected",
                "backend_id": prof_id,
                "label": label,
            },
        )
    _write_run_meta_preserving_hardware(
        run_dir,
        {"arm_cards": {bid: _wahs_arm_card(bid, config_path=eff_config_path) for bid in active_profiles}},
        client=client,
    )

    results_path = run_dir / "results.jsonl"
    scores: list[WahsCaseScore] = []
    cell_meta_list: list[dict[str, Any]] = []

    def _assemble_row(
        case: WahsEvalCase,
        b_tokens: int,
        prof_id: str,
        seed_val: int | None,
        scenario_id: str,
        full_envelope: dict[str, Any],
        started_iso: str,
        ended_iso: str,
    ) -> dict[str, Any]:
        score = score_wahs_case(case, full_envelope, budget_tokens=b_tokens)
        scores.append(score)
        parsed_prof = parse_wahs_profile_spec(
            prof_id,
            b_tokens,
            config_path=eff_config_path,
            default_prompt=eff_prompt_override,
            strict=False,
        )
        wahs_profile = str(full_envelope.get("wahs_profile") or parsed_prof.wahs_profile)
        prompt_id = full_envelope.get("prompt_id") or parsed_prof.prompt_override
        prompt_sha256 = full_envelope.get("prompt_sha256")
        active_enrichers = list(
            full_envelope.get("active_enrichers")
            if isinstance(full_envelope.get("active_enrichers"), list)
            else (parsed_prof.explicit_enrichers or parsed_prof.configured_enrichers)
        )
        enrichment_tokens = int(full_envelope.get("enrichment_tokens") or 0)
        slim_envelope = slim_response_envelope(
            run_dir,
            scenario_id,
            case.patient_id,
            full_envelope,
            extra_valid_uuids=list(case.valid_uuids),
        )
        req_meta: dict[str, Any] = {
            "patient": case.patient_id,
            "prompt": case.prompt,
            "question": case.prompt,
            "budget_tokens": b_tokens,
            "wahs_profile": wahs_profile,
            "profile": prof_id,
        }
        if prompt_id:
            req_meta["prompt_id"] = prompt_id
        if seed_val is not None:
            req_meta["seed"] = seed_val
        if norm_temp is not None:
            req_meta["temperature"] = norm_temp
        m_fam, underlying_m = _infer_model_family_and_id(prof_id, config_path=eff_config_path)
        lat_ms = int(full_envelope.get("latency_ms") or 0)
        timings_obj = (
            dict(full_envelope["timings"])
            if isinstance(full_envelope.get("timings"), dict)
            else {}
        )
        row: dict[str, Any] = {
            "case_id": case.case_id,
            "patient_id": case.patient_id,
            "use_case": case.use_case,
            "budget_tokens": b_tokens,
            "wahs_profile": wahs_profile,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "active_enrichers": active_enrichers,
            "enrichment_tokens": enrichment_tokens,
            "request": req_meta,
            "response": slim_envelope,
            "score": score.to_dict(),
            "profile_id": prof_id,
            "model_family": m_fam,
            "underlying_model": underlying_m,
            "scenario_id": scenario_id,
            "backend_id": prof_id,
            "turn": 1,
            "started_at": started_iso,
            "ended_at": ended_iso,
            "metrics": {
                "total_ms": lat_ms,
                "latency_ms": lat_ms,
                "prompt_ms": round(float(timings_obj.get("prompt_ms") or 0.0), 2),
                "predicted_ms": round(float(timings_obj.get("predicted_ms") or 0.0), 2),
                "engine_prep_ms": round(float(timings_obj.get("engine_prep_ms") or 0.0), 2),
                "http_status": 200,
                "answer_chars": len(str(full_envelope.get("answer") or "")),
                "citation_count": len(full_envelope.get("references") or []),
            },
        }
        if seed_val is not None:
            row["seed"] = seed_val
        cell_meta_list.append(
            {
                "profile_id": prof_id,
                "wahs_profile": wahs_profile,
                "prompt_id": prompt_id,
                "prompt_sha256": prompt_sha256,
                "active_enrichers": active_enrichers,
                "enrichment_tokens": enrichment_tokens,
                "model_family": m_fam,
                "underlying_model": underlying_m,
                "seed": seed_val,
                "latency_ms": lat_ms,
                "timings": timings_obj,
            }
        )
        return row

    warmup_lock = threading.Lock()
    last_warmed_model: list[str | None] = [None]

    def _maybe_warmup_model(prof_id: str, _b_tokens: int) -> None:
        if os.environ.get("WAHS_WARMUP_ON_MODEL_SWITCH", "1") == "0":
            return
        warmup_fn = getattr(client, "warmup_model", None)
        if not callable(warmup_fn):
            return
        is_live_requests = type(getattr(client, "_session", None)) is requests.Session
        is_custom_override = (
            hasattr(type(client), "warmup_model")
            and type(client).warmup_model is not WahsHubClient.warmup_model
        )
        if not (
            is_live_requests
            or is_custom_override
            or os.environ.get("WAHS_WARMUP_ON_MODEL_SWITCH") == "force"
        ):
            return
        _, underlying_m = _infer_model_family_and_id(prof_id, config_path=eff_config_path)
        model_arg = str(underlying_m or "").strip()
        if not model_arg:
            return
        with warmup_lock:
            if last_warmed_model[0] == model_arg:
                return
            warmup_fn(model_arg)
            last_warmed_model[0] = model_arg

    def _exec_cell(item: CellPlanItem) -> dict[str, Any]:
        case, b_tokens, prof_id, seed_val, scenario_id = item.payload
        _maybe_warmup_model(prof_id, b_tokens)
        started_iso = datetime.now(timezone.utc).isoformat()
        full_envelope = _invoke_client_evaluate_case(
            client,
            case,
            budget_tokens=b_tokens,
            profile_id=prof_id,
            seed=seed_val,
            temperature=temperature,
        )
        ended_iso = datetime.now(timezone.utc).isoformat()
        return _assemble_row(
            case,
            b_tokens,
            prof_id,
            seed_val,
            scenario_id,
            dict(full_envelope),
            started_iso,
            ended_iso,
        )

    def _resume_cell(item: CellPlanItem, prior: dict[str, Any]) -> dict[str, Any]:
        case, b_tokens, prof_id, seed_val, scenario_id = item.payload
        now_iso = datetime.now(timezone.utc).isoformat()
        return _assemble_row(
            case,
            b_tokens,
            prof_id,
            seed_val,
            scenario_id,
            dict(prior["response"]),
            str(prior.get("started_at") or now_iso),
            str(prior.get("ended_at") or now_iso),
        )

    def _on_error_cell(item: CellPlanItem, exc: Exception, http_code: int) -> dict[str, Any]:
        case, b_tokens, prof_id, seed_val, scenario_id = item.payload
        now_iso = datetime.now(timezone.utc).isoformat()
        err_msg = f"{type(exc).__name__}: {exc}"[:500]
        score = _missing_cell_score(case, b_tokens, reason=err_msg)
        scores.append(score)
        parsed_prof = parse_wahs_profile_spec(
            prof_id,
            b_tokens,
            config_path=eff_config_path,
            default_prompt=eff_prompt_override,
            strict=False,
        )
        req_meta: dict[str, Any] = {
            "patient": case.patient_id,
            "prompt": case.prompt,
            "question": case.prompt,
            "budget_tokens": b_tokens,
            "wahs_profile": parsed_prof.wahs_profile,
            "profile": prof_id,
        }
        if seed_val is not None:
            req_meta["seed"] = seed_val
        if norm_temp is not None:
            req_meta["temperature"] = norm_temp
        m_fam, underlying_m = _infer_model_family_and_id(prof_id, config_path=eff_config_path)
        row: dict[str, Any] = {
            "case_id": case.case_id,
            "patient_id": case.patient_id,
            "use_case": case.use_case,
            "budget_tokens": b_tokens,
            "wahs_profile": parsed_prof.wahs_profile,
            "prompt_id": parsed_prof.prompt_override,
            "prompt_sha256": None,
            "active_enrichers": [],
            "enrichment_tokens": 0,
            "request": req_meta,
            "response": None,
            "error": err_msg,
            "score": score.to_dict(),
            "profile_id": prof_id,
            "model_family": m_fam,
            "underlying_model": underlying_m,
            "scenario_id": scenario_id,
            "backend_id": prof_id,
            "turn": 1,
            "started_at": now_iso,
            "ended_at": now_iso,
            "metrics": {
                "total_ms": 0,
                "latency_ms": 0,
                "prompt_ms": 0.0,
                "predicted_ms": 0.0,
                "engine_prep_ms": 0.0,
                "http_status": http_code or 500,
                "answer_chars": 0,
                "citation_count": 0,
            },
        }
        if seed_val is not None:
            row["seed"] = seed_val
        cell_meta_list.append(
            {
                "profile_id": prof_id,
                "wahs_profile": parsed_prof.wahs_profile,
                "prompt_id": parsed_prof.prompt_override,
                "prompt_sha256": None,
                "active_enrichers": [],
                "enrichment_tokens": 0,
                "model_family": m_fam,
                "underlying_model": underlying_m,
                "seed": seed_val,
                "latency_ms": 0,
                "timings": {},
            }
        )
        return row

    execute_cell_matrix(
        plan_items,
        run_dir=run_dir,
        output_dir=Path(output_dir),
        execute_cell=_exec_cell,
        completed_rows=prior_rows,
        on_resume_cell=_resume_cell,
        on_error_cell=_on_error_cell,
        isolate_errors=True,
        events_path=events_path,
        run_id=run_id,
    )

    _write_judge_prep_artifacts(
        run_dir,
        cases,
        active_profiles,
        client,
        {},
        config_path=eff_config_path,
    )

    summary = _summarize_scores(
        scores,
        cell_meta_list=cell_meta_list,
        config_path=eff_config_path,
    )
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _sync_wahs_run_metadata(
        run_dir,
        cases=cases,
        scores=scores,
        cell_meta_list=cell_meta_list,
        summary=summary,
        config_path=eff_config_path,
    )
    append_event(
        events_path,
        {
            "event_type": "evaluation",
            "run_id": run_id,
            "check": "wahs_suite",
            "total_cells": summary["total_cells"],
            "passed_cells": summary["passed_cells"],
            "summary_path": "summary.json",
        },
    )
    return WahsRunResult(
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        results_path=results_path,
        summary_path=summary_path,
        total_cells=summary["total_cells"],
        passed_cells=summary["passed_cells"],
        summary=summary,
    )


def score_wahs_run(
    run_dir: Path | str,
    *,
    patients_summary: str | None = None,
    bundle_dirs: Sequence[Path | str] | None = None,
    profiles_config_path: Path | str | None = None,
) -> dict[str, Any]:
    """Re-score a frozen WAHS run directory offline without network or target access."""
    rdir = Path(run_dir)
    cases_path = rdir / "inputs" / "cases.jsonl"
    if not cases_path.is_file():
        cases_path = rdir / "inputs" / "wahs_eval_cases.jsonl"
    results_path = rdir / "results.jsonl"
    manifest_path = rdir / "run_manifest.json"
    manifest_data: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    from harness.validate.context_store import rehydrate_response_envelope

    cases = load_wahs_cases(cases_path)
    cases_by_id = {c.case_id: c for c in cases}

    recorded_rows: dict[tuple[str, int, str | None, str | None, str | None, int | None], dict[str, Any]] = {}
    observed_order: list[tuple[str, int, str | None, str | None, str | None, int | None]] = []
    ctx_cache: dict[str, dict[str, Any]] = {}
    if results_path.is_file():
        with results_path.open("r", encoding="utf-8") as rfh:
            for line in rfh:
                if not line.strip():
                    continue
                row = json.loads(line)
                cid = str(row["case_id"])
                b_tokens = int(row.get("budget_tokens") or 8192)
                c_arm = row.get("context_arm")
                c_mode = row.get("condense_mode")
                prof_id = row.get("profile_id")
                r_seed = int(row["seed"]) if row.get("seed") is not None else None
                key = (cid, b_tokens, c_arm, c_mode, prof_id, r_seed)
                recorded_rows[key] = row
                if key not in observed_order:
                    observed_order.append(key)

    expected_keys: list[tuple[str, int, str | None, str | None, str | None, int | None]] = []
    raw_expected = manifest_data.get("expected_cells")
    if isinstance(raw_expected, list) and raw_expected:
        for item in raw_expected:
            if isinstance(item, dict) and "case_id" in item:
                key = (
                    str(item["case_id"]),
                    int(item.get("budget_tokens") or 8192),
                    item.get("context_arm"),
                    item.get("condense_mode"),
                    item.get("profile_id"),
                    int(item["seed"]) if item.get("seed") is not None else None,
                )
                if key not in expected_keys:
                    expected_keys.append(key)
    else:
        manifest_budgets = manifest_data.get("budgets")
        manifest_profiles = manifest_data.get("profiles")
        manifest_seeds = manifest_data.get("seeds")
        active_profiles: list[str | None] = (
            [str(p) for p in manifest_profiles]
            if isinstance(manifest_profiles, list) and manifest_profiles
            else [None]
        )
        active_seeds: list[int | None] = (
            [int(s) for s in manifest_seeds]
            if isinstance(manifest_seeds, list) and manifest_seeds
            else [None]
        )
        for seed_val in active_seeds:
            for case in cases:
                active_budgets = (
                    [int(b) for b in manifest_budgets]
                    if isinstance(manifest_budgets, list) and manifest_budgets
                    else [int(b) for b in (case.target_token_budgets or DEFAULT_TOKEN_BUDGETS)]
                )
                for b_tokens in active_budgets:
                    for prof_id in active_profiles:
                        key = (case.case_id, b_tokens, None, None, prof_id, seed_val)
                        if key not in expected_keys:
                            expected_keys.append(key)
        for key in observed_order:
            if key not in expected_keys:
                expected_keys.append(key)

    scores: list[WahsCaseScore] = []
    cell_meta_list: list[dict[str, Any]] = []
    missing_cells: list[dict[str, Any]] = []
    expectations_path = rdir / "expectations.jsonl"
    with expectations_path.open("w", encoding="utf-8") as exp_fh:
        for cid, b_tokens, c_arm, c_mode, prof_id, seed_val in expected_keys:
            case = cases_by_id[cid]
            row = recorded_rows.get((cid, b_tokens, c_arm, c_mode, prof_id, seed_val))
            default_w_prof = _infer_wahs_profile(prof_id, config_path=profiles_config_path)
            if row is None or row.get("error") or not isinstance(row.get("response"), dict):
                err_msg = (
                    f"evaluation error for cell ({cid}, {b_tokens}): {row.get('error')}"
                    if row and row.get("error")
                    else f"missing or incomplete evaluation result for cell ({cid}, {b_tokens})"
                )
                score = _missing_cell_score(case, b_tokens, reason=err_msg)
                missing_entry = _cell_dict(cid, b_tokens, profile_id=prof_id, seed=seed_val)
                if c_arm is not None:
                    missing_entry["context_arm"] = c_arm
                if c_mode is not None:
                    missing_entry["condense_mode"] = c_mode
                missing_cells.append(missing_entry)
                if prof_id:
                    m_fam, underlying_m = _infer_model_family_and_id(
                        prof_id, config_path=profiles_config_path
                    )
                    cell_meta_list.append(
                        {
                            "profile_id": prof_id,
                            "wahs_profile": default_w_prof,
                            "prompt_id": row.get("prompt_id") if row else None,
                            "prompt_sha256": row.get("prompt_sha256") if row else None,
                            "active_enrichers": [],
                            "enrichment_tokens": 0,
                            "model_family": m_fam,
                            "underlying_model": underlying_m,
                            "seed": seed_val,
                            "latency_ms": 0,
                            "timings": {},
                        }
                    )
                else:
                    cell_meta_list.append({"seed": seed_val})
            else:
                raw_env = row.get("response") or {}
                env = (
                    rehydrate_response_envelope(rdir, raw_env, cache=ctx_cache)
                    if isinstance(raw_env, dict)
                    else {}
                )
                score = score_wahs_case(case, env, budget_tokens=b_tokens)
                row["score"] = score.to_dict()
                row["passed"] = score.passed
                req_d = row.get("request")
                if not isinstance(req_d, dict):
                    req_d = {}
                    row["request"] = req_d
                req_d.setdefault("patient", str(row.get("patient_id") or case.patient_id))
                if prof_id:
                    m_fam, underlying_m = _infer_model_family_and_id(
                        prof_id, config_path=profiles_config_path
                    )
                    w_prof = str(
                        row.get("wahs_profile")
                        or env.get("wahs_profile")
                        or default_w_prof
                    )
                    timings_obj = (
                        dict(env["timings"]) if isinstance(env.get("timings"), dict) else {}
                    )
                    cell_meta_list.append(
                        {
                            "profile_id": prof_id,
                            "wahs_profile": w_prof,
                            "prompt_id": row.get("prompt_id") or env.get("prompt_id"),
                            "prompt_sha256": row.get("prompt_sha256") or env.get("prompt_sha256"),
                            "active_enrichers": list(
                                row.get("active_enrichers")
                                or env.get("active_enrichers")
                                or []
                            ),
                            "enrichment_tokens": int(
                                row.get("enrichment_tokens")
                                or env.get("enrichment_tokens")
                                or 0
                            ),
                            "model_family": str(row.get("model_family") or m_fam),
                            "underlying_model": str(row.get("underlying_model") or underlying_m),
                            "seed": seed_val,
                            "latency_ms": int(env.get("latency_ms") or 0),
                            "timings": timings_obj,
                        }
                    )
                else:
                    cell_meta_list.append({"seed": seed_val})
            scores.append(score)
            exp_fh.write(json.dumps(score.to_dict()) + "\n")

    missing_scenario_files = {
        str(row.get("scenario_id") or row.get("case_id") or "")
        for row in recorded_rows.values()
        if (row.get("scenario_id") or row.get("case_id"))
        and (
            not (rdir / "inputs" / "charts" / f"{row.get('scenario_id') or row.get('case_id')}.json").is_file()
            or not (rdir / "inputs" / "scenarios" / f"{row.get('scenario_id') or row.get('case_id')}.json").is_file()
        )
    }
    if missing_scenario_files:
        observed_envelopes: dict[str, dict[str, Any]] = {}
        for row in recorded_rows.values():
            scen_id = str(row.get("scenario_id") or row.get("case_id") or "")
            if scen_id not in missing_scenario_files:
                continue
            raw_env = row.get("response")
            if isinstance(raw_env, dict):
                env = rehydrate_response_envelope(rdir, raw_env, cache=ctx_cache)
                observed_envelopes[scen_id] = _merge_scenario_envelopes(
                    observed_envelopes.get(scen_id),
                    env,
                )
        if observed_envelopes:
            resolver_client = (
                WahsHubClient(bundle_dirs=bundle_dirs, profiles_config_path=profiles_config_path)
                if bundle_dirs
                else None
            )
            _write_scenario_and_chart_inputs(
                rdir,
                cases,
                observed_envelopes,
                client=resolver_client,
                config_path=profiles_config_path,
            )

    summary = _summarize_scores(
        scores,
        missing_cells=missing_cells,
        cell_meta_list=cell_meta_list,
        config_path=profiles_config_path,
    )
    (rdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _sync_wahs_run_metadata(
        rdir,
        cases=cases,
        scores=scores,
        cell_meta_list=cell_meta_list,
        summary=summary,
        patients_summary=patients_summary,
        config_path=profiles_config_path,
    )
    return summary


_WAHS_PATIENT_PROFILES: dict[str, dict[str, Any]] = {
    "Maurice742_Auer97": {
        "badge": "Synthea Longitudinal Chart",
        "display": "Maurice Auer: Multi-year outpatient & inpatient history (~94k tokens)",
        "medications": [
            "Tacrolimus / cardiovascular longitudinal history",
            "Multi-specialty renal, cardiac & primary care",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Maurice742_Auer97_set_b": {
        "badge": "Synthea Longitudinal Chart",
        "display": "Maurice Auer: Multi-year outpatient & inpatient history (~94k tokens)",
        "medications": [
            "Tacrolimus (immunosuppression)",
            "Furosemide / Warfarin longitudinal history",
            "Multi-specialty renal, cardiac & hematology care",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "MIMIC_10014354_ICU_Heme_Cardiorenal": {
        "badge": "MIMIC-IV ICU & Hematology Chart",
        "display": "Complex ICU, Hematology & Cardiorenal Admission (~128k tokens; 1,100+ records)",
        "medications": [
            "Vancomycin (held for trough 28.4 ug/mL & acute kidney injury)",
            "Apixaban 5 mg BID (active) vs. Warfarin (discontinued)",
            "Norepinephrine & Furosemide ICU infusions",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b": {
        "badge": "MIMIC-IV ICU & Hematology Chart",
        "display": "Complex ICU, Hematology & Cardiorenal Admission (~128k tokens; 1,100+ records across 2022-2026)",
        "medications": [
            "Vancomycin (held for trough 28.4 ug/mL & acute kidney injury)",
            "Apixaban 5 mg BID (active) vs. Warfarin (discontinued)",
            "Norepinephrine & Furosemide ICU infusions",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "MIMIC_10019003_ICU_Hepatopulmonary": {
        "badge": "MIMIC-IV ICU Hepatopulmonary Chart",
        "display": "Decompensated Cirrhosis, Hepatorenal & ICU Admission (~110k tokens; long narrative notes)",
        "medications": [
            "Lactulose, Rifaximin & Spironolactone/Furosemide",
            "Albumin & vasoactive ICU support",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Marcus_Vance_Oncology_Immunotherapy": {
        "badge": "Multi-Clinic Oncology & Immunotherapy",
        "display": "Marcus Vance: Metastatic melanoma on checkpoint immunotherapy across clinics",
        "medications": [
            "Pembrolizumab / immune-related colitis & thyroiditis monitoring",
            "Prednisone taper & oncology specialty notes",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Elena_Rostova_Cardiorenal": {
        "badge": "Multi-Clinic Cardiorenal Chart",
        "display": "Elena Rostova: HFrEF, CKD Stage 3b & hyperkalemia cross-clinic reconciliation",
        "medications": [
            "Sacubitril/Valsartan, Empagliflozin, Carvedilol & Spironolactone",
            "Cross-clinic potassium & creatinine longitudinal trends",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Margaret_Chen_Polypharmacy": {
        "badge": "Polypharmacy & 42 CFR Part 2 / MHMDA Privacy",
        "display": "Margaret Chen: Multi-clinic polypharmacy with protected behavioral health / SDOH records",
        "medications": [
            "Diabetes, hypertension & geriatric polypharmacy regimen",
            "Protected SDOH & behavioral health entries",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Arthur_Pendelton_Anticoag": {
        "badge": "Anticoagulation & Cross-Clinic Reconciliation",
        "display": "Arthur Pendelton: Atrial fibrillation anticoagulation switch & renal dosing",
        "medications": [
            "Apixaban vs. Warfarin cross-clinic reconciliation",
            "INR & renal function monitoring",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Sofia_Alvarez_Maternal_Endocrine": {
        "badge": "Maternal, Endocrine & Privacy Chart",
        "display": "Sofia Alvarez: Pregnancy-adjacent hypertension, CKD Stage 3a, latex allergy, and sensitive social history",
        "medications": [
            "Amlodipine / Norvasc 5 mg duplicate reconciliation",
            "Ibuprofen NSAID renal and maternal safety review",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "Batch01_Synthea_HIV_Outpatient": {
        "badge": "Synthea HIV & Primary Care Cohort",
        "display": "Longitudinal outpatient HIV & primary-care charts",
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
}


def _wahs_patient_profile(patient_id: str) -> dict[str, Any]:
    known = _WAHS_PATIENT_PROFILES.get(patient_id)
    if known:
        return dict(known)
    for sfx in ("_set_b", "_set_a", "_multisource"):
        if patient_id.endswith(sfx):
            k2 = _WAHS_PATIENT_PROFILES.get(patient_id[: -len(sfx)])
            if k2:
                return dict(k2)
    return {
        "badge": "Clinical Chart",
        "display": patient_id.replace("_", " "),
        "chart_url": "https://wahs-demo.openclinai.org/",
    }


def _wahs_arm_card(
    backend_id: str,
    *,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    raw_id = str(backend_id or "").strip()
    parsed = parse_wahs_profile_spec(raw_id, config_path=config_path, strict=False)
    budget_tag = parsed.budget_tag or ""
    budget_suffix = f" · {budget_tag} chart" if budget_tag else ""
    short_budget = f" ({budget_tag})" if budget_tag else ""
    prompt_title_tag = f" · prompt={parsed.inline_prompt}" if parsed.inline_prompt else ""
    prompt_short_tag = f" [{parsed.inline_prompt}]" if parsed.inline_prompt else ""

    underlying = parsed.model_id or parsed.api_profile_id
    b_low = parsed.api_profile_id.lower()
    u_low = underlying.lower()

    model_info: dict[str, str] = {"family": "Gemma 4", "params": "12B", "quant": "Q8_0"}
    short_model = "Gemma 12B"
    full_model = "Gemma 4 12B"
    if "12b-q4" in b_low or "12b-q4" in u_low:
        model_info = {"family": "Gemma 4", "params": "12B", "quant": "Q4_K_M"}
        short_model = "Gemma 12B Q4"
        full_model = "Gemma 4 12B (Q4)"
    elif "qwen3-4b" in b_low or "qwen3-4b" in u_low:
        model_info = {"family": "Qwen 3", "params": "4B", "quant": "Q8_0"}
        short_model = "Qwen3 4B"
        full_model = "Qwen 3 4B"
    elif "qwen35-9b" in b_low or "qwen3.5-9b" in u_low or "qwen3:8b" in u_low:
        model_info = {"family": "Qwen 3.5", "params": "9B", "quant": "Q6_K"}
        short_model = "Qwen 3.5 9B"
        full_model = "Qwen 3.5 9B"
    elif "qwen3-14b" in b_low or "qwen3-14b" in u_low or "qwen3:14b" in u_low:
        model_info = {"family": "Qwen 3", "params": "14B", "quant": "Q8_0"}
        short_model = "Qwen3 14B"
        full_model = "Qwen 3 14B"
    elif "llama32-3b" in b_low or "llama-3.2-3b" in u_low:
        model_info = {"family": "Llama 3", "params": "3B", "quant": "Q8_0"}
        short_model = "Llama 3.2 3B"
        full_model = "Llama 3.2 3B"
    elif "llama31-8b" in b_low or "llama-3.1-8b" in u_low or "llama3.1:8b" in u_low:
        model_info = {"family": "Llama 3", "params": "8B", "quant": "Q8_0"}
        short_model = "Llama 3.1 8B"
        full_model = "Llama 3.1 8B"
    elif "hermes3-8b" in b_low or "hermes3-8b" in u_low:
        model_info = {"family": "Llama 3", "params": "8B", "quant": "Q8_0"}
        short_model = "Hermes 3 8B"
        full_model = "Hermes 3 (Llama 3.1) 8B"
    elif "medgemma-1.5-4b" in u_low or "medgemma-4b" in b_low:
        model_info = {"family": "MedGemma", "params": "4B", "quant": "Q8_0"}
        short_model = "MedGemma 4B"
        full_model = "MedGemma 1.5 4B"
    elif "e4b" in b_low or "4b" in b_low or "e4b" in u_low:
        model_info = {"family": "Gemma 4", "params": "E4B", "quant": "Q8_0"}
        short_model = "Gemma E4B"
        full_model = "Gemma 4 E4B"
    elif "26b" in b_low or "26b" in u_low:
        model_info = {"family": "Gemma 4", "params": "26B-A4B MoE", "quant": "Q4_K_M"}
        short_model = "Gemma 26B"
        full_model = "Gemma 4 26B-A4B MoE"
    elif "27b" in b_low or "medgemma" in u_low:
        model_info = {"family": "MedGemma", "params": "27B", "quant": "Q8_0"}
        short_model = "MedGemma 27B"
        full_model = "MedGemma 27B"
    elif "qwen35b" in b_low:
        model_info = {"family": "Qwen 3", "params": "35B MoE", "quant": "Q8_0"}
        short_model = "Qwen 35B"
        full_model = "Qwen 3 35B"
    elif "qwen30b" in b_low:
        model_info = {"family": "Qwen 3 Coder", "params": "30B MoE", "quant": "Q8_0"}
        short_model = "Qwen Coder 30B"
        full_model = "Qwen 3 Coder 30B"
    elif "lfm24b" in b_low:
        model_info = {"family": "Liquid LFM2", "params": "24B", "quant": "Q8_0"}
        short_model = "Liquid 24B"
        full_model = "Liquid LFM2 24B"

    prof_cfg = parsed.profile_config
    if parsed.kind == "raw-fhir":
        title = f"Offline Raw FHIR Baseline · No Condensation ({full_model}{budget_suffix}{prompt_title_tag})"
        short_title = f"Raw FHIR · {short_model}{short_budget}{prompt_short_tag}"
        path_desc = (
            "Offline Raw Chart Baseline: uncondensed raw FHIR R4 Bundle JSON (with UTF-8 decoded clinical note attachments) "
            "without wahs-engine deduplication, condensation, or [N] citation mapping"
        )
    elif parsed.kind == "wahs" and parsed.explicit_enrichers and not prof_cfg:
        mods_title = " + ".join(parsed.explicit_enrichers)
        mods_short = "+".join(parsed.explicit_enrichers)
        title = f"WAHS + {mods_title} ({full_model}{budget_suffix}{prompt_title_tag})"
        short_title = f"+{mods_short} · {short_model}{short_budget}{prompt_short_tag}"
        path_desc = f"Standalone wahs-engine verbatim condensation + ad-hoc enrichers ({mods_title})"
    elif parsed.kind == "wahs" and prof_cfg:
        title_suffix = str(prof_cfg.get("title_suffix") or f"WAHS {parsed.wahs_profile}")
        short_suffix = str(prof_cfg.get("short_suffix") or parsed.wahs_profile)
        title = f"{title_suffix} ({full_model}{budget_suffix}{prompt_title_tag})"
        short_title = f"{short_suffix} · {short_model}{short_budget}{prompt_short_tag}"
        path_desc = str(
            prof_cfg.get("description")
            or f"Standalone wahs-engine profile {parsed.wahs_profile!r}"
        )
    else:
        arm_label = parsed.wahs_profile or parsed.api_profile_id or raw_id or "custom"
        title = f"WAHS Arm · {arm_label} ({full_model}{budget_suffix}{prompt_title_tag})"
        short_title = f"{arm_label} · {short_model}{short_budget}{prompt_short_tag}"
        path_desc = f"WAHS evaluation arm {raw_id or arm_label}"

    model_info["id"] = underlying or raw_id
    return {
        "title": title,
        "short_title": short_title,
        "kind": "single",
        "path": path_desc,
        "models": [model_info],
    }


def _guardrail_entry(
    gid: str,
    label: str,
    scope: str,
    passed: int,
    total: int,
    *,
    status: str,
    detail: str,
) -> dict[str, Any]:
    ci = wilson_ci_95(passed, total)
    return {
        "id": gid,
        "label": label,
        "scope": scope,
        "passed": int(passed),
        "total": int(total),
        "pass_rate": round(passed / max(total, 1), 4),
        "ci95_low": ci.get("ci95_low"),
        "ci95_high": ci.get("ci95_high"),
        "status": status,
        "detail": detail,
    }


def _build_wahs_domain_guardrails(
    cases: list[WahsEvalCase],
    scores: list[WahsCaseScore],
    cell_meta_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cases_by_id = {c.case_id: c for c in cases}
    engine_pairs: list[tuple[WahsCaseScore, WahsEvalCase | None]] = []
    raw_pairs: list[tuple[WahsCaseScore, WahsEvalCase | None]] = []
    for idx, s in enumerate(scores):
        meta = cell_meta_list[idx] if idx < len(cell_meta_list) else {}
        w_prof = str(meta.get("wahs_profile") or "")
        c_obj = cases_by_id.get(s.case_id)
        if w_prof == "raw-fhir":
            raw_pairs.append((s, c_obj))
        else:
            engine_pairs.append((s, c_obj))

    active_pairs = engine_pairs if engine_pairs else [(s, cases_by_id.get(s.case_id)) for s in scores]
    engine_scope = "WAHS Engine setups" if raw_pairs else "All evaluated setups"
    out: list[dict[str, Any]] = []

    if active_pairs:
        t_passed = sum(1 for s, _ in active_pairs if s.token_budget_ok)
        t_total = len(active_pairs)
        violations = t_total - t_passed
        out.append(
            _guardrail_entry(
                "token_budget_compliance",
                "Token Budget Compliance Gate",
                engine_scope,
                t_passed,
                t_total,
                status="pass" if violations == 0 else "fail",
                detail=(
                    f"{t_passed}/{t_total} cells stayed within their target condensed-chart "
                    f"token budget ({violations} over-budget)"
                ),
            )
        )

        c_passed = sum(1 for s, _ in active_pairs if s.fabricated_citation_count == 0)
        c_total = len(active_pairs)
        total_cites = sum(s.citation_count for s, _ in active_pairs)
        resolved_cites = sum(s.resolved_citation_count for s, _ in active_pairs)
        unresolved_cites = sum(s.fabricated_citation_count for s, _ in active_pairs)
        rate = c_passed / max(c_total, 1)
        out.append(
            _guardrail_entry(
                "citation_uuid_resolution",
                "Inline [N] / [K] Citation Resolution Gate",
                engine_scope,
                c_passed,
                c_total,
                status="pass" if unresolved_cites == 0 else ("warn" if rate >= 0.95 else "fail"),
                detail=(
                    f"{c_passed}/{c_total} cells had zero unresolved inline [N] or [K] citations "
                    f"({resolved_cites}/{total_cites} cited indices resolved; "
                    f"{unresolved_cites} unresolved)"
                ),
            )
        )

    if raw_pairs:
        raw_passed = sum(
            1
            for s, _ in raw_pairs
            if s.token_budget_ok and s.fabricated_citation_count == 0
        )
        raw_total = len(raw_pairs)
        out.append(
            _guardrail_entry(
                "raw_fhir_ablation_control",
                "Offline Raw FHIR Baseline (Uncondensed Ablation)",
                "Offline Raw FHIR baseline",
                raw_passed,
                raw_total,
                status="ablation",
                detail=(
                    "Uncondensed raw FHIR R4 JSON without WAHS Engine condensation or "
                    f"[N] UUID citation map ({raw_passed}/{raw_total} passed budget & citation checks)"
                ),
            )
        )

    return out


def _sync_wahs_run_metadata(
    run_dir: Path,
    *,
    cases: list[WahsEvalCase],
    scores: list[WahsCaseScore],
    cell_meta_list: list[dict[str, Any]],
    summary: dict[str, Any],
    patients_summary: str | None = None,
    config_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Write standardized `run_manifest.json`, `run_meta.json`, and `domain_guardrails.json`."""
    rdir = Path(run_dir)
    rows: list[dict[str, Any]] = []
    results_path = rdir / "results.jsonl"
    if results_path.is_file():
        with results_path.open("r", encoding="utf-8") as rfh:
            for line in rfh:
                if not line.strip():
                    continue
                raw_row = json.loads(line)
                req = raw_row.get("request")
                patient_from_req = req.get("patient") if isinstance(req, dict) else None
                rows.append(
                    {
                        "backend_id": raw_row.get("backend_id"),
                        "profile_id": raw_row.get("profile_id"),
                        "budget_tokens": raw_row.get("budget_tokens"),
                        "patient_id": raw_row.get("patient_id"),
                        "request": {"patient": patient_from_req} if patient_from_req else {},
                    }
                )

    backend_ids: list[str] = []
    for r in rows:
        bid = str(r.get("backend_id") or r.get("profile_id") or "")
        if bid and bid not in backend_ids:
            backend_ids.append(bid)

    manifest_path = rdir / "run_manifest.json"
    manifest_data = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )

    if isinstance(manifest_data, dict):
        manifest_data["family"] = "wahs"
        manifest_data["report_family"] = "wahs"
        prof_list = [str(p) for p in (manifest_data.get("profiles") or backend_ids)]
        existing_ctx = manifest_data.get("context")
        if not (isinstance(existing_ctx, dict) and str(existing_ctx.get("text") or "").strip()):
            budgets_seen = sorted(
                {
                    int(r.get("budget_tokens"))
                    for r in rows
                    if isinstance(r.get("budget_tokens"), int)
                    and not isinstance(r.get("budget_tokens"), bool)
                }
            )
            budget_desc = (
                ", ".join(
                    f"{b // 1024}k" if b >= 1024 and b % 1024 == 0 else str(b)
                    for b in budgets_seen
                )
                if budgets_seen
                else "configured"
            )
            seeds_seen = summary.get("seeds") or manifest_data.get("seeds") or []
            seed_clause = (
                f" across {len(seeds_seen)} seeds ({', '.join(str(s) for s in seeds_seen)})"
                if seeds_seen
                else ""
            )
            manifest_data["context"] = {
                "text": (
                    f"What this run evaluates: {len(cases)} clinical scenario{'s' if len(cases) != 1 else ''} "
                    f"across {len(prof_list)} retrieval/model setup{'s' if len(prof_list) != 1 else ''}{seed_clause} "
                    f"at {budget_desc} token budget{'s' if len(budgets_seen) != 1 else ''} "
                    f"({len(rows)} total evaluation cells)."
                ),
                "url": "https://openclinai.org/wahs/llm-strategy/",
                "label": "WAHS LLM & Retrieval Strategy ->",
            }
        patients_map: dict[str, Any] = {}
        for c in cases:
            if c.patient_id and c.patient_id not in patients_map:
                patients_map[c.patient_id] = _wahs_patient_profile(c.patient_id)
        for r in rows:
            pid = str(r.get("patient_id") or (r.get("request") or {}).get("patient") or "")
            if pid and pid not in patients_map:
                patients_map[pid] = _wahs_patient_profile(pid)
        if patients_map:
            manifest_data["patients"] = patients_map

        resolved_pts_summary = patients_summary or str(manifest_data.get("patients_summary") or "").strip()
        if not resolved_pts_summary and backend_ids:
            n_pt = len(patients_map)
            pt_label = (
                f"{n_pt} complex ICU & multi-clinic patient{'s' if n_pt != 1 else ''}"
                if n_pt > 0
                else "Clinical cohort"
            )
            seeds_seen = summary.get("seeds") or []
            seed_tag = f" × {len(seeds_seen)} seeds" if len(seeds_seen) > 1 else ""
            resolved_pts_summary = (
                f"{pt_label} · {len(cases)} clinical question{'s' if len(cases) != 1 else ''} × {len(backend_ids)} setups{seed_tag}"
            )
        if resolved_pts_summary:
            manifest_data["patients_summary"] = resolved_pts_summary
        if manifest_path.is_file() or rows:
            manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    if backend_ids:
        _write_run_meta_preserving_hardware(
            rdir,
            {"arm_cards": {bid: _wahs_arm_card(bid, config_path=config_path) for bid in backend_ids}},
        )

    guardrails = _build_wahs_domain_guardrails(cases, scores, cell_meta_list)
    guardrails_path = rdir / "domain_guardrails.json"
    if guardrails:
        guardrails_path.write_text(
            json.dumps(guardrails, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        guardrails_path.unlink(missing_ok=True)
    return guardrails


def build_wahs_report_packet(
    run_dir: Path | str,
    *,
    patients_summary: str | None = None,
    bundle_dirs: Sequence[Path | str] | None = None,
    profiles_config_path: Path | str | None = None,
) -> dict[str, Any]:
    """Generate a standard OpenClinAI v2 report packet (`report-data.json`, `dashboard-data.json`,
    `run-summary.json`) for a completed WAHS run directory via `build_report()`.
    """
    import shutil
    from harness.validate.report import build_report

    rdir = Path(run_dir).resolve()
    if not (rdir / "results.jsonl").is_file():
        raise FileNotFoundError(f"results.jsonl not found in {rdir}")

    summary = score_wahs_run(
        rdir,
        patients_summary=patients_summary,
        bundle_dirs=bundle_dirs,
        profiles_config_path=profiles_config_path,
    )

    judge_path = rdir / "judge.jsonl"
    deterministic_actor_dir = rdir / "judges" / "wahs-deterministic-rubric-p1"
    if deterministic_actor_dir.is_dir():
        shutil.rmtree(deterministic_actor_dir)
        canon_path = rdir / "judges" / "canonical.json"
        if canon_path.is_file():
            try:
                canon_data = json.loads(canon_path.read_text(encoding="utf-8"))
                if canon_data.get("built_from") == ["wahs-deterministic-rubric-p1"]:
                    canon_path.unlink(missing_ok=True)
                    judge_path.unlink(missing_ok=True)
            except Exception:
                pass

    report_data_path = build_report(rdir)
    run_summary_path = rdir / "run-summary.json"
    dash_data_path = rdir / "dashboard-data.json"
    run_summary = (
        json.loads(run_summary_path.read_text(encoding="utf-8"))
        if run_summary_path.is_file()
        else {}
    )
    return {
        "run_dir": str(rdir),
        "report_data_json": str(report_data_path),
        "dashboard_data_json": str(dash_data_path) if dash_data_path.is_file() else None,
        "run_summary_json": str(run_summary_path),
        "total_cells": summary["total_cells"],
        "passed_cells": summary["passed_cells"],
        "domain_guardrails": run_summary.get("domain_guardrails") or [],
        "scout": run_summary.get("scout") or [],
    }
