"""Shared review-state semantics for validation report surfaces.

The static report and live dashboard have different renderers, but a confidence
or lifecycle value must mean the same thing in both.  Keep policy here and let
each renderer own only its HTML.
"""

from __future__ import annotations

from typing import Any


CONFIDENCE_LABELS = {
    "green": "Self-check high",
    "yellow": "Self-check medium",
    "red": "Self-check low",
}

VALIDATION_LABELS = {
    "checking": "Checking answer",
    "checked": "Checked",
    "edited": "Updated after check",
    "needs_review": "Needs review",
    "unavailable": "Check unavailable",
    "complete": "Complete",
    "failed": "Failed",
    "pending": "Pending",
}


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


def validation_display(validation: Any) -> dict[str, str] | None:
    """Return the shared label and tone for a check lifecycle object."""
    if not isinstance(validation, dict) or not validation.get("status"):
        return None
    status = str(validation.get("status")).strip().lower()
    tone = (
        "danger"
        if status in {"needs_review", "failed"}
        else "warning"
        if status in {"edited", "unavailable", "pending", "checking"}
        else "success"
    )
    return {
        "status": status,
        "label": str(validation.get("label") or VALIDATION_LABELS.get(status, status)),
        "tone": tone,
    }


def indepth_validation_display(indepth: Any) -> dict[str, str] | None:
    """Resolve an In-Depth check state, falling back to its delivery status."""
    if not isinstance(indepth, dict):
        return None
    validation = indepth.get("validation")
    if isinstance(validation, dict) and validation.get("status"):
        return validation_display(validation)
    if indepth.get("status"):
        return validation_display({"status": indepth.get("status")})
    return None


def score_formatter_js(name: str = "fmt10") -> str:
    """One browser formatter for the report and dashboard's 0-10 score strings."""
    return f"function {name}(v){{ return v==null ? '\u2014' : (Math.round(v*10)/10); }}"
