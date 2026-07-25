"""Compatibility readers for staged response artifacts.

Product profiles keep In-Depth inside ``response.inDepth``. Historical harness
runs used a second call at ``row.indepth.response``, while the oldest combined
answers embedded an In-Depth section in the answer text. Consumers should use
this module so judging and reports cannot silently disagree about what shipped.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .sources import build_sources


_IN_DEPTH_HEADING = re.compile(r"\*\*In\s*Depth\*\*", re.IGNORECASE)
_CITATION = re.compile(r"\[(\d+)\]")


def split_answer_sections(answer: Any) -> tuple[str, str]:
    """Split the historical combined Answer/In-Depth markdown envelope."""
    text = "" if answer is None else str(answer)
    match = _IN_DEPTH_HEADING.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.end() :].strip()


def _citation_indices(text: Any) -> set[int]:
    return {int(match.group(1)) for match in _CITATION.finditer(str(text or ""))}


def _block_reference_indices(blocks: Any) -> set[int]:
    found: set[int] = set()
    for block in blocks if isinstance(blocks, list) else []:
        for row in (block.get("rows") or []) if isinstance(block, dict) else []:
            for cell in ((row or {}).get("cells") or {}).values():
                for ref in (cell.get("refs") or []) if isinstance(cell, dict) else []:
                    if isinstance(ref, int) and not isinstance(ref, bool) and ref > 0:
                        found.add(ref)
    return found


def review_draft_from_trace(trace: Any) -> str:
    """Recover the earliest In-Depth draft that later checks could change."""
    if not isinstance(trace, dict):
        return ""
    for step in trace.get("steps") or []:
        if not isinstance(step, dict) or step.get("role") not in {
            "indepth",
            "indepth_synth",
            "indepth_resynth",
        }:
            continue
        claims = step.get("original_claims") or step.get("claims") or []
        if isinstance(claims, list):
            return "\n".join(f"- {claim}" for claim in claims if str(claim).strip())
    return ""


def prepare_answer_review(
    validation: Any,
    current_answer: Any,
    trace: Any,
    chart_fixture: dict[str, Any] | None,
) -> Any:
    """Attach an original Answer and its separate canonical sources for display only."""
    prepared = dict(validation) if isinstance(validation, dict) else {}
    original = str(prepared.get("originalAnswer") or "").strip()
    original_blocks = prepared.get("originalBlocks") or []
    if not original and isinstance(trace, dict):
        original = str(trace.get("original_answer_text") or "").strip()
        if original:
            prepared["originalAnswer"] = original
    current = str(current_answer or "").strip()
    has_original_reference_artifact = "originalReferences" in prepared
    if not original or (
        original == current
        and not original_blocks
        and not has_original_reference_artifact
    ):
        return prepared
    prepared["originalSources"] = build_sources(
        {
            "answer": original,
            "references": prepared.get("originalReferences") or [],
            "blocks": original_blocks,
        },
        chart_fixture,
    )
    return prepared


def prepare_indepth_review(
    indepth: Any,
    trace: Any,
    chart_fixture: dict[str, Any] | None,
) -> Any:
    """Attach review draft text and its separate canonical sources for display only."""
    if not isinstance(indepth, dict):
        return indepth
    prepared = dict(indepth)
    if not prepared.get("reviewDraft"):
        historical_draft = review_draft_from_trace(trace)
        final_draft = str(prepared.get("answer") or "").strip()
        if historical_draft and historical_draft.strip() != final_draft:
            prepared["reviewDraft"] = historical_draft
    draft = str(prepared.get("reviewDraft") or "").strip()
    if draft:
        prepared["reviewSources"] = build_sources(
            {
                "answer": draft,
                "references": prepared.get("reviewReferences") or [],
            },
            chart_fixture,
        )
    return prepared


def response_for_displayed_evidence(
    response: dict[str, Any],
    direct_answer: str,
    indepth: dict[str, Any],
    embedded_answer: str = "",
) -> dict[str, Any]:
    """Return the response subset whose evidence was actually displayed.

    A current ``response.inDepth`` object is authoritative. When it withholds or
    replaces an old embedded section, references used only by the discarded text
    are removed so evidence tiles and judges cannot see hidden claims.
    """
    background = indepth.get("answer") if isinstance(indepth, dict) else ""
    displayed = "\n\n".join(part for part in (direct_answer, background) if part).strip()
    artifact_ref_indices = {
        item.get("index")
        for item in indepth.get("references") or []
        if isinstance(item, dict)
        and isinstance(item.get("index"), int)
        and not isinstance(item.get("index"), bool)
    }
    artifact_ref_indices.update(
        ref
        for ref in indepth.get("citations") or []
        if isinstance(ref, int) and not isinstance(ref, bool)
    )
    allowed = (
        _citation_indices(displayed)
        | _block_reference_indices(response.get("blocks"))
        | artifact_ref_indices
    )
    discarded: set[int] = set()
    if embedded_answer and indepth.get("source") != "answer":
        discarded = _citation_indices(embedded_answer) - allowed

    artifact_refs = indepth.get("references") or []
    references = []
    seen: set[int] = set()
    for item in list(response.get("references") or []) + list(artifact_refs):
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index in discarded or index in seen:
            continue
        seen.add(index)
        references.append(item)

    citations = []
    for ref in list(response.get("citations") or []) + list(indepth.get("citations") or []):
        if isinstance(ref, int) and not isinstance(ref, bool) and ref not in discarded and ref not in citations:
            citations.append(ref)

    return {**response, "answer": displayed, "references": references, "citations": citations}


def in_depth_artifact(
    row: dict[str, Any],
    response: dict[str, Any],
    embedded_answer: str = "",
) -> dict[str, Any]:
    """Return one normalized view of current and historical In-Depth storage."""
    product = response.get("inDepth")
    if isinstance(product, dict):
        answer = product.get("answer")
        artifact = {
            "answer": answer.strip() if isinstance(answer, str) else "",
            "status": product.get("status"),
            "validation": product.get("validation"),
            "error": product.get("error"),
            "latency_ms": product.get("latency_ms"),
            "references": product.get("references") or [],
            "citations": product.get("citations") or [],
            "source": "response.inDepth",
        }
        if product.get("reviewDraft"):
            artifact["reviewDraft"] = product["reviewDraft"]
            artifact["reviewReferences"] = product.get("reviewReferences") or []
        return artifact

    separate = row.get("indepth") or {}
    nested = separate.get("response") or {}
    if isinstance(nested, str):
        try:
            nested = json.loads(nested)
        except (TypeError, ValueError):
            nested = {"answer": nested}
    answer = nested.get("answer") if isinstance(nested, dict) else ""
    normalized_answer = (
        answer.strip() if isinstance(answer, str) and answer else embedded_answer.strip()
    )
    outer_error = separate.get("error")
    nested_status = nested.get("status") if isinstance(nested, dict) else None
    nested_error = nested.get("error") if isinstance(nested, dict) else None
    return {
        "answer": normalized_answer,
        "status": nested_status or ("failed" if outer_error and not normalized_answer else None),
        "validation": nested.get("validation") if isinstance(nested, dict) else None,
        "error": nested_error or outer_error,
        "latency_ms": separate.get("latency_ms"),
        "references": (nested.get("references") or []) if isinstance(nested, dict) else [],
        "citations": (nested.get("citations") or []) if isinstance(nested, dict) else [],
        "source": "row.indepth" if separate else ("answer" if normalized_answer else None),
    }
