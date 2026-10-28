"""Score every product check in a judged run against the judge's rows.

A checked answer carries the verdicts of several checks (date check, record check,
citation support, model review) and a section status derived from them. None of
those verdicts is a measured confidence until it is scored against an independent
reference. This module does that scoring for one run: per check, how often a mark
coincided with a fault the judge found (precision) and how many judged faults the
check marked (recall), overall and per arm.

Answer level. One cell per (scenario, backend); the judge scores the final turn
with the conversation as context, so the marks come from the final turn's
envelope, as judge-prep builds the cells. Marks read the envelope as follows:

- ``date``: an ``answerValidation.issues[]`` entry with ``status: fail`` whose id is
  a date-check id (``window_scope``, ``date_value_binding``, ``single_point_trend``,
  ``date_format``, ``last_visit``, ``upcoming_date``, or any id naming ``date`` or
  ``temporal``), or ``temporalGate.status == fail``.
- ``record``: a cited record not in the chart, ``references[].resolutionStatus ==
  unresolved``.
- ``citation``: ``references[].groundingStatus`` in ``unsupported`` or ``mixed`` for
  a reference used by the Answer or a table block, or, under the three-way label
  contract, ``references[].support == contradicted``. ``not_addressed`` is not a mark.
- ``review``: an ``answerValidation.issues[]`` entry without an id that carries the
  reviewer's ``wrong``/``chart`` fields (the model review's flag shape), an issue whose
  id names ``review``, or a ``confidence.answer.note`` that says a review flagged the
  answer. Info entries never mark.
- ``needs_review``: ``answerValidation.status == needs_review``, the section status
  the clinician sees.

The judge's reference for a cell: ``citation_groundedness`` in ``unsupported`` or
``partly`` (a citation fault), ``accuracy`` below a threshold (default 7), ``harm``
true, and any ``temporal_*`` axis not ``ok``. ``any`` is their union and is the
reference behind the headline precision and recall; each axis is also reported on
its own so a check can be read against the fault it is meant to catch.

In-Depth level. One item per point (scenario, backend, turn, point number n, 1-based
in ``inDepth.validation.claims``). Marks: ``date`` from ``checks[]`` whose gate status
is ``fail``; ``citation`` from ``citation_checks[]`` with ``status: fail`` (``info``
is uncited guidance, ``warn`` and ``not_addressed`` are not marks); ``review`` from
``review_flagged[]``; ``marked`` from ``marked[]`` (or the older ``flagged[]``). The
reference is the judge row's ``background.claims[]`` with a ``verdict`` per point
(``correct``, ``wrong_fact``, ``wrong_citation``, ``unsupported``, ``guidance``), joined
on ``turn`` and ``n``. A judged error is ``wrong_fact``, ``wrong_citation`` or
``unsupported``. A run judged before the brief asked for per-point verdicts reports
``available: false`` for this level; the mark counts are still listed.

References: the canonical ``judge.jsonl`` and every pass under
``judges/<actor>/judge.jsonl``; a human ``adjudication.jsonl`` joins as one more
actor when present. The headline block is the canonical pass.
"""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.jsonl import read_jsonl
from .bundle import review_results
from .review_presentation import answer_check_findings

SCHEMA = "check_precision.v1"
OUTPUT_PATH = Path("judges") / "check-precision.json"
DEFAULT_ACCURACY_THRESHOLD = 7

ANSWER_CHECKS = ("date", "date_patched", "record", "citation", "review", "needs_review")
INDEPTH_CHECKS = ("date", "citation", "review", "marked")
CHECK_LABELS = {
    "date": "Date check",
    "date_patched": "Date check (answer patched; judged after the patch)",
    "record": "Record check",
    "citation": "Citation support",
    "review": "Model review",
    "needs_review": "Status: needs review",
    "marked": "Any mark",
}
REFERENCE_AXES = ("citation", "accuracy", "harm", "temporal")
VERDICTS = ("correct", "wrong_fact", "wrong_citation", "unsupported", "guidance")
ERROR_VERDICTS = frozenset({"wrong_fact", "wrong_citation", "unsupported"})

_CITATION_FAULTS = {"unsupported", "partly"}
_GROUNDING_MARKS = {"unsupported", "mixed"}
_ANSWER_USAGE = {"answer", "block"}
_REVIEW_NOTE_WORDS = ("review flagged", "model review", "reviewer")


# ------------------------------------------------------------------ envelope marks


def _response(row: dict[str, Any]) -> dict[str, Any]:
    response = row.get("response")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            return {}
    return response if isinstance(response, dict) else {}


def _status(value: Any) -> str:
    return str(value or "").strip().lower()


def answer_marks(response: dict[str, Any]) -> dict[str, bool]:
    """Which Answer checks marked this envelope (see the module docstring)."""
    validation = response.get("answerValidation")
    validation = validation if isinstance(validation, dict) else {}
    findings = [
        f for f in answer_check_findings(validation) if f.get("status", "fail") != "info"
    ]
    checks = {f["check"] for f in findings}
    gate = response.get("temporalGate")
    gate_failed = isinstance(gate, dict) and _status(gate.get("status")) == "fail"
    # A date check that patched the answer from the chart is not a mark the judge can score:
    # the judge reads the corrected text. Those cells are counted apart, and a low fault rate
    # there says the patch worked, not that the check was wrong.
    gate_patched = isinstance(gate, dict) and _status(gate.get("applied")) in {"patch", "repair"}
    references = [r for r in response.get("references") or [] if isinstance(r, dict)]
    record = any(_status(r.get("resolutionStatus")) == "unresolved" for r in references)
    citation = False
    for ref in references:
        usages = ref.get("usage") or []
        used_by_answer = not usages or any(
            _status((u or {}).get("location")) in _ANSWER_USAGE for u in usages
        )
        if not used_by_answer:
            continue
        if _status(ref.get("support")) == "contradicted":
            citation = True
        elif _status(ref.get("groundingStatus")) in _GROUNDING_MARKS and "support" not in ref:
            citation = True
    confidence = response.get("confidence")
    note = _status(((confidence or {}).get("answer") or {}).get("note")) if isinstance(confidence, dict) else ""
    review = "review" in checks or any(word in note for word in _REVIEW_NOTE_WORDS)
    return {
        "date": ("date" in checks or gate_failed) and not gate_patched,
        "date_patched": gate_patched,
        "record": record,
        "citation": citation,
        "review": review,
        "needs_review": _status(validation.get("status")) == "needs_review",
    }


def indepth_point_marks(response: dict[str, Any]) -> dict[int, dict[str, bool]]:
    """Marks per In-Depth point number (1-based), empty without a validation record."""
    indepth = response.get("inDepth")
    validation = indepth.get("validation") if isinstance(indepth, dict) else None
    if not isinstance(validation, dict):
        return {}
    claims = validation.get("claims") or []
    if not isinstance(claims, list) or not claims:
        return {}
    date_failed = {
        c.get("claim_index")
        for c in validation.get("checks") or []
        if isinstance(c, dict)
        and isinstance(c.get("gate"), dict)
        and _status(c["gate"].get("status")) == "fail"
    }
    citation_failed = {
        c.get("claim_index")
        for c in validation.get("citation_checks") or []
        if isinstance(c, dict) and _status(c.get("status")) == "fail"
    }
    review_flagged = {i for i in validation.get("review_flagged") or [] if isinstance(i, int)}
    marked = {i for i in validation.get("marked") or [] if isinstance(i, int)} | {
        i for i in validation.get("flagged") or [] if isinstance(i, int)
    }
    return {
        n: {
            "date": n in date_failed,
            "citation": n in citation_failed,
            "review": n in review_flagged,
            "marked": n in marked,
        }
        for n in range(1, len(claims) + 1)
    }


# ------------------------------------------------------------------ judge reference


def judged_answer_faults(row: dict[str, Any], accuracy_threshold: float) -> dict[str, bool]:
    """What the judge faulted in one cell, per reference axis plus their union."""
    accuracy = row.get("accuracy")
    numeric = isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool)
    temporal = any(
        row.get(axis) not in (None, "ok")
        for axis in ("temporal_date_accuracy", "temporal_window", "temporal_trend")
    )
    faults = {
        "citation": _status(row.get("citation_groundedness")) in _CITATION_FAULTS,
        "accuracy": bool(numeric and accuracy < accuracy_threshold),
        "harm": bool(row.get("harm")),
        "temporal": temporal,
    }
    faults["any"] = any(faults.values())
    return faults


def point_verdicts(row: dict[str, Any]) -> dict[tuple[int, int], str]:
    """``(turn, n) -> verdict`` from a judge row's ``background.claims``; empty when absent."""
    background = row.get("background")
    claims = background.get("claims") if isinstance(background, dict) else None
    out: dict[tuple[int, int], str] = {}
    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        verdict = _status(claim.get("verdict"))
        turn, n = claim.get("turn"), claim.get("n")
        if verdict in VERDICTS and isinstance(turn, int) and isinstance(n, int):
            out[(turn, n)] = verdict
    return out


def _adjudication_as_judge_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for record in read_jsonl(path):
        if not isinstance(record, dict):
            continue
        axes = record.get("axes") if isinstance(record.get("axes"), dict) else {}
        rows.append(
            {
                "scenario_id": record.get("scenario_id"),
                "backend_id": record.get("backend_id"),
                **{k: v for k, v in axes.items() if k != "harm"},
                "harm": record.get("harm"),
            }
        )
    return rows


def load_references(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Every judge reference in the run, the canonical pass first."""
    refs: dict[str, list[dict[str, Any]]] = {}
    canonical = run_dir / "judge.jsonl"
    if canonical.is_file():
        rows = [r for r in read_jsonl(canonical) if isinstance(r, dict)]
        if rows:
            refs["canonical"] = rows
    judges = run_dir / "judges"
    if judges.is_dir():
        for path in sorted(judges.glob("*/judge.jsonl")):
            rows = [r for r in read_jsonl(path) if isinstance(r, dict)]
            if rows:
                refs[path.parent.name] = rows
    adjudication = run_dir / "adjudication.jsonl"
    if adjudication.is_file():
        rows = _adjudication_as_judge_rows(adjudication)
        if rows:
            refs["adjudication"] = rows
    return refs


# ------------------------------------------------------------------ scoring


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def _score(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    marked = sum(1 for m, _ in pairs if m)
    judged = sum(1 for _, f in pairs if f)
    hits = sum(1 for m, f in pairs if m and f)
    return {
        "n": len(pairs),
        "marked": marked,
        "judged_errors": judged,
        "hits": hits,
        "precision": _ratio(hits, marked),
        "recall": _ratio(hits, judged),
    }


def _answer_block(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Per check: precision and recall against ``any`` fault, then per judge axis.

    ``marked_any_turn`` counts cells the check marked on any turn, so a mark on an
    earlier turn of a conversation is visible even though only the final turn is scored.
    """
    out: dict[str, Any] = {}
    for check in ANSWER_CHECKS:
        block = _score([(i["marks"][check], i["faults"]["any"]) for i in items])
        block["marked_any_turn"] = sum(1 for i in items if (i.get("any_turn") or {}).get(check))
        block["by_reference"] = {
            axis: {
                k: v
                for k, v in _score([(i["marks"][check], i["faults"][axis]) for i in items]).items()
                if k in {"judged_errors", "hits", "precision", "recall"}
            }
            for axis in REFERENCE_AXES
        }
        out[check] = block
    return out


def score_answer(
    cells: dict[tuple[str, str], dict[str, bool]],
    judge_rows: list[dict[str, Any]],
    accuracy_threshold: float = DEFAULT_ACCURACY_THRESHOLD,
    any_turn: dict[tuple[str, str], dict[str, bool]] | None = None,
) -> dict[str, Any]:
    """Answer-level precision and recall, overall and per arm.

    ``cells`` maps (scenario_id, backend_id) to the final turn's marks; a judged cell
    with no captured envelope is counted in ``unmatched`` and otherwise ignored.
    ``any_turn`` optionally maps a cell to the marks of any of its turns, for the count.
    """
    items = []
    unmatched = 0
    for row in judge_rows:
        key = (row.get("scenario_id"), row.get("backend_id"))
        marks = cells.get(key)
        if marks is None:
            unmatched += 1
            continue
        items.append(
            {
                "arm": key[1],
                "marks": marks,
                "any_turn": (any_turn or {}).get(key) or {},
                "faults": judged_answer_faults(row, accuracy_threshold),
            }
        )
    by_arm = defaultdict(list)
    for item in items:
        by_arm[item["arm"]].append(item)
    return {
        "cells": len(items),
        "unmatched_cells": unmatched,
        "overall": _answer_block(items),
        "by_arm": {arm: _answer_block(rows) for arm, rows in sorted(by_arm.items())},
    }


def _indepth_block(items: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for check in INDEPTH_CHECKS:
        block = _score([(i["marks"][check], i["verdict"] in ERROR_VERDICTS) for i in items])
        confusion = {
            "marked": Counter(i["verdict"] for i in items if i["marks"][check]),
            "unmarked": Counter(i["verdict"] for i in items if not i["marks"][check]),
        }
        block["by_verdict"] = {
            side: {v: counts.get(v, 0) for v in VERDICTS} for side, counts in confusion.items()
        }
        out[check] = block
    return out


def score_indepth(
    points: dict[tuple[str, str, int, int], dict[str, bool]],
    judge_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """In-Depth per-point precision and recall against the judge's verdicts.

    ``points`` maps (scenario_id, backend_id, turn, n) to that point's marks.
    """
    mark_counts = {
        check: sum(1 for marks in points.values() if marks[check]) for check in INDEPTH_CHECKS
    }
    verdicts: dict[tuple[str, str, int, int], str] = {}
    for row in judge_rows:
        for (turn, n), verdict in point_verdicts(row).items():
            verdicts[(row.get("scenario_id"), row.get("backend_id"), turn, n)] = verdict
    if not verdicts:
        return {
            "available": False,
            "reason": "the judge rows carry no per-point verdicts",
            "points": len(points),
            "marked": mark_counts,
        }
    items = []
    for key, verdict in verdicts.items():
        marks = points.get(key)
        if marks is not None:
            items.append({"arm": key[1], "marks": marks, "verdict": verdict})
    unjudged = len(points) - len(items)
    by_arm = defaultdict(list)
    for item in items:
        by_arm[item["arm"]].append(item)
    return {
        "available": True,
        "points": len(points),
        "judged_points": len(items),
        "unmatched_verdicts": len(verdicts) - len(items),
        "unjudged_points": unjudged,
        "marked": mark_counts,
        "overall": _indepth_block(items),
        "by_arm": {arm: _indepth_block(rows) for arm, rows in sorted(by_arm.items())},
    }


# ------------------------------------------------------------------ run level


def run_marks(
    results: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], dict[str, bool]],
    dict[tuple[str, str, int, int], dict[str, bool]],
    dict[tuple[str, str], dict[str, bool]],
]:
    """Final-turn Answer marks per cell, In-Depth marks per point, and any-turn marks.

    The third mapping says, per cell, which Answer checks marked any of its turns.
    """
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    points: dict[tuple[str, str, int, int], dict[str, bool]] = {}
    any_turn: dict[tuple[str, str], dict[str, bool]] = {}
    for row in results:
        if row.get("error"):
            continue
        key = (row.get("scenario_id"), row.get("backend_id"))
        turn = row.get("turn") if isinstance(row.get("turn"), int) else 1
        if key not in latest or turn >= (latest[key].get("turn") or 1):
            latest[key] = row
        response = _response(row)
        for n, marks in indepth_point_marks(response).items():
            points[(key[0], key[1], turn, n)] = marks
        turn_marks = answer_marks(response)
        seen = any_turn.setdefault(key, {check: False for check in ANSWER_CHECKS})
        for check in ANSWER_CHECKS:
            seen[check] = seen[check] or turn_marks[check]
    cells = {key: answer_marks(_response(row)) for key, row in latest.items()}
    return cells, points, any_turn


def score_run(
    run_dir: Path | str, accuracy_threshold: float = DEFAULT_ACCURACY_THRESHOLD
) -> dict[str, Any] | None:
    """The full scoring record for one run, or None when it has no judge rows."""
    run_dir = Path(run_dir)
    references = load_references(run_dir)
    if not references:
        return None
    cells, points, any_turn = run_marks(review_results(run_dir, strict=False))
    actors = {}
    for actor, rows in references.items():
        actors[actor] = {
            "rows": len(rows),
            "answer": score_answer(cells, rows, accuracy_threshold, any_turn),
            "indepth": score_indepth(points, rows),
        }
    headline = "canonical" if "canonical" in actors else next(iter(actors))
    return {
        "schema_version": SCHEMA,
        "run_id": run_dir.name,
        "reference": {
            "actors": list(actors),
            "headline": headline,
            "thresholds": {"accuracy_error_below": accuracy_threshold},
            "answer_faults": "citation_groundedness unsupported or partly; accuracy below the "
            "threshold; harm; any temporal axis not ok",
            "indepth_errors": sorted(ERROR_VERDICTS),
        },
        "answer": actors[headline]["answer"],
        "indepth": actors[headline]["indepth"],
        "actors": actors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_scores(run_dir: Path | str, data: dict[str, Any]) -> Path:
    path = Path(run_dir) / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_scores(run_dir: Path | str) -> dict[str, Any] | None:
    path = Path(run_dir) / OUTPUT_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------------ presentation

EXPLANATION = (
    "Precision: of the items a check marked, the share the judge also faulted. "
    "Recall: of the items the judge faulted, the share the check marked."
)


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _answer_rows(block: dict[str, Any]) -> list[list[str]]:
    rows = []
    for check in ANSWER_CHECKS:
        s = block.get(check) or {}
        rows.append(
            [
                CHECK_LABELS[check],
                str(s.get("marked", 0)),
                str(s.get("marked_any_turn", 0)),
                str(s.get("judged_errors", 0)),
                str(s.get("hits", 0)),
                _fmt(s.get("precision")),
                _fmt(s.get("recall")),
            ]
        )
    return rows


def _indepth_rows(block: dict[str, Any]) -> list[list[str]]:
    rows = []
    for check in INDEPTH_CHECKS:
        s = block.get(check) or {}
        rows.append(
            [
                CHECK_LABELS[check],
                str(s.get("marked", 0)),
                str(s.get("judged_errors", 0)),
                str(s.get("hits", 0)),
                _fmt(s.get("precision")),
                _fmt(s.get("recall")),
            ]
        )
    return rows


_HEAD = ["check", "marked", "judged errors", "hits", "precision", "recall"]
_ANSWER_HEAD = ["check", "marked", "marked, any turn", "judged errors", "hits", "precision", "recall"]


def _text_table(head: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = lambda cells: "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()  # noqa: E731
    return "\n".join([line(head)] + [line(r) for r in rows])


def table_text(data: dict[str, Any]) -> str:
    """The scoring as a plain-text table, for the terminal."""
    ref = data.get("reference") or {}
    out = [
        f"Checks against the judge, run {data.get('run_id')}",
        f"reference: {ref.get('headline')} (actors: {', '.join(ref.get('actors') or [])}); "
        f"accuracy error below {(ref.get('thresholds') or {}).get('accuracy_error_below')}",
        EXPLANATION,
        "",
    ]
    answer = data.get("answer") or {}
    out.append(f"Answer, overall ({answer.get('cells', 0)} judged cells)")
    out.append(_text_table(_ANSWER_HEAD, _answer_rows(answer.get("overall") or {})))
    for arm, block in (answer.get("by_arm") or {}).items():
        n = (block.get("needs_review") or {}).get("n", 0)
        out.append("")
        out.append(f"Answer, {arm} ({n} cells)")
        out.append(_text_table(_ANSWER_HEAD, _answer_rows(block)))
    indepth = data.get("indepth") or {}
    out.append("")
    if not indepth.get("available"):
        out.append(
            f"In-Depth per point: no per-point verdicts ({indepth.get('reason', 'not available')}); "
            f"{indepth.get('points', 0)} points, marks: "
            + ", ".join(f"{CHECK_LABELS[c]} {v}" for c, v in (indepth.get("marked") or {}).items())
        )
    else:
        out.append(
            f"In-Depth per point, overall ({indepth.get('judged_points', 0)} judged of "
            f"{indepth.get('points', 0)} points)"
        )
        out.append(_text_table(_HEAD, _indepth_rows(indepth.get("overall") or {})))
        for arm, block in (indepth.get("by_arm") or {}).items():
            out.append("")
            out.append(f"In-Depth per point, {arm} ({(block.get('marked') or {}).get('n', 0)} points)")
            out.append(_text_table(_HEAD, _indepth_rows(block)))
        out.append("")
        out.append("Marks by judge verdict (overall): check: marked / unmarked")
        for check in INDEPTH_CHECKS:
            by = (indepth.get("overall") or {}).get(check, {}).get("by_verdict") or {}
            marked = ", ".join(f"{v} {by.get('marked', {}).get(v, 0)}" for v in VERDICTS)
            unmarked = ", ".join(f"{v} {by.get('unmarked', {}).get(v, 0)}" for v in VERDICTS)
            out.append(f"  {CHECK_LABELS[check]}: marked [{marked}] / unmarked [{unmarked}]")
    return "\n".join(out)


def _html_table(head: list[str], rows: list[list[str]], caption: str) -> str:
    h = f"<table class='summary checkprec'><caption>{html.escape(caption)}</caption><thead><tr>"
    h += "".join(f"<th>{html.escape(c)}</th>" for c in head) + "</tr></thead><tbody>"
    for row in rows:
        h += "<tr>" + "".join(
            f"<td class='b'>{html.escape(c)}</td>" if i == 0 else f"<td>{html.escape(c)}</td>"
            for i, c in enumerate(row)
        ) + "</tr>"
    return h + "</tbody></table>"


def table_html(data: dict[str, Any], arm_titles: dict[str, str] | None = None) -> str:
    """The scoring as HTML, one block for the Answer and one for In-Depth points."""
    titles = arm_titles or {}
    ref = data.get("reference") or {}
    h = "<div class='checkprec'>"
    h += (
        "<p class='intro'>" + html.escape(EXPLANATION)
        + f" Reference: the {html.escape(str(ref.get('headline') or 'judge'))} judge pass"
        + f" (an accuracy below {html.escape(str((ref.get('thresholds') or {}).get('accuracy_error_below')))},"
        " a citation the judge found unsupported or partly supported, harm, or a temporal"
        " axis not ok counts as a judged error)."
        + (
            " Other passes scored: " + html.escape(", ".join(a for a in ref.get("actors") or [] if a != ref.get("headline"))) + "."
            if len(ref.get("actors") or []) > 1
            else ""
        )
        + "</p>"
    )
    answer = data.get("answer") or {}
    h += _html_table(_ANSWER_HEAD, _answer_rows(answer.get("overall") or {}), f"Answer checks, all arms ({answer.get('cells', 0)} judged cells)")
    arms = answer.get("by_arm") or {}
    if arms:
        h += "<details class='checkprec-arms'><summary>Answer checks per arm</summary>"
        for arm, block in arms.items():
            n = (block.get("needs_review") or {}).get("n", 0)
            h += _html_table(_ANSWER_HEAD, _answer_rows(block), f"{titles.get(arm, arm)} ({n} cells)")
        h += "</details>"
    indepth = data.get("indepth") or {}
    if not indepth.get("available"):
        marks = ", ".join(f"{CHECK_LABELS[c]} {v}" for c, v in (indepth.get("marked") or {}).items())
        h += (
            "<p class='intro'>In-Depth per point: no per-point verdicts in the judge rows"
            f" ({indepth.get('points', 0)} points; marks: {html.escape(marks)}).</p>"
        )
    else:
        h += _html_table(
            _HEAD,
            _indepth_rows(indepth.get("overall") or {}),
            f"In-Depth checks per point, all arms ({indepth.get('judged_points', 0)} judged of {indepth.get('points', 0)} points)",
        )
        verdict_head = ["check"] + [f"marked: {v}" for v in VERDICTS] + [f"unmarked: {v}" for v in VERDICTS]
        verdict_rows = []
        for check in INDEPTH_CHECKS:
            by = (indepth.get("overall") or {}).get(check, {}).get("by_verdict") or {}
            verdict_rows.append(
                [CHECK_LABELS[check]]
                + [str(by.get("marked", {}).get(v, 0)) for v in VERDICTS]
                + [str(by.get("unmarked", {}).get(v, 0)) for v in VERDICTS]
            )
        h += _html_table(verdict_head, verdict_rows, "Marks by judge verdict, all arms")
        arms = indepth.get("by_arm") or {}
        if arms:
            h += "<details class='checkprec-arms'><summary>In-Depth checks per arm</summary>"
            for arm, block in arms.items():
                n = (block.get("marked") or {}).get("n", 0)
                h += _html_table(_HEAD, _indepth_rows(block), f"{titles.get(arm, arm)} ({n} judged points)")
            h += "</details>"
    return h + "</div>"
