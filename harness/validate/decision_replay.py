"""Phase 0a and 0b offline decision-layer replay, calibration, and scoring.

Implements the harness side of ``DECISION-LAYER-2026-10``:
- Phase 0a: context-admission relevance extraction over ``gold.json`` (5 patients,
  8 topics, 7,840 record-topic pairs), leave-one-patient-out splits for Laya
  post-training, per-patient/topic recall and precision, calibration (Brier + ECE
  with >=10 observations per bin), temperature scaling, and Patient 39 renal-record
  admission tracking.
- Phase 0b: trace extraction from ``full-default`` L5 runs (Answer grounding pairs,
  In-Depth attribution pairs and missing-fact reasons, In-Depth review flags,
  Answer reviewer ``(wrong, chart)`` error pairs, and ``stage_timing`` latency
  shares), plus grounding/review-verification metrics and three-band threshold
  fitting (``verified`` green, ``uncertain`` yellow, ``unsupported`` red) on a
  seeded calibration split.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from harness.common.jsonl import read_jsonl
from harness.metadata import utc_now_iso
from harness.validate.adjudicate import weighted_kappa


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), separators=(",", ":")) + "\n")

__all__ = [
    "FORBIDDEN_ROUTES",
    "PATIENT_39_UUID",
    "PATIENT_39_RENAL_UUIDS",
    "TOPIC_QUESTIONS",
    "validate_decision_route",
    "sha256_json",
    "extract_relevance_pairs",
    "leave_one_patient_out_splits",
    "brier_score",
    "expected_calibration_error",
    "fit_temperature_scaling",
    "apply_temperature_scaling",
    "score_relevance_arm",
    "extract_trace_decision_items",
    "compute_stage_timing_summary",
    "fit_three_band_thresholds",
    "apply_three_band_thresholds",
    "build_stratified_adjudication_sheet",
    "score_grounding_and_review_arm",
    "write_replay_bundle",
]

FORBIDDEN_ROUTES = frozenset({"typesafe/jev-router", "jev-router"})

PATIENT_39_UUID = "dd5558ed-1691-11df-97a5-7038c432aabf"
PATIENT_39_RENAL_UUIDS = (
    "c1aede5e-1691-11df-97a5-7038c432aabf",
    "c4c1e455-1691-11df-97a5-7038c432aabf",
    "ccac7083-1691-11df-97a5-7038c432aabf",
)

TOPIC_QUESTIONS: dict[str, str] = {
    "programs": "Is this clinical record relevant to the patient's care programs or program enrollments?",
    "allergies": "Is this clinical record relevant to the patient's allergies or adverse reactions?",
    "medications": "Is this clinical record relevant to the patient's medications or drug orders?",
    "eye": "Is this clinical record relevant to the patient's eye or vision findings?",
    "heart": "Is this clinical record relevant to the patient's heart or cardiovascular findings?",
    "fractures": "Is this clinical record relevant to bone fractures or musculoskeletal injuries?",
    "kidney": "Is this clinical record relevant to the patient's kidney or renal function (including serum creatinine or eGFR)?",
    "mental": "Is this clinical record relevant to the patient's mental health or psychiatric findings?",
}


def validate_decision_route(route: str) -> str:
    """Refuse router products (`typesafe/jev-router`) per DECISION-LAYER-2026-10 rules."""
    cleaned = str(route or "").strip()
    if not cleaned:
        raise ValueError("decision model route must be non-empty")
    if cleaned.lower() in FORBIDDEN_ROUTES or cleaned.lower().endswith("/jev-router"):
        raise ValueError(
            f"route {cleaned!r} is forbidden: typesafe/jev-router is an LLM router, not a decision model"
        )
    return cleaned


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# --------------------------------------------------------------------------- #
# Phase 0a: Context admission relevance pairs and LOPO splits
# --------------------------------------------------------------------------- #
def extract_relevance_pairs(gold: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten ``gold.json`` into deterministic ``(patient_uuid, topic, record_uuid)`` pairs."""
    pairs: list[dict[str, Any]] = []
    for cell_key in sorted(gold.keys()):
        if "|" not in cell_key:
            continue
        patient_uuid, topic = cell_key.split("|", 1)
        cell = gold[cell_key] or {}
        ontopic_map = cell.get("ontopic") or {}
        focus_map = cell.get("focus_uuids") or {}
        for record_uuid in sorted(focus_map.keys()):
            record_text = str(focus_map[record_uuid] or "")
            is_ontopic = record_uuid in ontopic_map
            pairs.append(
                {
                    "pair_id": f"{patient_uuid}|{topic}|{record_uuid}",
                    "cell_key": cell_key,
                    "patient_uuid": patient_uuid,
                    "topic": topic,
                    "question": TOPIC_QUESTIONS.get(
                        topic, f"Is this clinical record relevant to {topic}?"
                    ),
                    "record_uuid": record_uuid,
                    "record_text": record_text,
                    "label": 1 if is_ontopic else 0,
                    "is_ontopic": is_ontopic,
                }
            )
    return pairs


def leave_one_patient_out_splits(
    pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Construct the 5 rotating leave-one-patient-out folds for Laya fine-tuning."""
    patients = sorted({str(p["patient_uuid"]) for p in pairs})
    folds: list[dict[str, Any]] = []
    for test_patient in patients:
        train = [dict(p) for p in pairs if p["patient_uuid"] != test_patient]
        test = [dict(p) for p in pairs if p["patient_uuid"] == test_patient]
        folds.append(
            {
                "held_out_patient": test_patient,
                "train_patients": [p for p in patients if p != test_patient],
                "n_train": len(train),
                "n_test": len(test),
                "n_train_ontopic": sum(1 for p in train if p.get("label") == 1),
                "n_test_ontopic": sum(1 for p in test if p.get("label") == 1),
                "train": train,
                "test": test,
            }
        )
    return folds


# --------------------------------------------------------------------------- #
# Proper scoring rules and temperature scaling
# --------------------------------------------------------------------------- #
def _clip_prob(p: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, float(p)))


def _logit(p: float) -> float:
    clipped = _clip_prob(p)
    return math.log(clipped / (1.0 - clipped))


def _sigmoid(z: float) -> float:
    if z >= 0:
        exp_neg = math.exp(-z)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(z)
    return exp_pos / (1.0 + exp_pos)


def brier_score(probabilities: Sequence[float], labels: Sequence[int]) -> float | None:
    """Mean squared error between predicted probabilities in [0, 1] and binary 0/1 outcomes."""
    if not probabilities or len(probabilities) != len(labels):
        return None
    total = sum(
        (float(p) - (1.0 if int(y) else 0.0)) ** 2
        for p, y in zip(probabilities, labels)
    )
    return total / len(probabilities)


def expected_calibration_error(
    probabilities: Sequence[float],
    labels: Sequence[int],
    *,
    min_bin_size: int = 10,
    max_bins: int = 10,
) -> dict[str, Any]:
    """Compute ECE using adaptive quantile bins with at least ``min_bin_size`` items per bin."""
    n = len(probabilities)
    if n == 0 or n != len(labels) or n < min_bin_size:
        return {"ece": None, "n": n, "bins": []}

    n_bins = max(1, min(max_bins, n // min_bin_size))
    paired = sorted(
        zip((float(p) for p in probabilities), (1 if int(y) else 0 for y in labels)),
        key=lambda item: item[0],
    )
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for b in range(n_bins):
        start = (b * n) // n_bins
        end = ((b + 1) * n) // n_bins if b < n_bins - 1 else n
        chunk = paired[start:end]
        if not chunk:
            continue
        mean_p = sum(p for p, _ in chunk) / len(chunk)
        mean_y = sum(y for _, y in chunk) / len(chunk)
        gap = abs(mean_p - mean_y)
        ece += (len(chunk) / n) * gap
        bins.append(
            {
                "count": len(chunk),
                "min_prob": chunk[0][0],
                "max_prob": chunk[-1][0],
                "mean_prob": mean_p,
                "empirical_rate": mean_y,
                "abs_gap": gap,
            }
        )
    return {"ece": ece, "n": n, "bins": bins}


def apply_temperature_scaling(
    probabilities: Sequence[float], temperature: float
) -> list[float]:
    """Scale probabilities by dividing logits by ``temperature`` (> 0)."""
    temp = max(1e-3, float(temperature))
    return [_sigmoid(_logit(p) / temp) for p in probabilities]


def fit_temperature_scaling(
    probabilities: Sequence[float],
    labels: Sequence[int],
    *,
    grid_steps: int = 100,
) -> dict[str, Any]:
    """Fit a single scalar temperature T in [0.1, 5.0] minimizing Brier score."""
    if not probabilities or len(probabilities) != len(labels):
        return {"temperature": 1.0, "before_brier": None, "after_brier": None}
    before_brier = brier_score(probabilities, labels)
    best_t = 1.0
    best_brier = before_brier if before_brier is not None else float("inf")
    for step in range(1, grid_steps + 1):
        candidate_t = 0.1 + (4.9 * step / grid_steps)
        scaled = apply_temperature_scaling(probabilities, candidate_t)
        score = brier_score(scaled, labels)
        if score is not None and score < best_brier:
            best_brier = score
            best_t = candidate_t
    return {
        "temperature": round(best_t, 4),
        "before_brier": before_brier,
        "after_brier": best_brier,
    }


def score_relevance_arm(
    pairs: Sequence[Mapping[str, Any]],
    probabilities_by_pair_id: Mapping[str, float],
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Score a Phase 0a context-admission arm against frozen gold pairs."""
    probs: list[float] = []
    labels: list[int] = []
    per_cell: dict[str, dict[str, int]] = {}
    for pair in pairs:
        pid = str(pair["pair_id"])
        if pid not in probabilities_by_pair_id:
            continue
        p = float(probabilities_by_pair_id[pid])
        y = 1 if int(pair["label"]) else 0
        pred = 1 if p >= threshold else 0
        probs.append(p)
        labels.append(y)
        cell_stats = per_cell.setdefault(
            str(pair["cell_key"]), {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        )
        if pred == 1 and y == 1:
            cell_stats["tp"] += 1
        elif pred == 1 and y == 0:
            cell_stats["fp"] += 1
        elif pred == 0 and y == 1:
            cell_stats["fn"] += 1
        else:
            cell_stats["tn"] += 1

    total_tp = sum(c["tp"] for c in per_cell.values())
    total_fp = sum(c["fp"] for c in per_cell.values())
    total_fn = sum(c["fn"] for c in per_cell.values())
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else None
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else None

    cell_metrics: dict[str, dict[str, Any]] = {}
    for cell_key, counts in sorted(per_cell.items()):
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        c_rec = tp / (tp + fn) if (tp + fn) else None
        c_prec = tp / (tp + fp) if (tp + fp) else (1.0 if (tp + fn) == 0 else 0.0)
        cell_metrics[cell_key] = {
            **counts,
            "recall": c_rec,
            "precision": c_prec,
        }

    renal_key_prefix = f"{PATIENT_39_UUID}|kidney|"
    renal_details = {}
    for uuid in PATIENT_39_RENAL_UUIDS:
        pid = renal_key_prefix + uuid
        prob = probabilities_by_pair_id.get(pid)
        renal_details[uuid] = {
            "probability": prob,
            "admitted": bool(prob is not None and float(prob) >= threshold),
        }

    return {
        "n_scored": len(probs),
        "threshold": threshold,
        "overall": {
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
            "recall": recall,
            "precision": precision,
            "brier": brier_score(probs, labels),
            "calibration": expected_calibration_error(probs, labels),
        },
        "patient_39_renal": {
            "admitted_count": sum(
                1 for item in renal_details.values() if item["admitted"]
            ),
            "total_renal_records": len(PATIENT_39_RENAL_UUIDS),
            "all_admitted": all(item["admitted"] for item in renal_details.values()),
            "records": renal_details,
        },
        "per_cell": cell_metrics,
    }


# --------------------------------------------------------------------------- #
# Phase 0b: Trace extraction (grounding, In-Depth attribution, review flags)
# --------------------------------------------------------------------------- #
def _reference_lookup(references: Sequence[Mapping[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for ref in references or []:
        idx = ref.get("index")
        if not isinstance(idx, int):
            continue
        text = str(ref.get("sourceText") or ref.get("title") or "").strip()
        date = str(ref.get("date") or "").strip()
        if date and text and not text.startswith(f"({date})"):
            lookup[idx] = f"[{idx}] ({date}) {text}"
        elif text:
            lookup[idx] = f"[{idx}] {text}"
    return lookup


def extract_trace_decision_items(
    traces: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract Answer grounding, In-Depth attribution, and review-flag items from Hub traces."""
    items: list[dict[str, Any]] = []
    for trace_idx, tr in enumerate(traces or []):
        level_id = str(tr.get("level_id") or "")
        question = str(tr.get("question") or "")
        corr = tr.get("correlation") or {}
        session = str(corr.get("session") or tr.get("session") or "")
        request_id = str(corr.get("request_id") or tr.get("request_id") or f"trace-{trace_idx}")
        refs = tr.get("final_references") or []
        ref_by_idx = _reference_lookup(refs)

        # 1. Answer and In-Depth citation grounding checks on final_references
        seen_checks: set[tuple[str, str, tuple[int, ...]]] = set()
        for ref in refs:
            if not isinstance(ref, Mapping):
                continue
            for check in ref.get("groundingChecks") or ():
                if not isinstance(check, Mapping):
                    continue
                method = str(check.get("method") or "")
                if method.startswith("deterministic"):
                    continue
                location = str(check.get("location") or "answer")
                claim = str(check.get("claim") or "").strip()
                source_indices = tuple(
                    sorted(
                        idx
                        for idx in (check.get("source_indices") or [ref.get("index")])
                        if isinstance(idx, int)
                    )
                )
                if not claim or not source_indices:
                    continue
                dedup_key = (location, claim, source_indices)
                if dedup_key in seen_checks:
                    continue
                seen_checks.add(dedup_key)
                sources_text = "\n".join(
                    ref_by_idx.get(idx, f"[{idx}]") for idx in source_indices
                )
                status = str(check.get("status") or "unchecked")
                hub_verdict = (
                    True
                    if status == "verified"
                    else False
                    if status == "unsupported"
                    else None
                )
                kind = (
                    "indepth_grounding" if location == "indepth" else "answer_grounding"
                )
                items.append(
                    {
                        "item_id": f"{request_id}:{kind}:{len(items)}",
                        "request_id": request_id,
                        "session": session,
                        "level_id": level_id,
                        "question": question,
                        "kind": kind,
                        "location": location,
                        "source_indices": list(source_indices),
                        "source_text": sources_text,
                        "claim": claim,
                        "hub_status": status,
                        "hub_verdict": hub_verdict,
                        "missing_facts": check.get("missing_facts"),
                    }
                )

        # 2. In-Depth gate citation checks (captures missing_facts / reasons from 7fe138b)
        indepth_gate = tr.get("indepth_temporal_gate") or {}
        for ccheck in indepth_gate.get("citation_checks") or ():
            if not isinstance(ccheck, Mapping):
                continue
            c_status = str(ccheck.get("status") or "")
            if c_status == "info":
                continue
            claim_index = ccheck.get("claim_index")
            claim = str(ccheck.get("claim") or "").strip()
            source_indices = tuple(
                sorted(
                    idx
                    for idx in (ccheck.get("source_indices") or ())
                    if isinstance(idx, int)
                )
            )
            dedup_key = ("indepth", claim, source_indices)
            if not claim or dedup_key in seen_checks:
                continue
            seen_checks.add(dedup_key)
            sources_text = "\n".join(
                ref_by_idx.get(idx, f"[{idx}]") for idx in source_indices
            )
            items.append(
                {
                    "item_id": f"{request_id}:indepth_grounding:{len(items)}",
                    "request_id": request_id,
                    "session": session,
                    "level_id": level_id,
                    "question": question,
                    "kind": "indepth_grounding",
                    "location": "indepth",
                    "claim_index": claim_index,
                    "source_indices": list(source_indices),
                    "source_text": sources_text,
                    "claim": claim,
                    "hub_status": (
                        "unsupported"
                        if c_status == "fail"
                        else "unchecked"
                        if c_status == "warn"
                        else "verified"
                    ),
                    "hub_verdict": (
                        False
                        if c_status == "fail"
                        else None
                        if c_status == "warn"
                        else True
                    ),
                    "reason": ccheck.get("reason"),
                    "missing_facts": ccheck.get("missing_facts"),
                }
            )

        # 3. Answer review candidate errors[] (Pattern A: reviewer-error verification)
        for step in tr.get("steps") or ():
            if not isinstance(step, Mapping):
                continue
            if step.get("role") == "answer_review":
                for err in step.get("errors") or ():
                    if not isinstance(err, Mapping):
                        continue
                    wrong = str(err.get("wrong") or "").strip()
                    chart = str(err.get("chart") or "").strip()
                    if not wrong and not chart:
                        continue
                    items.append(
                        {
                            "item_id": f"{request_id}:answer_review_error:{len(items)}",
                            "request_id": request_id,
                            "session": session,
                            "level_id": level_id,
                            "question": question,
                            "kind": "answer_review_error",
                            "reviewer_model": step.get("model"),
                            "wrong": wrong,
                            "chart": chart,
                            "overruled_by_date_checks": False,
                            "hub_verdict": True,
                        }
                    )
                for err in step.get("overruled_by_date_checks") or ():
                    if not isinstance(err, Mapping):
                        continue
                    wrong = str(err.get("wrong") or "").strip()
                    chart = str(err.get("chart") or "").strip()
                    items.append(
                        {
                            "item_id": f"{request_id}:answer_review_error:{len(items)}",
                            "request_id": request_id,
                            "session": session,
                            "level_id": level_id,
                            "question": question,
                            "kind": "answer_review_error",
                            "reviewer_model": step.get("model"),
                            "wrong": wrong,
                            "chart": chart,
                            "overruled_by_date_checks": True,
                            "hub_verdict": False,
                        }
                    )
            elif step.get("role") == "indepth_validator":
                claims = list(tr.get("in_depth_claims") or ())
                flagged_set = set(step.get("flag") or ())
                for idx, claim_text in enumerate(claims, start=1):
                    items.append(
                        {
                            "item_id": f"{request_id}:indepth_review:{idx}:{len(items)}",
                            "request_id": request_id,
                            "session": session,
                            "level_id": level_id,
                            "question": question,
                            "kind": "indepth_review",
                            "reviewer_model": step.get("model"),
                            "claim_index": idx,
                            "claim": str(claim_text),
                            "hub_flagged": idx in flagged_set,
                            "hub_issues": step.get("issues") or "",
                        }
                    )
    return items


def compute_stage_timing_summary(
    traces: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize per-stage wall-clock timings and latency shares across turns (P0.2)."""
    by_stage: dict[str, list[float]] = {}
    turn_totals: list[float] = []
    review_shares: list[float] = []
    grounding_shares: list[float] = []

    for tr in traces or ():
        stage_sums: dict[str, float] = {}
        for step in tr.get("steps") or ():
            if not isinstance(step, Mapping) or step.get("role") != "stage_timing":
                continue
            stage = str(step.get("stage") or "")
            dur = float(step.get("duration_ms") or 0.0)
            if stage:
                stage_sums[stage] = stage_sums.get(stage, 0.0) + dur
                by_stage.setdefault(stage, []).append(dur)
        turn_total = sum(stage_sums.values())
        if turn_total > 0:
            turn_totals.append(turn_total)
            review_shares.append(stage_sums.get("review", 0.0) / turn_total)
            grounding_shares.append(
                (
                    stage_sums.get("ground_verdicts", 0.0)
                    + stage_sums.get("indepth_gate", 0.0)
                )
                / turn_total
            )

    def _stats(values: Sequence[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "mean_ms": None, "median_ms": None, "p90_ms": None}
        ordered = sorted(values)
        p90_idx = min(len(ordered) - 1, max(0, math.ceil(0.9 * len(ordered)) - 1))
        return {
            "count": len(ordered),
            "mean_ms": round(statistics.fmean(ordered), 2),
            "median_ms": round(statistics.median(ordered), 2),
            "p90_ms": round(ordered[p90_idx], 2),
        }

    return {
        "n_traces": len(traces or ()),
        "turn_total_ms": _stats(turn_totals),
        "mean_review_latency_share": (
            round(statistics.fmean(review_shares), 4) if review_shares else None
        ),
        "mean_grounding_latency_share": (
            round(statistics.fmean(grounding_shares), 4) if grounding_shares else None
        ),
        "stages": {stage: _stats(vals) for stage, vals in sorted(by_stage.items())},
    }


# --------------------------------------------------------------------------- #
# Three-band threshold fitting and Phase 0b scoring
# --------------------------------------------------------------------------- #
def apply_three_band_thresholds(
    probability: float,
    *,
    low: float,
    high: float,
) -> str:
    """Map a calibrated support probability to ``unsupported`` / ``unclear`` / ``supported``."""
    p = float(probability)
    if p < low:
        return "unsupported"
    if p >= high:
        return "supported"
    return "unclear"


def fit_three_band_thresholds(
    adjudicated: Sequence[Mapping[str, Any]],
    *,
    seed: int = 42,
    calib_fraction: float = 0.5,
) -> dict[str, Any]:
    """Fit ``(low, high)`` probability thresholds on a calibration split and score held-out.

    Each item in ``adjudicated`` carries ``probability`` in [0, 1] and ``human_label``
    in ``{"supported", "unclear", "unsupported"}``.
    """
    valid = [
        dict(row)
        for row in adjudicated
        if row.get("probability") is not None
        and row.get("human_label") in {"supported", "unclear", "unsupported"}
    ]
    if len(valid) < 4:
        return {
            "low": 0.35,
            "high": 0.75,
            "calib_accuracy": None,
            "held_out_accuracy": None,
            "n_calib": len(valid),
            "n_held_out": 0,
        }
    ordered = sorted(valid, key=lambda r: str(r.get("item_id") or ""))
    rng = random.Random(seed)
    shuffled = list(ordered)
    rng.shuffle(shuffled)
    split_idx = max(2, min(len(shuffled) - 2, round(calib_fraction * len(shuffled))))
    calib = shuffled[:split_idx]
    held_out = shuffled[split_idx:]

    def _acc(rows: Sequence[Mapping[str, Any]], low: float, high: float) -> float:
        correct = sum(
            1
            for r in rows
            if apply_three_band_thresholds(float(r["probability"]), low=low, high=high)
            == r["human_label"]
        )
        return correct / len(rows)

    best_low, best_high = 0.35, 0.75
    best_score = -1.0
    for low_step in range(10, 60, 5):
        low = low_step / 100.0
        for high_step in range(low_step + 5, 95, 5):
            high = high_step / 100.0
            score = _acc(calib, low, high)
            if score > best_score:
                best_score = score
                best_low, best_high = low, high

    return {
        "low": best_low,
        "high": best_high,
        "calib_accuracy": round(best_score, 4),
        "held_out_accuracy": round(_acc(held_out, best_low, best_high), 4),
        "n_calib": len(calib),
        "n_held_out": len(held_out),
    }


def score_grounding_and_review_arm(
    items: Sequence[Mapping[str, Any]],
    probabilities_by_item_id: Mapping[str, float],
    human_labels_by_item_id: Mapping[str, str] | None = None,
    *,
    binary_threshold: float = 0.5,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute P0.6 metrics and G1 gate check for a decision-model grounding arm."""
    human_map = dict(human_labels_by_item_id or {})
    hub_unchecked = sum(1 for item in items if item.get("hub_verdict") is None)
    decision_covered = sum(
        1 for item in items if str(item.get("item_id")) in probabilities_by_item_id
    )

    hub_binary: list[int] = []
    dec_binary: list[int] = []
    human_binary: list[int] = []
    dec_probs_on_human: list[float] = []
    adjudicated_rows: list[dict[str, Any]] = []

    agree_when_hub_right: list[int] = []
    agree_when_hub_wrong: list[int] = []
    hub_errors: set[str] = set()
    dec_errors: set[str] = set()

    for item in items:
        iid = str(item.get("item_id"))
        prob = probabilities_by_item_id.get(iid)
        h_label = human_map.get(iid)
        if h_label in {"supported", "unclear", "unsupported"} and prob is not None:
            adjudicated_rows.append(
                {
                    "item_id": iid,
                    "probability": float(prob),
                    "human_label": h_label,
                }
            )
        if h_label not in {"supported", "unsupported"} or prob is None:
            continue
        h_bin = 1 if h_label == "supported" else 0
        d_bin = 1 if float(prob) >= binary_threshold else 0
        hub_v = item.get("hub_verdict")
        if hub_v is None:
            continue
        g_bin = 1 if bool(hub_v) else 0
        human_binary.append(h_bin)
        dec_binary.append(d_bin)
        hub_binary.append(g_bin)
        dec_probs_on_human.append(float(prob))

        if g_bin != h_bin:
            hub_errors.add(iid)
            agree_when_hub_wrong.append(1 if d_bin == g_bin else 0)
        else:
            agree_when_hub_right.append(1 if d_bin == g_bin else 0)
        if d_bin != h_bin:
            dec_errors.add(iid)

    kappa_hub = (
        weighted_kappa(hub_binary, human_binary, max_score=1)
        if len(human_binary) >= 2
        else None
    )
    kappa_dec = (
        weighted_kappa(dec_binary, human_binary, max_score=1)
        if len(human_binary) >= 2
        else None
    )

    def _unsupported_recall(preds: Sequence[int], gold: Sequence[int]) -> float | None:
        unsupported_indices = [i for i, y in enumerate(gold) if y == 0]
        if not unsupported_indices:
            return None
        caught = sum(1 for i in unsupported_indices if preds[i] == 0)
        return caught / len(unsupported_indices)

    recall_unsupported_hub = _unsupported_recall(hub_binary, human_binary)
    recall_unsupported_dec = _unsupported_recall(dec_binary, human_binary)

    errors_not_subset = bool(
        not dec_errors.issubset(hub_errors)
    )
    g1_pass = bool(
        kappa_hub is not None
        and kappa_dec is not None
        and (kappa_dec >= kappa_hub - 0.05)
        and (
            recall_unsupported_hub is None
            or (
                recall_unsupported_dec is not None
                and recall_unsupported_dec >= recall_unsupported_hub
            )
        )
        and errors_not_subset
    )

    return {
        "n_items_total": len(items),
        "n_adjudicated_binary": len(human_binary),
        "hub_unchecked_rate": (
            round(hub_unchecked / len(items), 4) if items else 0.0
        ),
        "decision_coverage_rate": (
            round(decision_covered / len(items), 4) if items else 0.0
        ),
        "kappa_vs_human": {
            "hub_grounder": kappa_hub,
            "decision_model": kappa_dec,
        },
        "recall_of_unsupported": {
            "hub_grounder": recall_unsupported_hub,
            "decision_model": recall_unsupported_dec,
        },
        "brier": brier_score(dec_probs_on_human, human_binary),
        "calibration": expected_calibration_error(dec_probs_on_human, human_binary),
        "conditional_agreement_with_hub": {
            "when_hub_right": (
                round(statistics.fmean(agree_when_hub_right), 4)
                if agree_when_hub_right
                else None
            ),
            "when_hub_wrong": (
                round(statistics.fmean(agree_when_hub_wrong), 4)
                if agree_when_hub_wrong
                else None
            ),
        },
        "three_band_thresholds": fit_three_band_thresholds(
            adjudicated_rows, seed=seed
        ),
        "gate_g1": {
            "binary_threshold": binary_threshold,
            "kappa_within_0_05": (
                kappa_dec >= kappa_hub - 0.05
                if (kappa_dec is not None and kappa_hub is not None)
                else None
            ),
            "unsupported_recall_at_least_hub": (
                recall_unsupported_dec >= recall_unsupported_hub
                if (
                    recall_unsupported_dec is not None
                    and recall_unsupported_hub is not None
                )
                else None
            ),
            "errors_not_subset_of_hub": errors_not_subset,
            "pass": g1_pass,
        },
    }


def build_stratified_adjudication_sheet(
    items: Sequence[Mapping[str, Any]],
    *,
    per_stratum: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Build the P0.5 stratified 60-item adjudication sheet (20 verified, 20 unsupported, 20 review/borderline)."""
    verified_pool = [
        dict(item)
        for item in items
        if item.get("kind") in {"answer_grounding", "indepth_grounding"}
        and item.get("hub_status") == "verified"
    ]
    unsupported_pool = [
        dict(item)
        for item in items
        if item.get("kind") in {"answer_grounding", "indepth_grounding"}
        and item.get("hub_status") == "unsupported"
    ]
    review_pool = [
        dict(item)
        for item in items
        if item.get("kind") in {"answer_review_error", "indepth_review"}
    ]

    rng = random.Random(seed)

    def _sample(pool: list[dict[str, Any]], stratum: str) -> list[dict[str, Any]]:
        ordered = sorted(pool, key=lambda r: str(r.get("item_id") or ""))
        if len(ordered) > per_stratum:
            chosen = rng.sample(ordered, per_stratum)
        else:
            chosen = ordered
        return [
            {
                **row,
                "stratum": stratum,
                "human_label": None,
                "adjudication_notes": "",
            }
            for row in chosen
        ]

    return (
        _sample(verified_pool, "hub_verified")
        + _sample(unsupported_pool, "hub_unsupported")
        + _sample(review_pool, "review_or_borderline")
    )


def write_replay_bundle(
    output_dir: Path,
    *,
    gold_path: Path | None = None,
    trace_path: Path | None = None,
    route: str = "local/offline-extraction",
    model_version: str = "laya-base-or-jev-1.13",
) -> dict[str, Any]:
    """Extract Phase 0a and 0b replay datasets and write a provenance manifest."""
    validate_decision_route(route)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "decision_replay.v1",
        "spec_id": "DECISION-LAYER-2026-10",
        "created_at": utc_now_iso(),
        "route": route,
        "model_version": model_version,
        "inputs": {},
        "outputs": {},
    }

    if gold_path is not None and gold_path.exists():
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        pairs = extract_relevance_pairs(gold)
        folds = leave_one_patient_out_splits(pairs)
        pairs_file = output_dir / "phase0a_relevance_pairs.jsonl"
        folds_file = output_dir / "phase0a_lopo_folds_summary.json"
        _write_jsonl(pairs_file, pairs)
        folds_summary = [
            {k: v for k, v in fold.items() if k not in {"train", "test"}}
            for fold in folds
        ]
        folds_file.write_text(
            json.dumps(folds_summary, indent=2) + "\n", encoding="utf-8"
        )
        manifest["inputs"]["gold_path"] = str(gold_path)
        manifest["inputs"]["gold_sha256"] = sha256_file(gold_path)
        manifest["outputs"]["phase0a_pairs"] = len(pairs)
        manifest["outputs"]["phase0a_ontopic"] = sum(
            1 for p in pairs if p.get("label") == 1
        )
        manifest["outputs"]["phase0a_folds"] = len(folds)

    if trace_path is not None and trace_path.exists():
        traces = read_jsonl(trace_path, strict=False)
        items = extract_trace_decision_items(traces)
        timings = compute_stage_timing_summary(traces)
        sheet = build_stratified_adjudication_sheet(items)
        items_file = output_dir / "phase0b_decision_items.jsonl"
        sheet_file = output_dir / "phase0b_adjudication_sheet.jsonl"
        timings_file = output_dir / "phase0b_stage_timings.json"
        _write_jsonl(items_file, items)
        _write_jsonl(sheet_file, sheet)
        timings_file.write_text(
            json.dumps(timings, indent=2) + "\n", encoding="utf-8"
        )
        manifest["inputs"]["trace_path"] = str(trace_path)
        manifest["inputs"]["trace_sha256"] = sha256_file(trace_path)
        manifest["outputs"]["phase0b_items"] = len(items)
        manifest["outputs"]["phase0b_adjudication_sheet_items"] = len(sheet)
        manifest["outputs"]["phase0b_by_kind"] = {
            kind: sum(1 for item in items if item.get("kind") == kind)
            for kind in sorted({str(item.get("kind")) for item in items})
        }
        manifest["outputs"]["stage_timings"] = timings

    manifest_file = output_dir / "manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
