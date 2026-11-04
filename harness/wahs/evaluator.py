"""Deterministic and multi-modality evaluation runner for WAHS+ FHIR R4 condensation & Q&A.

Supports three distinct evaluation modalities (`evaluation_modality`), forwarded to
`WahsHubClient.evaluate_case` and recorded in `run_manifest.json` and `summary.json`:
1. `deterministic_pipeline` (Deterministic Pipeline Gate):
   Evaluates the deterministic 5-Tier FHIR Condenser (`condense_mode="tiered"`,
   `use_lookup_tools=False`) and 4-Layer Clinical KB rules (token budget compliance,
   IPS safety core retention, deterministic conflict recall, and zero-leakage privacy redaction).
2. `condensation_retrieval_ablation` (Condensation & Retrieval Ablation):
   Evaluates structural information retention (`condense_mode="lossless_structural"`,
   `use_lookup_tools=False`) across token budgets stratified by question horizon.
3. `live_model_and_team_eval` (Live Model & KB Team Evaluation):
   Evaluates hybrid condensation with on-demand lookup tools (`condense_mode="lossless_structural"`,
   `use_lookup_tools=True`), combining deterministic citation/privacy gates with HealthBench-style
   weighted rubrics, VeriFact atomic claim entailment, and patient readability metrics.

Runs offline against frozen run directories or live against a caller-supplied
Med Agent Hub HTTP endpoint without importing product source trees or calling Git/Docker.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from ..metadata import RunManifest, append_event, copy_target_provenance, write_manifest

_CITATION_RE = re.compile(r"\[(\d+)\]")
_ABSTENTION_RE = re.compile(
    r"\b("
    r"not documented|no documented|no documentation|not recorded|no record|no records|"
    r"no information|not listed|cannot find|do not see|does not show|"
    r"cannot verify|not found in|not present in|does not contain|do not contain|"
    r"does not include|does not list|not mentioned|no mention|not available|"
    r"abstain|abstains|grounded abstention"
    r")\b",
    re.IGNORECASE,
)
_ABSTENTION_META_OR_NEG_RE = re.compile(
    r"\b(?:"
    r"not\s+documented|no\s+documented|no\s+documentation|not\s+recorded|no\s+records?|"
    r"no\s+information|not\s+listed|cannot\s+find|do\s+not\s+see|does\s+not\s+show|"
    r"cannot\s+verify|not\s+found\s+in|not\s+present\s+in|does\s+not\s+(?:contain|include|list|document|show)|"
    r"do\s+not\s+(?:contain|include|list|document|show)|not\s+mentioned|no\s+mention|not\s+available|unavailable|"
    r"abstain|abstains|grounded\s+abstention|neither|nor|cannot\s+answer|cannot\s+provide|unable\s+to|"
    r"no\s+matching\s+records|unrecorded|undocumented|missing|absent|without|none|no\s+evidence|no\s+results?|"
    r"safety\s+posture|grounding\s+rules|external\s+share|external_share|patient_self|"
    r"42\s+cfr|mhmda|my\s+health\s+my\s+data|redacted|excluded|withheld|hidden|"
    r"switch\s+(?:back\s+)?to|ask\s+your\s+doctor|doctor|physician|provider|clinic|clinician|care\s+team|specialist|"
    r"only\s+reports\s+facts|chart|bundle|health\s+records?|medical\s+records?|reviewed|however|while|although|if\s+you"
    r")\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_CLINICAL_FINDING_RE = re.compile(
    r"\b(?:"
    r"showed|shows|revealed|reveals|demonstrated|demonstrates|confirmed|confirms|"
    r"diagnosed\s+with|positive\s+for|negative\s+for|was\s+found\s+to\s+have|"
    r"cancer|malignan\w+|carcinoma|tumor|infarct|stroke|hemorrhage|anaphylaxis|"
    r"is\s+\d+(?:\.\d+)?\s*(?:%|mg|ml|mmol|g/dl|iu)"
    r")\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z]+")
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<!\bvs)(?<!\bdr)(?<!\bmr)(?<!\bms)(?:[.!?;]+(?:\s|$))|\n+",
    re.IGNORECASE,
)
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)

_ANOMALY_DENIAL_RE = re.compile(
    r"\b(?:"
    r"no\s+(?:active\s+)?(?:duplicate|conflicting|conflicts?|anomal(?:y|ies)|contradictions?|discrepanc(?:y|ies)|interaction\s+hazards?)|"
    r"there\s+are\s+no\s+(?:duplicate|conflicting|conflicts?|anomal(?:y|ies)|contradictions?)|"
    r"without\s+(?:any\s+)?(?:duplicate|conflict|anomal|contradiction)|"
    r"equivalence\s+is\s+not\s+flagged|"
    r"no\s+medication\s+conflicts?\b"
    r")",
    re.IGNORECASE,
)
_ANOMALY_AFFIRM_RE = re.compile(
    r"\b(?:"
    r"duplicat(?:e|ed|es|ion)|conflict(?:s|ing)?|contradict(?:s|ion|ory)?|"
    r"discrepanc(?:y|ies)|anomal(?:y|ies)|both\s+active|simultaneously|concurrent(?:ly)?|"
    r"supersed(?:e|ed|es)|overlap(?:ping)?|hazard|interaction|alert|flagged|"
    r"hold|discontinu(?:e|ed|ation)|stop(?:ped)?|redacted|sensitive|privacy|"
    r"3rd\s+.*?\bdose|2\s+doses|repeat\s+doses?|same\s+(?:drug\s+)?class|therapeutic\s+class"
    r")\b",
    re.IGNORECASE,
)
_ANOMALY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "statin": ("statin", "simvastatin", "atorvastatin", "lipitor", "rosuvastatin", "pravastatin", "hmg-coa"),
    "flu": ("flu", "influenza"),
    "covid": ("covid", "sars-cov-2"),
    "hpv": ("hpv", "papillomavirus"),
    "zoster": ("zoster", "shingles", "zostavax", "shingrix"),
    "ckd": ("ckd", "kidney", "renal", "egfr"),
    "prediabetes": ("prediabetes", "diabetes", "glycemic", "a1c", "hba1c"),
    "diabetes": ("diabetes", "prediabetes", "glycemic", "a1c", "hba1c"),
    "glycemic": ("diabetes", "prediabetes", "glycemic", "a1c", "hba1c"),
    "sinusitis": ("sinusitis", "sinus"),
    "lisinopril": ("lisinopril", "prinivil", "ace"),
    "prinivil": ("prinivil", "lisinopril", "ace"),
    "clopidogrel": ("clopidogrel", "plavix", "antiplatelet", "thienopyridine"),
    "plavix": ("plavix", "clopidogrel", "antiplatelet", "thienopyridine"),
    "simvastatin": ("simvastatin", "lipitor", "atorvastatin", "statin", "hmg-coa"),
    "lipitor": ("lipitor", "simvastatin", "atorvastatin", "statin", "hmg-coa"),
    "hyperkalemia": ("hyperkalemia", "potassium", "spironolactone", "aldactone", "kcl"),
    "anticoag": ("anticoag", "warfarin", "eliquis", "apixaban", "hemorrhage", "bleed", "gastrointestinal"),
    "gib": ("hemorrhage", "bleed", "gastrointestinal", "gi", "warfarin", "eliquis", "naproxen"),
    "beers": ("beers", "sedative", "lorazepam", "ativan", "zolpidem", "ambien"),
    "sedative": ("sedative", "beers", "lorazepam", "ativan", "zolpidem", "ambien"),
    "ipv": ("intimate partner", "abuse", "domestic", "ipv", "privacy", "sensitive", "sdoh", "redacted"),
    "criminal": ("criminal", "record", "privacy", "sensitive", "sdoh", "redacted"),
}
_ANOMALY_STOPWORDS = {
    "anom",
    "anomaly",
    "uc",
    "case",
    "seta",
    "setb",
    "setc",
    "dup",
    "duplicate",
    "conflict",
    "reconcile",
    "byron",
    "lamar",
    "maurice",
    "elena",
    "arthur",
    "margaret",
    "live",
    "repeat",
    "status",
    "stage",
    "3dose",
    "age11",
    "iis",
    "pharmacy",
    "dual",
    "and",
    "privacy",
    "sdoh",
}

VALID_EVALUATION_MODALITIES = (
    "deterministic_pipeline",
    "condensation_retrieval_ablation",
    "live_model_and_team_eval",
)

DEFAULT_TOKEN_BUDGETS = (8192, 4096, 2048, 1024, 512)

VALID_CONTEXT_ARMS = (
    "raw_fhir_json",
    "lossless_structural",
    "tiered_condensed",
    "hybrid_lookup",
)

VALID_CONDENSE_MODES = (
    "tiered",
    "lossless_structural",
    "hierarchical",
)

# Synchronized with Med Agent Hub `server/fhir/normalizers.py` (`_PRIVACY_SENSITIVE_PATTERNS`).
DEFAULT_SENSITIVE_TERMS = (
    "intimate partner violence",
    "victim of intimate partner abuse",
    "intimate partner abuse",
    "ipv",
    "domestic abuse",
    "domestic violence",
    "violence in the environment",
    "criminal record",
    "unhealthy alcohol",
    "alcohol abuse",
    "drug abuse",
    "substance abuse",
    "sexual assault",
    "limited social contact",
    "social isolation",
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
        return 1.0 if (inline and any(n in idx_map and idx_map[n] for n in inline)) else 0.0

    cited_count = 0
    for seg in substantive:
        nums = _CITATION_RE.findall(seg)
        if nums and any(n in idx_map and idx_map[n] for n in nums):
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
    target_token_budgets: list[int] = field(default_factory=lambda: list(DEFAULT_TOKEN_BUDGETS))
    expected_anomaly_ids: list[str] = field(default_factory=list)
    expected_target_uuids: list[str] = field(default_factory=list)
    valid_uuids: list[str] = field(default_factory=list)
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
        budgets = [int(b) for b in (data.get("target_token_budgets") or DEFAULT_TOKEN_BUDGETS)]
        exp_uuids = data.get("expected_target_uuids") or data.get("expected_resource_uuids") or []
        valid_uuids = data.get("valid_uuids") or data.get("chart_uuids") or []
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
        rubric_criteria = [str(x) for x in (data.get("rubric_criteria") or [])]
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
            valid_uuids=[str(x) for x in valid_uuids],
            forbidden_uuids=[str(x) for x in forb_uuids],
            forbidden_terms=[str(x) for x in (data.get("forbidden_terms") or [])],
            must_abstain=must_abstain,
            rubric_criteria=rubric_criteria,
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


def _extract_known_uuids(
    envelope: dict[str, Any],
) -> tuple[set[str], dict[str, str], dict[str, set[str]]]:
    """Return `(all_uuid_set, index_to_primary_uuid_map, index_to_all_uuids_map)` from a WAHS response envelope."""
    uuids: set[str] = set()
    idx_map: dict[str, str] = {}
    idx_all_uuids: dict[str, set[str]] = {}

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
                idx_all_uuids.setdefault(key_num, set()).add(clean)
            elif isinstance(v, dict):
                raw_u = str(v.get("resourceUuid") or v.get("uuid") or v.get("id") or "")
                if raw_u:
                    clean = raw_u.replace("urn:uuid:", "")
                    uuids.add(clean)
                    idx_map[key_num] = clean
                    idx_all_uuids.setdefault(key_num, set()).add(clean)

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
                bucket = idx_all_uuids.setdefault(c_idx, set())
                if raw_u:
                    clean = raw_u.replace("urn:uuid:", "")
                    uuids.add(clean)
                    idx_map[c_idx] = clean
                    bucket.add(clean)
                for mu in ref.get("member_uuids") or ref.get("memberUuids") or []:
                    if isinstance(mu, str) and mu:
                        uuids.add(mu.replace("urn:uuid:", ""))
                        bucket.add(mu.replace("urn:uuid:", ""))

    for c_idx in list(idx_all_uuids.keys()):
        idx_all_uuids[c_idx] = idx_all_uuids[c_idx] & uuids

    return uuids, idx_map, idx_all_uuids


def _extract_trusted_uuids(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    valid_uuids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> set[str]:
    """Collect trusted record UUIDs from caller/case/chart expectations or condensation mappings.
    Never trusts self-declared `references`, `citations`, `citation_map`, `valid_uuids`, or `retained_uuids`
    from the response alone.
    """
    trusted: set[str] = set()
    for source in (
        valid_uuids or (),
        case.valid_uuids,
        case.expected_target_uuids,
    ):
        for u in source:
            if isinstance(u, str) and u.strip():
                trusted.add(u.strip().replace("urn:uuid:", ""))

    for assertion in case.citation_entailment_assertions:
        if isinstance(assertion, dict):
            ru = str(assertion.get("resource_uuid") or "").strip().replace("urn:uuid:", "")
            if ru:
                trusted.add(ru)

    mappings = (
        envelope.get("mappings")
        or (envelope.get("condensation") or {}).get("mappings")
        or []
    )
    if isinstance(mappings, list):
        for m in mappings:
            if not isinstance(m, dict):
                continue
            ru = str(m.get("resourceUuid") or m.get("resource_uuid") or "").strip().replace("urn:uuid:", "")
            if ru:
                trusted.add(ru)
            for mu in m.get("memberUuids") or m.get("member_uuids") or []:
                if isinstance(mu, str) and mu.strip():
                    trusted.add(mu.strip().replace("urn:uuid:", ""))

    condensed_text = str(envelope.get("condensed_text") or "")
    if condensed_text:
        for cand in _extract_known_uuids(envelope)[0]:
            if len(cand) >= 4 and cand in condensed_text:
                trusted.add(cand)

    return trusted


def _collect_delivered_text(envelope: dict[str, Any]) -> str:
    """Gather all delivered text fields from a WAHS response envelope for privacy inspection."""
    parts: list[str] = []
    for key in (
        "answer",
        "condensed_text",
        "chart_text",
        "patient_plain_summary",
        "clinician_technical_note",
        "clinician_summary",
        "abstention_reason",
        "redaction_notice",
    ):
        val = envelope.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    for list_key in ("what_to_ask_doctor", "questions_for_doctor"):
        items = envelope.get(list_key)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, str) and it.strip():
                    parts.append(it)
        elif isinstance(items, str) and items.strip():
            parts.append(items)
    for ref_key in ("references", "citations", "anomalies", "findings", "redacted_for_privacy"):
        items = envelope.get(ref_key)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    for sub_k in ("text", "display", "title", "summary", "description", "patient_plain_summary"):
                        sub_v = it.get(sub_k)
                        if isinstance(sub_v, str) and sub_v.strip():
                            parts.append(sub_v)
                elif isinstance(it, str) and it.strip():
                    parts.append(it)
    return "\n".join(parts)


def _evaluate_expected_anomalies(
    case: WahsEvalCase,
    answer_text: str,
    envelope: dict[str, Any],
) -> list[str]:
    """Verify each `expected_anomaly_ids` entry is affirmed (and not denied) in the response."""
    if not case.expected_anomaly_ids or case.must_abstain:
        return []

    ans_low = (answer_text or "").lower()
    if not ans_low.strip():
        return [f"missing expected anomaly in empty answer: {', '.join(case.expected_anomaly_ids)}"]

    has_denial = bool(_ANOMALY_DENIAL_RE.search(answer_text))
    has_affirm = bool(_ANOMALY_AFFIRM_RE.search(answer_text))

    structured_ids: set[str] = set()
    for key in ("anomaly_ids", "anomalies", "detected_anomalies", "findings"):
        raw = envelope.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    structured_ids.add(item.strip().lower())
                elif isinstance(item, dict):
                    for k in ("id", "anomaly_id", "kb_rule_id", "title", "domain"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            structured_ids.add(v.strip().lower())

    missing: list[str] = []
    for anom_id in case.expected_anomaly_ids:
        anom_low = anom_id.strip().lower()
        if not anom_low:
            continue
        if has_denial:
            missing.append(anom_id)
            continue
        if anom_low in structured_ids or anom_low in ans_low:
            continue

        raw_tokens = [
            tok
            for tok in re.split(r"[^a-z0-9]+", anom_low)
            if tok and tok not in _ANOMALY_STOPWORDS
        ]
        domain_matched = False
        if not raw_tokens:
            domain_matched = True
        else:
            for tok in raw_tokens:
                candidates = _ANOMALY_SYNONYMS.get(tok, (tok,))
                if any(cand in ans_low for cand in candidates):
                    domain_matched = True
                    break
        if not (has_affirm and domain_matched):
            missing.append(anom_id)

    if missing:
        return [f"missing or denied expected anomaly: {', '.join(missing)}"]
    return []


def _evaluate_weighted_rubric(
    case: WahsEvalCase,
    answer_text: str,
    condensed_text: str,
) -> tuple[float, list[str]]:
    """Evaluate HealthBench-style positive weighted criteria, `expected_facts`, `rubric_criteria`,
    and negative penalty items strictly against `answer_text`.
    """
    ans_low = (answer_text or "").lower()
    rubric_failures: list[str] = []

    effective_positive: list[dict[str, Any]] = list(case.positive_rubric_items)
    if not effective_positive and case.expected_facts:
        effective_positive = [
            {
                "id": f"fact_{idx + 1}",
                "criterion": f"Mentions grounded clinical fact '{fact}'",
                "required_any": [fact],
                "weight": 1.0,
            }
            for idx, fact in enumerate(case.expected_facts)
        ]
    for idx, crit_text in enumerate(case.rubric_criteria):
        if str(crit_text).strip():
            effective_positive.append(
                {
                    "id": f"rubric_criterion_{idx + 1}",
                    "criterion": str(crit_text),
                    "required_any": [str(crit_text)],
                    "weight": 1.0,
                }
            )

    total_weight = 0.0
    earned_weight = 0.0
    for item in effective_positive:
        weight = float(item.get("weight", 1.0))
        total_weight += weight
        req_any = [str(x).lower() for x in (item.get("required_any") or []) if str(x).strip()]
        req_all = [
            str(x).lower()
            for x in (item.get("required_all") or item.get("required_keywords") or [])
            if str(x).strip()
        ]
        if req_all and req_any:
            crit_matched = all(tok in ans_low for tok in req_all) and any(
                tok in ans_low for tok in req_any
            )
        elif req_all:
            crit_matched = all(tok in ans_low for tok in req_all)
        elif req_any:
            crit_matched = any(tok in ans_low for tok in req_any)
        else:
            crit_matched = True
        if ans_low.strip() and crit_matched:
            earned_weight += weight
        else:
            crit = item.get("criterion") or item.get("id") or str(req_any or req_all)
            if item.get("strict", True) and not item.get("optional", False):
                rubric_failures.append(f"missing required rubric criterion: {crit}")

    if total_weight > 0:
        base_score = earned_weight / total_weight
    else:
        base_score = 1.0 if (ans_low.strip() or case.must_abstain) else 0.0

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
    idx_all_uuids: dict[str, set[str]] | None = None,
    trusted_uuids: set[str] | None = None,
) -> tuple[float, int, list[str]]:
    """Verify VeriFact / MiniCheck-style atomic claim entailment against the inline `[N]`
    citations on the supporting answer claim/sentence.
    """
    if not case.citation_entailment_assertions:
        return (1.0 if (answer_text.strip() or case.must_abstain) else 0.0), 0, []

    ans_low = (answer_text or "").lower()
    if not ans_low.strip():
        return (
            0.0,
            0,
            ["unentailed claim: answer text is empty"],
        )

    effective_idx_uuids: dict[str, set[str]] = {}
    for k, u in idx_map.items():
        s = set((idx_all_uuids or {}).get(k, set()))
        if u:
            s.add(u)
        if trusted_uuids is not None:
            s = s & trusted_uuids
        effective_idx_uuids[k] = s

    all_inline_cited_uuids: set[str] = set()
    for n in _CITATION_RE.findall(answer_text):
        all_inline_cited_uuids.update(effective_idx_uuids.get(n, set()))

    lines = [ln.strip() for ln in answer_text.splitlines() if ln.strip()] or [answer_text]
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer_text) if s.strip()] or [answer_text]

    passed_assertions = 0
    distortions = 0
    failures: list[str] = []

    for assertion in case.citation_entailment_assertions:
        single_uuid = str(assertion.get("resource_uuid") or "").replace("urn:uuid:", "")
        allowed_uuids = {
            str(u).replace("urn:uuid:", "")
            for u in (assertion.get("allowed_resource_uuids") or [])
            if str(u).strip()
        }
        if single_uuid:
            allowed_uuids.add(single_uuid)
        target_label = single_uuid or (", ".join(sorted(allowed_uuids)) if allowed_uuids else "claim")

        must_mention_any = [
            str(x).lower() for x in (assertion.get("must_mention_any") or []) if str(x).strip()
        ]
        must_mention_all = [
            str(x).lower()
            for x in (assertion.get("must_mention_all") or assertion.get("claim_keywords") or [])
            if str(x).strip()
        ]
        must_not_distort = [
            str(x).lower() for x in (assertion.get("must_not_distort") or []) if str(x).strip()
        ]

        distort_hit = [tok for tok in must_not_distort if tok in ans_low]
        if distort_hit:
            distortions += len(distort_hit)
            failures.append(
                f"citation distortion for {target_label}: found distorted value/status {', '.join(distort_hit)}"
            )
            continue

        if must_mention_all and must_mention_any:
            mention_ok = all(tok in ans_low for tok in must_mention_all) and any(
                tok in ans_low for tok in must_mention_any
            )
        elif must_mention_all:
            mention_ok = all(tok in ans_low for tok in must_mention_all)
        elif must_mention_any:
            mention_ok = any(tok in ans_low for tok in must_mention_any)
        else:
            mention_ok = True

        if not mention_ok:
            missing_desc = ", ".join(must_mention_all or must_mention_any)
            failures.append(
                f"unentailed claim for {target_label}: missing {missing_desc}"
            )
            continue

        if not allowed_uuids:
            passed_assertions += 1
            continue

        mention_tokens = must_mention_any or must_mention_all
        if mention_tokens:
            # Bind the assertion to the inline citation(s) on the supporting sentence or line
            uuid_ok = False
            matching_sentences = [
                s for s in sentences if any(tok in s.lower() for tok in mention_tokens)
            ]
            for sent in matching_sentences:
                sent_cites = _CITATION_RE.findall(sent)
                if sent_cites:
                    sent_uuids = {
                        u for n in sent_cites for u in effective_idx_uuids.get(n, set())
                    }
                    if sent_uuids & allowed_uuids:
                        uuid_ok = True
                        break
                else:
                    # Sentence had no inline citation of its own; check enclosing line if it has citations
                    for ln in lines:
                        if sent in ln:
                            ln_cites = _CITATION_RE.findall(ln)
                            ln_uuids = {
                                u for n in ln_cites for u in effective_idx_uuids.get(n, set())
                            }
                            if ln_uuids & allowed_uuids:
                                uuid_ok = True
                                break
                    if uuid_ok:
                        break
            if not uuid_ok and (all_inline_cited_uuids & allowed_uuids):
                # Also accept when the claim keywords appear across adjacent lines in the same section
                # and the allowed resource UUID is cited inline in the answer.
                uuid_ok = True
        else:
            uuid_ok = bool(all_inline_cited_uuids & allowed_uuids)

        if uuid_ok:
            passed_assertions += 1
        else:
            failures.append(
                f"unentailed claim for {target_label}: supporting claim does not cite expected resource"
            )

    rate = passed_assertions / max(len(case.citation_entailment_assertions), 1)
    return rate, distortions, failures


def _is_clean_abstention(answer_text: str, envelope: dict[str, Any]) -> bool:
    """Verify a `must_abstain` response explicitly abstains without making contradictory
    affirmative clinical assertions.
    """
    if not (answer_text or "").strip():
        return False
    if ("abstained" in envelope and envelope["abstained"] is False) or (
        "abstains" in envelope and envelope["abstains"] is False
    ):
        return False

    summary_part = re.split(
        r"\n+\s*(?:#+\s*)?QUESTIONS[_\s]+FOR[_\s]+(?:YOUR[_\s]+)?(?:DOCTOR|CLINICIAN|PROVIDER)\s*:?",
        answer_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    envelope_abstained = bool(envelope.get("abstained")) or bool(envelope.get("abstains"))
    explicit_abstains = envelope_abstained or bool(_ABSTENTION_RE.search(summary_part))
    if not explicit_abstains:
        return False

    raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(summary_part) if s.strip()]
    for sent in raw_sentences:
        if sent.startswith("#") or sent.endswith(":"):
            continue
        words = _WORD_RE.findall(sent)
        if len(words) < 3:
            continue
        has_neg_or_meta = bool(_ABSTENTION_META_OR_NEG_RE.search(sent))
        has_explicit_abstain = bool(_ABSTENTION_RE.search(sent))
        has_affirm_finding = bool(_AFFIRMATIVE_CLINICAL_FINDING_RE.search(sent))
        if has_affirm_finding and not has_explicit_abstain and not _CITATION_RE.search(sent):
            return False
        if not has_neg_or_meta and not _CITATION_RE.search(sent):
            return False

    return True


def score_wahs_case(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    *,
    budget_tokens: int = 8192,
    valid_uuids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> WahsCaseScore:
    """Deterministically score a single WAHS evaluation case response envelope."""
    failures: list[str] = []
    tier_info = envelope.get("tier_info") if isinstance(envelope.get("tier_info"), dict) else {}
    raw_tokens = (
        tier_info.get("actual_tokens")
        if tier_info.get("actual_tokens") is not None
        else envelope.get("actual_tokens")
    )
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

    known_uuids, idx_map, idx_all_uuids = _extract_known_uuids(envelope)
    trusted_uuids = _extract_trusted_uuids(case, envelope, valid_uuids=valid_uuids)
    answer = str(envelope.get("answer") or "")
    condensed_text = str(envelope.get("condensed_text") or "")

    # 1. Target UUID recall & Expected Anomaly verification
    if case.expected_target_uuids and not case.must_abstain:
        expected_clean = [u.replace("urn:uuid:", "") for u in case.expected_target_uuids]
        matched = [
            u
            for u in expected_clean
            if u in known_uuids or u in answer
        ]
        required_uuid_recall = len(matched) / len(expected_clean)
        if required_uuid_recall < 1.0:
            missing = [u for u in expected_clean if u not in matched]
            failures.append(f"missing expected target UUID(s): {', '.join(missing)}")
    else:
        required_uuid_recall = 1.0

    anomaly_failures = _evaluate_expected_anomalies(case, answer, envelope)
    failures.extend(anomaly_failures)

    # 2. Inline citation resolution against trusted case/chart evidence
    trusted_idx_map: dict[str, str] = {}
    for k, primary_u in idx_map.items():
        cand_set = set(idx_all_uuids.get(k, set()))
        if primary_u in known_uuids:
            cand_set.add(primary_u)
        matched_trusted = cand_set & trusted_uuids
        if matched_trusted:
            trusted_idx_map[k] = primary_u if primary_u in matched_trusted else sorted(matched_trusted)[0]

    inline_nums = _CITATION_RE.findall(answer)
    if inline_nums:
        resolved = sum(1 for n in inline_nums if n in trusted_idx_map and trusted_idx_map[n])
        fabricated_citation_count = len(inline_nums) - resolved
        citation_resolution_rate = resolved / len(inline_nums)
        if fabricated_citation_count > 0:
            unresolved = sorted({f"[{n}]" for n in inline_nums if n not in trusted_idx_map})
            failures.append(f"unresolved inline citation(s): {', '.join(unresolved)}")
    else:
        fabricated_citation_count = 0
        citation_resolution_rate = 1.0

    sentence_citation_coverage = compute_sentence_citation_coverage(
        answer, trusted_idx_map, must_abstain=case.must_abstain
    )

    # 3. Privacy zero-leakage gate across all delivered text fields
    leaked_items: list[str] = []
    delivered_text = _collect_delivered_text(envelope)
    for fu in case.forbidden_uuids:
        clean_fu = fu.replace("urn:uuid:", "")
        if clean_fu in known_uuids or clean_fu in delivered_text:
            leaked_items.append(f"uuid:{clean_fu}")

    terms_to_check = list(case.forbidden_terms)
    if case.sharing_posture == "external_share":
        existing_lower = {t.lower() for t in terms_to_check}
        for dt in DEFAULT_SENSITIVE_TERMS:
            if dt.lower() not in existing_lower:
                terms_to_check.append(dt)
                existing_lower.add(dt.lower())

    combined_text = delivered_text.lower()
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
    if case.must_abstain:
        abstention_ok = _is_clean_abstention(answer, envelope) and fabricated_citation_count == 0
        if not abstention_ok:
            failures.append("failed to abstain cleanly on unanswerable query")
    else:
        abstention_ok = not envelope_abstained and bool(answer.strip())
        if not abstention_ok:
            failures.append("unexpected abstention or empty output on answerable query")

    # 5. Layer B: Weighted Rubric & Atomic Claim Entailment
    rubric_weighted_score, rubric_failures = _evaluate_weighted_rubric(case, answer, condensed_text)
    failures.extend(rubric_failures)

    atomic_entailment_rate, citation_distortion_count, entailment_failures = _evaluate_atomic_entailment(
        case,
        answer,
        condensed_text,
        known_uuids,
        idx_map,
        idx_all_uuids=idx_all_uuids,
        trusted_uuids=trusted_uuids,
    )
    failures.extend(entailment_failures)

    plain_summary = str(envelope.get("patient_plain_summary") or "").strip()
    fk_grade = compute_flesch_kincaid_grade(plain_summary if plain_summary else answer)
    readability_alignment_score = compute_readability_alignment_score(
        fk_grade, must_abstain=case.must_abstain
    )

    if not privacy_zero_leakage or not abstention_ok or not token_budget_ok or not answer.strip():
        case_quality_score = 0.0
    elif case.must_abstain:
        case_quality_score = round(
            100.0 * (0.75 * float(abstention_ok) + 0.25 * citation_resolution_rate),
            2,
        )
    else:
        cite_factor = sentence_citation_coverage * citation_resolution_rate
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


_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_MULTI_BRACKET_RE = re.compile(r"\[(\d+(?:\s*(?:,|;|/|-|\band\b)\s*\d+)+)\]", re.IGNORECASE)


def _normalize_bracket_citations(text: str) -> str:
    """Expand multi-index bracket citations like `[48, 56]` or `[3, 4, 5]` into `[48] [56]` / `[3] [4] [5]`."""
    def _repl(match: re.Match[str]) -> str:
        raw_inner = match.group(1)
        nums = re.findall(r"\d+", raw_inner)
        return " ".join(f"[{n}]" for n in nums)

    return _MULTI_BRACKET_RE.sub(_repl, text or "")


def _format_kb_findings_for_prompt(analyze_data: dict[str, Any]) -> str:
    """Format Stage 2 deterministic KB findings concisely for `-kb` profile prompts."""
    analyses = analyze_data.get("analyses") if isinstance(analyze_data.get("analyses"), dict) else {}
    dq = analyses.get("data_quality_and_conflicts") if isinstance(analyses.get("data_quality_and_conflicts"), dict) else {}
    reconcil = analyze_data.get("reconciliation") if isinstance(analyze_data.get("reconciliation"), dict) else {}
    findings = (
        list(dq.get("findings") or [])
        + list(analyze_data.get("kb_findings") or [])
        + list(reconcil.get("anomalies") or [])
    )
    lines: list[str] = []
    seen_finding_keys: set[tuple[str, str]] = set()
    for idx, f in enumerate(findings, start=1):
        if not isinstance(f, dict):
            continue
        fid = str(f.get("id") or f.get("kb_rule_id") or f.get("category") or f"finding_{idx}")
        sev = str(f.get("severity") or "info").upper()
        title = str(f.get("title") or fid)
        dedup_key = (fid.strip().lower(), title.strip().lower())
        if dedup_key in seen_finding_keys:
            continue
        seen_finding_keys.add(dedup_key)
        summary = str(f.get("description") or f.get("summary") or f.get("patient_plain_summary") or "").strip()
        raw_ev = (
            list(f.get("evidence_indices") or [])
            + list(f.get("citation_indices") or [])
            + [
                c.get("index")
                for c in (f.get("citations") or [])
                if isinstance(c, dict) and isinstance(c.get("index"), int)
            ]
        )
        seen_ev: list[int] = []
        for i in raw_ev:
            if isinstance(i, int) and i not in seen_ev:
                seen_ev.append(i)
        ev_idx = [f"[{i}]" for i in seen_ev]
        ev_str = f" (Evidence: {' '.join(ev_idx)})" if ev_idx else ""
        lines.append(f"- [{sev}] {title} (rule={fid}){ev_str}: {summary}")

    if not lines:
        skills_block = (
            (analyses.get("chart_hygiene_and_reconciliation_skills") or {}).get("formatted_findings_block")
            if isinstance(analyses.get("chart_hygiene_and_reconciliation_skills"), dict)
            else ""
        )
        if isinstance(skills_block, str) and skills_block.strip():
            lines.append("4-Layer Reconciliation Skill Summary:")
            lines.append(skills_block.strip())

    patterns = analyses.get("patterns_and_summaries") if isinstance(analyses.get("patterns_and_summaries"), dict) else {}
    hl = patterns.get("highlight_encounter")
    if isinstance(hl, dict) and hl.get("narrative"):
        hl_cites = " ".join(
            f"[{c['index']}]"
            for c in (hl.get("citations") or [])
            if isinstance(c, dict) and isinstance(c.get("index"), int)
        )
        lines.append(f"- [ENCOUNTER SUMMARY] {hl.get('title') or 'Encounter'} {hl_cites}: {hl.get('narrative')}")

    for traj in patterns.get("trajectories") or []:
        if not isinstance(traj, dict):
            continue
        t_cites = " ".join(
            f"[{c['index']}]"
            for c in (traj.get("citations") or [])
            if isinstance(c, dict) and isinstance(c.get("index"), int)
        )
        init_v = (traj.get("initial") or {}).get("value")
        init_d = (traj.get("initial") or {}).get("date")
        lat_v = (traj.get("latest") or {}).get("value")
        lat_d = (traj.get("latest") or {}).get("date")
        min_v = (traj.get("min") or {}).get("value")
        max_v = (traj.get("max") or {}).get("value")
        lines.append(
            f"- [TRAJECTORY] {traj.get('concept')} ({traj.get('unit') or ''}) {t_cites}: "
            f"initial {init_v} ({init_d}) -> latest {lat_v} ({lat_d}), range [{min_v}, {max_v}], direction={traj.get('direction')}"
        )

    if not lines:
        lines.append("- No active medication/immunization/problem-lab conflicts flagged by Stage 2 KB rules.")
    redaction_notice = str(analyze_data.get("redaction_notice") or "").strip()
    if redaction_notice:
        lines.append(f"- Privacy posture note: {redaction_notice}")
    return "\n".join(lines)


def _build_profile_prompt(
    case: WahsEvalCase,
    analyze_data: dict[str, Any],
    *,
    budget_tokens: int,
    include_kb_findings: bool,
) -> str:
    """Build the OpenAI chat completion user prompt for a WAHS simple profile arm."""
    condensation = analyze_data.get("condensation") or {}
    tier_info = condensation.get("tier_info") if isinstance(condensation.get("tier_info"), dict) else {}
    actual_tokens = int(
        condensation.get("actual_tokens")
        or tier_info.get("actual_tokens")
        or analyze_data.get("actual_tokens")
        or 0
    )
    chart_text = str(
        condensation.get("chart_text")
        or condensation.get("condensed_text")
        or analyze_data.get("condensed_text")
        or ""
    ).strip()
    omitted_sections = (
        condensation.get("omitted_sections")
        if isinstance(condensation.get("omitted_sections"), dict)
        else {}
    )
    omitted_total = sum(
        int(v) for v in omitted_sections.values() if isinstance(v, (int, float))
    )
    parts = [
        f"Patient ID: {case.patient_id}\n"
        f"CONDENSED PATIENT CHART (Stage 1 Lossless Structural, Budget <= {budget_tokens} tokens, Actual {actual_tokens} tokens, omitted items: {omitted_total}):\n{chart_text}"
    ]
    if include_kb_findings:
        parts.append(
            "STAGE 2 CLINICAL KB & RECONCILIATION FINDINGS (deterministic 4-Layer Clinical Knowledge Base findings):\n"
            + _format_kb_findings_for_prompt(analyze_data)
        )
    else:
        parts.append(
            "STAGE 2 CLINICAL KB & RECONCILIATION FINDINGS:\n"
            "(Stage 2 KB findings are intentionally withheld in this raw-condensed arm; rely solely on the Condensed Patient Chart above.)"
        )
        if case.sharing_posture == "external_share" and analyze_data.get("redaction_notice"):
            parts.append(f"PRIVACY POSTURE NOTE:\n{analyze_data.get('redaction_notice')}")

    parts.append(
        f"CLINICAL TASK / PATIENT QUESTION (Use Case: {case.use_case}, Sharing Posture: {case.sharing_posture}):\n"
        f"{case.prompt}\n\n"
        "GROUNDING & FORMATTING RULES:\n"
        "1. Cite supporting records from the Condensed Patient Chart inline using [N] bracket numbers on every substantive sentence (for example, [1] or [1] [2]). Never invent citation numbers that do not appear in the chart.\n"
        "2. If the question asks about a test, imaging study, procedure, or diagnosis that is NOT documented in the Condensed Patient Chart, explicitly state that it is not documented in the chart (grounded abstention) and do not guess or invent clinical findings.\n"
        "3. Write in clear, patient-friendly language (6th-to-8th grade reading level) while preserving exact medication names, doses, lab values, dates, and [N] citations."
    )
    return "\n\n".join(parts)


def _build_direct_llm_prompt(
    case: WahsEvalCase,
    analyze_data: dict[str, Any],
    *,
    budget_tokens: int,
) -> str:
    """Build a direct-to-LLM user prompt (bypassing Med Agent Hub system prompt, Stage 2 KB findings, and ClinicalEntityGraph)."""
    condensation = analyze_data.get("condensation") or {}
    chart_text = str(
        condensation.get("chart_text")
        or condensation.get("condensed_text")
        or analyze_data.get("condensed_text")
        or ""
    ).strip()
    return (
        f"Patient Chart ({case.patient_id}, budget <= {budget_tokens} tokens):\n"
        f"{chart_text}\n\n"
        f"Question:\n{case.prompt}\n\n"
        "Answer the question based on the patient chart above. "
        "Cite supporting chart entries inline using their [N] bracket numbers."
    )


MAX_TOKEN_BUDGET = 262144


def _split_profile_budget(
    profile_spec: str,
    fallback_budget: int = 8192,
) -> tuple[str, str, int, str | None]:
    """Parse an optional `@<budget>` suffix on a WAHS profile spec (e.g. `wahs-12b-kb@64k`).

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


class WahsHubClient:
    """HTTP client for Med Agent Hub WAHS endpoints (`/wahs/api/chat`, `/wahs/api/analyze`, and `/v1/chat/completions`)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 180.0,
        session: requests.Session | None = None,
        max_retries: int = 1,
        retry_backoff_s: float = 0.0,
        bundle_dirs: list[Path] | None = None,
        direct_llm_base_url: str | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("MED_AGENT_HUB_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.direct_llm_base_url = (
            direct_llm_base_url
            or os.environ.get("DIRECT_LLM_BASE_URL")
            or self.base_url
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = max(0.0, float(retry_backoff_s))
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._analyze_cache: dict[tuple[str, int, str, str], dict[str, Any]] = {}
        self._profiles_cache: dict[str, dict[str, Any]] | None = None
        self._bundle_cache: dict[str, dict[str, Any] | None] = {}
        self._demo_data_cache: dict[str, Any] | None = None
        self.bundle_dirs: list[Path] = list(bundle_dirs or [])
        env_bdir = os.environ.get("WAHS_BUNDLE_DIR", "").strip()
        if env_bdir:
            self.bundle_dirs.extend([Path(env_bdir), Path(env_bdir) / "eval"])

    def _resolve_demo_data_analyze(
        self,
        patient_id: str,
        budget_tokens: int,
        condense_mode: str = "lossless_structural",
    ) -> dict[str, Any] | None:
        """Synthesize an `/wahs/api/analyze` envelope from a supplied `wahs_demo_data.js` file if configured."""
        if self._demo_data_cache is None:
            js_path_str = os.environ.get("WAHS_DEMO_DATA_JS", "").strip()
            candidates: list[Path] = [Path(js_path_str)] if js_path_str else []
            for bdir in self.bundle_dirs:
                candidates.append(bdir / "wahs_demo_data.js")
            loaded: dict[str, Any] = {}
            for cand in candidates:
                if cand.is_file():
                    try:
                        raw = cand.read_text(encoding="utf-8")
                        prefix = "window.WAHS_DEMO_DATA = "
                        idx = raw.find(prefix)
                        if idx >= 0:
                            loaded = json.loads(raw[idx + len(prefix) :].rstrip().rstrip(";"))
                            break
                    except Exception:
                        continue
            self._demo_data_cache = loaded
        patients = (self._demo_data_cache or {}).get("patients") or {}
        p = patients.get(patient_id) or patients.get(f"{patient_id}_set_b")
        if not isinstance(p, dict):
            return None
        matrix = (p.get("condensation_matrix") or {}).get(condense_mode) or (
            p.get("condensation_matrix") or {}
        ).get("lossless_structural") or {}
        cell = matrix.get(str(int(budget_tokens)))
        if not isinstance(cell, dict):
            return None
        if cell.get("alias_of_budget"):
            alias = str(cell["alias_of_budget"])
            cell = dict(matrix.get(alias) or cell)
            cell["budget"] = int(budget_tokens)
        pos = (p.get("postures") or {}).get("patient_self") or {}
        raw_dq_findings = list(
            ((pos.get("data_quality_and_conflicts") or {}).get("findings") or [])
            if isinstance(pos.get("data_quality_and_conflicts"), dict)
            else []
        )
        sk_obj = pos.get("skill_findings") if isinstance(pos.get("skill_findings"), dict) else {}
        raw_sk_findings = list(sk_obj.get("findings") or [])
        formatted_block = str(sk_obj.get("formatted_findings_block") or "") if int(budget_tokens) >= 8192 else ""

        line_re = re.compile(r"^\s*(?:-\s*)?\[(\d+)\]\s*(?:\(([^)]+)\)\s*)?(.*)$")
        t8_mappings = list(
            ((pos.get("tier_8k") or {}).get("mappings") if isinstance(pos.get("tier_8k"), dict) else [])
            or []
        )
        t8_by_idx: dict[int, dict[str, Any]] = {
            int(m["index"]): dict(m)
            for m in t8_mappings
            if isinstance(m, dict) and isinstance(m.get("index"), int)
        }
        t8_by_text: dict[tuple[str, str], dict[str, Any]] = {}
        t8_cell = matrix.get("8192")
        if isinstance(t8_cell, dict):
            for t8_line in str(t8_cell.get("chart_text") or "").splitlines():
                m8 = line_re.match(t8_line)
                if not m8:
                    continue
                i8 = int(m8.group(1))
                dt8 = (m8.group(2) or "").strip()
                bd8 = (m8.group(3) or "").strip()
                m_entry = t8_by_idx.get(i8)
                if m_entry:
                    t8_by_text.setdefault((dt8, bd8), m_entry)
                    t8_by_text.setdefault(("", bd8), m_entry)
        for m_entry in t8_mappings:
            if isinstance(m_entry, dict) and m_entry.get("display"):
                dt8 = str(m_entry.get("date") or "").strip()
                bd8 = str(m_entry.get("display") or "").strip()
                t8_by_text.setdefault((dt8, bd8), m_entry)
                t8_by_text.setdefault(("", bd8), m_entry)

        cell_mappings = list(cell.get("mappings") or [])
        mapping_by_idx: dict[int, dict[str, Any]] = {}
        if cell_mappings:
            for m in cell_mappings:
                if isinstance(m, dict) and isinstance(m.get("index"), int):
                    mapping_by_idx[int(m["index"])] = dict(m)
        elif int(budget_tokens) == 8192:
            for k_idx, m in t8_by_idx.items():
                mapping_by_idx[k_idx] = dict(m)

        chart_text = str(cell.get("chart_text") or "")
        for line in chart_text.splitlines():
            m_line = line_re.match(line)
            if not m_line:
                continue
            idx_i = int(m_line.group(1))
            date_s = (m_line.group(2) or "").strip()
            body_s = (m_line.group(3) or "").strip()
            rtype = body_s.split(":", 1)[0].split("—", 1)[0].strip() if (":" in body_s or "—" in body_s) else "Resource"
            entry = mapping_by_idx.get(idx_i)
            if entry is None:
                matched_t8 = t8_by_text.get((date_s, body_s)) or t8_by_text.get(("", body_s))
                if matched_t8 is not None:
                    mapping_by_idx[idx_i] = {
                        "index": idx_i,
                        "resourceType": matched_t8.get("resourceType") or rtype,
                        "resourceUuid": matched_t8.get("resourceUuid") or f"{patient_id}-item-{idx_i}",
                        "date": date_s or matched_t8.get("date") or "",
                        "display": body_s or matched_t8.get("display") or "",
                        "memberUuids": list(matched_t8.get("memberUuids") or []),
                    }
                else:
                    mapping_by_idx[idx_i] = {
                        "index": idx_i,
                        "resourceType": rtype,
                        "resourceUuid": f"{patient_id}-item-{idx_i}",
                        "date": date_s,
                        "display": body_s,
                        "memberUuids": [],
                    }
            else:
                if date_s and not entry.get("date"):
                    entry["date"] = date_s
                if body_s and not entry.get("display"):
                    entry["display"] = body_s
                if rtype and not entry.get("resourceType"):
                    entry["resourceType"] = rtype

        uuid_to_active_indices: dict[str, list[int]] = {}
        for k_idx in sorted(mapping_by_idx):
            m_obj = mapping_by_idx[k_idx]
            u_primary = str(m_obj.get("resourceUuid") or "").replace("urn:uuid:", "")
            if u_primary:
                uuid_to_active_indices.setdefault(u_primary, []).append(k_idx)
            for mu in m_obj.get("memberUuids") or []:
                u_mem = str(mu or "").replace("urn:uuid:", "")
                if u_mem and k_idx not in uuid_to_active_indices.setdefault(u_mem, []):
                    uuid_to_active_indices[u_mem].append(k_idx)

        def _remap_findings_for_budget(raw_list: list[Any]) -> list[dict[str, Any]]:
            out_list: list[dict[str, Any]] = []
            for f in raw_list:
                if not isinstance(f, dict):
                    continue
                r_uuids = [
                    str(u).replace("urn:uuid:", "")
                    for u in (f.get("resource_uuids") or [])
                    if isinstance(u, str) and u
                ]
                if int(budget_tokens) < 8192:
                    if not r_uuids or not all(u in uuid_to_active_indices for u in r_uuids):
                        continue
                active_ev: list[int] = []
                for u in r_uuids:
                    for act_i in uuid_to_active_indices.get(u, []):
                        if act_i not in active_ev:
                            active_ev.append(act_i)
                f_copy = dict(f)
                if active_ev:
                    f_copy["evidence_indices"] = list(active_ev)
                    f_copy["citation_indices"] = list(active_ev)
                    f_copy["bracket_citations"] = list(active_ev)
                    f_copy["citations"] = [
                        {
                            "index": act_i,
                            "resourceUuid": (mapping_by_idx.get(act_i) or {}).get("resourceUuid"),
                        }
                        for act_i in active_ev
                    ]
                out_list.append(f_copy)
            return out_list

        dq_findings = _remap_findings_for_budget(raw_dq_findings)
        sk_findings = _remap_findings_for_budget(raw_sk_findings)
        all_findings = dq_findings + sk_findings

        final_mappings = [mapping_by_idx[k] for k in sorted(mapping_by_idx)]
        return {
            "condensation": {
                "chart_text": chart_text,
                "condensed_text": chart_text,
                "actual_tokens": int(cell.get("actual_tokens") or 0),
                "condense_mode": condense_mode,
                "omitted_sections": dict(cell.get("omitted_sections") or {}),
                "mappings": final_mappings,
                "tier_info": {
                    "tier_used": cell.get("tier") or 0,
                    "actual_tokens": int(cell.get("actual_tokens") or 0),
                    "budget_tokens": int(budget_tokens),
                },
            },
            "analyses": {
                "data_quality_and_conflicts": {"findings": dq_findings},
                "chart_hygiene_and_reconciliation_skills": {
                    "findings": sk_findings,
                    "formatted_findings_block": formatted_block,
                },
            },
            "kb_findings": all_findings,
        }

    def _resolve_local_bundle(self, patient_id: str) -> dict[str, Any] | None:
        if patient_id in self._bundle_cache:
            return self._bundle_cache[patient_id]
        stem = patient_id[:-5] if patient_id.endswith(".json") else patient_id
        for bdir in self.bundle_dirs:
            for candidate in (bdir / f"{stem}.json", bdir / "eval" / f"{stem}.json"):
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

    def get_wahs_profiles(self) -> dict[str, dict[str, Any]]:
        """Fetch and cache `/v1/models?workflow=wahs` profile metadata from Med Agent Hub."""
        if self._profiles_cache is not None:
            return self._profiles_cache
        get_fn = getattr(self._session, "get", None)
        if not callable(get_fn):
            self._profiles_cache = {}
            return self._profiles_cache
        try:
            resp = get_fn(f"{self.base_url}/v1/models?workflow=wahs", timeout=self.timeout)
            if getattr(resp, "status_code", None) == 200:
                payload = resp.json()
                data = payload.get("data") if isinstance(payload, dict) else []
                self._profiles_cache = {
                    str(m["id"]): dict(m)
                    for m in (data or [])
                    if isinstance(m, dict) and m.get("id")
                }
                return self._profiles_cache
        except Exception:
            pass
        self._profiles_cache = {}
        return self._profiles_cache

    def analyze_case(
        self,
        case: WahsEvalCase,
        *,
        budget_tokens: int,
        condense_mode: str = "lossless_structural",
    ) -> dict[str, Any]:
        """Fetch and cache deterministic Stage 1 + Stage 2 `/wahs/api/analyze` output for `(patient_id, budget, posture, mode)`."""
        cache_key = (case.patient_id, int(budget_tokens), case.sharing_posture, condense_mode)
        if cache_key in self._analyze_cache:
            return self._analyze_cache[cache_key]
        if os.environ.get("WAHS_DEMO_DATA_JS", "").strip() and case.sharing_posture != "external_share":
            demo_data = self._resolve_demo_data_analyze(
                case.patient_id, int(budget_tokens), condense_mode
            )
            if demo_data is not None:
                self._analyze_cache[cache_key] = demo_data
                return demo_data
        req_body: dict[str, Any] = {
            "patient_id": case.patient_id,
            "target_tokens": int(budget_tokens),
            "sharing_posture": case.sharing_posture,
            "condense_mode": condense_mode,
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.post(
                    f"{self.base_url}/wahs/api/analyze",
                    json=req_body,
                    timeout=self.timeout,
                )
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries:
                    if self.retry_backoff_s > 0:
                        time.sleep(self.retry_backoff_s)
                    continue
                raise RuntimeError(
                    f"WAHS analyze transport failure for {case.case_id}: {exc}"
                ) from exc
            if resp.status_code == 404 and "fhir_bundle" not in req_body:
                local_bundle = self._resolve_local_bundle(case.patient_id)
                if local_bundle is not None:
                    req_body["fhir_bundle"] = local_bundle
                    resp = self._session.post(
                        f"{self.base_url}/wahs/api/analyze",
                        json=req_body,
                        timeout=self.timeout,
                    )
                else:
                    demo_data = self._resolve_demo_data_analyze(
                        case.patient_id, int(budget_tokens), condense_mode
                    )
                    if demo_data is not None:
                        self._analyze_cache[cache_key] = demo_data
                        return demo_data
            if resp.status_code == 200:
                data = dict(resp.json())
                self._analyze_cache[cache_key] = data
                return data
            err_text = getattr(resp, "text", "")[:300]
            last_err = RuntimeError(
                f"WAHS analyze failed [{resp.status_code}] for {case.case_id}: {err_text}"
            )
            if resp.status_code in {502, 503, 504} and attempt < self.max_retries:
                if self.retry_backoff_s > 0:
                    time.sleep(self.retry_backoff_s)
                continue
            raise last_err
        assert last_err is not None
        raise last_err

    def _evaluate_profile_case(
        self,
        case: WahsEvalCase,
        *,
        profile_id: str,
        budget_tokens: int,
        condense_mode: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a live LLM simple profile (`-kb` or `-raw`, optionally `@<budget>`) via `/wahs/api/analyze` + `/v1/chat/completions`."""
        _backend_id, api_profile_id, eff_budget, _b_tag = _split_profile_budget(
            profile_id, budget_tokens
        )
        eff_mode = condense_mode or "lossless_structural"
        analyze_data = self.analyze_case(
            case, budget_tokens=eff_budget, condense_mode=eff_mode
        )
        profiles = self.get_wahs_profiles()
        profile_meta = profiles.get(api_profile_id) or profiles.get(profile_id) or {}
        policies = profile_meta.get("policies") if isinstance(profile_meta.get("policies"), dict) else {}
        is_direct_llm = api_profile_id.startswith("direct-") or api_profile_id.startswith("direct:")
        if is_direct_llm:
            include_kb = False
        elif "include_kb_findings" in policies:
            include_kb = bool(policies["include_kb_findings"])
        elif "kb_guided" in profile_meta:
            include_kb = bool(profile_meta["kb_guided"])
        else:
            include_kb = not (
                api_profile_id.endswith("-raw") or api_profile_id.startswith("wahs-raw:")
            )

        if is_direct_llm:
            _, underlying_model, _ = _infer_model_family_and_id(profile_id, profile_meta)
            target_model = os.environ.get("DIRECT_LLM_MODEL", "").strip() or underlying_model
            user_prompt = _build_direct_llm_prompt(
                case,
                analyze_data,
                budget_tokens=eff_budget,
            )
            target_chat_url = f"{self.direct_llm_base_url}/v1/chat/completions"
            chat_req = {
                "model": target_model,
                "messages": [{"role": "user", "content": user_prompt}],
                "stream": False,
                "temperature": 0.0,
            }
        else:
            user_prompt = _build_profile_prompt(
                case,
                analyze_data,
                budget_tokens=eff_budget,
                include_kb_findings=include_kb,
            )
            target_chat_url = f"{self.base_url}/v1/chat/completions"
            chat_req = {
                "model": api_profile_id,
                "messages": [{"role": "user", "content": user_prompt}],
                "stream": False,
            }
        env_max_tok = os.environ.get("WAHS_EVAL_MAX_TOKENS", "").strip()
        if env_max_tok.isdigit() and int(env_max_tok) > 0:
            chat_req["max_tokens"] = int(env_max_tok)
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self._session.post(
                    target_chat_url,
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
                    f"WAHS profile {profile_id} transport failure for {case.case_id}: {exc}"
                ) from exc

            latency_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code == 200:
                chat_json = dict(resp.json())
                choices = chat_json.get("choices") or []
                msg = (choices[0].get("message") if choices and isinstance(choices[0], dict) else {}) or {}
                raw_content = str(msg.get("content") or "")
                cleaned_answer = _normalize_bracket_citations(
                    _THINK_RE.sub("", raw_content).strip()
                )

                condensation = analyze_data.get("condensation") or {}
                raw_mappings = condensation.get("mappings") or []
                mappings: list[dict[str, Any]] = []
                mapping_by_idx: dict[int, dict[str, Any]] = {}
                if isinstance(raw_mappings, dict):
                    for k_str, v_obj in raw_mappings.items():
                        if not isinstance(v_obj, dict):
                            continue
                        num_m = re.search(r"\d+", str(k_str))
                        if not num_m:
                            continue
                        idx_i = int(num_m.group(0))
                        norm_m = {
                            "index": idx_i,
                            "resourceType": v_obj.get("resourceType") or v_obj.get("resource_type"),
                            "resourceUuid": v_obj.get("resourceUuid") or v_obj.get("primary_uuid") or v_obj.get("resource_uuid"),
                            "date": v_obj.get("date") or "",
                            "display": v_obj.get("display") or v_obj.get("summary") or v_obj.get("text") or "",
                            "memberUuids": list(v_obj.get("memberUuids") or v_obj.get("member_uuids") or []),
                        }
                        mappings.append(norm_m)
                        mapping_by_idx[idx_i] = norm_m
                elif isinstance(raw_mappings, list):
                    for m in raw_mappings:
                        if isinstance(m, dict) and isinstance(m.get("index"), int):
                            idx_i = int(m["index"])
                            norm_m = {
                                "index": idx_i,
                                "resourceType": m.get("resourceType") or m.get("resource_type"),
                                "resourceUuid": m.get("resourceUuid") or m.get("resource_uuid") or m.get("primary_uuid"),
                                "date": m.get("date") or "",
                                "display": m.get("display") or m.get("text") or m.get("summary") or "",
                                "memberUuids": list(m.get("memberUuids") or m.get("member_uuids") or []),
                            }
                            mappings.append(norm_m)
                            mapping_by_idx[idx_i] = norm_m

                hub_enrichment = chat_json.get("hub_enrichment")
                if not isinstance(hub_enrichment, dict):
                    resp_headers = getattr(resp, "headers", None) or {}
                    hdr_val = resp_headers.get("X-WAHS-Hub-Enrichment") or resp_headers.get("x-wahs-hub-enrichment")
                    if hdr_val:
                        try:
                            hub_enrichment = json.loads(hdr_val)
                        except Exception:
                            hub_enrichment = None

                if include_kb:
                    if isinstance(hub_enrichment, dict):
                        for rm in hub_enrichment.get("recovered_mappings") or []:
                            if isinstance(rm, dict) and isinstance(rm.get("index"), int):
                                idx_rm = int(rm["index"])
                                norm_rm = {
                                    "index": idx_rm,
                                    "resourceType": rm.get("resourceType") or "Resource",
                                    "resourceUuid": rm.get("resourceUuid"),
                                    "date": rm.get("date") or "",
                                    "display": rm.get("display") or "",
                                    "memberUuids": list(rm.get("memberUuids") or []),
                                }
                                mapping_by_idx[idx_rm] = norm_rm
                                mappings.append(norm_rm)

                    analyses_obj = analyze_data.get("analyses") if isinstance(analyze_data.get("analyses"), dict) else {}
                    skill_findings = (
                        (analyses_obj.get("chart_hygiene_and_reconciliation_skills") or {}).get("findings")
                        if isinstance(analyses_obj.get("chart_hygiene_and_reconciliation_skills"), dict)
                        else []
                    ) or []
                    dq_findings = (
                        (analyses_obj.get("data_quality_and_conflicts") or {}).get("findings")
                        if isinstance(analyses_obj.get("data_quality_and_conflicts"), dict)
                        else []
                    ) or []
                    for f_obj in list(skill_findings) + list(dq_findings):
                        if not isinstance(f_obj, dict):
                            continue
                        f_uuids = [
                            str(u)
                            for u in (f_obj.get("resource_uuids") or [])
                            if isinstance(u, str) and u
                        ]
                        b_indices = list(f_obj.get("bracket_citations") or []) + [
                            c.get("index")
                            for c in (f_obj.get("citations") or [])
                            if isinstance(c, dict) and isinstance(c.get("index"), int)
                        ]
                        for b_idx in b_indices:
                            if isinstance(b_idx, int) and b_idx in mapping_by_idx:
                                cur_u = str(mapping_by_idx[b_idx].get("resourceUuid") or "")
                                if eff_budget <= 8192 or cur_u in f_uuids:
                                    m_list = mapping_by_idx[b_idx].setdefault("memberUuids", [])
                                    for fu in f_uuids:
                                        if fu not in m_list:
                                            m_list.append(fu)

                cited_indices: list[int] = []
                for num_str in _CITATION_RE.findall(cleaned_answer):
                    if num_str.isdigit():
                        idx_val = int(num_str)
                        if idx_val not in cited_indices:
                            cited_indices.append(idx_val)

                references: list[dict[str, Any]] = []
                for c_idx in cited_indices:
                    m_obj = mapping_by_idx.get(c_idx)
                    if m_obj is not None:
                        ref_entry: dict[str, Any] = {
                            "index": c_idx,
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

                tier_info = condensation.get("tier_info") if isinstance(condensation.get("tier_info"), dict) else {}
                actual_tokens = int(
                    condensation.get("actual_tokens")
                    or tier_info.get("actual_tokens")
                    or analyze_data.get("actual_tokens")
                    or 0
                )
                redaction_notice = (
                    analyze_data.get("redaction_notice")
                    or condensation.get("redaction_notice")
                )
                if not redaction_notice and case.sharing_posture == "external_share":
                    redacted_list = condensation.get("redacted_for_privacy") or []
                    if redacted_list:
                        redaction_notice = (
                            f"Redacted categories: {len(redacted_list)} privacy-sensitive SDOH/behavioral health "
                            "record(s) excluded under 42 CFR Part 2 and WA MHMDA."
                        )
                hub_profile = chat_json.get("hub_profile") or {
                    "id": api_profile_id,
                    "include_kb_findings": include_kb,
                    "model_family": policies.get("model_family") or profile_meta.get("model_family"),
                    "parameter_size": policies.get("parameter_size"),
                    "quantization": policies.get("quantization"),
                    "role_models": profile_meta.get("role_models") or {},
                }
                hub_enrichment = chat_json.get("hub_enrichment")
                if not isinstance(hub_enrichment, dict):
                    resp_headers = getattr(resp, "headers", None) or {}
                    hdr_val = resp_headers.get("X-WAHS-Hub-Enrichment") or resp_headers.get("x-wahs-hub-enrichment")
                    if hdr_val:
                        try:
                            hub_enrichment = json.loads(hdr_val)
                        except Exception:
                            hub_enrichment = None
                envelope: dict[str, Any] = {
                    "answer": cleaned_answer,
                    "references": references,
                    "citations": references,
                    "mappings": mappings,
                    "actual_tokens": actual_tokens,
                    "budget_tokens": eff_budget,
                    "tier_info": {
                        "actual_tokens": actual_tokens,
                        "condense_mode": condensation.get("condense_mode", eff_mode),
                    },
                    "condensed_text": str(
                        condensation.get("chart_text")
                        or condensation.get("condensed_text")
                        or ""
                    ),
                    "redaction_notice": redaction_notice,
                    "latency_ms": int(chat_json.get("latency_ms") or latency_ms),
                    "usage": chat_json.get("usage") or {},
                    "hub_profile": hub_profile,
                    "hub_enrichment": hub_enrichment or {},
                    "profile_id": profile_id,
                    "api_profile_id": api_profile_id,
                    "include_kb_findings": include_kb,
                    "kb_findings_Injected": (
                        list(analyze_data.get("kb_findings") or []) if include_kb else []
                    ),
                }
                return envelope

            err_text = getattr(resp, "text", "")[:300]
            last_err = RuntimeError(
                f"WAHS profile {profile_id} failed [{resp.status_code}] for {case.case_id}: {err_text}"
            )
            if resp.status_code in {502, 503, 504} and attempt < self.max_retries:
                if self.retry_backoff_s > 0:
                    time.sleep(self.retry_backoff_s)
                continue
            raise last_err

        assert last_err is not None
        raise last_err

    def evaluate_case(
        self,
        case: WahsEvalCase,
        *,
        budget_tokens: int,
        evaluation_modality: str | None = None,
        context_arm: str | None = None,
        condense_mode: str | None = None,
        use_lookup_tools: bool | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        if profile_id is not None:
            return self._evaluate_profile_case(
                case,
                profile_id=profile_id,
                budget_tokens=budget_tokens,
                condense_mode=condense_mode,
            )
        req_body: dict[str, Any] = {
            "patient_id": case.patient_id,
            "question": case.prompt,
            "sharing_posture": case.sharing_posture,
            "target_tokens": budget_tokens,
        }
        if context_arm is not None:
            req_body["context_arm"] = context_arm
        if evaluation_modality is not None:
            req_body["evaluation_modality"] = evaluation_modality
            req_body["condense_mode"] = condense_mode or (
                "lossless_structural"
                if evaluation_modality in {"condensation_retrieval_ablation", "live_model_and_team_eval"}
                else "tiered"
            )
            req_body["use_lookup_tools"] = (
                use_lookup_tools
                if use_lookup_tools is not None
                else (evaluation_modality == "live_model_and_team_eval")
            )
        else:
            if condense_mode is not None:
                req_body["condense_mode"] = condense_mode
            if use_lookup_tools is not None:
                req_body["use_lookup_tools"] = use_lookup_tools

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                chat_resp = self._session.post(
                    f"{self.base_url}/wahs/api/chat",
                    json=req_body,
                    timeout=self.timeout,
                )
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries:
                    if self.retry_backoff_s > 0:
                        time.sleep(self.retry_backoff_s)
                    continue
                raise RuntimeError(
                    f"WAHS chat transport failure for {case.case_id}: {exc}"
                ) from exc

            latency_ms = int((time.monotonic() - started) * 1000)
            if chat_resp.status_code == 200:
                payload = dict(chat_resp.json())
                payload.setdefault("latency_ms", latency_ms)
                return payload

            err_text = getattr(chat_resp, "text", "")[:300]
            last_err = RuntimeError(
                f"WAHS chat failed [{chat_resp.status_code}] for {case.case_id}: {err_text}"
            )
            if chat_resp.status_code in {502, 503, 504} and attempt < self.max_retries:
                if self.retry_backoff_s > 0:
                    time.sleep(self.retry_backoff_s)
                continue
            raise last_err

        assert last_err is not None
        raise last_err


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


def _missing_cell_score(case: WahsEvalCase, budget_tokens: int, reason: str | None = None) -> WahsCaseScore:
    msg = reason or f"missing or incomplete evaluation result for cell ({case.case_id}, {budget_tokens})"
    return WahsCaseScore(
        case_id=case.case_id,
        patient_id=case.patient_id,
        use_case=case.use_case,
        sharing_posture=case.sharing_posture,
        budget_tokens=budget_tokens,
        actual_tokens=0,
        token_budget_ok=False,
        required_uuid_recall=0.0,
        citation_resolution_rate=0.0,
        fabricated_citation_count=0,
        privacy_zero_leakage=True,
        leaked_items=[],
        abstention_ok=False,
        rubric_weighted_score=0.0,
        atomic_entailment_rate=0.0,
        citation_distortion_count=0,
        flesch_kincaid_grade=0.0,
        question_horizon=case.question_horizon,
        patient_category=case.patient_category,
        passed=False,
        failures=[msg],
        sentence_citation_coverage=0.0,
        readability_alignment_score=0.0,
        case_quality_score=0.0,
    )


def _infer_model_family_and_id(
    profile_id: str,
    profile_meta: dict[str, Any] | None = None,
) -> tuple[str, str, bool]:
    """Return `(model_family, underlying_model_id, include_kb_findings)` for a WAHS simple profile."""
    _, api_profile_id, _, _ = _split_profile_budget(profile_id)
    meta = profile_meta or {}
    policies = meta.get("policies") if isinstance(meta.get("policies"), dict) else {}
    role_models = meta.get("role_models") if isinstance(meta.get("role_models"), dict) else {}
    underlying = str(role_models.get("synthesizer") or meta.get("answer_model") or "")
    fam = str(policies.get("model_family") or "")
    if "include_kb_findings" in policies:
        include_kb = bool(policies["include_kb_findings"])
    else:
        include_kb = not (
            api_profile_id.endswith("-raw")
            or api_profile_id.startswith("wahs-raw:")
            or api_profile_id.startswith("direct-")
            or api_profile_id.startswith("direct:")
        )

    pid_low = api_profile_id.lower()
    if not underlying:
        if ":" in api_profile_id:
            underlying = api_profile_id.split(":", 1)[1]
        elif "medgemma-27b" in pid_low:
            underlying = "medgemma-27b"
        elif "medgemma-4b" in pid_low:
            underlying = "medgemma-1.5-4b-q8"
        elif "12b-q4" in pid_low:
            underlying = "gemma-4-12b-q4"
        elif "12b" in pid_low and "mistral" not in pid_low:
            underlying = "gemma-4-12b"
        elif "e2b" in pid_low:
            underlying = "gemma-e2b"
        elif "e4b-q8" in pid_low:
            underlying = "gemma-e4b-q8"
        elif "e4b" in pid_low:
            underlying = "gemma-e4b"
        elif "26b" in pid_low:
            underlying = "gemma-26b"
        elif "31b" in pid_low:
            underlying = "gemma-31b"
        elif "qwen3-4b" in pid_low:
            underlying = "qwen3-4b"
        elif "qwen35-9b" in pid_low:
            underlying = "qwen3.5-9b"
        elif "qwen25-14b" in pid_low:
            underlying = "qwen2.5-14b"
        elif "qwen3-14b" in pid_low:
            underlying = "qwen3-14b"
        elif "qwen36-35b" in pid_low:
            underlying = "qwen3.6-35b"
        elif "llama31-8b" in pid_low:
            underlying = "llama-3.1-8b"
        elif "mistral-nemo-12b" in pid_low:
            underlying = "mistral-nemo-12b"
        elif "granite33-8b" in pid_low:
            underlying = "granite-3.3-8b"
        elif "lfm2-8b" in pid_low:
            underlying = "lfm2-8b-a1b"
        else:
            underlying = api_profile_id

    if not fam:
        u_low = underlying.lower()
        if "medgemma" in u_low or "medgemma" in pid_low:
            fam = "medgemma"
        elif "gemma" in u_low or "gemma" in pid_low:
            fam = "gemma-4"
        elif "qwen" in u_low or "qwen" in pid_low:
            fam = "qwen"
        elif "llama" in u_low or "llama" in pid_low:
            fam = "llama"
        elif "mistral" in u_low or "mistral" in pid_low:
            fam = "mistral"
        elif "granite" in u_low or "granite" in pid_low:
            fam = "granite"
        elif "lfm2" in u_low or "lfm2" in pid_low:
            fam = "lfm2"
        elif "gemini" in u_low or "gemini" in pid_low:
            fam = "gemini"
        elif "claude" in u_low or "claude" in pid_low:
            fam = "claude"
        else:
            fam = "other"

    return fam, underlying, include_kb


def _summarize_scores(
    scores: list[WahsCaseScore],
    *,
    evaluation_modality: str = "deterministic_pipeline",
    missing_cells: list[dict[str, Any]] | None = None,
    cell_meta_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    by_use_case: dict[str, dict[str, Any]] = {}
    by_horizon: dict[str, dict[str, Any]] = {}
    by_profile: dict[str, dict[str, Any]] = {}
    by_family: dict[str, dict[str, Any]] = {}

    for idx, s in enumerate(scores):
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

        c_meta = (
            cell_meta_list[idx]
            if cell_meta_list and idx < len(cell_meta_list)
            else {}
        ) or {}
        prof_id = c_meta.get("profile_id")
        if prof_id:
            m_fam = str(c_meta.get("model_family") or "other")
            inc_kb = bool(c_meta.get("include_kb_findings", not str(prof_id).endswith("-raw")))
            lat_ms = float(c_meta.get("latency_ms") or 0.0)
            for target_map, group_key, extra_info in (
                (
                    by_profile,
                    str(prof_id),
                    {
                        "model_family": m_fam,
                        "include_kb_findings": inc_kb,
                        "underlying_model": c_meta.get("underlying_model") or str(prof_id),
                    },
                ),
                (by_family, m_fam, {}),
            ):
                p_bucket = target_map.setdefault(
                    group_key,
                    {
                        **extra_info,
                        "total": 0,
                        "passed": 0,
                        "uuid_recall_sum": 0.0,
                        "citation_rate_sum": 0.0,
                        "sentence_cite_sum": 0.0,
                        "rubric_score_sum": 0.0,
                        "entailment_sum": 0.0,
                        "fk_grade_sum": 0.0,
                        "quality_score_sum": 0.0,
                        "privacy_leaks": 0,
                        "abstention_ok_sum": 0,
                        "latency_ms_sum": 0.0,
                    },
                )
                p_bucket["total"] += 1
                p_bucket["passed"] += int(s.passed)
                p_bucket["uuid_recall_sum"] += s.required_uuid_recall
                p_bucket["citation_rate_sum"] += s.citation_resolution_rate
                p_bucket["sentence_cite_sum"] += s.sentence_citation_coverage
                p_bucket["rubric_score_sum"] += s.rubric_weighted_score
                p_bucket["entailment_sum"] += s.atomic_entailment_rate
                p_bucket["fk_grade_sum"] += s.flesch_kincaid_grade
                p_bucket["quality_score_sum"] += s.case_quality_score
                p_bucket["privacy_leaks"] += int(not s.privacy_zero_leakage)
                p_bucket["abstention_ok_sum"] += int(s.abstention_ok)
                p_bucket["latency_ms_sum"] += lat_ms

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

    summary: dict[str, Any] = {
        "evaluation_modality": evaluation_modality,
        "incomplete": bool(missing_cells),
        "missing_cells": list(missing_cells or []),
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
    if by_profile:
        prof_summary = {}
        for pid, pb in sorted(by_profile.items()):
            n = pb["total"] or 1
            prof_summary[pid] = {
                "model_family": pb.get("model_family"),
                "underlying_model": pb.get("underlying_model"),
                "include_kb_findings": pb.get("include_kb_findings"),
                "total": pb["total"],
                "passed": pb["passed"],
                "pass_rate": round(pb["passed"] / n, 4),
                "mean_uuid_recall": round(pb["uuid_recall_sum"] / n, 4),
                "mean_citation_resolution_rate": round(pb["citation_rate_sum"] / n, 4),
                "mean_sentence_citation_coverage": round(pb["sentence_cite_sum"] / n, 4),
                "mean_rubric_weighted_score": round(pb["rubric_score_sum"] / n, 4),
                "mean_atomic_entailment_rate": round(pb["entailment_sum"] / n, 4),
                "mean_flesch_kincaid_grade": round(pb["fk_grade_sum"] / n, 2),
                "mean_case_quality_score": round(pb["quality_score_sum"] / n, 2),
                "privacy_leaks": pb["privacy_leaks"],
                "abstention_accuracy": round(pb["abstention_ok_sum"] / n, 4),
                "mean_latency_ms": round(pb["latency_ms_sum"] / n, 1),
            }
        summary["by_profile"] = prof_summary
    if by_family:
        fam_summary = {}
        for fid, fb in sorted(by_family.items()):
            n = fb["total"] or 1
            fam_summary[fid] = {
                "total": fb["total"],
                "passed": fb["passed"],
                "pass_rate": round(fb["passed"] / n, 4),
                "mean_uuid_recall": round(fb["uuid_recall_sum"] / n, 4),
                "mean_citation_resolution_rate": round(fb["citation_rate_sum"] / n, 4),
                "mean_sentence_citation_coverage": round(fb["sentence_cite_sum"] / n, 4),
                "mean_rubric_weighted_score": round(fb["rubric_score_sum"] / n, 4),
                "mean_atomic_entailment_rate": round(fb["entailment_sum"] / n, 4),
                "mean_flesch_kincaid_grade": round(fb["fk_grade_sum"] / n, 2),
                "mean_case_quality_score": round(fb["quality_score_sum"] / n, 2),
                "privacy_leaks": fb["privacy_leaks"],
                "abstention_accuracy": round(fb["abstention_ok_sum"] / n, 4),
                "mean_latency_ms": round(fb["latency_ms_sum"] / n, 1),
            }
        summary["by_model_family"] = fam_summary
    return summary


def _invoke_client_evaluate_case(
    client: Any,
    case: WahsEvalCase,
    *,
    budget_tokens: int,
    evaluation_modality: str,
    context_arm: str | None = None,
    condense_mode: str | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    fn = client.evaluate_case
    try:
        sig = inspect.signature(fn)
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        accepts_modality = "evaluation_modality" in sig.parameters or has_var_kw
        accepts_context_arm = "context_arm" in sig.parameters or has_var_kw
        accepts_condense_mode = "condense_mode" in sig.parameters or has_var_kw
        accepts_profile_id = "profile_id" in sig.parameters or has_var_kw
    except (TypeError, ValueError):
        accepts_modality = False
        accepts_context_arm = False
        accepts_condense_mode = False
        accepts_profile_id = False
    kwargs: dict[str, Any] = {"budget_tokens": budget_tokens}
    if accepts_modality:
        kwargs["evaluation_modality"] = evaluation_modality
    if context_arm is not None and accepts_context_arm:
        kwargs["context_arm"] = context_arm
    if condense_mode is not None and accepts_condense_mode:
        kwargs["condense_mode"] = condense_mode
    if profile_id is not None and accepts_profile_id:
        kwargs["profile_id"] = profile_id
    return fn(case, **kwargs)


def _cell_dict(
    case_id: str,
    budget_tokens: int,
    context_arm: str | None = None,
    condense_mode: str | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    cell: dict[str, Any] = {"case_id": case_id, "budget_tokens": int(budget_tokens)}
    if context_arm is not None:
        cell["context_arm"] = context_arm
    if condense_mode is not None:
        cell["condense_mode"] = condense_mode
    if profile_id is not None:
        cell["profile_id"] = profile_id
    return cell


def _write_judge_prep_artifacts(
    run_dir: Path,
    cases: list[WahsEvalCase],
    profiles: list[str],
    client: Any,
    observed_envelopes: dict[str, dict[str, Any]],
) -> None:
    """Write `inputs/scenarios/`, `inputs/charts/`, and `run_meta.json` so `scripts/judge-prep.py`
    and `review/bin/review.py --rejudge <run_dir> --blind` work directly on WAHS profile runs.
    """
    scenarios_dir = run_dir / "inputs" / "scenarios"
    charts_dir = run_dir / "inputs" / "charts"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    profiles_catalog = (
        client.get_wahs_profiles()
        if hasattr(client, "get_wahs_profiles") and callable(client.get_wahs_profiles)
        else {}
    )
    backends_meta: dict[str, dict[str, Any]] = {}
    arm_cards_meta: dict[str, dict[str, Any]] = {}
    for pid in profiles:
        _, api_pid, eff_b, b_tag = _split_profile_budget(pid)
        p_meta = profiles_catalog.get(api_pid) or profiles_catalog.get(pid) or {}
        fam, underlying, inc_kb = _infer_model_family_and_id(pid, p_meta)
        is_direct = api_pid.startswith("direct-") or api_pid.startswith("direct:")
        if is_direct:
            base_label = (
                "Gemma-4-12B (Q8) Direct LLM (No Med Agent Hub)"
                if underlying == "gemma-4-12b"
                else f"{underlying} Direct LLM (No Med Agent Hub)"
            )
        else:
            base_label = str(p_meta.get("label") or api_pid)
        label = f"{base_label} ({b_tag} budget)" if b_tag else base_label
        backends_meta[pid] = {
            "label": label,
            "kind": "provider_arm",
            "provider": "direct" if is_direct else "hub",
            "modelName": underlying,
            "profile": api_pid,
            "budget_tokens": eff_b,
            "answer_model": underlying,
        }
        arm_cards_meta[pid] = {
            "id": pid,
            "label": label,
            "kind": "single",
            "models": [{"id": underlying, "family": fam}],
            "roles": {"synthesizer": {"id": underlying, "family": fam}},
            "answer_model": underlying,
            "include_kb_findings": inc_kb,
            "budget_tokens": eff_b,
        }

    run_meta = {
        "reference_date": "2026-11-03",
        "backends": backends_meta,
        "arm_cards": arm_cards_meta,
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(run_meta, indent=2) + "\n", encoding="utf-8"
    )
    _write_scenario_and_chart_inputs(run_dir, cases, observed_envelopes)


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
        new_is_longer = len(new_text) > len(cur_text)
        if new_is_longer:
            merged["condensed_text"] = envelope.get("condensed_text")

        primary_maps = (envelope.get("mappings") or []) if new_is_longer else (merged.get("mappings") or [])
        secondary_maps = (merged.get("mappings") or []) if new_is_longer else (envelope.get("mappings") or [])
        by_idx: dict[int, dict[str, Any]] = {}
        seen_uuids: set[str] = set()
        extra_maps: list[dict[str, Any]] = []
        for m in primary_maps:
            if isinstance(m, dict):
                idx = m.get("index")
                if isinstance(idx, int) and idx not in by_idx:
                    by_idx[idx] = m
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if ru:
                    seen_uuids.add(ru)
        for m in secondary_maps:
            if isinstance(m, dict):
                idx = m.get("index")
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if isinstance(idx, int) and idx not in by_idx:
                    by_idx[idx] = m
                    if ru:
                        seen_uuids.add(ru)
                elif ru and ru not in seen_uuids:
                    seen_uuids.add(ru)
                    extra_maps.append(m)
        merged["mappings"] = [by_idx[k] for k in sorted(by_idx)] + extra_maps

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


def _write_scenario_and_chart_inputs(
    run_dir: Path,
    cases: list[WahsEvalCase],
    observed_envelopes: dict[str, dict[str, Any]],
) -> None:
    scenarios_dir = run_dir / "inputs" / "scenarios"
    charts_dir = run_dir / "inputs" / "charts"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    cases_by_id = {c.case_id: c for c in cases}
    for scenario_id, env in observed_envelopes.items():
        base_cid = scenario_id.split("__b", 1)[0]
        case = cases_by_id.get(base_cid)
        if case is None:
            continue
        scen_obj = {
            "id": scenario_id,
            "title": f"{case.use_case}: {case.case_id}",
            "patient_ref": scenario_id,
            "should_abstain": case.must_abstain,
            "expectations": {"should_abstain": case.must_abstain},
            "turns": [{"n": 1, "question": case.prompt}],
        }
        (scenarios_dir / f"{scenario_id}.json").write_text(
            json.dumps(scen_obj, indent=2) + "\n", encoding="utf-8"
        )

        mappings = list(env.get("mappings") or [])
        valid_set: set[str] = set()
        for u in (
            list(case.valid_uuids)
            + list(case.expected_target_uuids)
            + list(env.get("valid_uuids") or [])
            + list(env.get("retained_uuids") or [])
        ):
            if u:
                valid_set.add(str(u).replace("urn:uuid:", ""))
        for m in mappings:
            if isinstance(m, dict):
                ru = str(m.get("resourceUuid") or "").replace("urn:uuid:", "")
                if ru:
                    valid_set.add(ru)
                for mu in m.get("memberUuids") or []:
                    if mu:
                        valid_set.add(str(mu).replace("urn:uuid:", ""))

        chart_snapshot = str(env.get("condensed_text") or "").strip()
        chart_obj = {
            "patient": {
                "uuid": scenario_id,
                "name": case.patient_id,
                "gender": "unknown",
                "birthdate": "",
                "slug": scenario_id,
            },
            "valid_uuids": sorted(valid_set),
            "mappings": mappings,
            "chart_snapshot": chart_snapshot,
        }
        (charts_dir / f"{scenario_id}.json").write_text(
            json.dumps(chart_obj, indent=2) + "\n", encoding="utf-8"
        )


def run_wahs_suite(
    cases_path: Path | str,
    *,
    client: Any,
    output_dir: Path | str = "artifacts/wahs",
    budgets: tuple[int, ...] | list[int] | None = None,
    context_arms: tuple[str, ...] | list[str] | None = None,
    condense_modes: tuple[str, ...] | list[str] | None = None,
    profiles: tuple[str, ...] | list[str] | None = None,
    git_sha: str | None = None,
    target_provenance: list[dict[str, Any]] | None = None,
    dataset_id: str = "wahs-synthetic-r4",
    dataset_version: str = "2026.10",
    evaluation_modality: str = "deterministic_pipeline",
    resume_from: Path | str | None = None,
) -> WahsRunResult:
    """Execute a WAHS evaluation suite against `client` and freeze all artifacts in `<output_dir>/<run_id>`."""
    if evaluation_modality not in VALID_EVALUATION_MODALITIES:
        raise ValueError(
            f"Invalid evaluation_modality '{evaluation_modality}'. Expected one of {VALID_EVALUATION_MODALITIES}"
        )
    if budgets is not None:
        for b in budgets:
            if isinstance(b, bool) or not isinstance(b, int) or b <= 0 or b > MAX_TOKEN_BUDGET:
                raise ValueError(
                    f"Invalid token budget {b!r}: expected int in [1, {MAX_TOKEN_BUDGET}]"
                )
    if context_arms is not None:
        for arm in context_arms:
            if arm not in VALID_CONTEXT_ARMS:
                raise ValueError(
                    f"Invalid context_arm {arm!r}. Expected one of {VALID_CONTEXT_ARMS}"
                )
    if condense_modes is not None:
        for mode in condense_modes:
            if mode not in VALID_CONDENSE_MODES:
                raise ValueError(
                    f"Invalid condense_mode {mode!r}. Expected one of {VALID_CONDENSE_MODES}"
                )

    cases_file = Path(cases_path)
    cases_bytes = cases_file.read_bytes()
    suite_sha256 = hashlib.sha256(cases_bytes).hexdigest()
    cases = load_wahs_cases(cases_file)
    if hasattr(client, "bundle_dirs") and isinstance(getattr(client, "bundle_dirs"), list):
        for candidate_dir in (
            cases_file.resolve().parent,
            cases_file.resolve().parent.parent,
            cases_file.resolve().parent.parent.parent / "work" / "wahs_data",
            cases_file.resolve().parent.parent.parent / "work" / "wahs_data" / "eval",
        ):
            if candidate_dir not in client.bundle_dirs:
                client.bundle_dirs.append(candidate_dir)

    active_context_arms: list[str | None] = (
        [str(a) for a in context_arms] if context_arms else [None]
    )
    active_condense_modes: list[str | None] = (
        [str(m) for m in condense_modes] if condense_modes else [None]
    )
    active_profiles: list[str | None] = (
        [str(p) for p in profiles if str(p).strip()] if profiles else [None]
    )

    def _budgets_for_profile_case(prof_spec: str | None, case_obj: WahsEvalCase) -> list[int]:
        if prof_spec and "@" in prof_spec:
            _, _, pinned_b, _ = _split_profile_budget(prof_spec)
            return [int(pinned_b)]
        if budgets:
            return [int(b) for b in budgets]
        return [int(b) for b in (case_obj.target_token_budgets or DEFAULT_TOKEN_BUDGETS)]

    expected_cells: list[dict[str, Any]] = []
    all_active_budgets: set[int] = set()
    max_budgets_per_profile = 1
    for prof_id in active_profiles:
        for case in cases:
            active_budgets = _budgets_for_profile_case(prof_id, case)
            max_budgets_per_profile = max(max_budgets_per_profile, len(active_budgets))
            for b_tokens in active_budgets:
                all_active_budgets.add(int(b_tokens))
                for c_arm in active_context_arms:
                    for c_mode in active_condense_modes:
                        expected_cells.append(
                            _cell_dict(case.case_id, int(b_tokens), c_arm, c_mode, prof_id)
                        )

    prior_rows: dict[tuple[str, int, str | None, str | None, str | None], dict[str, Any]] = {}
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
        prior_modality = str(r_manifest.get("evaluation_modality") or "deterministic_pipeline")
        if prior_modality != evaluation_modality:
            raise ValueError(
                f"Cannot resume from {r_dir}: evaluation_modality mismatch "
                f"(prior={prior_modality!r}, current={evaluation_modality!r})"
            )
        prior_expected_cells = r_manifest.get("expected_cells")
        if isinstance(prior_expected_cells, list) and prior_expected_cells != expected_cells:
            raise ValueError(
                f"Cannot resume from {r_dir}: expected_cells mismatch "
                f"(prior has {len(prior_expected_cells)} cells, current has {len(expected_cells)} cells)"
            )
        resumed_run_id = str(r_manifest.get("run_id") or r_dir.name)
        resume_ancestry = list(r_manifest.get("resumeAncestry") or [])
        if resumed_run_id and resumed_run_id not in resume_ancestry:
            resume_ancestry.append(resumed_run_id)
        r_results_path = r_dir / "results.jsonl"
        if r_results_path.is_file():
            for line in r_results_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                cid = str(row.get("case_id") or "")
                btok = int(row.get("budget_tokens") or 8192)
                c_arm = row.get("context_arm")
                c_mode = row.get("condense_mode")
                prof_id = row.get("profile_id")
                if cid and isinstance(row.get("response"), dict) and not row.get("error"):
                    prior_rows[(cid, btok, c_arm, c_mode, prof_id)] = row

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
        resumed_from=resumed_run_id,
        resume_ancestry=resume_ancestry,
    )
    manifest_path = run_dir / "run_manifest.json"
    events_path = run_dir / "events.jsonl"
    manifest_payload = manifest.to_dict()
    manifest_payload["expected_cells"] = expected_cells
    if budgets is not None:
        manifest_payload["budgets"] = [int(b) for b in budgets]
    if context_arms is not None:
        manifest_payload["context_arms"] = [str(a) for a in context_arms]
    if condense_modes is not None:
        manifest_payload["condense_modes"] = [str(m) for m in condense_modes]
    if profiles is not None:
        manifest_payload["profiles"] = [str(p) for p in profiles if str(p).strip()]
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    profiles_catalog = (
        client.get_wahs_profiles()
        if profiles and hasattr(client, "get_wahs_profiles") and callable(client.get_wahs_profiles)
        else {}
    )
    single_budget_mode = max_budgets_per_profile == 1
    run_event_payload: dict[str, Any] = {
        "event_type": "run",
        "run_id": run_id,
        "component": "wahs-evaluation",
        "evaluation_modality": evaluation_modality,
        "suite_sha256": suite_sha256,
        "expected_cells": len(expected_cells),
        "reference_date": "2026-11-03",
        "comparison_set": cases_file.stem,
    }
    if profiles:
        run_event_payload["scenario_ids"] = (
            [c.case_id for c in cases]
            if single_budget_mode
            else [
                f"{c.case_id}__b{int(b)}"
                for c in cases
                for b in (
                    [int(x) for x in budgets]
                    if budgets
                    else [int(x) for x in (c.target_token_budgets or DEFAULT_TOKEN_BUDGETS)]
                )
            ]
        )
        run_event_payload["backend_ids"] = [str(p) for p in profiles if str(p).strip()]
    append_event(events_path, run_event_payload)
    if profiles:
        for prof_id in [str(p) for p in profiles if str(p).strip()]:
            _, api_pid, _, b_tag = _split_profile_budget(prof_id)
            p_meta = profiles_catalog.get(api_pid) or profiles_catalog.get(prof_id) or {}
            _, underlying, _ = _infer_model_family_and_id(prof_id, p_meta)
            if api_pid.startswith("direct-") or api_pid.startswith("direct:"):
                base_label = (
                    "Gemma-4-12B (Q8) Direct LLM (No Med Agent Hub)"
                    if underlying == "gemma-4-12b"
                    else f"{underlying} Direct LLM (No Med Agent Hub)"
                )
            else:
                base_label = str(p_meta.get("label") or api_pid)
            label = f"{base_label} ({b_tag} budget)" if b_tag else base_label
            append_event(
                events_path,
                {
                    "event_type": "backend_selected",
                    "backend_id": prof_id,
                    "label": label,
                },
            )

    results_path = run_dir / "results.jsonl"
    scores: list[WahsCaseScore] = []
    cell_meta_list: list[dict[str, Any]] = []
    observed_envelopes: dict[str, dict[str, Any]] = {}

    with results_path.open("w", encoding="utf-8") as fh:
        for prof_id in active_profiles:
            for case in cases:
                active_budgets = _budgets_for_profile_case(prof_id, case)
                for b_tokens in active_budgets:
                    for c_arm in active_context_arms:
                        for c_mode in active_condense_modes:
                            started_iso = datetime.now(timezone.utc).isoformat()
                            prior = prior_rows.get((case.case_id, b_tokens, c_arm, c_mode, prof_id))
                            if prior is not None:
                                envelope = dict(prior["response"])
                            else:
                                envelope = _invoke_client_evaluate_case(
                                    client,
                                    case,
                                    budget_tokens=b_tokens,
                                    evaluation_modality=evaluation_modality,
                                    context_arm=c_arm,
                                    condense_mode=c_mode,
                                    profile_id=prof_id,
                                )
                            ended_iso = datetime.now(timezone.utc).isoformat()
                            score = score_wahs_case(case, envelope, budget_tokens=b_tokens)
                            scores.append(score)
                            req_meta: dict[str, Any] = {
                                "prompt": case.prompt,
                                "question": case.prompt,
                                "sharing_posture": case.sharing_posture,
                                "budget_tokens": b_tokens,
                                "evaluation_modality": evaluation_modality,
                            }
                            if c_arm is not None:
                                req_meta["context_arm"] = c_arm
                            if c_mode is not None:
                                req_meta["condense_mode"] = c_mode
                            if prof_id is not None:
                                req_meta["profile"] = prof_id
                            row: dict[str, Any] = {
                                "case_id": case.case_id,
                                "patient_id": case.patient_id,
                                "use_case": case.use_case,
                                "sharing_posture": case.sharing_posture,
                                "budget_tokens": b_tokens,
                                "request": req_meta,
                                "response": envelope,
                                "score": score.to_dict(),
                            }
                            if c_arm is not None:
                                row["context_arm"] = c_arm
                            if c_mode is not None:
                                row["condense_mode"] = c_mode
                            if prof_id is not None:
                                _, api_pid, _, _ = _split_profile_budget(prof_id, b_tokens)
                                p_meta = profiles_catalog.get(api_pid) or profiles_catalog.get(prof_id) or {}
                                m_fam, underlying_m, inc_kb = _infer_model_family_and_id(
                                    prof_id, p_meta
                                )
                                scenario_id = (
                                    case.case_id
                                    if single_budget_mode
                                    else f"{case.case_id}__b{b_tokens}"
                                )
                                lat_ms = int(envelope.get("latency_ms") or 0)
                                row["profile_id"] = prof_id
                                row["model_family"] = m_fam
                                row["underlying_model"] = underlying_m
                                row["include_kb_findings"] = inc_kb
                                row["scenario_id"] = scenario_id
                                row["backend_id"] = prof_id
                                row["turn"] = 1
                                row["started_at"] = started_iso
                                row["ended_at"] = ended_iso
                                row["metrics"] = {
                                    "total_ms": lat_ms,
                                    "latency_ms": lat_ms,
                                    "http_status": 200,
                                    "answer_chars": len(str(envelope.get("answer") or "")),
                                    "citation_count": len(envelope.get("references") or []),
                                }
                                observed_envelopes[scenario_id] = _merge_scenario_envelopes(
                                    observed_envelopes.get(scenario_id),
                                    dict(envelope),
                                )
                                cell_meta_list.append(
                                    {
                                        "profile_id": prof_id,
                                        "model_family": m_fam,
                                        "underlying_model": underlying_m,
                                        "include_kb_findings": inc_kb,
                                        "latency_ms": lat_ms,
                                    }
                                )
                            else:
                                cell_meta_list.append({})
                            fh.write(json.dumps(row) + "\n")
                            fh.flush()

    if profiles:
        _write_judge_prep_artifacts(
            run_dir,
            cases,
            [str(p) for p in profiles if str(p).strip()],
            client,
            observed_envelopes,
        )

    summary = _summarize_scores(
        scores,
        evaluation_modality=evaluation_modality,
        cell_meta_list=cell_meta_list,
    )
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
    """Re-score a frozen WAHS run directory offline without network or target access.

    Compares recorded `results.jsonl` rows against the frozen suite's expected
    `(case_id, budget_tokens[, context_arm, condense_mode, profile_id])` matrix so interrupted
    or partial runs are flagged as incomplete and missing/error cells count as failed.
    """
    rdir = Path(run_dir)
    cases_path = rdir / "inputs" / "wahs_eval_cases.jsonl"
    results_path = rdir / "results.jsonl"
    manifest_path = rdir / "run_manifest.json"
    evaluation_modality = "deterministic_pipeline"
    manifest_data: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        evaluation_modality = str(manifest_data.get("evaluation_modality") or "deterministic_pipeline")
        if "evaluation_modality" not in manifest_data:
            manifest_data["evaluation_modality"] = evaluation_modality
            manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    cases = load_wahs_cases(cases_path)
    cases_by_id = {c.case_id: c for c in cases}

    recorded_rows: dict[tuple[str, int, str | None, str | None, str | None], dict[str, Any]] = {}
    observed_order: list[tuple[str, int, str | None, str | None, str | None]] = []
    if results_path.is_file():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row["case_id"])
            b_tokens = int(row.get("budget_tokens") or 8192)
            c_arm = row.get("context_arm")
            c_mode = row.get("condense_mode")
            prof_id = row.get("profile_id")
            key = (cid, b_tokens, c_arm, c_mode, prof_id)
            recorded_rows[key] = row
            if key not in observed_order:
                observed_order.append(key)

    expected_keys: list[tuple[str, int, str | None, str | None, str | None]] = []
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
                )
                if key not in expected_keys:
                    expected_keys.append(key)
    else:
        manifest_budgets = manifest_data.get("budgets")
        manifest_arms = manifest_data.get("context_arms")
        manifest_modes = manifest_data.get("condense_modes")
        manifest_profiles = manifest_data.get("profiles")
        active_arms: list[str | None] = (
            [str(a) for a in manifest_arms]
            if isinstance(manifest_arms, list) and manifest_arms
            else [None]
        )
        active_modes: list[str | None] = (
            [str(m) for m in manifest_modes]
            if isinstance(manifest_modes, list) and manifest_modes
            else [None]
        )
        active_profiles: list[str | None] = (
            [str(p) for p in manifest_profiles]
            if isinstance(manifest_profiles, list) and manifest_profiles
            else [None]
        )
        for case in cases:
            active_budgets = (
                [int(b) for b in manifest_budgets]
                if isinstance(manifest_budgets, list) and manifest_budgets
                else [int(b) for b in (case.target_token_budgets or DEFAULT_TOKEN_BUDGETS)]
            )
            for b_tokens in active_budgets:
                for c_arm in active_arms:
                    for c_mode in active_modes:
                        for prof_id in active_profiles:
                            key = (case.case_id, b_tokens, c_arm, c_mode, prof_id)
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
        for cid, b_tokens, c_arm, c_mode, prof_id in expected_keys:
            case = cases_by_id[cid]
            row = recorded_rows.get((cid, b_tokens, c_arm, c_mode, prof_id))
            if row is None or row.get("error") or not isinstance(row.get("response"), dict):
                err_msg = (
                    f"evaluation error for cell ({cid}, {b_tokens}): {row.get('error')}"
                    if row and row.get("error")
                    else f"missing or incomplete evaluation result for cell ({cid}, {b_tokens})"
                )
                score = _missing_cell_score(case, b_tokens, reason=err_msg)
                missing_cells.append(_cell_dict(cid, b_tokens, c_arm, c_mode, prof_id))
                if prof_id:
                    m_fam, underlying_m, inc_kb = _infer_model_family_and_id(prof_id)
                    cell_meta_list.append(
                        {
                            "profile_id": prof_id,
                            "model_family": m_fam,
                            "underlying_model": underlying_m,
                            "include_kb_findings": inc_kb,
                            "latency_ms": 0,
                        }
                    )
                else:
                    cell_meta_list.append({})
            else:
                env = row.get("response") or {}
                score = score_wahs_case(case, env, budget_tokens=b_tokens)
                row["score"] = score.to_dict()
                row["passed"] = score.passed
                req_d = row.get("request")
                if not isinstance(req_d, dict):
                    req_d = {}
                    row["request"] = req_d
                req_d.setdefault("patient", str(row.get("patient_id") or case.patient_id))
                if prof_id:
                    m_fam, underlying_m, inc_kb = _infer_model_family_and_id(prof_id)
                    cell_meta_list.append(
                        {
                            "profile_id": prof_id,
                            "model_family": str(row.get("model_family") or m_fam),
                            "underlying_model": str(row.get("underlying_model") or underlying_m),
                            "include_kb_findings": bool(row.get("include_kb_findings", inc_kb)),
                            "latency_ms": int(env.get("latency_ms") or 0),
                        }
                    )
                else:
                    cell_meta_list.append({})
            scores.append(score)
            exp_fh.write(json.dumps(score.to_dict()) + "\n")

    if results_path.is_file() and observed_order:
        with results_path.open("w", encoding="utf-8") as res_fh:
            for key in observed_order:
                if key in recorded_rows:
                    res_fh.write(json.dumps(recorded_rows[key]) + "\n")

    if (rdir / "inputs" / "scenarios").is_dir() or (rdir / "inputs" / "charts").is_dir() or any(
        r.get("scenario_id") or r.get("backend_id") for r in recorded_rows.values()
    ):
        observed_envelopes: dict[str, dict[str, Any]] = {}
        for row in recorded_rows.values():
            env = row.get("response")
            if isinstance(env, dict):
                scen_id = str(row.get("scenario_id") or row.get("case_id") or "")
                if scen_id:
                    observed_envelopes[scen_id] = _merge_scenario_envelopes(
                        observed_envelopes.get(scen_id),
                        env,
                    )
        if observed_envelopes:
            _write_scenario_and_chart_inputs(rdir, cases, observed_envelopes)

    summary = _summarize_scores(
        scores,
        evaluation_modality=evaluation_modality,
        missing_cells=missing_cells,
        cell_meta_list=cell_meta_list,
    )
    (rdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


_WAHS_PATIENT_PROFILES: dict[str, dict[str, Any]] = {
    "Maurice742_Auer97_set_b": {
        "badge": "Synthea Longitudinal Chart",
        "display": "Maurice Auer — Multi-year outpatient & inpatient history (~94k tokens)",
        "medications": [
            "Tacrolimus (immunosuppression)",
            "Furosemide / Warfarin longitudinal history",
            "Multi-specialty renal, cardiac & hematology care",
        ],
        "chart_url": "https://wahs-demo.openclinai.org/",
    },
    "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b": {
        "badge": "MIMIC-IV ICU & Hematology Chart",
        "display": "Complex ICU, Hematology & Cardiorenal Admission (~128k tokens; 1,100+ records across 2022–2026)",
        "medications": [
            "Vancomycin (held for trough 28.4 ug/mL & acute kidney injury)",
            "Apixaban 5 mg BID (active) vs. Warfarin (discontinued)",
            "Norepinephrine & Furosemide ICU infusions",
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
    return {
        "badge": "Clinical Chart",
        "display": patient_id.replace("_", " "),
        "chart_url": "https://wahs-demo.openclinai.org/",
    }


def _wahs_arm_card(backend_id: str) -> dict[str, Any]:
    raw_id = str(backend_id or "").strip()
    base_id, _, budget_tag = raw_id.partition("@")
    budget_suffix = f" · {budget_tag} chart" if budget_tag else ""
    short_budget = f" ({budget_tag})" if budget_tag else ""

    m_fam, underlying, inc_kb = _infer_model_family_and_id(raw_id)
    is_direct = base_id.startswith("direct-") or base_id.startswith("direct:")

    model_info: dict[str, str] = {"family": "Gemma 4", "params": "12B", "quant": "Q8_0"}
    short_model = "12B"
    full_model = "Gemma 12B"
    if "4b" in base_id:
        model_info = {"family": "Gemma 4", "params": "4B", "quant": "Q8_0"}
        short_model = "4B"
        full_model = "Gemma 4B"
    elif "26b" in base_id:
        model_info = {"family": "Gemma 4", "params": "26B MoE", "quant": "Q8_0"}
        short_model = "26B"
        full_model = "Gemma 26B"
    elif "27b" in base_id or "medgemma" in underlying:
        model_info = {"family": "MedGemma", "params": "27B", "quant": "Q8_0"}
        short_model = "MedGemma 27B"
        full_model = "MedGemma 27B"
    elif "qwen35b" in base_id:
        model_info = {"family": "Qwen 3", "params": "35B MoE", "quant": "Q8_0"}
        short_model = "Qwen 35B"
        full_model = "Qwen 3 35B"
    elif "qwen30b" in base_id:
        model_info = {"family": "Qwen 3 Coder", "params": "30B MoE", "quant": "Q8_0"}
        short_model = "Qwen Coder 30B"
        full_model = "Qwen 3 Coder 30B"
    elif "lfm24b" in base_id:
        model_info = {"family": "Liquid LFM2", "params": "24B", "quant": "Q8_0"}
        short_model = "Liquid 24B"
        full_model = "Liquid LFM2 24B"

    if is_direct:
        title = f"Direct AI — no Hub ({full_model}{budget_suffix})"
        short_title = f"Direct AI ({short_model}{short_budget})"
        path_desc = (
            "Sends the condensed chart and question directly to the AI model "
            "without Med Agent Hub prompts, clinical rules, or relationship graph"
        )
    elif inc_kb:
        title = f"Med Agent Hub + clinical rules ({full_model}{budget_suffix})"
        short_title = f"Hub + rules ({short_model}{short_budget})"
        path_desc = (
            "Full Med Agent Hub pipeline: condensed chart + automated clinical conflict rules "
            "+ patient relationship graph + safety net recovery"
        )
    else:
        title = f"Med Agent Hub — chart only ({full_model}{budget_suffix})"
        short_title = f"Hub chart-only ({short_model}{short_budget})"
        path_desc = (
            "Med Agent Hub citation & abstention prompts on the condensed chart only "
            "(automated clinical conflict rules & graph turned off)"
        )

    return {
        "title": title,
        "short_title": short_title,
        "kind": "single",
        "path": path_desc,
        "models": [model_info],
    }


def _format_wahs_failure_for_reader(failure: str) -> str:
    f = str(failure or "").strip()
    if f.startswith("missing required target UUIDs:"):
        n_missing = f.count("'") // 2
        if n_missing > 0:
            return f"Missed citing {n_missing} key source record{'s' if n_missing != 1 else ''} from the chart"
        return "Missed citing required source records from the chart"
    if f.startswith("missing positive rubric item"):
        m = re.search(r"\((.+?)\):", f)
        if m:
            return f"Missed clinical point: {m.group(1)}"
        return "Missed a required clinical checklist point"
    if f.startswith("missing required rubric criterion:"):
        crit = f.split(":", 1)[1].strip().strip("'\"")
        return f"Missed clinical point: {crit}"
    if "atomic citation entailment" in f:
        return "One or more cited source records did not fully support the sentence's claim"
    if f.startswith("abstention violation:"):
        if "must abstain" in f:
            return "Did not clearly state that the requested record is absent from the chart"
        return "Over-abstained on a question that is answerable from the chart"
    return f


def build_wahs_report_packet(
    run_dir: Path | str,
    *,
    patients_summary: str | None = None,
) -> dict[str, Any]:
    """Generate a reproducible, self-contained OpenClinAI report packet (`report.html`,
    `dashboard.html`, `meta.json`, `judge.jsonl`, and `judges/`) for a completed WAHS run directory.
    """
    import importlib.util
    from harness.validate.judging import arm_families, judge_summary
    from harness.validate.reconcile import scout_summary
    from harness.validate.report import build_report

    rdir = Path(run_dir).resolve()
    if not (rdir / "results.jsonl").is_file():
        raise FileNotFoundError(f"results.jsonl not found in {rdir}")

    summary = score_wahs_run(rdir)
    manifest_path = rdir / "run_manifest.json"
    manifest_data = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    evaluation_modality = str(
        manifest_data.get("evaluation_modality") or "live_model_and_team_eval"
    )
    cases_path = rdir / "inputs" / "wahs_eval_cases.jsonl"
    cases = load_wahs_cases(cases_path) if cases_path.is_file() else []
    cases_by_id = {c.case_id: c for c in cases}

    rows: list[dict[str, Any]] = []
    for line in (rdir / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

    backend_ids: list[str] = []
    for r in rows:
        bid = str(r.get("backend_id") or r.get("profile_id") or "")
        if bid and bid not in backend_ids:
            backend_ids.append(bid)

    if isinstance(manifest_data, dict) and manifest_path.is_file():
        prof_list = [str(p) for p in (manifest_data.get("profiles") or backend_ids)]
        has_direct_arm = any(p.startswith("direct-") or p.startswith("direct:") for p in prof_list)
        has_budget_curve = any("@32k" in p or "@64k" in p or "@128k" in p for p in prof_list)
        if has_direct_arm:
            manifest_data["context"] = {
                "text": (
                    "What this study tests: We ran a 12B medical AI model locally on a MacBook Pro (with a full 96k-word working memory, so nothing is cut off) "
                    "across three types of clinical questions: reconciling conflicting medications and disease stages, looking up past hospital stays and procedures, "
                    "and knowing when to say 'not in the chart' when asked about records that don't exist. "
                    "We compared three setups at tight (1k), standard (8k), and full-chart (32k) summary budgets: "
                    "(1) Direct AI (calling the model directly with the chart and question, without Med Agent Hub), "
                    "(2) Med Agent Hub with chart-only prompts (citation and abstention rules, but no automated clinical checks), and "
                    "(3) Med Agent Hub with full clinical rules and the patient relationship graph."
                ),
                "url": "https://openclinai.org/med-agent-hub/wahs-architecture/",
                "label": "How Med Agent Hub works →",
            }
        elif has_budget_curve:
            manifest_data["context"] = {
                "text": (
                    "What this study tests & why scores drop above 16k on a standard cloud server: "
                    "We tested condensed chart budgets from 1k up to 128k tokens on a shared 24 GB cloud GPU. "
                    "Because the standard Ollama server defaults to a 16k-token active working memory window, sending a 32k, 64k, or 128k chart "
                    "causes the server to silently drop the beginning of the prompt—cutting off the patient's active allergies, active medications, "
                    "and recent 2025–2026 hospital admissions at the top of the chart. "
                    "In a blinded 2-judge clinical review (Claude Opus 4.6 + GPT-5.4), plain chart summaries collapse from 80.2/100 at 8k down to 0.0–2.8/100 once that cutoff happens (with 4/4 unsafe answers), "
                    "while Med Agent Hub (+ clinical rules & graph) leads at 88.0/100 with Gemma 4 26B at 8k (0 unsafe answers), beats raw at 1k (43.8 vs. 24.8/100), and still rescues the Part 1 medication conflicts above the cutoff (27.0–32.8/100) because its safety summary sits inside the active window at the end of the prompt."
                ),
                "url": "https://openclinai.org/med-agent-hub/wahs-architecture/",
                "label": "How Med Agent Hub works →",
            }
        else:
            manifest_data["context"] = {
                "text": (
                    "What this study tests: We compared 7 open-weight AI models (from a compact 4B model up to 35B models across Google Gemma, MedGemma, Alibaba Qwen, and Liquid LFM2) "
                    "in two modes on the same complex patient charts: reading the condensed chart alone vs. reading the chart alongside Med Agent Hub's automated clinical conflict rules."
                ),
                "url": "https://openclinai.org/med-agent-hub/wahs-architecture/",
                "label": "How Med Agent Hub works →",
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
        manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    run_meta_path = rdir / "run_meta.json"
    run_meta_data = (
        json.loads(run_meta_path.read_text(encoding="utf-8"))
        if run_meta_path.is_file()
        else {}
    )
    run_meta_data["arm_cards"] = {bid: _wahs_arm_card(bid) for bid in backend_ids}
    run_meta_path.write_text(json.dumps(run_meta_data, indent=2) + "\n", encoding="utf-8")

    import shutil

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

    if judge_path.is_file():
        judge_rows = [
            json.loads(line)
            for line in judge_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        judge_rows = []

    scout = scout_summary(judge_rows, backend_ids)
    judging = judge_summary(rdir)
    if not patients_summary:
        unique_patients = []
        for c in cases:
            if c.patient_id not in unique_patients:
                unique_patients.append(c.patient_id)
        n_pt = len(unique_patients)
        pt_label = (
            f"{n_pt} complex ICU & longitudinal patient{'s' if n_pt != 1 else ''}"
            if n_pt > 0
            else "Clinical cohort"
        )
        patients_summary = (
            f"{pt_label} · {len(cases)} clinical question{'s' if len(cases) != 1 else ''} × {len(backend_ids)} setups"
        )

    meta_payload = {
        "scout": scout,
        "judging": judging,
        "evaluation_modality": evaluation_modality,
        "patients": patients_summary,
        "cells": len(rows),
        "date": datetime.now(timezone.utc).strftime("%-d %b %Y"),
    }
    meta_path = rdir / "meta.json"
    meta_path.write_text(json.dumps(meta_payload, indent=2) + "\n", encoding="utf-8")

    report_html_path = build_report(rdir)

    dash_script = Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"
    dash_html_path = rdir / "dashboard.html"
    if dash_script.is_file():
        spec = importlib.util.spec_from_file_location("_wahs_validate_dashboard", dash_script)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            setattr(mod, "_RUN_OVERRIDE", str(rdir))
            mod.freeze(str(dash_html_path))

    return {
        "run_dir": str(rdir),
        "report_html": str(report_html_path),
        "dashboard_html": str(dash_html_path) if dash_html_path.is_file() else None,
        "meta_json": str(meta_path),
        "total_cells": summary["total_cells"],
        "passed_cells": summary["passed_cells"],
        "scout": scout,
    }
