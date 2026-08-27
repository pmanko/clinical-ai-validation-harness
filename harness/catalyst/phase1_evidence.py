"""Read the complete stored evidence for a Catalyst Phase 1 comparison.

This module never calls Catalyst or PostgreSQL. It turns one finished run
directory into the same case records used by the reader-review input and the
HTML report, so reviewers do not receive a thinner view than the report.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def artifact_body(path: Path) -> dict[str, Any]:
    """Return an exchange response body, or a direct JSON object's body."""

    payload = load_json(path)
    response = payload.get("response")
    if isinstance(response, dict) and isinstance(response.get("body"), dict):
        return dict(response["body"])
    return payload


def _scenario_map(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in suite.get("scenarios") or []
        if isinstance(item, dict) and item.get("id")
    }


def _existing_artifacts(
    run_dir: Path,
    prefix: str,
    names: dict[str, str],
    evidence_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    evidence: dict[str, Any] = {}
    links: dict[str, str] = {}
    root = run_dir.resolve()
    for label, name in names.items():
        relative = f"{prefix}/{name}"
        path = (run_dir / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"evidence path escapes run directory: {relative}")
        if not path.is_file():
            continue
        if evidence_index is not None and relative not in evidence_index:
            raise ValueError(f"reader evidence is not in the signed index: {relative}")
        evidence[label] = artifact_body(path)
        links[label] = relative
    return evidence, links


def _turn_evidence(
    run_dir: Path,
    prefix: str,
    *,
    turn_index: int,
    instruction: str,
    expected_outcome: str,
    observed_outcome: str,
    answer_text: Any,
    sql: Any,
    retained_sql: Any = None,
    evidence_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if turn_index == 1:
        names = {
            "generation": "03-initial-generation-evidence.json",
            "validation": "05-validate-base.json",
            "execution": "06-execute-base.json",
            "independentAnswerCheck": "15-gold-execution-match-base.json",
        }
    else:
        followup_index = turn_index - 1
        suffix = "" if followup_index == 1 else f"-t{followup_index}"
        names = {
            "generation": f"11-followup-generation-evidence{suffix}.json",
            "validation": f"12-validate-successor{suffix}.json",
            "execution": f"13-execute-successor{suffix}.json",
            "independentAnswerCheck": (
                f"16-gold-execution-match-successor{suffix}.json"
            ),
        }
    evidence, links = _existing_artifacts(
        run_dir,
        prefix,
        names,
        evidence_index,
    )
    return {
        "turn": turn_index,
        "instruction": instruction,
        "expectedOutcome": expected_outcome,
        "observedOutcome": observed_outcome,
        "answerText": answer_text,
        "sql": sql,
        "retainedSql": retained_sql,
        "evidence": evidence,
        "evidencePaths": links,
    }


def case_records(
    run_dir: Path | str,
    suite: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    evidence_index: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one complete review record per model-team/scenario result."""

    run_dir = Path(run_dir)
    suite = suite or load_json(run_dir / "suite.json")
    results = results or load_json(run_dir / "results.json")
    scenarios = _scenario_map(suite)
    records: list[dict[str, Any]] = []
    for row in results.get("results") or []:
        if not isinstance(row, dict) or row.get("status") in {
            "skipped",
            "infrastructure_failed",
        }:
            continue
        scenario_id = str(row.get("scenarioId") or "")
        scenario = scenarios.get(scenario_id) or {}
        prefix = str(row.get("evidencePrefix") or "")
        if not prefix:
            raise ValueError(
                f"completed reader result has no evidence directory: {scenario_id}"
            )
        if evidence_index is not None:
            root = run_dir.resolve()
            prefix_path = (run_dir / prefix).resolve()
            if not prefix_path.is_relative_to(root) or not prefix_path.is_dir():
                raise ValueError(f"reader evidence directory is missing: {prefix}")
        turns = [
            _turn_evidence(
                run_dir,
                prefix,
                turn_index=1,
                instruction=str(scenario.get("initialQuestion") or ""),
                expected_outcome=str(row.get("expectedBaseOutcome") or ""),
                observed_outcome=str(row.get("baseOutcome") or ""),
                answer_text=row.get("baseAnswerText"),
                sql=row.get("baseSql"),
                evidence_index=evidence_index,
            )
        ]
        turn_summaries = row.get("turns") or []
        if not isinstance(turn_summaries, list) or any(
            not isinstance(turn, dict) for turn in turn_summaries
        ):
            raise ValueError(
                f"completed reader result has malformed turns: {scenario_id}"
            )
        for offset, turn in enumerate(turn_summaries, start=2):
            turns.append(
                _turn_evidence(
                    run_dir,
                    prefix,
                    turn_index=offset,
                    instruction=str(turn.get("instruction") or ""),
                    expected_outcome=str(turn.get("expectedOutcome") or ""),
                    observed_outcome=str(turn.get("observedOutcome") or ""),
                    answer_text=turn.get("answerText"),
                    sql=turn.get("sql"),
                    retained_sql=turn.get("retainedSql"),
                    evidence_index=evidence_index,
                )
            )
        records.append(
            {
                "profileId": row.get("profileId"),
                "scenarioId": scenario_id,
                "family": row.get("family") or scenario.get("family"),
                "measurementValid": row.get("measurementValid"),
                "turns": turns,
                "assertions": row.get("assertions") or [],
                "timing": row.get("timing") or {},
                "evidencePrefix": prefix,
            }
        )
    return records


def collection_summary(
    suite: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    """The intentionally small completion check used before review/reporting."""

    profiles = [str(value) for value in suite.get("comparisonProfiles") or []]
    if not profiles:
        profiles = [""]
    scenarios = [
        str(item.get("id"))
        for item in suite.get("scenarios") or []
        if isinstance(item, dict) and item.get("id")
    ]
    expected = {(profile, scenario, 1) for profile in profiles for scenario in scenarios}
    keys: list[tuple[str, str, int]] = []
    for row in results.get("results") or []:
        if not isinstance(row, dict) or row.get("status") in {
            "skipped",
            "infrastructure_failed",
        }:
            continue
        keys.append(
            (
                str(row.get("profileId") or ""),
                str(row.get("scenarioId") or ""),
                int(row.get("repetition") or 1),
            )
        )
    counts = Counter(keys)
    actual = set(keys)
    duplicates = [list(key) for key, count in sorted(counts.items()) if count > 1]
    missing = [list(key) for key in sorted(expected - actual)]
    unexpected = [list(key) for key in sorted(actual - expected)]
    complete = (
        not duplicates
        and not missing
        and not unexpected
        and results.get("measurementValid") is True
    )
    return {
        "complete": complete,
        "expectedConversations": len(expected),
        "recordedConversations": len(keys),
        "missing": missing,
        "duplicates": duplicates,
        "unexpected": unexpected,
    }
