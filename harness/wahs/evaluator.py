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
_ABSTENTION_META_OR_NEG_RE = re.compile(
    r"\b(?:"
    r"not\s+documented|no\s+documented|no\s+documentation|not\s+recorded|no\s+record|"
    r"cannot\s+verify|not\s+found\s+in|not\s+present\s+in|abstain|abstains|grounded\s+abstention|"
    r"no\s+matching\s+records|unrecorded|undocumented|missing|absent|without|none|"
    r"safety\s+posture|grounding\s+rules|external\s+share|external_share|patient_self|"
    r"42\s+cfr|mhmda|my\s+health\s+my\s+data|redacted|excluded|withheld|hidden|"
    r"switch\s+(?:back\s+)?to|ask\s+your\s+doctor|only\s+reports\s+facts"
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
    target_token_budgets: list[int] = field(default_factory=lambda: [8192, 4096, 2048])
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
        budgets = [int(b) for b in (data.get("target_token_budgets") or [8192, 4096, 2048])]
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
    """Collect trusted record UUIDs from case expectations, chart fixtures, or condensation manifests.
    Never trusts self-declared `references`, `citations`, or `citation_map` from the response alone.
    """
    trusted: set[str] = set()
    for source in (
        valid_uuids or (),
        case.valid_uuids,
        case.expected_target_uuids,
        envelope.get("valid_uuids") or (),
        envelope.get("retained_uuids") or (),
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
        if ans_low.strip() and (not req_any or any(tok in ans_low for tok in req_any)):
            earned_weight += weight
        else:
            crit = item.get("criterion") or item.get("id") or str(req_any)
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
        target_uuid = str(assertion.get("resource_uuid") or "").replace("urn:uuid:", "")
        must_mention = [str(x).lower() for x in (assertion.get("must_mention_any") or []) if str(x).strip()]
        must_not_distort = [str(x).lower() for x in (assertion.get("must_not_distort") or []) if str(x).strip()]

        distort_hit = [tok for tok in must_not_distort if tok in ans_low]
        if distort_hit:
            distortions += len(distort_hit)
            failures.append(
                f"citation distortion for {target_uuid or 'claim'}: found distorted value/status {', '.join(distort_hit)}"
            )
            continue

        mention_ok = (not must_mention) or any(tok in ans_low for tok in must_mention)
        if not mention_ok:
            failures.append(
                f"unentailed claim for {target_uuid or 'assertion'}: missing {', '.join(must_mention)}"
            )
            continue

        if not target_uuid:
            passed_assertions += 1
            continue

        if must_mention:
            # Bind the assertion to the inline citation(s) on the supporting sentence or line
            uuid_ok = False
            matching_sentences = [
                s for s in sentences if any(tok in s.lower() for tok in must_mention)
            ]
            for sent in matching_sentences:
                sent_cites = _CITATION_RE.findall(sent)
                if sent_cites:
                    sent_uuids = {
                        u for n in sent_cites for u in effective_idx_uuids.get(n, set())
                    }
                    if target_uuid in sent_uuids:
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
                            if target_uuid in ln_uuids:
                                uuid_ok = True
                                break
                    if uuid_ok:
                        break
        else:
            uuid_ok = target_uuid in all_inline_cited_uuids

        if uuid_ok:
            passed_assertions += 1
        else:
            failures.append(
                f"unentailed claim for {target_uuid}: supporting claim does not cite expected resource"
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

    envelope_abstained = bool(envelope.get("abstained")) or bool(envelope.get("abstains"))
    explicit_abstains = envelope_abstained or bool(_ABSTENTION_RE.search(answer_text))
    if not explicit_abstains:
        return False

    raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer_text) if s.strip()]
    for sent in raw_sentences:
        if sent.startswith("#") or sent.endswith(":"):
            continue
        words = _WORD_RE.findall(sent)
        if len(words) < 3:
            continue
        has_neg_or_meta = bool(_ABSTENTION_META_OR_NEG_RE.search(sent))
        has_affirm_finding = bool(_AFFIRMATIVE_CLINICAL_FINDING_RE.search(sent))
        if has_affirm_finding and not has_neg_or_meta:
            return False
        if not has_neg_or_meta:
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
            if u in known_uuids or u in answer or u in condensed_text
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


class WahsHubClient:
    """HTTP client for Med Agent Hub WAHS endpoints (`/wahs/api/chat` and `/wahs/api/analyze`)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 120.0,
        session: requests.Session | None = None,
        max_retries: int = 1,
        retry_backoff_s: float = 0.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("MED_AGENT_HUB_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = max(0.0, float(retry_backoff_s))
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def evaluate_case(
        self,
        case: WahsEvalCase,
        *,
        budget_tokens: int,
        evaluation_modality: str | None = None,
        condense_mode: str | None = None,
        use_lookup_tools: bool | None = None,
    ) -> dict[str, Any]:
        req_body: dict[str, Any] = {
            "patient_id": case.patient_id,
            "question": case.prompt,
            "sharing_posture": case.sharing_posture,
            "target_tokens": budget_tokens,
        }
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


def _summarize_scores(
    scores: list[WahsCaseScore],
    *,
    evaluation_modality: str = "deterministic_pipeline",
    missing_cells: list[dict[str, Any]] | None = None,
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
    return summary


def _invoke_client_evaluate_case(
    client: Any,
    case: WahsEvalCase,
    *,
    budget_tokens: int,
    evaluation_modality: str,
) -> dict[str, Any]:
    fn = client.evaluate_case
    try:
        sig = inspect.signature(fn)
        accepts_modality = "evaluation_modality" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
    except (TypeError, ValueError):
        accepts_modality = False
    if accepts_modality:
        return fn(case, budget_tokens=budget_tokens, evaluation_modality=evaluation_modality)
    return fn(case, budget_tokens=budget_tokens)


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
    resume_from: Path | str | None = None,
) -> WahsRunResult:
    """Execute a WAHS evaluation suite against `client` and freeze all artifacts in `<output_dir>/<run_id>`."""
    if evaluation_modality not in VALID_EVALUATION_MODALITIES:
        raise ValueError(
            f"Invalid evaluation_modality '{evaluation_modality}'. Expected one of {VALID_EVALUATION_MODALITIES}"
        )
    if budgets is not None:
        for b in budgets:
            if isinstance(b, bool) or not isinstance(b, int) or b <= 0 or b > 65536:
                raise ValueError(f"Invalid token budget {b!r}: expected int in [1, 65536]")

    cases_file = Path(cases_path)
    cases_bytes = cases_file.read_bytes()
    suite_sha256 = hashlib.sha256(cases_bytes).hexdigest()
    cases = load_wahs_cases(cases_file)

    expected_cells: list[dict[str, Any]] = []
    for case in cases:
        active_budgets = (
            [int(b) for b in budgets]
            if budgets
            else [int(b) for b in (case.target_token_budgets[:1] or [8192])]
        )
        for b_tokens in active_budgets:
            expected_cells.append({"case_id": case.case_id, "budget_tokens": int(b_tokens)})

    prior_rows: dict[tuple[str, int], dict[str, Any]] = {}
    resumed_run_id: str | None = None
    resume_ancestry: list[str] = []
    if resume_from is not None:
        r_dir = Path(resume_from)
        r_manifest_path = r_dir / "run_manifest.json"
        if r_manifest_path.is_file():
            r_manifest = json.loads(r_manifest_path.read_text(encoding="utf-8"))
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
                if cid and isinstance(row.get("response"), dict) and not row.get("error"):
                    prior_rows[(cid, btok)] = row

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
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    append_event(
        events_path,
        {
            "event_type": "run",
            "run_id": run_id,
            "component": "wahs-evaluation",
            "evaluation_modality": evaluation_modality,
            "suite_sha256": suite_sha256,
            "expected_cells": len(expected_cells),
        },
    )

    results_path = run_dir / "results.jsonl"
    scores: list[WahsCaseScore] = []
    with results_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            active_budgets = (
                [int(b) for b in budgets]
                if budgets
                else [int(b) for b in (case.target_token_budgets[:1] or [8192])]
            )
            for b_tokens in active_budgets:
                prior = prior_rows.get((case.case_id, b_tokens))
                if prior is not None:
                    envelope = dict(prior["response"])
                else:
                    envelope = _invoke_client_evaluate_case(
                        client,
                        case,
                        budget_tokens=b_tokens,
                        evaluation_modality=evaluation_modality,
                    )
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
                        "evaluation_modality": evaluation_modality,
                    },
                    "response": envelope,
                    "score": score.to_dict(),
                }
                fh.write(json.dumps(row) + "\n")
                fh.flush()

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
    """Re-score a frozen WAHS run directory offline without network or target access.

    Compares recorded `results.jsonl` rows against the frozen suite's expected
    `(case_id, budget_tokens)` matrix so interrupted or partial runs are flagged
    as incomplete and missing/error cells count as failed.
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

    recorded_rows: dict[tuple[str, int], dict[str, Any]] = {}
    observed_order: list[tuple[str, int]] = []
    if results_path.is_file():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row["case_id"])
            b_tokens = int(row.get("budget_tokens") or 8192)
            key = (cid, b_tokens)
            recorded_rows[key] = row
            if key not in observed_order:
                observed_order.append(key)

    expected_pairs: list[tuple[str, int]] = []
    raw_expected = manifest_data.get("expected_cells")
    if isinstance(raw_expected, list) and raw_expected:
        for item in raw_expected:
            if isinstance(item, dict) and "case_id" in item:
                pair = (str(item["case_id"]), int(item.get("budget_tokens") or 8192))
                if pair not in expected_pairs:
                    expected_pairs.append(pair)
    else:
        manifest_budgets = manifest_data.get("budgets")
        for case in cases:
            active_budgets = (
                [int(b) for b in manifest_budgets]
                if isinstance(manifest_budgets, list) and manifest_budgets
                else [int(b) for b in (case.target_token_budgets[:1] or [8192])]
            )
            for b_tokens in active_budgets:
                pair = (case.case_id, b_tokens)
                if pair not in expected_pairs:
                    expected_pairs.append(pair)
        for pair in observed_order:
            if pair not in expected_pairs:
                expected_pairs.append(pair)

    scores: list[WahsCaseScore] = []
    missing_cells: list[dict[str, Any]] = []
    expectations_path = rdir / "expectations.jsonl"
    with expectations_path.open("w", encoding="utf-8") as exp_fh:
        for cid, b_tokens in expected_pairs:
            case = cases_by_id[cid]
            row = recorded_rows.get((cid, b_tokens))
            if row is None or row.get("error") or not isinstance(row.get("response"), dict):
                err_msg = (
                    f"evaluation error for cell ({cid}, {b_tokens}): {row.get('error')}"
                    if row and row.get("error")
                    else f"missing or incomplete evaluation result for cell ({cid}, {b_tokens})"
                )
                score = _missing_cell_score(case, b_tokens, reason=err_msg)
                missing_cells.append({"case_id": cid, "budget_tokens": b_tokens})
            else:
                score = score_wahs_case(case, row.get("response") or {}, budget_tokens=b_tokens)
            scores.append(score)
            exp_fh.write(json.dumps(score.to_dict()) + "\n")

    summary = _summarize_scores(
        scores,
        evaluation_modality=evaluation_modality,
        missing_cells=missing_cells,
    )
    (rdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
