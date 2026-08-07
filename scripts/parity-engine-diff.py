#!/usr/bin/env python3
"""Engine-parity contract diff (AC-3 + AC-4): the parity ledger.

Classifies every JSON path across two captured answer-leg engine requests
(scripts/parity-engine-probe.py artifacts) into:

  identical                the two arms agree
  documented_divergence    listed in the engine-parity.v1 contract with a reason
  violation                undocumented drift — the diff FAILS

must_match paths are stricter: any difference (or absence on either side) is a
violation even if someone documents it — documenting a must-match is itself drift.

Retrieval parity (AC-4): chart records are extracted from the prompts by their
serialized form "[n] (YYYY-MM-DD) text" and compared as sets, numbering-agnostic —
both arms must feed the model the same records or the diff FAILS.

Usage:
  scripts/parity-engine-diff.py artifacts/parity-engine/engine_request.bundled.json \
      artifacts/parity-engine/engine_request.hub.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_DEFAULT_CONTRACT = "datasets/validation/conformance/engine-parity.v1.json"
_MISSING = object()
_RECORD_RE = re.compile(r"^\[\d+\] (\((\d{4}-\d{2}-\d{2})\) .*?)\s*$", re.MULTILINE)


def _leaf_paths(node: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts to {dotted.path: leaf}; lists and scalars are leaves."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(_leaf_paths(value, path))
        return out
    return {prefix: node}


def _is_documented(path: str, documented: list[dict[str, str]]) -> str | None:
    for entry in documented:
        doc_path = entry["path"]
        if path == doc_path or path.startswith(doc_path + "."):
            return entry.get("reason", "")
    return None


def classify(a: dict[str, Any], b: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """The AC-3 ledger over the union of both requests' JSON paths."""
    must_match = set(contract.get("must_match", []))
    documented = list(contract.get("documented_divergences", []))
    flat_a = _leaf_paths(a)
    flat_b = _leaf_paths(b)
    identical: list[str] = []
    documented_out: list[dict[str, str]] = []
    violations: list[dict[str, Any]] = []

    for path in sorted(set(flat_a) | set(flat_b)):
        left = flat_a.get(path, _MISSING)
        right = flat_b.get(path, _MISSING)
        if left is not _MISSING and right is not _MISSING and left == right:
            identical.append(path)
            continue
        # A difference. must_match wins: never excusable by documentation.
        covering_must = path in must_match or any(
            path == m or path.startswith(m + ".") for m in must_match
        )
        if covering_must:
            violations.append({
                "path": path,
                "a": None if left is _MISSING else left,
                "b": None if right is _MISSING else right,
                "must_match": True,
            })
            continue
        reason = _is_documented(path, documented)
        if reason is not None:
            documented_out.append({"path": path, "reason": reason})
        else:
            violations.append({
                "path": path,
                "a": None if left is _MISSING else left,
                "b": None if right is _MISSING else right,
            })
    return {"identical": identical, "documented": documented_out, "violations": violations}


def _records(body: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for message in body.get("messages", []):
        # System prompts carry FORMAT DEMONSTRATION record lines (fake non-medical
        # data) — chart records only ever ride in non-system messages.
        if message.get("role") == "system":
            continue
        content = str(message.get("content", ""))
        for match in _RECORD_RE.finditer(content):
            found.add(match.group(1).strip())
    return found


def compare_record_sets(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """AC-4: the chart records each arm fed the model, numbering-agnostic."""
    records_a = _records(a)
    records_b = _records(b)
    return {
        "equal": records_a == records_b,
        "count_a": len(records_a),
        "count_b": len(records_b),
        "only_a": sorted(records_a - records_b),
        "only_b": sorted(records_b - records_a),
    }


_MANDATORY_LINE_RE = re.compile(
    r"^\[\d+\] (?:\(\d{4}-\d{2}-\d{2}\) )?(Allergy: .*?|Condition: .*?ACTIVE.*?)\s*$",
    re.MULTILINE,
)


def mandatory_core_parity(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """HARD invariant (post context-slice consolidation): the mandatory clinical core —
    allergies + active conditions — must appear in BOTH answer-leg prompts. Compared on
    record TEXT, date-agnostic: bundled renders allergies undated by design, the hub dates
    them. Unlike the overlap metric this can never be excused by a documented divergence."""

    def core(body: dict[str, Any]) -> set[str]:
        found: set[str] = set()
        for message in body.get("messages", []):
            if message.get("role") == "system":
                continue
            for match in _MANDATORY_LINE_RE.finditer(str(message.get("content", ""))):
                found.add(match.group(1).strip())
        return found

    core_a = core(a)
    core_b = core(b)
    return {
        "equal": core_a == core_b,
        "core_a": sorted(core_a),
        "core_b": sorted(core_b),
        "only_a": sorted(core_a - core_b),
        "only_b": sorted(core_b - core_a),
    }


def evaluate_retrieval(
    a: dict[str, Any], b: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    """AC-4 verdict: equal record sets -> identical; unequal sets are a violation
    UNLESS the contract carries an explicit ``documented_retrieval_divergence`` entry
    (reasoned, reviewable, meant to be deleted once the context policies align). The
    overlap is always measured and reported either way — a documented divergence must
    never go dark."""
    result = compare_record_sets(a, b)
    if result["equal"]:
        result["status"] = "identical"
        return result
    documented = contract.get("documented_retrieval_divergence")
    if isinstance(documented, dict) and documented.get("reason"):
        result["status"] = "documented_divergence"
        result["reason"] = documented["reason"]
    else:
        result["status"] = "violation"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_a")
    parser.add_argument("artifact_b")
    parser.add_argument("--contract", default=_DEFAULT_CONTRACT)
    parser.add_argument("--out", default="artifacts/parity-engine/parity-diff.json")
    args = parser.parse_args()

    a = json.loads(Path(args.artifact_a).read_bytes())
    b = json.loads(Path(args.artifact_b).read_bytes())
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))

    ledger = classify(a, b, contract)
    retrieval = evaluate_retrieval(a, b, contract)
    mandatory = mandatory_core_parity(a, b)
    report = {
        "contract": contract.get("schema_version"),
        "artifact_a": args.artifact_a,
        "artifact_b": args.artifact_b,
        "ledger": ledger,
        "retrieval": retrieval,
        "mandatory_core": mandatory,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"identical paths:      {len(ledger['identical'])}")
    print(f"documented divergent: {len(ledger['documented'])}")
    for entry in ledger["documented"]:
        print(f"  ~ {entry['path']}: {entry['reason']}")
    print(f"violations:           {len(ledger['violations'])}")
    for violation in ledger["violations"]:
        tag = " [must_match]" if violation.get("must_match") else ""
        print(f"  ✗ {violation['path']}{tag}: a={violation['a']!r} b={violation['b']!r}")
    print(f"retrieval parity:     {retrieval['status']} "
          f"(a={retrieval['count_a']} records, b={retrieval['count_b']})")
    if retrieval.get("reason"):
        print(f"  ~ documented: {retrieval['reason']}")
    for record in retrieval["only_a"]:
        print(f"  < only in A: {record}")
    for record in retrieval["only_b"]:
        print(f"  > only in B: {record}")
    print(f"report -> {out}")

    print(f"mandatory core:       equal={mandatory['equal']} "
          f"(a={len(mandatory['core_a'])}, b={len(mandatory['core_b'])})")
    for record in mandatory["only_a"]:
        print(f"  ! core only in A: {record}")
    for record in mandatory["only_b"]:
        print(f"  ! core only in B: {record}")

    if ledger["violations"]:
        print("FAIL: undocumented engine-request divergence")
        return 1
    if not mandatory["equal"]:
        print("FAIL: mandatory clinical core differs between the arms — the shared slice "
              "guarantees it in both; never excusable by a documented divergence")
        return 1
    if not mandatory["core_a"] or not mandatory["core_b"]:
        print("FAIL: mandatory clinical core is empty in one or both arms; parity cannot be "
              "claimed without exercising required evidence")
        return 1
    if retrieval["status"] == "violation":
        print("FAIL: retrieval record sets differ with no explicit contract entry (AC-4)")
        return 1
    print("PASS: zero violations; mandatory core parity holds; retrieval "
          + ("sets identical" if retrieval["status"] == "identical"
             else "residual divergence is the documented hub budget ceiling + lexical union"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
