"""Deterministic and multi-modality evaluation runner for WAHS+ FHIR R4 condensation & Q&A.

Supports three distinct evaluation modalities (`evaluation_modality`):
1. `deterministic_pipeline` (Deterministic Pipeline Gate):
   Evaluates the deterministic 5-Tier FHIR Condenser and 4-Layer Clinical KB rules
   (token budget compliance, IPS safety core retention, deterministic conflict recall,
   and zero-leakage privacy redaction).
2. `condensation_retrieval_ablation` (Condensation & Retrieval Ablation):
   Evaluates information retention across Tier 1 (16k) -> Tier 4 (2k) static condensation
   vs. Tier 4 (2k) + On-Demand Full-Chart Lookup Tools stratified by question horizon.
3. `live_model_and_team_eval` (Live Model & KB Team Evaluation):
   Evaluates live local open-weight models and multi-agent KB setups over identical
   condensed inputs, combining deterministic citation/privacy gates with HealthBench-style
   weighted rubrics, VeriFact atomic claim entailment, and patient readability metrics.

Runs offline against frozen run directories or live against a caller-supplied
Med Agent Hub HTTP endpoint without importing product source trees or calling Git/Docker.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from ..metadata import RunManifest, append_event, copy_target_provenance, write_manifest

_CITATION_RE = re.compile(r"\[(\d+)\]")
_ABSTENTION_RE = re.compile(
    r"\b(not documented|no documented|no documentation|not recorded|no record|cannot verify|not found in|not present in|abstain|abstains|grounded abstention)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?:[.!?;]+(?:\s|$))|\n+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_REDACTION_BANNER_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*\*(?:Privacy-Protected|Sensitive SDOH Status|\d+\s+Sensitive SDOH).*$",
    re.IGNORECASE | re.MULTILINE,
)

VALID_EVALUATION_MODALITIES = (
    "deterministic_pipeline",
    "condensation_retrieval_ablation",
    "live_model_and_team_eval",
)

DEFAULT_SENSITIVE_TERMS = (
    "intimate partner violence",
    "victim of intimate partner abuse",
    "ipv",
    "domestic violence",
)


def compute_flesch_kincaid_grade(text: str) -> float:
    """Compute Flesch-Kincaid Grade Level on prose after stripping markdown code/citation noise."""
    cleaned = re.sub(r"`[^`]*`", " ", text or "")
    cleaned = re.sub(r"\[\d+\]", " ", cleaned)
    cleaned = re.sub(r"[#*_>|]", " ", cleaned)
    words = _WORD_RE.findall(cleaned)
    if not words:
        return 0.0
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if _WORD_RE.search(s)]
    num_sentences = max(len(sentences), 1)
    num_words = len(words)

    def _count_syllables(word: str) -> int:
        w = word.lower()
        if len(w) <= 3:
            return 1
        w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
        w = re.sub(r"^y", "", w)
        groups = _VOWEL_GROUP_RE.findall(w)
        return max(len(groups), 1)

    syllables = sum(_count_syllables(w) for w in words)
    grade = 0.39 * (num_words / num_sentences) + 11.8 * (syllables / num_words) - 15.59
    return round(max(0.0, grade), 2)


def compute_sentence_citation_coverage(
    answer_text: str,
    idx_map: dict[str, str],
    *,
    must_abstain: bool = False,
) -> float:
    """Compute the fraction of substantive prose sentences (>= 4 words) in `answer_text`
    that carry at least one valid `[N]` inline citation resolving in `idx_map`.
    """
    if must_abstain:
        return 1.0
    stripped = (answer_text or "").strip()
    if not stripped:
        return 0.0
    if "\n" in stripped:
        raw_segments = [s.strip() for s in re.split(r"\n+", stripped) if s.strip()]
    else:
        raw_segments = [s.strip() for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()]
    substantive: list[str] = []
    for seg in raw_segments:
        if seg.startswith("#") or seg.endswith(":"):
            continue
        words = _WORD_RE.findall(seg)
        if len(words) >= 4:
            substantive.append(seg)
    if not substantive:
        inline = _CITATION_RE.findall(answer_text)
        return 1.0 if inline else 0.0

    cited_count = 0
    for seg in substantive:
        nums = _CITATION_RE.findall(seg)
        if nums and any((not idx_map) or (n in idx_map and idx_map[n]) for n in nums):
            cited_count += 1
    return round(cited_count / len(substantive), 4)


def compute_readability_alignment_score(
    fk_grade: float,
    *,
    must_abstain: bool = False,
) -> float:
    """Continuous readability alignment score in `[0.25, 1.0]` relative to the target
    patient-facing Flesch-Kincaid Grade 5.5-9.0 band.
    """
    if must_abstain or fk_grade <= 0.0:
        return 1.0
    if 5.5 <= fk_grade <= 9.0:
        return 1.0
    if fk_grade > 9.0:
        return round(max(0.25, 1.0 - 0.07 * (fk_grade - 9.0)), 4)
    return round(max(0.70, 1.0 - 0.04 * (5.5 - fk_grade)), 4)


@dataclass(frozen=True)
class WahsEvalCase:
    case_id: str
    patient_id: str
    use_case: str
    prompt: str
    sharing_posture: str = "patient_self"
    target_token_budgets: list[int] = field(default_factory=lambda: [8192, 4096, 2048])
    expected_anomaly_ids: list[str] = field(default_factory=list)
    expected_target_uuids: list[str] = field(default_factory=list)
    forbidden_uuids: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    must_abstain: bool = False
    rubric_criteria: list[str] = field(default_factory=list)
    expected_facts: list[str] = field(default_factory=list)
    positive_rubric_items: list[dict[str, Any]] = field(default_factory=list)
    negative_penalty_items: list[dict[str, Any]] = field(default_factory=list)
    citation_entailment_assertions: list[dict[str, Any]] = field(default_factory=list)
    question_horizon: str = "current_active_state"
    patient_category: str = "medication_reconciliation"

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
        budgets = [int(b) for b in (data.get("target_token_budgets") or [8192, 4096, 2048])]
        exp_uuids = data.get("expected_target_uuids") or data.get("expected_resource_uuids") or []
        forb_uuids = data.get("forbidden_uuids") or data.get("forbidden_resource_uuids") or []
        exp_anoms = data.get("expected_anomaly_ids") or (
            [data["anomaly_id"]] if data.get("anomaly_id") else []
        )
        must_abstain = (
            bool(data.get("must_abstain", False))
            or bool(data.get("expect_abstention", False))
            or data.get("expected_answer_type") == "abstain_not_in_chart"
            or str(use_case).endswith("abstention")
        )
        expected_facts = [str(x) for x in (data.get("expected_facts") or [])]
        pos_items = list(data.get("positive_rubric_items") or [])
        if not pos_items and expected_facts:
            pos_items = [
                {
                    "id": f"fact_{idx + 1}",
                    "criterion": f"Mentions grounded clinical fact '{fact}'",
                    "required_any": [fact],
                    "weight": 1.0,
                }
                for idx, fact in enumerate(expected_facts)
            ]
        neg_items = list(data.get("negative_penalty_items") or [])
        entailment_items = list(data.get("citation_entailment_assertions") or [])

        return cls(
            case_id=str(case_id),
            patient_id=str(patient_id),
            use_case=str(use_case),
            prompt=str(prompt),
            sharing_posture=str(data.get("sharing_posture") or "patient_self"),
            target_token_budgets=budgets,
            expected_anomaly_ids=[str(x) for x in exp_anoms],
            expected_target_uuids=[str(x) for x in exp_uuids],
            forbidden_uuids=[str(x) for x in forb_uuids],
            forbidden_terms=[str(x) for x in (data.get("forbidden_terms") or [])],
            must_abstain=must_abstain,
            rubric_criteria=[str(x) for x in (data.get("rubric_criteria") or [])],
            expected_facts=expected_facts,
            positive_rubric_items=pos_items,
            negative_penalty_items=neg_items,
            citation_entailment_assertions=entailment_items,
            question_horizon=str(data.get("question_horizon") or "current_active_state"),
            patient_category=str(data.get("patient_category") or "medication_reconciliation"),
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
    sharing_posture: str
    budget_tokens: int
    actual_tokens: int
    token_budget_ok: bool
    required_uuid_recall: float
    citation_resolution_rate: float
    fabricated_citation_count: int
    privacy_zero_leakage: bool
    leaked_items: list[str]
    abstention_ok: bool
    rubric_weighted_score: float
    atomic_entailment_rate: float
    citation_distortion_count: int
    flesch_kincaid_grade: float
    question_horizon: str
    patient_category: str
    passed: bool
    failures: list[str]
    sentence_citation_coverage: float = 1.0
    readability_alignment_score: float = 1.0
    case_quality_score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "patient_id": self.patient_id,
            "use_case": self.use_case,
            "sharing_posture": self.sharing_posture,
            "budget_tokens": self.budget_tokens,
            "actual_tokens": self.actual_tokens,
            "token_budget_ok": self.token_budget_ok,
            "required_uuid_recall": round(self.required_uuid_recall, 4),
            "citation_resolution_rate": round(self.citation_resolution_rate, 4),
            "sentence_citation_coverage": round(self.sentence_citation_coverage, 4),
            "fabricated_citation_count": self.fabricated_citation_count,
            "privacy_zero_leakage": self.privacy_zero_leakage,
            "leaked_items": list(self.leaked_items),
            "abstention_ok": self.abstention_ok,
            "rubric_weighted_score": round(self.rubric_weighted_score, 4),
            "atomic_entailment_rate": round(self.atomic_entailment_rate, 4),
            "citation_distortion_count": self.citation_distortion_count,
            "flesch_kincaid_grade": self.flesch_kincaid_grade,
            "readability_alignment_score": round(self.readability_alignment_score, 4),
            "case_quality_score": round(self.case_quality_score, 2),
            "question_horizon": self.question_horizon,
            "patient_category": self.patient_category,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def _extract_known_uuids(envelope: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    """Return (all_uuid_set, index_to_uuid_map) from a WAHS response envelope."""
    uuids: set[str] = set()
    idx_map: dict[str, str] = {}

    for u in envelope.get("retained_uuids") or []:
        if isinstance(u, str) and u:
            uuids.add(u.replace("urn:uuid:", ""))

    cmap = envelope.get("citation_map")
    if isinstance(cmap, dict):
        for k, v in cmap.items():
            key_num = str(k).strip("[] ")
            if isinstance(v, str) and v:
                clean = v.replace("urn:uuid:", "")
                uuids.add(clean)
                idx_map[key_num] = clean
            elif isinstance(v, dict):
                raw_u = str(v.get("resourceUuid") or v.get("uuid") or v.get("id") or "")
                if raw_u:
                    clean = raw_u.replace("urn:uuid:", "")
                    uuids.add(clean)
                    idx_map[key_num] = clean

    for ref_key in ("references", "citations"):
        refs = envelope.get(ref_key)
        if isinstance(refs, list):
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
                c_idx = str(ref.get("index") or idx).strip("[] ")
                if raw_u:
                    clean = raw_u.replace("urn:uuid:", "")
                    uuids.add(clean)
                    idx_map[c_idx] = clean
                for mu in ref.get("member_uuids") or ref.get("memberUuids") or []:
                    if isinstance(mu, str) and mu:
                        uuids.add(mu.replace("urn:uuid:", ""))

    return uuids, idx_map


def _evaluate_weighted_rubric(case: WahsEvalCase, answer_text: str, condensed_text: str) -> tuple[float, list[str]]:
    """Evaluate HealthBench-style positive weighted criteria and negative penalty items.

    When `answer_text` is non-empty, rubric criteria are checked strictly against `answer_text`
    so facts present only in the input `condensed_text` do not inflate answer quality scores.
    """
    target_low = answer_text.lower() if answer_text.strip() else condensed_text.lower()
    ans_low = answer_text.lower()
    rubric_failures: list[str] = []

    total_weight = 0.0
    earned_weight = 0.0
    for item in case.positive_rubric_items:
        weight = float(item.get("weight", 1.0))
        total_weight += weight
        req_any = [str(x).lower() for x in (item.get("required_any") or []) if str(x).strip()]
        if not req_any or any(tok in target_low for tok in req_any):
            earned_weight += weight
        else:
            crit = item.get("criterion") or item.get("id") or str(req_any)
            if item.get("strict", False):
                rubric_failures.append(f"missing required rubric criterion: {crit}")

    base_score = (earned_weight / total_weight) if total_weight > 0 else 1.0

    penalty_total = 0.0
    for neg in case.negative_penalty_items:
        forb_any = [str(x).lower() for x in (neg.get("forbidden_any") or []) if str(x).strip()]
        if forb_any and any(tok in ans_low for tok in forb_any):
            penalty = float(neg.get("penalty", 0.25))
            penalty_total += penalty
            crit = neg.get("criterion") or neg.get("id") or str(forb_any)
            rubric_failures.append(f"negative rubric penalty triggered: {crit}")

    return max(0.0, min(1.0, base_score - penalty_total)), rubric_failures


def _evaluate_atomic_entailment(
    case: WahsEvalCase,
    answer_text: str,
    condensed_text: str,
    known_uuids: set[str],
    idx_map: dict[str, str],
) -> tuple[float, int, list[str]]:
    """Verify VeriFact / MiniCheck-style atomic claim entailment against cited FHIR UUIDs."""
    if not case.citation_entailment_assertions:
        return 1.0, 0, []

    ans_low = answer_text.lower()
    target_low = ans_low if answer_text.strip() else condensed_text.lower()
    cited_uuids = {
        idx_map[n]
        for n in _CITATION_RE.findall(answer_text)
        if n in idx_map and idx_map[n]
    } | known_uuids

    passed_assertions = 0
    distortions = 0
    failures: list[str] = []

    for assertion in case.citation_entailment_assertions:
        target_uuid = str(assertion.get("resource_uuid") or "").replace("urn:uuid:", "")
        must_mention = [str(x).lower() for x in (assertion.get("must_mention_any") or []) if str(x).strip()]
        must_not_distort = [str(x).lower() for x in (assertion.get("must_not_distort") or []) if str(x).strip()]

        uuid_ok = (not target_uuid) or (target_uuid in cited_uuids)
        mention_ok = (not must_mention) or any(tok in target_low for tok in must_mention)
        distort_hit = [tok for tok in must_not_distort if tok in ans_low]

        if distort_hit:
            distortions += len(distort_hit)
            failures.append(
                f"citation distortion for {target_uuid or 'claim'}: found distorted value/status {', '.join(distort_hit)}"
            )
        elif uuid_ok and mention_ok:
            passed_assertions += 1
        else:
            failures.append(
                f"unentailed claim for {target_uuid or 'assertion'}: missing {', '.join(must_mention)}"
            )

    rate = passed_assertions / max(len(case.citation_entailment_assertions), 1)
    return rate, distortions, failures


def score_wahs_case(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    *,
    budget_tokens: int = 8192,
) -> WahsCaseScore:
    """Deterministically score a single WAHS evaluation case response envelope."""
    failures: list[str] = []
    tier_info = envelope.get("tier_info") or {}
    raw_tokens = (
        tier_info.get("actual_tokens")
        if tier_info.get("actual_tokens") is not None
        else envelope.get("actual_tokens")
    )
    actual_tokens = int(raw_tokens) if raw_tokens is not None else 0
    if raw_tokens is None:
        failures.append("missing actual token count")
    token_budget_ok = raw_tokens is not None and actual_tokens <= budget_tokens
    if raw_tokens is not None and not token_budget_ok:
        failures.append(
            f"token budget exceeded: actual_tokens={actual_tokens} > budget_tokens={budget_tokens}"
        )

    known_uuids, idx_map = _extract_known_uuids(envelope)
    answer = str(envelope.get("answer") or "")
    condensed_text = str(envelope.get("condensed_text") or "")

    # 1. Target UUID recall
    if case.expected_target_uuids and not case.must_abstain:
        expected_clean = [u.replace("urn:uuid:", "") for u in case.expected_target_uuids]
        matched = [
            u
            for u in expected_clean
            if u in known_uuids or u in answer or u in condensed_text
        ]
        required_uuid_recall = len(matched) / len(expected_clean)
        if required_uuid_recall < 1.0:
            missing = [u for u in expected_clean if u not in matched]
            failures.append(f"missing expected target UUID(s): {', '.join(missing)}")
    else:
        required_uuid_recall = 1.0

    # 2. Inline citation resolution
    inline_nums = _CITATION_RE.findall(answer)
    if inline_nums:
        resolved = sum(1 for n in inline_nums if n in idx_map and idx_map[n])
        fabricated_citation_count = len(inline_nums) - resolved
        citation_resolution_rate = resolved / len(inline_nums)
        if fabricated_citation_count > 0:
            unresolved = sorted({f"[{n}]" for n in inline_nums if n not in idx_map})
            failures.append(f"unresolved inline citation(s): {', '.join(unresolved)}")
    else:
        fabricated_citation_count = 0
        citation_resolution_rate = 1.0

    sentence_citation_coverage = compute_sentence_citation_coverage(
        answer, idx_map, must_abstain=case.must_abstain
    )

    # 3. Privacy zero-leakage gate
    leaked_items: list[str] = []
    for fu in case.forbidden_uuids:
        clean_fu = fu.replace("urn:uuid:", "")
        if clean_fu in known_uuids or clean_fu in answer or clean_fu in condensed_text:
            leaked_items.append(f"uuid:{clean_fu}")

    terms_to_check = list(case.forbidden_terms)
    if case.sharing_posture == "external_share" and not terms_to_check:
        terms_to_check = list(DEFAULT_SENSITIVE_TERMS)

    # Exclude explicit redaction transparency notice banners when checking forbidden_terms
    redaction_banner = str(envelope.get("redaction_notice") or "")
    inspectable_answer = answer
    if redaction_banner:
        inspectable_answer = inspectable_answer.replace(redaction_banner, "")
    if case.sharing_posture == "external_share" and "REDACTED in External Share" in inspectable_answer:
        inspectable_answer = _REDACTION_BANNER_LINE_RE.sub("", inspectable_answer)

    combined_text = f"{inspectable_answer}\n{condensed_text}".lower()
    for term in terms_to_check:
        t_low = term.lower()
        if len(t_low) <= 4:
            if re.search(rf"\b{re.escape(t_low)}\b", combined_text):
                leaked_items.append(f"term:{term}")
        elif t_low in combined_text:
            leaked_items.append(f"term:{term}")

    privacy_zero_leakage = len(leaked_items) == 0
    if not privacy_zero_leakage:
        failures.append(f"privacy leakage detected: {', '.join(leaked_items)}")

    # 4. Abstention verification (supports both `abstained` and `abstains` keys)
    envelope_abstained = bool(envelope.get("abstained")) or bool(envelope.get("abstains"))
    explicit_abstains = envelope_abstained or bool(_ABSTENTION_RE.search(answer))
    if case.must_abstain:
        abstention_ok = explicit_abstains and fabricated_citation_count == 0
        if not abstention_ok:
            failures.append("failed to abstain cleanly on unanswerable query")
    else:
        abstention_ok = not envelope_abstained and bool(answer.strip() or condensed_text.strip())
        if not abstention_ok:
            failures.append("unexpected abstention or empty output on answerable query")

    # 5. Layer B: Weighted Rubric & Atomic Claim Entailment
    rubric_weighted_score, rubric_failures = _evaluate_weighted_rubric(case, answer, condensed_text)
    failures.extend(rubric_failures)

    atomic_entailment_rate, citation_distortion_count, entailment_failures = _evaluate_atomic_entailment(
        case, answer, condensed_text, known_uuids, idx_map
    )
    failures.extend(entailment_failures)

    plain_summary = str(envelope.get("patient_plain_summary") or "").strip()
    fk_grade = compute_flesch_kincaid_grade(plain_summary if plain_summary else answer)
    readability_alignment_score = compute_readability_alignment_score(
        fk_grade, must_abstain=case.must_abstain
    )

    if not privacy_zero_leakage or not abstention_ok or not token_budget_ok:
        case_quality_score = 0.0
    elif case.must_abstain:
        case_quality_score = round(
            100.0 * (0.75 * float(abstention_ok) + 0.25 * citation_resolution_rate),
            2,
        )
    else:
        cite_factor = (
            sentence_citation_coverage * citation_resolution_rate
            if answer.strip()
            else citation_resolution_rate
        )
        raw_quality = (
            0.30 * required_uuid_recall
            + 0.25 * rubric_weighted_score
            + 0.20 * atomic_entailment_rate
            + 0.15 * cite_factor
            + 0.10 * readability_alignment_score
        )
        case_quality_score = round(100.0 * max(0.0, min(1.0, raw_quality)), 2)

    return WahsCaseScore(
        case_id=case.case_id,
        patient_id=case.patient_id,
        use_case=case.use_case,
        sharing_posture=case.sharing_posture,
        budget_tokens=budget_tokens,
        actual_tokens=actual_tokens,
        token_budget_ok=token_budget_ok,
        required_uuid_recall=required_uuid_recall,
        citation_resolution_rate=citation_resolution_rate,
        fabricated_citation_count=fabricated_citation_count,
        privacy_zero_leakage=privacy_zero_leakage,
        leaked_items=leaked_items,
        abstention_ok=abstention_ok,
        rubric_weighted_score=rubric_weighted_score,
        atomic_entailment_rate=atomic_entailment_rate,
        citation_distortion_count=citation_distortion_count,
        flesch_kincaid_grade=fk_grade,
        question_horizon=case.question_horizon,
        patient_category=case.patient_category,
        passed=len(failures) == 0,
        failures=failures,
        sentence_citation_coverage=sentence_citation_coverage,
        readability_alignment_score=readability_alignment_score,
        case_quality_score=case_quality_score,
    )


class WahsHubClient:
    """HTTP client for Med Agent Hub WAHS endpoints (`/wahs/api/chat` and `/wahs/api/analyze`)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 120.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("MED_AGENT_HUB_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def evaluate_case(self, case: WahsEvalCase, *, budget_tokens: int) -> dict[str, Any]:
        started = time.monotonic()
        chat_resp = self._session.post(
            f"{self.base_url}/wahs/api/chat",
            json={
                "patient_id": case.patient_id,
                "question": case.prompt,
                "sharing_posture": case.sharing_posture,
                "target_tokens": budget_tokens,
            },
            timeout=self.timeout,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        if chat_resp.status_code != 200:
            raise RuntimeError(
                f"WAHS chat failed [{chat_resp.status_code}] for {case.case_id}: {chat_resp.text[:300]}"
            )
        payload = dict(chat_resp.json())
        payload.setdefault("latency_ms", latency_ms)
        return payload


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


def _summarize_scores(
    scores: list[WahsCaseScore],
    *,
    evaluation_modality: str = "deterministic_pipeline",
) -> dict[str, Any]:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    by_use_case: dict[str, dict[str, Any]] = {}
    by_horizon: dict[str, dict[str, Any]] = {}

    for s in scores:
        bucket = by_use_case.setdefault(
            s.use_case,
            {
                "total": 0,
                "passed": 0,
                "uuid_recall_sum": 0.0,
                "citation_rate_sum": 0.0,
                "sentence_cite_sum": 0.0,
                "rubric_score_sum": 0.0,
                "entailment_sum": 0.0,
                "quality_score_sum": 0.0,
                "privacy_leaks": 0,
            },
        )
        bucket["total"] += 1
        bucket["passed"] += int(s.passed)
        bucket["uuid_recall_sum"] += s.required_uuid_recall
        bucket["citation_rate_sum"] += s.citation_resolution_rate
        bucket["sentence_cite_sum"] += s.sentence_citation_coverage
        bucket["rubric_score_sum"] += s.rubric_weighted_score
        bucket["entailment_sum"] += s.atomic_entailment_rate
        bucket["quality_score_sum"] += s.case_quality_score
        bucket["privacy_leaks"] += int(not s.privacy_zero_leakage)

        h_bucket = by_horizon.setdefault(
            s.question_horizon,
            {
                "total": 0,
                "passed": 0,
                "uuid_recall_sum": 0.0,
                "rubric_score_sum": 0.0,
                "quality_score_sum": 0.0,
            },
        )
        h_bucket["total"] += 1
        h_bucket["passed"] += int(s.passed)
        h_bucket["uuid_recall_sum"] += s.required_uuid_recall
        h_bucket["rubric_score_sum"] += s.rubric_weighted_score
        h_bucket["quality_score_sum"] += s.case_quality_score

    use_case_summary = {}
    for uc, b in sorted(by_use_case.items()):
        n = b["total"] or 1
        use_case_summary[uc] = {
            "total": b["total"],
            "passed": b["passed"],
            "pass_rate": round(b["passed"] / n, 4),
            "mean_uuid_recall": round(b["uuid_recall_sum"] / n, 4),
            "mean_citation_resolution_rate": round(b["citation_rate_sum"] / n, 4),
            "mean_sentence_citation_coverage": round(b["sentence_cite_sum"] / n, 4),
            "mean_rubric_weighted_score": round(b["rubric_score_sum"] / n, 4),
            "mean_atomic_entailment_rate": round(b["entailment_sum"] / n, 4),
            "mean_case_quality_score": round(b["quality_score_sum"] / n, 2),
            "privacy_leaks": b["privacy_leaks"],
        }

    horizon_summary = {}
    for hz, hb in sorted(by_horizon.items()):
        n = hb["total"] or 1
        horizon_summary[hz] = {
            "total": hb["total"],
            "passed": hb["passed"],
            "pass_rate": round(hb["passed"] / n, 4),
            "mean_uuid_recall": round(hb["uuid_recall_sum"] / n, 4),
            "mean_rubric_weighted_score": round(hb["rubric_score_sum"] / n, 4),
            "mean_case_quality_score": round(hb["quality_score_sum"] / n, 2),
        }

    return {
        "evaluation_modality": evaluation_modality,
        "total_cells": total,
        "passed_cells": passed,
        "pass_rate": round(passed / (total or 1), 4),
        "token_budget_compliance_rate": round(
            sum(1 for s in scores if s.token_budget_ok) / (total or 1), 4
        ),
        "mean_uuid_recall": round(
            sum(s.required_uuid_recall for s in scores) / (total or 1), 4
        ),
        "mean_citation_resolution_rate": round(
            sum(s.citation_resolution_rate for s in scores) / (total or 1), 4
        ),
        "mean_sentence_citation_coverage": round(
            sum(s.sentence_citation_coverage for s in scores) / (total or 1), 4
        ),
        "mean_rubric_weighted_score": round(
            sum(s.rubric_weighted_score for s in scores) / (total or 1), 4
        ),
        "mean_atomic_entailment_rate": round(
            sum(s.atomic_entailment_rate for s in scores) / (total or 1), 4
        ),
        "citation_distortion_count": sum(s.citation_distortion_count for s in scores),
        "mean_flesch_kincaid_grade": round(
            sum(s.flesch_kincaid_grade for s in scores) / (total or 1), 2
        ),
        "mean_readability_alignment_score": round(
            sum(s.readability_alignment_score for s in scores) / (total or 1), 4
        ),
        "mean_case_quality_score": round(
            sum(s.case_quality_score for s in scores) / (total or 1), 2
        ),
        "privacy_leak_count": sum(1 for s in scores if not s.privacy_zero_leakage),
        "abstention_accuracy": round(
            sum(1 for s in scores if s.abstention_ok) / (total or 1), 4
        ),
        "by_use_case": use_case_summary,
        "by_question_horizon": horizon_summary,
    }


def run_wahs_suite(
    cases_path: Path | str,
    *,
    client: Any,
    output_dir: Path | str = "artifacts/wahs",
    budgets: tuple[int, ...] | list[int] | None = None,
    git_sha: str | None = None,
    target_provenance: list[dict[str, Any]] | None = None,
    dataset_id: str = "wahs-synthetic-r4",
    dataset_version: str = "2026.10",
    evaluation_modality: str = "deterministic_pipeline",
) -> WahsRunResult:
    """Execute a WAHS evaluation suite against `client` and freeze all artifacts in `<output_dir>/<run_id>`."""
    if evaluation_modality not in VALID_EVALUATION_MODALITIES:
        raise ValueError(
            f"Invalid evaluation_modality '{evaluation_modality}'. Expected one of {VALID_EVALUATION_MODALITIES}"
        )
    cases_file = Path(cases_path)
    cases_bytes = cases_file.read_bytes()
    suite_sha256 = hashlib.sha256(cases_bytes).hexdigest()
    cases = load_wahs_cases(cases_file)

    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    frozen_cases_path = inputs_dir / "wahs_eval_cases.jsonl"
    frozen_cases_path.write_bytes(cases_bytes)

    frozen_provenance = copy_target_provenance(target_provenance)
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="wahs-evaluation",
        git_sha=git_sha,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_mapping_version="fhir-r4-uscore-ips@v1",
        gen_ai_provider_name="med-agent-hub",
        gen_ai_operation_name="wahs_condense_and_qa",
        evidence_status="development",
        target_provenance=frozen_provenance,
        report_family="wahs",
        evaluation_modality=evaluation_modality,
        suite_id=cases_file.stem,
        suite_sha256=suite_sha256,
    )
    manifest_path = run_dir / "run_manifest.json"
    events_path = run_dir / "events.jsonl"
    write_manifest(manifest_path, manifest)
    append_event(
        events_path,
        {
            "event_type": "run",
            "run_id": run_id,
            "component": "wahs-evaluation",
            "evaluation_modality": evaluation_modality,
            "suite_sha256": suite_sha256,
        },
    )

    results_path = run_dir / "results.jsonl"
    scores: list[WahsCaseScore] = []
    with results_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            active_budgets = list(budgets) if budgets else list(case.target_token_budgets[:1] or [8192])
            for b_tokens in active_budgets:
                envelope = client.evaluate_case(case, budget_tokens=b_tokens)
                score = score_wahs_case(case, envelope, budget_tokens=b_tokens)
                scores.append(score)
                row = {
                    "case_id": case.case_id,
                    "patient_id": case.patient_id,
                    "use_case": case.use_case,
                    "sharing_posture": case.sharing_posture,
                    "budget_tokens": b_tokens,
                    "request": {
                        "prompt": case.prompt,
                        "sharing_posture": case.sharing_posture,
                        "budget_tokens": b_tokens,
                    },
                    "response": envelope,
                    "score": score.to_dict(),
                }
                fh.write(json.dumps(row) + "\n")

    summary = _summarize_scores(scores, evaluation_modality=evaluation_modality)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    append_event(
        events_path,
        {
            "event_type": "evaluation",
            "run_id": run_id,
            "check": "wahs_suite",
            "evaluation_modality": evaluation_modality,
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


def score_wahs_run(run_dir: Path | str) -> dict[str, Any]:
    """Re-score a frozen WAHS run directory offline without network or target access."""
    rdir = Path(run_dir)
    cases_path = rdir / "inputs" / "wahs_eval_cases.jsonl"
    results_path = rdir / "results.jsonl"
    manifest_path = rdir / "run_manifest.json"
    evaluation_modality = "deterministic_pipeline"
    if manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        evaluation_modality = str(manifest_data.get("evaluation_modality") or "deterministic_pipeline")
        if "evaluation_modality" not in manifest_data:
            manifest_data["evaluation_modality"] = evaluation_modality
            manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    cases_by_id = {c.case_id: c for c in load_wahs_cases(cases_path)}

    scores: list[WahsCaseScore] = []
    expectations_path = rdir / "expectations.jsonl"
    with expectations_path.open("w", encoding="utf-8") as exp_fh:
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            case = cases_by_id[row["case_id"]]
            b_tokens = int(row.get("budget_tokens") or 8192)
            score = score_wahs_case(case, row.get("response") or {}, budget_tokens=b_tokens)
            scores.append(score)
            exp_fh.write(json.dumps(score.to_dict()) + "\n")

    summary = _summarize_scores(scores, evaluation_modality=evaluation_modality)
    (rdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
