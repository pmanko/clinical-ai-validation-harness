"""Deterministic evaluation and HTTP suite runner for WAHS+ FHIR R4 condensation & Q&A.

Evaluates the four EHIgnite / WAHS+ Phase 2 target use cases:
- Use Case A (`use_case_a_reconciliation`): Cross-clinic medication, problem, allergy,
  and immunization reconciliation recall and conflict surfacing.
- Use Case B-1 (`use_case_b1_summary`): Encounter, ICU, and longitudinal pattern
  condensation under strict token budgets (16k -> 1k).
- Use Case B-2 (`use_case_b2_privacy`): Sensitive SDOH / IPV / 42 CFR Part 2 / WA MHMDA
  privacy segmentation (`patient_self` vs `external_share` zero-leakage gate).
- Use Case B-3 (`use_case_b3_grounded_qa`): Grounded patient & clinician Q&A with
  `[N] -> resourceUuid` citation resolution and explicit abstention on unanswerable queries.

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
    r"\b(not documented|no documented|no record|cannot verify|not found in|not present in|abstain)\b",
    re.IGNORECASE,
)

DEFAULT_SENSITIVE_TERMS = (
    "intimate partner violence",
    "victim of intimate partner abuse",
    "ipv",
    "domestic violence",
)


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WahsEvalCase":
        case_id = data.get("case_id")
        patient_id = data.get("patient_id") or data.get("patient_bundle")
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
            or data.get("expected_answer_type") == "abstain_not_in_chart"
            or str(use_case).endswith("abstention")
        )
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
    passed: bool
    failures: list[str]

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
            "fabricated_citation_count": self.fabricated_citation_count,
            "privacy_zero_leakage": self.privacy_zero_leakage,
            "leaked_items": list(self.leaked_items),
            "abstention_ok": self.abstention_ok,
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

    for ref in envelope.get("citations") or []:
        if not isinstance(ref, dict):
            continue
        raw = ref.get("resource_uuid")
        members = ref.get("member_uuids") or []
        for value in [raw, *members]:
            if isinstance(value, str) and value:
                uuids.add(value.removeprefix("urn:uuid:"))
        if isinstance(raw, str) and raw and ref.get("index") is not None:
            idx_map[str(ref["index"])] = raw.removeprefix("urn:uuid:")

    return uuids, idx_map


def score_wahs_case(
    case: WahsEvalCase,
    envelope: dict[str, Any],
    *,
    budget_tokens: int = 8192,
) -> WahsCaseScore:
    """Deterministically score a single WAHS evaluation case response envelope."""
    failures: list[str] = []
    raw_tokens = (envelope.get("tier_info") or {}).get("actual_tokens")
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

    # 3. Privacy zero-leakage gate
    leaked_items: list[str] = []
    for fu in case.forbidden_uuids:
        clean_fu = fu.replace("urn:uuid:", "")
        if clean_fu in known_uuids or clean_fu in answer or clean_fu in condensed_text:
            leaked_items.append(f"uuid:{clean_fu}")

    terms_to_check = list(case.forbidden_terms)
    if case.sharing_posture == "external_share" and not terms_to_check:
        terms_to_check = list(DEFAULT_SENSITIVE_TERMS)

    combined_text = f"{answer}\n{condensed_text}".lower()
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

    # 4. Abstention verification
    explicit_abstains = bool(envelope.get("abstained")) or bool(_ABSTENTION_RE.search(answer))
    if case.must_abstain:
        abstention_ok = explicit_abstains and fabricated_citation_count == 0
        if not abstention_ok:
            failures.append("failed to abstain cleanly on unanswerable query")
    else:
        abstention_ok = not bool(envelope.get("abstained")) and bool(answer.strip() or condensed_text.strip())
        if not abstention_ok:
            failures.append("unexpected abstention or empty output on answerable query")

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
        passed=len(failures) == 0,
        failures=failures,
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


def _summarize_scores(scores: list[WahsCaseScore]) -> dict[str, Any]:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    by_use_case: dict[str, dict[str, Any]] = {}
    for s in scores:
        bucket = by_use_case.setdefault(
            s.use_case,
            {"total": 0, "passed": 0, "uuid_recall_sum": 0.0, "citation_rate_sum": 0.0, "privacy_leaks": 0},
        )
        bucket["total"] += 1
        bucket["passed"] += int(s.passed)
        bucket["uuid_recall_sum"] += s.required_uuid_recall
        bucket["citation_rate_sum"] += s.citation_resolution_rate
        bucket["privacy_leaks"] += int(not s.privacy_zero_leakage)

    use_case_summary = {}
    for uc, b in sorted(by_use_case.items()):
        n = b["total"] or 1
        use_case_summary[uc] = {
            "total": b["total"],
            "passed": b["passed"],
            "pass_rate": round(b["passed"] / n, 4),
            "mean_uuid_recall": round(b["uuid_recall_sum"] / n, 4),
            "mean_citation_resolution_rate": round(b["citation_rate_sum"] / n, 4),
            "privacy_leaks": b["privacy_leaks"],
        }

    return {
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
        "privacy_leak_count": sum(1 for s in scores if not s.privacy_zero_leakage),
        "abstention_accuracy": round(
            sum(1 for s in scores if s.abstention_ok) / (total or 1), 4
        ),
        "by_use_case": use_case_summary,
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
) -> WahsRunResult:
    """Execute a WAHS evaluation suite against `client` and freeze all artifacts in `<output_dir>/<run_id>`."""
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

    summary = _summarize_scores(scores)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
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


def score_wahs_run(run_dir: Path | str) -> dict[str, Any]:
    """Re-score a frozen WAHS run directory offline without network or target access."""
    rdir = Path(run_dir)
    cases_path = rdir / "inputs" / "wahs_eval_cases.jsonl"
    results_path = rdir / "results.jsonl"
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

    summary = _summarize_scores(scores)
    (rdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
