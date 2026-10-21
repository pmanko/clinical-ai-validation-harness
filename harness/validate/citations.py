"""Score a run's citations against a gold file of on-topic records per cell.

The gold format and the cell rule are the ones ChartSearchAI's eval/drift-metric uses:
per cell (`<patientUuid>|<topic>`) `present`, `ontopic` and `focus_uuids`; a cited record
is on-topic (gold or adjudicated on), off-topic (in focus, or adjudicated off) or
unknown. Present cells score precision, recall and F1 over the on-topic universe;
absent cells score whether the answer cited nothing. Only the model's own citations
count: a reference the module attached (`attachedByTheModule`) is not scored.

A scenario names its cell in `expectations.gold_cell`. The gold and any adjudication
file are copied into the run directory with their hashes, so the scores re-derive
offline from the run alone.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from statistics import mean
from typing import Any

from .models import load_scenario


def model_cited(references: list[dict[str, Any]] | None) -> list[str]:
    seen: list[str] = []
    for ref in references or []:
        uuid = ref.get("resourceUuid")
        if uuid and not ref.get("attachedByTheModule") and uuid not in seen:
            seen.append(uuid)
    return seen


def score_cell(cited: list[str], present: bool, ontopic: set[str], focus: set[str],
               off_adj: set[str] = frozenset(), on_adj: set[str] = frozenset()) -> dict[str, Any]:
    onset = set(ontopic) | set(on_adj)
    on = [c for c in cited if c in onset]
    off = [c for c in cited if c not in onset and (c in focus or c in off_adj)]
    unk = [c for c in cited if c not in onset and c not in focus and c not in off_adj]
    result: dict[str, Any] = {"on": on, "off": off, "unk": unk, "present": present}
    if present:
        result["scoreable"] = bool(onset)
        if not onset:
            result["prec"] = result["rec"] = result["f1"] = None
        else:
            prec = len(on) / len(cited) if cited else 0.0
            rec = len(on) / len(onset)
            result.update(prec=prec, rec=rec,
                          f1=2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    else:
        result["abstain_ok"] = not cited
    return result


def _freeze(run_dir: Path, path: Path) -> str:
    target = run_dir / "inputs" / "gold" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != target.resolve():
        shutil.copyfile(path, target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def score_run(run_dir: Path, gold_path: Path, adjudication_path: Path | None = None) -> dict:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    adj = json.loads(adjudication_path.read_text(encoding="utf-8")) if adjudication_path else {}
    on_adj = {k: set(v) for k, v in adj.get("_ontopic", {}).items()}
    off_adj = {k: set(v) for k, v in adj.items() if k != "_ontopic"}
    cells = {}
    for path in sorted((run_dir / "inputs" / "scenarios").glob("*.json")):
        scenario = load_scenario(path)
        cell = scenario.expectations.get("gold_cell")
        if cell:
            cells[scenario.id] = (cell, max(t.n for t in scenario.turns))
    per_backend: dict[str, dict[str, Any]] = {}
    for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("scenario_id") not in cells:
            continue
        cell, last_turn = cells[row["scenario_id"]]
        if row.get("turn") != last_turn or cell not in gold:
            continue
        g = gold[cell]
        envelope = row.get("response") if isinstance(row.get("response"), dict) else {}
        scored = score_cell(model_cited(envelope.get("references")), bool(g["present"]),
                            set(g.get("ontopic", {})), set(g.get("focus_uuids", {})),
                            off_adj.get(cell, set()), on_adj.get(cell, set()))
        scored.update(cell=cell, scenario_id=row["scenario_id"], answered="answer" in envelope)
        per_backend.setdefault(row.get("backend_id"), {})[cell] = scored
    summary = {}
    for backend, scored in per_backend.items():
        present = [s for s in scored.values() if s["present"] and s["scoreable"]]
        absent = [s for s in scored.values() if not s["present"]]
        summary[backend] = {
            "cells": len(scored),
            "unanswered": sum(not s["answered"] for s in scored.values()),
            "present_cells_scored": len(present),
            "meanF1": round(mean(s["f1"] for s in present), 3) if present else None,
            "absent_cells": len(absent),
            "abstention_accuracy": round(sum(s["abstain_ok"] for s in absent) / len(absent), 3)
            if absent else None,
            "offtopic_citations": sum(len(s["off"]) for s in scored.values()),
            "unknown_citations": sum(len(s["unk"]) for s in scored.values()),
        }
    out = {"gold": {"file": gold_path.name, "sha256": _freeze(run_dir, gold_path)},
           "adjudication": ({"file": adjudication_path.name,
                             "sha256": _freeze(run_dir, adjudication_path)}
                            if adjudication_path else None),
           "summary": summary, "cells": per_backend}
    (run_dir / "citation_scores.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
