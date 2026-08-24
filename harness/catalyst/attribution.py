"""What a failed check means, in one place.

Three surfaces need the same answer -- the live dashboard, the triage gate
that guards `finish`, and the comparison page that records the decision --
and for a while each carried its own copy of the slot regex, the ledger
join and the precedence list. They drifted. This module is the single
source they all import.

The split itself lives with the runner (`assertion_class`), because the
runner stamps it into the artifacts; this module is about explaining a
failure once it has one.
"""

from __future__ import annotations

import json
from typing import Any

from .notebook_validation import _SLOT_SUFFIX, assertion_class

_ROOT_PRECEDENCE = (
    # First failed match wins; everything after it failed as a consequence.
    ("base_writer_outcome", "the opening answer was the wrong kind"),
    ("writer_outcome", "the writer's answer was rejected or of the wrong kind"),
    ("successor_execution_succeeded", "the accepted query failed to execute"),
    ("base_gold_execution_match",
     "the answer disagrees with the independent reference"),
    ("successor_gold_execution_match",
     "the answer disagrees with the independent reference"),
    ("no_sql_after_non_ready_base", "a refusal or question left SQL behind"),
    ("token_evidence_recorded", "no token accounting was published"),
)

_LEDGER_CACHE: dict[str, dict[tuple[str, ...], dict[str, Any]]] = {}


def root_name(name: str) -> str:
    """The check's name without its turn slot (`-base`, `-t2`)."""
    return _SLOT_SUFFIX.sub("", name)


def signature(assertions: list[dict[str, Any]]) -> tuple[str, ...]:
    """The sorted, slot-free names of the failures in one conversation."""
    return tuple(
        sorted({root_name(a["name"]) for a in assertions if not a.get("passed")})
    )


def vetted_ledger(path: str | None) -> dict[tuple[str, ...], dict[str, Any]]:
    """The recorded rationales, keyed by signature. Missing file -> empty."""
    if not path:
        return {}
    cached = _LEDGER_CACHE.get(path)
    if cached is None:
        try:
            with open(path, encoding="utf-8") as handle:
                cached = {tuple(e["signature"]): e for e in json.load(handle)}
        except Exception:
            cached = {}
        _LEDGER_CACHE[path] = cached
    return cached


def conformed(assertions: list[dict[str, Any]]) -> bool:
    """Whether these assertions show the system behaving as designed.

    A failed `evaluation` check means the model answered badly along a path
    the product allows. Only a failed `conformance` check says the run
    itself misbehaved and measured nothing trustworthy.
    """
    failed = [a for a in assertions if not a.get("passed")]
    for item in failed:
        if (item.get("class") or assertion_class(item.get("name") or "")) == "conformance":
            return False
    return True


def sentence(assertion: dict[str, Any]) -> str | None:
    """One plain sentence for a failed check, or None if it has no story.

    Gold verdicts recorded before the runner wrote sentences are summarized
    from their structured evidence; the runner compacts evidence to a JSON
    string, so a clipped blob simply fails to parse and falls through.
    """
    evidence = assertion.get("evidence")
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except (ValueError, TypeError):
            return evidence or None
    if not isinstance(evidence, dict):
        return None
    if isinstance(evidence.get("disagreement"), str):
        return evidence["disagreement"]
    if "observed" in evidence and "expected" in evidence:
        return (
            f"answered {evidence['observed']!r} where the scenario expects "
            f"{evidence['expected']!r}"
        )
    if "modelRowCount" in evidence and "referenceRowCount" in evidence:
        extra = evidence.get("extraKeys")
        missing = evidence.get("missingKeys")
        mismatched = evidence.get("valueMismatches")
        if extra or missing or mismatched:
            parts = []
            if extra:
                parts.append(
                    f"the answer has {len(extra)} groups the reference does not have"
                )
            if missing:
                parts.append(f"{len(missing)} reference groups missing")
            if mismatched:
                parts.append(f"counts disagree on {len(mismatched)} groups")
            return "; ".join(parts)
        model = evidence["modelRowCount"]
        counted = f"over {model}" if evidence.get("modelRowsExceededCap") else str(model)
        return (
            f"the answer returned {counted} rows; the independent reference "
            f"returns {evidence['referenceRowCount']}"
        )
    return None


def blame(
    assertions: list[dict[str, Any]], ledger_path: str | None = None
) -> dict[str, Any]:
    """One attributed explanation for a failed conversation.

    The root cause is the highest-precedence failure, said in plain words;
    the rest followed from it. `kind` is what the grid keys on: a broken
    contract invalidates the measurement, a judged failure is the finding
    the comparison exists to record.
    """
    failed = [a for a in assertions if not a.get("passed")]
    root = None
    for name, human in _ROOT_PRECEDENCE:
        hit = next((a for a in failed if root_name(a["name"]) == name), None)
        if hit is not None:
            root = {"name": name, "human": human, "why": sentence(hit),
                    "evidence": hit.get("evidence")}
            break
    if root is None and failed:
        first = failed[0]
        root = {"name": first["name"], "human": first["name"],
                "why": sentence(first), "evidence": first.get("evidence")}
    entry = vetted_ledger(ledger_path).get(signature(assertions))
    return {
        "kind": "judged" if conformed(assertions) else "invalid",
        "root": root,
        "consequences": max(0, len(failed) - 1),
        "rationale": entry["rationale"] if entry else None,
    }
