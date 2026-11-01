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
    "brief_sha256", "brief_path", "rubric", "rubric_sha256", "pass_index", "passes",
    "started_at", "finished_at",
)

# Publishable identity fields projected into standalone reports and dashboards (never local paths).
PUBLISHABLE_CARD_FIELDS = (
    "schema_version", "actor_id", "actor_type", "reviewer", "agent", "agent_version",
    "model", "reasoning_effort", "sampling", "method", "brief_sha256",
    "rubric", "rubric_sha256", "pass_index", "passes", "started_at", "finished_at",
    "created_at", "promoted_to_canonical", "canonical", "blinded", "n_rows",
    "judge_family", "arm_families", "self_preference_risk", "self_preference_arms",
)


def _validate_pass_counts(card: dict[str, Any]) -> tuple[int, int | None]:
    raw_idx = card.get("pass_index")
    if raw_idx in (None, ""):
        idx = 1
    else:
        if isinstance(raw_idx, bool) or not isinstance(raw_idx, (int, str)):
            raise ValueError(f"pass_index must be a positive integer, got {raw_idx!r}")
        idx = int(raw_idx)
        if idx < 1:
            raise ValueError(f"pass_index must be >= 1, got {idx}")
    raw_passes = card.get("passes")
    if raw_passes in (None, ""):
        passes = None
    else:
        if isinstance(raw_passes, bool) or not isinstance(raw_passes, (int, str)):
            raise ValueError(f"passes must be a positive integer, got {raw_passes!r}")
        passes = int(raw_passes)
        if passes < 1:
            raise ValueError(f"passes must be >= 1, got {passes}")
        if idx > passes:
            raise ValueError(f"pass_index ({idx}) cannot exceed passes ({passes})")
    return idx, passes


def actor_id(card: dict[str, Any]) -> str:
    """A directory name for a pass: ``<agent>-<model>-<effort>-p<n>``, lower case, dashed."""
    idx, _passes = _validate_pass_counts(card)
    parts = [str(card.get(k) or "") for k in ("agent", "model", "reasoning_effort")]
    parts = [p for p in parts if p]
    parts.append(f"p{idx}")
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
        aid = card.get("actor_id") or path.parent.name
        projected = {k: card[k] for k in PUBLISHABLE_CARD_FIELDS if k in card}
        projected["actor_id"] = aid
        projected["canonical"] = aid in canonical
        cards.append(projected)
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
    return [str(a) for a in built if a] if isinstance(built, list) else []


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

# A model's family from its name: the arms' models are known by name, a judge by its card.
FAMILY_PREFIXES = (
    ("gemma", "google"), ("medgemma", "google"), ("gemini", "google"),
    ("gpt", "openai"), ("o1", "openai"), ("o3", "openai"), ("o4", "openai"), ("codex", "openai"),
    ("claude", "anthropic"), ("llama", "meta"), ("qwen", "alibaba"), ("mistral", "mistral"),
    ("deepseek", "deepseek"),
)


def model_family(name: Any) -> str | None:
    """The family a model name belongs to, or None when the name says nothing (a Hub profile)."""
    text = str(name or "").strip().lower()
    for prefix, family in FAMILY_PREFIXES:
        if text.startswith(prefix):
            return family
    return None


def arm_families(run_dir: Path | str) -> dict[str, list[str]]:
    """Each arm's model families, from the run's frozen run_meta.json (backends' modelName and
    arm cards' model ids and roles); arms whose model names say nothing are left out."""
    try:
        meta = json.loads((Path(run_dir) / "run_meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}

    def _add(arm: str, candidate: Any) -> None:
        family = model_family(candidate)
        if family:
            families = out.setdefault(arm, [])
            if family not in families:
                families.append(family)

    for arm, backend in (meta.get("backends") or {}).items():
        if isinstance(backend, dict):
            _add(arm, backend.get("modelName"))
            for key in ("answer_model", "review_model", "ground_model", "indepth_model", "orchestrator_model"):
                _add(arm, backend.get(key))
    for arm, card in (meta.get("arm_cards") or {}).items():
        if not isinstance(card, dict):
            continue
        for model in card.get("models") or []:
            if isinstance(model, dict):
                _add(arm, model.get("id"))
                _add(arm, model.get("family"))
        for role_model in (card.get("roles") or {}).values():
            if isinstance(role_model, dict):
                _add(arm, role_model.get("id"))
                _add(arm, role_model.get("family"))
            else:
                _add(arm, role_model)
        for key in ("answer_model", "review_model", "ground_model", "indepth_model", "orchestrator_model"):
            _add(arm, card.get(key))
    return out


def self_preference(card: dict[str, Any], run_dir: Path | str) -> dict[str, Any]:
    """Whether the judge on ``card`` is from the same family as an arm it judges: the
    fields a card records so a reader can weigh that risk."""
    judge_family = model_family(card.get("model"))
    arms = arm_families(run_dir)
    same = sorted(
        arm for arm, families in arms.items()
        if judge_family and (judge_family in families if isinstance(families, list) else families == judge_family)
    )
    return {"judge_family": judge_family, "arm_families": arms,
            "self_preference_risk": bool(same), "self_preference_arms": same}


def judge_summary(run_dir: Path | str) -> dict[str, Any]:
    """What a page shows about the judging: the cards, which are canonical, and one
    sentence. ``recorded`` is false when the canonical judge is not recorded."""
    cards = load_judge_cards(run_dir)
    canon_ids = canonical_actors(run_dir)
    card_by_id = {c["actor_id"]: c for c in cards}
    canonical = [card_by_id.get(a, {"actor_id": a, "canonical": True}) for a in canon_ids]
    aggregation = str(canonical_record(run_dir).get("aggregation") or "")
    lines = [judge_card_line(c) for c in canonical]
    known_lines = [line for line in lines if line != "judge not recorded"]
    others = [judge_card_line(c) for c in cards if not c["canonical"]]
    if not canonical or not known_lines:
        sentence = "Judge not recorded for this run."
    elif aggregation == "median-majority" and len(canonical) > 1:
        sentence = (f"Judged in {len(canonical)} passes by " + "; ".join(lines)
                    + "; the headline is the median of each 0-10 axis and the majority of each label"
                    " across the passes, a harm tie counting as harmful.")
    else:
        sentence = "Judged by " + "; ".join(lines) + "."
    if others:
        sentence += " Also scored by " + "; ".join(others) + "."
    return {"recorded": bool(known_lines), "cards": cards, "canonical": list(canon_ids),
            "aggregation": aggregation, "sentence": sentence, "consensus": consensus(run_dir)}


def consensus(run_dir: Path | str) -> dict[str, Any]:
    """``judges/consensus.json`` (alpha per axis, thresholds, widest cells); empty when absent or stale."""
    rec = canonical_record(run_dir)
    if rec and rec.get("aggregation") not in ("", "median-majority"):
        return {}
    path = Path(run_dir) / "judges" / "consensus.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if rec and isinstance(rec.get("built_from"), list):
        if sorted(str(a) for a in rec["built_from"] if a) != sorted(str(a) for a in (data.get("actors") or []) if a):
            return {}
    return data
