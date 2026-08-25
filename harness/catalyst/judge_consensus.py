"""Cross-actor agreement and human adjudication for the catalyst judge.

Two weaknesses of the judging layer that the report could not previously
even name:

* **Self-agreement is not validity.** Three passes of one model, finalized
  by median, measure how stably that model scores — not whether it scores
  correctly. Only a judge from a different family can disagree in a way
  that means something.
* **No human anchor.** Without one adjudicated row there is no way to say
  whether a marked-down score was harsh, lenient, or right.

This module holds the arithmetic for both, and — just as importantly —
lets a report state plainly when neither is present. A run with one actor
and no adjudication should say so rather than imply consensus it never had.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

_AXES = (
    "intent_fidelity",
    "sql_quality",
    "schema_discipline",
    "followup_coherence",
)

ADJUDICATION_NAME = "judge_adjudication.json"


def actor_id(row: dict[str, Any]) -> str:
    """Which judge produced this row: provider/model/version."""
    return "/".join(
        str(row.get(field) or "?")
        for field in ("provider", "model", "model_version")
    )


def group_by_actor(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    actors: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        actors.setdefault(actor_id(row), []).append(row)
    return actors


def cell_key(row: dict[str, Any]) -> str:
    """The judged unit: one version of one query in one scenario turn."""
    return f"{row.get('scenario_id')}:{row.get('turn')}:{row.get('version_id')}"


def consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-cell agreement across judge actors.

    `actors` is how many distinct judges scored anything. When it is 1 the
    result carries `single_actor: True` and empty disagreement lists: there
    is nothing to agree about, and a report must say that rather than
    present a lone judge's numbers as a consensus.
    """
    by_actor = group_by_actor(rows)
    names = sorted(by_actor)
    per_cell: dict[str, dict[str, dict[str, Any]]] = {}
    for name, actor_rows in by_actor.items():
        for row in actor_rows:
            per_cell.setdefault(cell_key(row), {})[name] = row

    disagreements: list[dict[str, Any]] = []
    if len(names) > 1:
        for key, scored in sorted(per_cell.items()):
            if len(scored) < 2:
                continue
            worst_axis: tuple[str, int] | None = None
            for axis in _AXES:
                values = [
                    int(row[axis])
                    for row in scored.values()
                    if isinstance(row.get(axis), (int, float))
                ]
                if len(values) < 2:
                    continue
                spread = max(values) - min(values)
                if spread and (worst_axis is None or spread > worst_axis[1]):
                    worst_axis = (axis, spread)
            if worst_axis is not None:
                disagreements.append(
                    {
                        "cell": key,
                        "axis": worst_axis[0],
                        "spread": worst_axis[1],
                        "scores": {
                            name: row.get(worst_axis[0])
                            for name, row in sorted(scored.items())
                        },
                    }
                )
    disagreements.sort(key=lambda item: -item["spread"])
    return {
        "actors": names,
        "single_actor": len(names) <= 1,
        "cells": len(per_cell),
        "cells_scored_by_all": sum(
            1 for scored in per_cell.values() if len(scored) == len(names)
        ),
        "disagreements": disagreements,
    }


def load_adjudication(run_dir: Path | str) -> dict[str, Any]:
    """Human verdicts on judged cells, or {} when nobody adjudicated.

    Shape: {"verdicts": {"<cell key>": {"agree": true|false, "note": "..."}}}
    Written by a person; absence is the normal state and never an error.
    """
    path = Path(run_dir) / ADJUDICATION_NAME
    if not path.is_file():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return blob if isinstance(blob, dict) else {}


def agreement(
    rows: list[dict[str, Any]], adjudication: dict[str, Any]
) -> dict[str, Any] | None:
    """How often the judge's call matched the human's, on reviewed cells.

    None when nothing was adjudicated — the honest state for most runs, and
    the one the report should print rather than a fabricated rate.
    """
    verdicts = (adjudication or {}).get("verdicts") or {}
    if not verdicts:
        return None
    judged = {cell_key(row) for row in rows}
    reviewed = [key for key in verdicts if key in judged]
    if not reviewed:
        return None
    agreed = sum(1 for key in reviewed if bool(verdicts[key].get("agree")))
    return {
        "reviewed": len(reviewed),
        "agreed": agreed,
        "rate": agreed / len(reviewed),
        "unknown_cells": sorted(set(verdicts) - judged),
        "notes": {
            key: str(verdicts[key].get("note") or "")
            for key in reviewed
            if verdicts[key].get("note")
        },
    }


def axis_medians(rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for axis in _AXES:
        values = [
            float(row[axis]) for row in rows if isinstance(row.get(axis), (int, float))
        ]
        if values:
            out[axis] = float(median(values))
    return out
