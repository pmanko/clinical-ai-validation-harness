"""Finalize the judge fan-out into judge.jsonl."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import sys

from .blinding import MAP_FILE, load_map, unblind_rows
from .judging import (
    CARD_SCHEMA,
    RUNNER_FIELDS,
    actor_id,
    canonical_actors,
    self_preference,
)
from .resources import read_rubric_bytes

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _portable_path(raw: str | pathlib.Path, rd: pathlib.Path) -> str:
    path = pathlib.Path(raw).expanduser().resolve()
    for base in (rd.resolve(), (ROOT / ".claude" / "skills").resolve(), ROOT.resolve()):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return pathlib.Path(raw).name


def _portable_rubric_ref(raw: str, rd: pathlib.Path) -> str:
    p = pathlib.Path(raw)
    if p.is_absolute() or ".." in p.parts or raw.startswith("~"):
        return _portable_path(raw, rd)
    return p.as_posix()


def _resolve_rubric_digest(
    rubric_ref: str, rd: pathlib.Path, explicit_digest: str | None
) -> str | None:
    if explicit_digest:
        return str(explicit_digest)
    raw_path = pathlib.Path(rubric_ref).expanduser()
    candidates = [
        raw_path,
        ROOT / ".claude" / "skills" / rubric_ref,
        ROOT / rubric_ref,
        rd / rubric_ref,
    ]
    for cand in candidates:
        if cand.is_file():
            return hashlib.sha256(cand.read_bytes()).hexdigest()
    if rubric_ref.replace("\\", "/").endswith("clinical-answer-scoring/rubric.md"):
        try:
            return hashlib.sha256(read_rubric_bytes()).hexdigest()
        except OSError:
            return None
    return None


def _invalidate_stale_agreement(rd: pathlib.Path, actor: str | None, promoted: bool) -> None:
    judges_dir = rd / "judges"
    if not judges_dir.is_dir():
        return
    for name in ("consensus.json", "combined.json"):
        path = judges_dir / name
        if not path.is_file():
            continue
        if promoted or actor:
            path.unlink(missing_ok=True)
    if promoted:
        for mpath in judges_dir.glob("*/manifest.json"):
            if actor and mpath.parent.name == actor:
                continue
            try:
                manifest = json.loads(mpath.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(manifest, dict) and manifest.get("promoted_to_canonical"):
                manifest["promoted_to_canonical"] = False
                mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_dir(arg: str) -> pathlib.Path:
    p = pathlib.Path(arg)
    if p.is_dir():
        return p
    for base in (pathlib.Path.cwd(), ROOT):
        cand = base / "artifacts/validate" / arg
        if cand.is_dir():
            return cand
    sys.exit(f"no run dir for {arg!r}")


def has_temporal_claim(row: dict) -> bool:
    """Accept the legacy workflow flag or the rubric's documented temporal fields."""
    return bool(row.get("has_temporal_claim")) or any(
        key in row
        for key in (
            "temporal_date_accuracy",
            "temporal_window",
            "temporal_trend",
        )
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize judge fan-out rows into judge.jsonl")
    parser.add_argument("run", help="Run id or artifacts/validate/<run> directory")
    parser.add_argument("rows", help="Workflow rows JSON array/dict")
    parser.add_argument(
        "--actor",
        help="Optional independent judge actor id; writes judges/<actor>/judge.jsonl",
    )
    parser.add_argument(
        "--actor-type",
        choices=("llm-judge", "human"),
        default="llm-judge",
        help="Actor provenance stored with an independent pass.",
    )
    parser.add_argument(
        "--model",
        help="Judge model/version, or the human reviewer role for a human pass.",
    )
    parser.add_argument(
        "--method",
        default="clinical-answer-scoring",
        help="Review method or workflow identifier.",
    )
    parser.add_argument(
        "--card",
        help="JSON file with the runner's judge card fields.",
    )
    parser.add_argument(
        "--blind",
        action="store_true",
        help="Unblind lettered backend_ids using judge-blind-map.json.",
    )
    parser.add_argument(
        "--blind-dir",
        help="Directory or file containing judge-blind-map.json; implies --blind.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="When --actor is set, also copy this actor pass to root judge.jsonl for report rendering.",
    )
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Do not write root judge.jsonl. Mainly useful for explicitness with --actor.",
    )
    return parser.parse_args(argv)


def _load_explicit_blind_map(
    rd: pathlib.Path,
    blind_dir: str | None,
    cells: list[dict] | None = None,
) -> tuple[dict[str, dict[str, str]], pathlib.Path]:
    if blind_dir:
        cand = pathlib.Path(blind_dir)
        map_path = cand if cand.is_file() else cand / MAP_FILE
        return load_map(map_path, cells=cells), map_path
    return load_map(rd, cells=cells), rd / MAP_FILE


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rd = run_dir(args.run)
    card = {}
    raw_rubric_input: str | None = None
    if args.card:
        raw_card = json.loads(pathlib.Path(args.card).read_text(encoding="utf-8"))
        if not isinstance(raw_card, dict):
            sys.exit(f"{args.card}: a judge card is a JSON object")
        if raw_card.get("rubric") not in (None, ""):
            raw_rubric_input = str(raw_card["rubric"])
        card = {k: raw_card[k] for k in RUNNER_FIELDS if raw_card.get(k) not in (None, "")}
        if "blinded" in card:
            card["blinded"] = bool(card["blinded"])
        if "brief_path" in card:
            card["brief_path"] = _portable_path(str(card["brief_path"]), rd)
        if "rubric" in card:
            card["rubric"] = _portable_rubric_ref(str(card["rubric"]), rd)
        if not args.model and card.get("model"):
            args.model = card["model"]
        if card.get("agent") == "human" and args.actor_type == "llm-judge":
            args.actor_type = "human"
        if not args.actor:
            try:
                args.actor = actor_id(card)
            except ValueError as exc:
                sys.exit(str(exc))
    if args.actor and not args.model:
        sys.exit("--model is required with --actor so independent judgments have provenance")
    with open(args.rows, encoding="utf-8") as rows_fh:
        rows = json.load(rows_fh)
    if isinstance(rows, dict):
        rows = rows.get("result") or rows.get("rows") or rows.get("return") or list(rows.values())
    if not isinstance(rows, list):
        sys.exit(f"{args.rows}: expected a JSON list of judge rows")

    cells = {}
    cell_list = []
    with open(rd / "judge-cells.jsonl", encoding="utf-8") as cells_fh:
        for line in cells_fh:
            if not line.strip():
                continue
            c = json.loads(line)
            cells[(c["scenario_id"], c["backend_id"])] = c
            cell_list.append(c)

    blind_requested = bool(
        args.blind
        or args.blind_dir
        or card.get("blinded") is True
        or any(isinstance(r, dict) and r.get("blinded") is True for r in rows)
    )
    if blind_requested:
        blind_map, map_path = _load_explicit_blind_map(rd, args.blind_dir, cells=cell_list)
        if not blind_map:
            sys.exit(f"blinded input requires a valid blind map at {map_path}")
        for r in rows:
            if not isinstance(r, dict) or r.get("_error") or "accuracy" not in r:
                continue
            sid = str(r.get("scenario_id") or "")
            bid = str(r.get("backend_id") or "")
            if bid not in (blind_map.get(sid) or {}):
                sys.exit(f"blinded row {sid}/{bid} is not present in {map_path}")
        rows, unblinded = unblind_rows(rows, blind_map)
        if unblinded:
            print(f"unblinded {unblinded} rows through {map_path}")

    out, skipped = [], []
    for r in rows:
        if not isinstance(r, dict) or r.get("_error") or "accuracy" not in r:
            skipped.append(
                r.get("scenario_id", "?") + "/" + r.get("backend_id", "?")
                if isinstance(r, dict)
                else "?"
            )
            continue
        sid, bid = r["scenario_id"], r["backend_id"]
        if cells and (sid, bid) not in cells:
            sys.exit(f"unknown cell {sid}/{bid}: not present in {rd / 'judge-cells.jsonl'}")
        cell = cells.get((sid, bid), {})
        row = {
            "scenario_id": sid,
            "backend_id": bid,
            "accuracy": r["accuracy"],
            "completeness": r["completeness"],
            "relevance": r["relevance"],
            "abstention_outcome": r["abstention_outcome"],
            "citation_groundedness": r["citation_groundedness"],
            "harm": bool(r["harm"]),
        }
        if has_temporal_claim(r):
            row["temporal_date_accuracy"] = r.get("temporal_date_accuracy", "ok")
            row["temporal_window"] = r.get("temporal_window", "ok")
            row["temporal_trend"] = r.get("temporal_trend", "ok")
        row["citation_resolution"] = cell.get("citation_resolution") or {
            "n_refs": 0,
            "n_resolved": 0,
            "n_unresolved": 0,
            "unresolved": [],
            "rate": None,
        }
        row["note"] = r.get("note", "")
        score_background = (
            cell.get("score_background")
            if "score_background" in cell
            else cell.get("has_in_depth", cell.get("is_team"))
        )
        if score_background and isinstance(r.get("background"), dict):
            row["background"] = r["background"]
        out.append(row)

    out.sort(key=lambda x: (x["scenario_id"], x["backend_id"]))
    destinations: list[tuple[pathlib.Path, bool]] = []
    if args.actor:
        promote = args.promote and not args.no_promote
        if not promote and args.actor in canonical_actors(rd):
            sys.exit(
                f"actor {args.actor!r} is currently in canonical.json; "
                "pass --promote to update the canonical judgment"
            )
        actor_dir = rd / "judges" / args.actor
        actor_dir.mkdir(parents=True, exist_ok=True)
        destinations.append((actor_dir / "judge.jsonl", False))
    else:
        promote = not args.no_promote
    if promote:
        destinations.append((rd / "judge.jsonl", True))
    if not destinations:
        sys.exit("no output destination selected; omit --no-promote or pass --actor")

    for jpath, canonical in destinations:
        with open(jpath, "w", encoding="utf-8") as fh:
            for row in out:
                fh.write(json.dumps(row) + "\n")
        print(f"wrote {len(out)} judge rows -> {jpath}")
        if canonical:
            (rd / "judges").mkdir(parents=True, exist_ok=True)
            (rd / "judges" / "canonical.json").write_text(
                json.dumps(
                    {
                        "schema_version": "judge_canonical.v1",
                        "built_from": [args.actor] if args.actor else [],
                        "aggregation": "single-pass" if args.actor else "not-recorded",
                        "written_at": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        if args.actor and not canonical:
            raw_rubric_ref = raw_rubric_input or str(
                card.get("rubric") or "clinical-answer-scoring/rubric.md"
            )
            rubric_ref = _portable_rubric_ref(raw_rubric_ref, rd)
            rubric_sha256 = _resolve_rubric_digest(
                raw_rubric_ref,
                rd,
                str(card["rubric_sha256"]) if card.get("rubric_sha256") else None,
            )
            manifest = {
                **card,
                **self_preference({**card, "model": args.model}, rd),
                "schema_version": CARD_SCHEMA,
                "actor_id": args.actor,
                "actor_type": args.actor_type,
                "model": args.model,
                "method": args.method,
                "run_id": rd.name,
                "source_cells": "judge-cells.jsonl",
                "source_rows": _portable_path(args.rows, rd),
                "output": "judge.jsonl",
                "promoted_to_canonical": promote,
                "blinded": bool(blind_requested),
                "n_rows": len(out),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rubric": rubric_ref,
                "rubric_sha256": rubric_sha256,
                "source_cells_sha256": hashlib.sha256(
                    (rd / "judge-cells.jsonl").read_bytes()
                ).hexdigest(),
                "source_rows_sha256": hashlib.sha256(
                    pathlib.Path(args.rows).read_bytes()
                ).hexdigest(),
                "output_sha256": hashlib.sha256(jpath.read_bytes()).hexdigest(),
            }
            (jpath.parent / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    _invalidate_stale_agreement(rd, args.actor, promote)
    if skipped:
        print(f"  SKIPPED {len(skipped)} (judge error/missing): {', '.join(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
