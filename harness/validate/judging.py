"""Judge cards: who scored a run, with what, and how many times.

A judge pass lives under ``<run>/judges/<actor>/``: its ``judge.jsonl`` rows and a
``manifest.json`` card. ``<run>/judges/canonical.json`` names the pass (or passes) the
canonical ``<run>/judge.jsonl`` was built from. Every page that shows a judged score reads
the cards through :func:`load_judge_cards` and names the judge with :func:`judge_card_line`,
so a reader can tell which model, at what effort, under which brief, produced a number.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CARD_SCHEMA = "judge_actor.v2"

# Fields a runner supplies about the session it ran; everything else the finalizer adds.
RUNNER_FIELDS = (
    "agent", "agent_version", "model", "reasoning_effort", "sampling",
    "brief_sha256", "brief_path", "pass_index", "passes", "started_at", "finished_at",
)


def actor_id(card: dict[str, Any]) -> str:
    """A directory name for a pass: ``<agent>-<model>-<effort>-p<n>``, lower case, dashed."""
    parts = [str(card.get(k) or "") for k in ("agent", "model", "reasoning_effort")]
    parts = [p for p in parts if p]
    parts.append(f"p{int(card.get('pass_index') or 1)}")
    raw = "-".join(parts).lower()
    return "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in raw).strip("-")


def load_judge_cards(run_dir: Path | str) -> list[dict[str, Any]]:
    """Every pass's card under ``judges/*/manifest.json``, each with its ``actor_id``,
    canonical passes first, then by actor id. A card that cannot be parsed is skipped."""
    run_dir = Path(run_dir)
    canonical = set(canonical_actors(run_dir))
    cards: list[dict[str, Any]] = []
    for path in sorted((run_dir / "judges").glob("*/manifest.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(card, dict):
            continue
        card = dict(card)
        card["actor_id"] = card.get("actor_id") or path.parent.name
        card["canonical"] = card["actor_id"] in canonical
        cards.append(card)
    cards.sort(key=lambda c: (not c["canonical"], c["actor_id"]))
    return cards


def canonical_record(run_dir: Path | str) -> dict[str, Any]:
    """``judges/canonical.json`` as written by finalize or aggregate; empty when absent."""
    path = Path(run_dir) / "judges" / "canonical.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def canonical_actors(run_dir: Path | str) -> list[str]:
    """The actor ids the canonical ``judge.jsonl`` was built from; empty when not recorded."""
    built = canonical_record(run_dir).get("built_from")
    return [str(a) for a in built] if isinstance(built, list) else []


def judge_card_line(card: dict[str, Any]) -> str:
    """One line naming a pass's judge: model, effort, agent and version, pass, brief.

    ``"gpt-6-astra, reasoning high, Codex CLI 0.160.1, pass 1 of 1, brief 8b3b7a1"``.
    A human pass names the reviewer role instead. Unknown fields are left out, never
    guessed; a card with no model reads ``"judge not recorded"``.
    """
    if card.get("actor_type") == "human":
        who = card.get("model") or card.get("reviewer") or "human reviewer"
        return f"human review by {who}"
    model = card.get("model")
    if not model:
        return "judge not recorded"
    bits = [str(model)]
    if card.get("reasoning_effort"):
        bits.append(f"reasoning {card['reasoning_effort']}")
    if card.get("agent"):
        agent = AGENT_NAMES.get(str(card["agent"]), str(card["agent"]))
        bits.append(f"{agent} {card['agent_version']}".strip() if card.get("agent_version") else agent)
    passes = card.get("passes")
    index = card.get("pass_index")
    if index and passes:
        bits.append(f"pass {index} of {passes}")
    elif index:
        bits.append(f"pass {index}")
    if card.get("brief_sha256"):
        bits.append(f"brief {str(card['brief_sha256'])[:7]}")
    return ", ".join(bits)


AGENT_NAMES = {"codex": "Codex CLI", "claude": "Claude Code CLI", "gemini": "Gemini CLI"}


def judge_summary(run_dir: Path | str) -> dict[str, Any]:
    """What a page shows about the judging: the cards, which are canonical, and one
    sentence. ``recorded`` is false when the run carries no card at all."""
    cards = load_judge_cards(run_dir)
    canonical = [c for c in cards if c["canonical"]] or cards[:1]
    aggregation = str(canonical_record(run_dir).get("aggregation") or "")
    lines = [judge_card_line(c) for c in canonical]
    others = [judge_card_line(c) for c in cards if c not in canonical]
    if not cards:
        sentence = "Judge not recorded for this run."
    elif aggregation == "median-majority" and len(canonical) > 1:
        sentence = (f"Judged in {len(canonical)} passes by " + "; ".join(lines)
                    + "; the headline is the median of each 0-10 axis and the majority of each label"
                    " across the passes, a harm tie counting as harmful.")
    else:
        sentence = "Judged by " + "; ".join(lines) + "."
    if cards and others:
        sentence += " Also scored by " + "; ".join(others) + "."
    return {"recorded": bool(cards), "cards": cards, "canonical": [c["actor_id"] for c in canonical],
            "aggregation": aggregation, "sentence": sentence, "consensus": consensus(run_dir)}


def consensus(run_dir: Path | str) -> dict[str, Any]:
    """``judges/consensus.json`` (alpha per axis, thresholds, widest cells); empty when absent."""
    path = Path(run_dir) / "judges" / "consensus.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
