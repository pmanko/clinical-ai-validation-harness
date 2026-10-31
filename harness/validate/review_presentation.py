"""Shared review-state semantics for validation report surfaces.

The static report and live dashboard have different renderers, but a status,
check finding or source verdict must mean the same thing in both. Keep the label
policy here and let each renderer own only its layout.

Each visible section (Answer, In-Depth) gets one status, named from the product's
check lifecycle, plus one short note naming which checks questioned it and why.
The product's confidence level is kept as secondary information with the
product's own wording; it is never called a self-check, because an arm's reviewer
may be another model and some arms run no review at all.
"""

from __future__ import annotations

import html
import re
from typing import Any

from .response_artifacts import in_depth_artifact, split_answer_sections


CONFIDENCE_LABELS = {
    "green": "High confidence",
    "yellow": "Medium confidence",
    "red": "Low confidence",
}

# Lifecycle status -> (plain label, tone, grid symbol). Raw status strings never
# reach a reader; an unknown status is humanized instead.
SECTION_STATUS = {
    "checked": ("Checked", "success", "✓"),
    "edited": ("Updated after check", "warning", "✎"),
    "needs_review": ("Needs review", "danger", "!"),
    "unavailable": ("Check unavailable", "warning", "?"),
    "no_claims": ("No points written", "neutral", "∅"),
    "checking": ("Checking", "warning", "…"),
    "pending": ("Pending", "warning", "…"),
    "failed": ("Failed", "danger", "×"),
    "not_checked": ("Not checked", "neutral", "·"),
    "not_in_profile": ("No In-Depth in this profile", "neutral", "–"),
}

# Worst first wins when a grid cell summarizes several turns.
_SEVERITY = {
    "needs_review": 6,
    "failed": 6,
    "unavailable": 4,
    "edited": 3,
    "checking": 2,
    "pending": 2,
    "checked": 1,
    "not_checked": 1,
    "no_claims": 0,
    "not_in_profile": 0,
}

CHECK_NAMES = {
    "date": "Date check",
    "review": "Model review",
    "citation": "Citation support",
}

_DATE_CHECK_IDS = {
    "window_scope",
    "date_value_binding",
    "single_point_trend",
    "date_format",
    "last_visit",
    "upcoming_date",
}

SUPPORT_LABELS = {
    "verified": ("supports its claim", "success"),
    "unsupported": ("does not support its claim", "danger"),
    "mixed": ("partly supports its claim", "warning"),
    "unchecked": ("support not checked", "neutral"),
    "checking": ("support being checked", "neutral"),
}

DRAFT_VIEWS = {
    "withheld": {
        "title": "In-Depth draft that was not delivered",
        "note": (
            "The product delivered no In-Depth for this turn. The model's draft is "
            "shown for review only; it is not part of the response."
        ),
    },
    "changed": {
        "title": "In-Depth draft before checks",
        "note": (
            "The delivered In-Depth above differs from the model's draft. The draft "
            "is shown for review only; it is not part of the response."
        ),
    },
}

_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_INLINE_MARK = re.compile(r"\*\((?:Check|General guidance)[^)]*\)\*", re.IGNORECASE)


def _humanize(status: str) -> str:
    words = status.replace("_", " ").replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else "Unknown"


def status_display(status: Any) -> dict[str, str]:
    """Plain label, tone and grid symbol for one lifecycle status."""
    key = str(status or "not_checked").strip().lower()
    label, tone, symbol = SECTION_STATUS.get(key, (_humanize(key), "neutral", "·"))
    return {"status": key, "label": label, "tone": tone, "symbol": symbol}


def _rated_display(conf: dict[str, Any]) -> dict[str, str]:
    """A section rated by the product without a check lifecycle: its confidence is the status."""
    return {"status": "rated", "label": conf["label"], "tone": conf["tone"], "symbol": "\u00b7"}


def worst_status(statuses: list[Any]) -> str | None:
    present = [str(s) for s in statuses if s]
    if not present:
        return None
    return max(present, key=lambda s: _SEVERITY.get(s, 1))


def confidence_display(confidence: Any) -> dict[str, Any] | None:
    """Return renderer-neutral confidence behavior for one visible section."""
    if not isinstance(confidence, dict) or not confidence.get("level"):
        return None
    level = str(confidence.get("level")).strip().lower()
    note = str(confidence.get("note") or "")
    if level == "red":
        treatment = "prominent"
        tone = "danger"
    elif level == "yellow":
        treatment = "collapsible"
        tone = "warning"
    else:
        treatment = "none"
        tone = "success" if level == "green" else "neutral"
    return {
        "level": level,
        "label": CONFIDENCE_LABELS.get(level, "Unrated"),
        "note": note,
        "note_treatment": treatment,
        # Flagged output is evidence for a reviewer; confidence never hides it.
        "show_output": True,
        "tone": tone,
    }


def section_confidence_displays(
    trace: Any, response_confidence: Any
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Use shipped response confidence, with trace as a historical fallback."""
    answer = None
    indepth = None
    if isinstance(response_confidence, dict):
        answer = response_confidence.get("answer")
        indepth = response_confidence.get("in_depth")
    if isinstance(trace, dict):
        answer = answer or trace.get("answer_confidence")
        indepth = indepth or trace.get("indepth_confidence")
    return confidence_display(answer), confidence_display(indepth)


# ---------------------------------------------------------------- text helpers


def citation_indices(text: Any) -> list[int]:
    """Cited record numbers in order, reading both ``[1][3]`` and ``[1, 3]``."""
    found: list[int] = []
    for match in _CITATION.finditer(str(text or "")):
        for part in match.group(1).split(","):
            value = int(part.strip())
            if value not in found:
                found.append(value)
    return found


def normalize_for_comparison(text: Any) -> str:
    """Text with citation formatting, inline check marks and spacing made uniform."""
    value = _INLINE_MARK.sub("", str(text or ""))
    value = _CITATION.sub(
        lambda m: "".join(f"[{part.strip()}]" for part in m.group(1).split(",")), value
    )
    value = re.sub(r"^\s*[-*•]\s+", "", value, flags=re.MULTILINE)
    return " ".join(value.split())


def differs_in_substance(draft: Any, delivered: Any) -> bool:
    return normalize_for_comparison(draft) != normalize_for_comparison(delivered)


def _inline_markdown(escaped: str) -> str:
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    out = re.sub(
        r"\*\((Check:[^)]*)\)\*", r"<em class='claim-mark'>(\1)</em>", out, flags=re.IGNORECASE
    )
    out = re.sub(
        r"\*\((General guidance[^)]*)\)\*",
        r"<em class='claim-guidance'>(\1)</em>",
        out,
        flags=re.IGNORECASE,
    )
    return re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", out)


def markdown_html(text: Any) -> str:
    """Render the small markdown subset product sections use, escaping first.

    Bullets become a list, ``**bold**`` and ``*italic*`` are kept, and each
    claim's inline check mark or general-guidance tag stays visible with its own
    class. The output has no raw newlines, so it reads the same inside the
    dashboard's pre-wrap boxes and the report's section bodies.
    """
    lines = html.escape("" if text is None else str(text)).replace("\\n", "\n").split("\n")
    parts: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []
    list_tag = ""

    def flush_paragraph() -> None:
        if paragraph:
            parts.append("<p class='md-p'>" + "<br>".join(paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if items:
            parts.append(f"<{list_tag} class='md-list'>" + "".join(items) + f"</{list_tag}>")
            items.clear()
        list_tag = ""

    for raw in lines:
        line = raw.strip()
        bullet = re.match(r"^[-*•]\s+(.*)$", line)
        numbered = re.match(r"^\d+[.)]\s+(.*)$", line)
        if bullet or numbered:
            flush_paragraph()
            tag = "ul" if bullet else "ol"
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            items.append("<li>" + _inline_markdown((bullet or numbered).group(1)) + "</li>")
            continue
        flush_list()
        if not line:
            flush_paragraph()
            continue
        heading = re.match(r"^#{1,6}\s+(.*)$", line)
        paragraph.append(
            "<strong>" + _inline_markdown(heading.group(1)) + "</strong>"
            if heading
            else _inline_markdown(line)
        )
    flush_list()
    flush_paragraph()
    return "".join(parts)


def _short(text: Any, limit: int = 160) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _points(indices: list[int]) -> str:
    ordered = sorted(set(indices))
    word = "point" if len(ordered) == 1 else "points"
    return f"{word} {', '.join(str(i) for i in ordered)}"


# -------------------------------------------------------------- answer section


def _confidence(confidence: Any) -> dict[str, Any] | None:
    """Accept a raw product confidence or an existing display; label it the product's way."""
    if not isinstance(confidence, dict) or not confidence.get("level"):
        return None
    return confidence_display({"level": confidence["level"], "note": confidence.get("note")})


def answer_check_findings(validation: Any) -> list[dict[str, str]]:
    """Which checks questioned the Answer and why, from ``answerValidation.issues``."""
    if not isinstance(validation, dict):
        return []
    findings: list[dict[str, str]] = []
    for issue in validation.get("issues") or []:
        if not isinstance(issue, dict) or str(issue.get("status") or "").lower() == "pass":
            continue
        check_id = str(issue.get("id") or "")
        if check_id in _DATE_CHECK_IDS or "temporal" in check_id or "date" in check_id:
            check = "date"
            reason = str(issue.get("reason") or "")
        elif check_id.startswith("citation"):
            check = "citation"
            reason = str(issue.get("reason") or "")
            if check_id.endswith("unavailable"):
                reason = reason or "Citation support could not be checked."
        elif not check_id and (issue.get("wrong") or issue.get("chart")):
            check = "review"
            reason = f"questioned “{issue.get('wrong') or ''}”"
            if issue.get("chart"):
                reason += f"; the chart says: {issue.get('chart')}"
        else:
            check = check_id or "review"
            reason = str(issue.get("reason") or issue.get("summary") or "")
        findings.append(
            {
                "check": check,
                "name": CHECK_NAMES.get(check, _humanize(check)),
                "reason": reason.strip().rstrip("."),
            }
        )
    return findings


def _record_identities(references: Any) -> set[tuple[Any, Any]]:
    return {
        (ref.get("index"), ref.get("sourceId") or ref.get("resourceUuid"))
        for ref in references or []
        if isinstance(ref, dict) and (ref.get("sourceId") or ref.get("resourceUuid"))
    }


def answer_original_differs(
    validation: Any,
    current_answer: Any,
    current_blocks: Any = None,
    current_references: Any = None,
) -> bool:
    """Whether the pre-check answer differs in wording, cited records or tables.

    Citation order and formatting are not a difference. Supporting records count
    as changed only when the same citation now names a different record.
    """
    if not isinstance(validation, dict):
        return False
    original = str(validation.get("originalAnswer") or "").strip()
    if not original:
        return False
    if differs_in_substance(original, current_answer):
        return True
    if set(citation_indices(original)) != set(citation_indices(current_answer)):
        return True
    before = _record_identities(validation.get("originalReferences"))
    after = _record_identities(current_references)
    if before and after:
        cited = set(citation_indices(original))
        if {r for r in before if r[0] in cited} != {r for r in after if r[0] in cited}:
            return True
    original_blocks = validation.get("originalBlocks") or []
    return bool(original_blocks) and original_blocks != (current_blocks or [])


def answer_section_view(
    validation: Any,
    confidence: Any,
    current_answer: Any = "",
    current_blocks: Any = None,
    current_references: Any = None,
) -> dict[str, Any] | None:
    """One status and note for the Answer, or None when the arm reports no checks."""
    conf = _confidence(confidence)
    has_validation = isinstance(validation, dict) and validation.get("status")
    if not has_validation and conf is None:
        return None
    display = status_display(validation.get("status")) if has_validation else _rated_display(conf)
    findings = answer_check_findings(validation)
    note_parts = [f"{f['name']}: {f['reason']}" if f["reason"] else f["name"] for f in findings]
    show_original = answer_original_differs(
        validation, current_answer, current_blocks, current_references
    )
    if (
        display["status"] == "edited"
        and isinstance(validation, dict)
        and validation.get("originalAnswer")
        and not show_original
    ):
        note_parts.append("the check reported a change, but the wording and cited records are the same")
    if not note_parts and conf and conf.get("level") != "green" and conf.get("note"):
        note_parts.append(str(conf["note"]).strip().rstrip("."))
    return {
        **display,
        "confidence": conf.get("label") if conf and display["status"] != "rated" else None,
        "confidence_level": conf.get("level") if conf else None,
        "note": ("; ".join(note_parts) + ".") if note_parts else "",
        "checks": list(dict.fromkeys(f["name"] for f in findings)),
        "show_original": show_original,
    }


# ------------------------------------------------------------ In-Depth section


def _verdict(verdict: str, tone: str, reason: str = "") -> dict[str, str]:
    return {"verdict": verdict, "tone": tone, "reason": reason.strip()}


def _date_verdict(check: Any) -> dict[str, str]:
    gate = (check or {}).get("gate") if isinstance(check, dict) else None
    if not isinstance(gate, dict):
        return _verdict("not run", "neutral")
    status = str(gate.get("status") or "").lower()
    reasons = [
        str(item.get("reason") or "").strip()
        for item in gate.get("checks") or []
        if isinstance(item, dict) and str(item.get("status") or "").lower() in {"fail", "warn"}
    ]
    reason = " ".join(r if r.endswith(".") else r + "." for r in reasons if r)
    if status == "fail":
        return _verdict("conflict", "danger", reason)
    if status == "warn":
        return _verdict("warning", "warning", reason)
    if status == "pass":
        return _verdict("passed", "success")
    if status == "not_applicable":
        return _verdict("no dated facts", "neutral")
    return _verdict(_humanize(status).lower() if status else "not run", "neutral", reason)


def _review_reasons(issues: str, flagged: list[int]) -> dict[int, str]:
    """Split a review note into per-claim sentences when it names claim numbers."""
    pattern = re.compile(r"(?:Claim|Point)\s+(\d+)\s*[:.,\-]?\s*", re.IGNORECASE)
    matches = list(pattern.finditer(issues))
    per_claim: dict[int, str] = {}
    for pos, match in enumerate(matches):
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(issues)
        index = int(match.group(1))
        text = issues[match.start() : end].strip()
        per_claim[index] = (per_claim.get(index, "") + " " + text).strip()
    return {index: per_claim.get(index) or issues.strip() for index in flagged}


def _citation_verdict(
    entry: Any, cited: list[int], support: dict[int, str], checks_ran: bool
) -> dict[str, str]:
    if isinstance(entry, dict):
        status = str(entry.get("status") or "").lower()
        reason = str(entry.get("reason") or "").strip()
        records = entry.get("source_indices") or []
        if records:
            reason = f"{reason} Records {', '.join(f'[{r}]' for r in records)}.".strip()
        if status == "info":
            return _verdict("general guidance", "neutral", reason)
        if status == "fail":
            return _verdict("not supported", "danger", reason)
        if status == "warn":
            return _verdict("not checked", "warning", reason)
        if status == "pass":
            return _verdict("supported", "success", reason)
    if not cited:
        return _verdict("general guidance", "neutral")
    states = [support.get(index) for index in cited]
    if states and all(state == "verified" for state in states):
        return _verdict("supported", "success")
    if any(state in {"unsupported", "mixed"} for state in states):
        return _verdict("not supported", "danger")
    return _verdict("not checked", "neutral" if not checks_ran else "warning")


def indepth_claim_rows(indepth: Any, sources_v1: Any = None) -> list[dict[str, Any]]:
    """One row per In-Depth claim with each check's verdict and reason."""
    validation = indepth.get("validation") if isinstance(indepth, dict) else None
    if not isinstance(validation, dict):
        return []
    claims = validation.get("claims") or []
    if not claims:
        return []
    gates = {
        check.get("claim_index"): check
        for check in validation.get("checks") or []
        if isinstance(check, dict)
    }
    citation_entries = {
        entry.get("claim_index"): entry
        for entry in validation.get("citation_checks") or []
        if isinstance(entry, dict)
    }
    checks_ran = "citation_checks" in validation
    support = {
        source.get("citation_index"): source.get("support_status")
        for source in (sources_v1 or {}).get("sources") or []
        if isinstance(source, dict)
    } if isinstance(sources_v1, dict) else {}
    review_status = str(validation.get("review_status") or "").lower()
    review_flagged = [int(i) for i in validation.get("review_flagged") or [] if str(i).isdigit()]
    review_reasons = _review_reasons(str(validation.get("review_issues") or ""), review_flagged)
    marked = set(validation.get("marked") or []) | set(validation.get("flagged") or [])
    rows = []
    for position, claim in enumerate(claims, start=1):
        cited = citation_indices(claim)
        if review_status == "flagged" and position in review_flagged:
            review = _verdict("flagged", "warning", review_reasons.get(position, ""))
        elif review_status == "unavailable":
            review = _verdict("unavailable", "warning")
        elif review_status == "flagged":
            review = _verdict("not flagged", "success")
        else:
            review = _verdict("no flag recorded", "neutral")
        rows.append(
            {
                "index": position,
                "text": _short(claim),
                "cited": cited,
                "general_guidance": not cited,
                "marked": position in marked,
                "checks": {
                    "date": _date_verdict(gates.get(position)),
                    "review": review,
                    "citation": _citation_verdict(
                        citation_entries.get(position), cited, support, checks_ran
                    ),
                },
            }
        )
    return rows


def _indepth_status(indepth: dict[str, Any]) -> str:
    validation = indepth.get("validation")
    if isinstance(validation, dict) and validation.get("status"):
        return str(validation["status"]).lower()
    answer = str(indepth.get("answer") or "").strip()
    status = str(indepth.get("status") or "").lower()
    if not answer and not indepth.get("error") and status in {"", "complete"}:
        return "not_in_profile"
    if status in {"", "complete"}:
        return "not_checked"
    return status


def draft_view(indepth: Any) -> dict[str, Any] | None:
    """The kept draft, when it differs from what was delivered, named for what it is."""
    if not isinstance(indepth, dict):
        return None
    draft = str(indepth.get("reviewDraft") or "").strip()
    delivered = str(indepth.get("answer") or "").strip()
    if not draft or not differs_in_substance(draft, delivered):
        return None
    kind = "changed" if delivered else "withheld"
    return {"kind": kind, **DRAFT_VIEWS[kind], "text": draft}


def indepth_section_view(
    indepth: Any, confidence: Any = None, sources_v1: Any = None
) -> dict[str, Any] | None:
    """One status, note, rendered body and per-claim rows for the In-Depth."""
    if not isinstance(indepth, dict):
        return None
    conf = _confidence(confidence)
    display = status_display(_indepth_status(indepth))
    if display["status"] == "not_checked" and conf:
        display = _rated_display(conf)
    validation = indepth.get("validation") if isinstance(indepth.get("validation"), dict) else {}
    rows = indepth_claim_rows(indepth, sources_v1)
    questioned: dict[str, list[int]] = {}
    for row in rows:
        for check, verdict in row["checks"].items():
            if verdict["tone"] in {"danger", "warning"} and verdict["verdict"] != "unavailable":
                questioned.setdefault(check, []).append(row["index"])
    note_parts = [
        f"{CHECK_NAMES[check].lower()} ({_points(indices)})"
        for check, indices in sorted(
            questioned.items(), key=lambda item: list(CHECK_NAMES).index(item[0])
        )
    ]
    marked = sorted(
        set(validation.get("marked") or [])
        | {row["index"] for row in rows if row["marked"]}
    )
    note = ""
    if note_parts:
        lead = f"{len(marked)} of {len(rows)} points marked" if marked and rows else "Questioned"
        note = f"{lead}: " + ", ".join(note_parts) + "."
    if str(validation.get("review_status") or "").lower() == "unavailable":
        note = (note + " " if note else "") + "The model review was unavailable."
    if not note and display["status"] not in {"checked", "no_claims", "not_in_profile"} and not (
        conf and conf.get("level") == "green"
    ):
        fallback = indepth.get("error") or (conf.get("note") if conf else "")
        note = str(fallback or "").strip()
    answer = str(indepth.get("answer") or "").strip()
    return {
        **display,
        "confidence": (
            conf.get("label")
            if conf and display["status"] not in {"not_in_profile", "rated"}
            else None
        ),
        "confidence_level": conf.get("level") if conf else None,
        "note": note,
        "checks": [CHECK_NAMES[c] for c in CHECK_NAMES if c in questioned],
        "marked": marked,
        "claim_count": len(rows),
        "body_html": markdown_html(answer) if answer else "",
        "claims": rows,
        "draft": draft_view(indepth),
        "check_names": dict(CHECK_NAMES),
        "validation": validation or None,
    }


# ------------------------------------------------------------------ evidence


def annotate_sources(
    sources_v1: Any,
    answer_text: Any = "",
    blocks: Any = None,
    indepth: Any = None,
) -> Any:
    """Add the citing section(s) and plain support/record words to each source."""
    if not isinstance(sources_v1, dict):
        return sources_v1
    answer_refs = set(citation_indices(answer_text))
    for block in blocks if isinstance(blocks, list) else []:
        for row in (block.get("rows") or []) if isinstance(block, dict) else []:
            for cell in ((row or {}).get("cells") or {}).values():
                if isinstance(cell, dict):
                    answer_refs.update(r for r in cell.get("refs") or [] if isinstance(r, int))
    indepth_refs: set[int] = set()
    if isinstance(indepth, dict):
        indepth_refs.update(citation_indices(indepth.get("answer")))
        indepth_refs.update(r for r in indepth.get("citations") or [] if isinstance(r, int))
        for ref in indepth.get("references") or []:
            if isinstance(ref, dict) and isinstance(ref.get("index"), int):
                indepth_refs.add(ref["index"])
    annotated = []
    for source in sources_v1.get("sources") or []:
        if not isinstance(source, dict):
            continue
        index = source.get("citation_index")
        sections = [
            name
            for name, refs in (("Answer", answer_refs), ("In-Depth", indepth_refs))
            if index in refs
        ]
        support = str(source.get("support_status") or "unchecked").lower()
        support_label, support_tone = SUPPORT_LABELS.get(support, (_humanize(support).lower(), "neutral"))
        if str(source.get("resource_type") or "").lower() == "knowledgereference":
            record_label, record_tone = "knowledge reference", "neutral"
        else:
            resolution = str(source.get("resolution_status") or "unknown").lower()
            record_label, record_tone = {
                "resolved": ("in this chart", "success"),
                "unresolved": ("not found in this chart", "danger"),
            }.get(resolution, ("chart match unknown", "neutral"))
        annotated.append(
            {
                **source,
                "sections": sections,
                "support_label": support_label,
                "support_tone": support_tone,
                "record_label": record_label,
                "record_tone": record_tone,
            }
        )
    knowledge = {s["citation_index"] for s in annotated if s["record_label"] == "knowledge reference"}
    diagnostics = dict(sources_v1.get("diagnostics") or {})
    if diagnostics.get("unresolved_refs"):
        # A knowledge reference is not a chart record, so it is not an unresolved chart ref.
        diagnostics["unresolved_refs"] = [
            ref for ref in diagnostics["unresolved_refs"] if ref not in knowledge
        ]
    return {**sources_v1, "sources": annotated, "diagnostics": diagnostics}


# ----------------------------------------------------------------------- grid


def row_review_summary(row: Any) -> dict[str, Any]:
    """Answer and In-Depth status for one result row, from its captured response."""
    response = (row or {}).get("response") if isinstance(row, dict) else None
    response = response if isinstance(response, dict) else {}
    validation = response.get("answerValidation")
    answer = (
        str(validation.get("status")).lower()
        if isinstance(validation, dict) and validation.get("status")
        else None
    )
    _, embedded = split_answer_sections(response.get("answer"))
    artifact = in_depth_artifact(row, response, embedded)
    indepth = _indepth_status(artifact)
    marks = (artifact.get("validation") or {}).get("marked") if isinstance(
        artifact.get("validation"), dict
    ) else None
    return {"answer": answer, "indepth": indepth, "marked": len(marks or [])}


def cell_review_summary(rows: list[Any]) -> dict[str, Any]:
    """Worst Answer and In-Depth status across a cell's turns, with marked points."""
    summaries = [row_review_summary(row) for row in rows]
    answer = worst_status([s["answer"] for s in summaries]) or ("not_checked" if summaries else None)
    indepth = worst_status([s["indepth"] for s in summaries])
    return {
        "answer": status_display(answer) if answer else None,
        "indepth": status_display(indepth) if indepth else None,
        "marked": sum(s["marked"] for s in summaries),
    }


def status_legend() -> list[dict[str, str]]:
    """Every status a grid cell can show, in the order a legend lists them."""
    order = ["checked", "edited", "needs_review", "unavailable", "no_claims", "not_in_profile", "not_checked"]
    return [status_display(status) for status in order]


def format_latency(ms: Any) -> str:
    """Seconds with one decimal, for every latency a reader sees."""
    try:
        return f"{float(ms) / 1000:.1f} s"
    except (TypeError, ValueError):
        return "n/a"


def score_formatter_js(name: str = "fmt10") -> str:
    """One browser formatter for the report and dashboard's 0-10 score strings."""
    return f"function {name}(v){{ return v==null ? '\u2014' : (Math.round(v*10)/10); }}"
