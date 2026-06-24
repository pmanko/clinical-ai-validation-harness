"""Shared arm-makeup resolver for the report / dashboard / index surfaces.

ONE place that turns a `backend_id` into a structured "arm card": its engine path
(SINGLE vanilla-chartsearchai vs the med-agent-hub TEAM), and its model makeup
(family·size·quant for a single arm; the role→model lineup for a team) — so the three
render surfaces stop string-parsing the label and agree on what each arm is.

Derivation (not stored): kind comes from the backends.json endpoint (`:8077` llama-router
= single, `:8080` med-agent-hub = team); team roles come from med-agent-hub levels.yaml;
per-model family/params/quant/note come from datasets/validation/model_registry.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKENDS = _ROOT / "datasets/validation/backends.json"
_REGISTRY = _ROOT / "datasets/validation/model_registry.json"
_LEVELS = _ROOT / "targets/med-agent-hub/server/levels.yaml"
_LLAMA_INI = _ROOT / "scripts/llama-router.ini"
_PROMPTS = _ROOT / "targets/med-agent-hub/server/prompts"

_ROLES = ("orchestrator", "expert", "synthesizer", "validator")

# The role -> prompt file the hub uses by default (no per-level override). Mirrors
# med-agent-hub's wiring: orchestrator drives tool calls, the expert reads the chart,
# the synthesizer writes the direct answer, the validator cross-checks it.
_ROLE_PROMPT_FILE = {
    "orchestrator": "orchestrator.txt",
    "expert": "medical_expert.txt",
    "synthesizer": "synthesis-answer.txt",
    "validator": "validation-answer.txt",
}
# A per-level YAML key (e.g. `synthesis_prompt: synthesis-chartsearchai`) overrides the
# default file for that role; the value is the prompt stem (".txt" appended).
_ROLE_OVERRIDE_KEY = {
    "orchestrator": "orchestrator_prompt",
    "expert": "expert_prompt",
    "synthesizer": "synthesis_prompt",
    "validator": "validation_prompt",
}

# Mirror of chartsearchai's LlmProvider.DEFAULT_SYSTEM_PROMPT
# (targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/LlmProvider.java:51).
# The GP `chartsearchai.llm.systemPrompt` is NULL, so this constant is what the single
# (vanilla chartsearchai) arm actually sends. Kept verbatim — if the Java constant changes,
# update this string. The trailing FORMAT-DEMONSTRATION few-shot is elided for the panel
# (the operative instructions are above it); the full demo lives in the Java source.
_CHARTSEARCHAI_DEFAULT_SYSTEM_PROMPT = (
    "You are a clinical assistant helping a clinician review a patient's chart. "
    "Answer ONLY the specific query. Use only the patient records below (sorted most recent first). "
    "When the query asks for the latest, current, or most recent value, the relevant record is the "
    "FIRST matching one in the list; report that value and do not present an older reading as the "
    "current one. Never infer, assume, or add information not explicitly stated in the records. "
    "Records beginning with \"Drug reference\" are clinical reference data, not this patient's data; "
    "cite them the same way, but never present reference dosing as a value already recorded for the "
    "patient. Include ALL relevant records in your answer — never omit any for brevity. Cite EVERY "
    "record you reference by its number in brackets (e.g. [1], [3]). Respond with ONLY a JSON object "
    "with a \"reasoning\" string, then an \"answer\" string and a \"citations\" array listing every "
    "record number you cited. In \"reasoning\", first work out what the query refers to and which "
    "records match it by clinical meaning — not just shared words — before you write the answer.\n"
    "Respond with ONLY a JSON object matching the schema: \"answer\" (string), \"citations\" (array "
    "of ints), \"blocks\" (array, may be empty).\n\n"
    "STRUCTURED TABLES: if the query asks to LIST, SHOW, ENUMERATE, or TABULATE multiple items "
    "(medications, allergies, labs, vitals, problems, diagnoses, encounters, orders, immunizations, "
    "procedures), emit a \"table\" block in \"blocks\" with columns + rows (one row per unique item); "
    "the \"answer\" string gives a brief one-sentence prose summary. Only leave \"blocks\" as [] for "
    "single-fact answers (age, gender, yes/no).\n\n"
    "Use plain text only in the answer — no markdown, no bullet markers, no headers. "
    "If no records are relevant, name what is missing. Your answer must not vary based on the "
    "punctuation or phrasing of the query — focus only on its semantic meaning.\n\n"
    "[A FORMAT-DEMONSTRATION few-shot with fake non-medical data follows in the live prompt.]"
)

# Retrieval is owned by the querystore module; chartsearchai exposes these as runtime GPs.
# Hardcoded to the current chartsearchai GP values (live capture is a later step).
_CHARTSEARCHAI_RETRIEVAL = {
    "embedding_topk": 10,
    "querystore_topk": 30,
    "threshold": 0.47,
    "pipeline": "embedding",
}

# Knob keys surfaced on the panel, in display order. The three dry-* keys collapse to one
# "dry" summary (see _summarize_knobs).
_KNOB_KEYS = ("temp", "top-p", "top-k", "ctx-size", "seed", "max-tokens", "reasoning-budget")
_DRY_KEYS = ("dry-multiplier", "dry-base", "dry-allowed-length")


def _parse_ini(p: Path) -> dict[str, dict[str, str]]:
    """Tiny INI reader for llama-router.ini: `[section]` headers, `key = value` lines, and
    `#`/`;` line comments (configparser can't be used — `;` mid-line and the `[*]` section
    name trip it). Inline comments are NOT stripped (a value like `99` has none, and the
    file keeps its remarks on their own lines). Returns {section: {key: value}}."""
    out: dict[str, dict[str, str]] = {}
    cur: str | None = None
    try:
        lines = Path(p).read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            out.setdefault(cur, {})
            continue
        if cur is None or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[cur][key.strip()] = val.strip()
    return out


def _resolve_knobs(model_id: str, ini: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Merge the shared `[*]` defaults with the model's own `[<model_id>]` overrides and
    summarize the surfaced sampler knobs (dry-* collapsed into one "dry" line)."""
    merged = dict(ini.get("*", {}))
    merged.update(ini.get(model_id, {}))
    if not merged:
        return {}
    knobs: dict[str, Any] = {}
    for k in _KNOB_KEYS:
        if k in merged:
            knobs[k.replace("-", "_")] = merged[k]
    dry_parts = [f"{k.replace('dry-', '')} {merged[k]}" for k in _DRY_KEYS if k in merged]
    if dry_parts:
        knobs["dry"] = " · ".join(dry_parts)
    return knobs


def _prompt_entry(role: str, level: dict, label: str) -> dict[str, str] | None:
    """Resolve one role -> {label, source, text, summary}. Honors a per-level prompt
    override (e.g. `synthesis_prompt: synthesis-chartsearchai`); falls back to the default
    file for the role. Missing file -> None (role had no prompt)."""
    stem = level.get(_ROLE_OVERRIDE_KEY.get(role, ""))
    fname = f"{str(stem).strip()}.txt" if stem else _ROLE_PROMPT_FILE.get(role)
    if not fname:
        return None
    try:
        text = (_PROMPTS / fname).read_text(encoding="utf-8").strip()
    except Exception:
        return None
    summary = " ".join(text.split())
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "…"
    return {"label": label, "source": f"prompts/{fname}", "text": text, "summary": summary}


def _team_config(
    roles_map: dict[str, str], level: dict, ini: dict[str, dict[str, str]]
) -> dict[str, Any]:
    knobs = {m: _resolve_knobs(m, ini) for m in roles_map.values()}
    role_labels = {
        "orchestrator": "Orchestrator (coordinator)",
        "expert": "Medical expert",
        "synthesizer": "Synthesizer (answer writer)",
        "validator": "Validator (cross-check)",
    }
    prompts = []
    for role in _ROLES:
        if role not in roles_map:
            continue
        entry = _prompt_entry(role, level, role_labels.get(role, role))
        if entry:
            prompts.append(entry)
    return {"knobs": knobs, "prompts": prompts, "retrieval": _CHARTSEARCHAI_RETRIEVAL}


def _single_config(model_id: str, ini: dict[str, dict[str, str]]) -> dict[str, Any]:
    summary = " ".join(_CHARTSEARCHAI_DEFAULT_SYSTEM_PROMPT.split())
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "…"
    return {
        "knobs": {model_id: _resolve_knobs(model_id, ini)},
        "prompts": [{
            "label": "System prompt (chartsearchai DEFAULT_SYSTEM_PROMPT)",
            "source": "LlmProvider.DEFAULT_SYSTEM_PROMPT",
            "text": _CHARTSEARCHAI_DEFAULT_SYSTEM_PROMPT,
            "summary": summary,
        }],
        "retrieval": _CHARTSEARCHAI_RETRIEVAL,
    }


def _load_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_levels(p: Path) -> dict[str, dict]:
    """Parse med-agent-hub levels.yaml -> {team_name: {role: model}}. A tiny indent-aware
    reader so the resolver doesn't hard-depend on PyYAML (the hub owns the real loader)."""
    out: dict[str, dict] = {}
    cur: str | None = None
    try:
        lines = Path(p).read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    in_levels = False
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_levels = line.strip() == "levels:"
            continue
        if not in_levels:
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 2 and stripped.endswith(":"):
            cur = stripped[:-1]
            out[cur] = {}
        elif indent >= 4 and cur and ":" in stripped:
            k, _, v = stripped.partition(":")
            v = v.strip()
            if k.strip() in _ROLES and v and v != "null":
                out[cur][k.strip()] = v
    return out


def _load_levels_raw(p: Path) -> dict[str, dict[str, str]]:
    """Like _load_levels but captures EVERY scalar key per level (incl. the per-level
    prompt overrides like `synthesis_prompt`/`orchestrator_prompt`), not just role->model —
    so the config resolver can honor a prompt override. Same tiny indent-aware reader."""
    out: dict[str, dict[str, str]] = {}
    cur: str | None = None
    try:
        lines = Path(p).read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    in_levels = False
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_levels = line.strip() == "levels:"
            continue
        if not in_levels:
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 2 and stripped.endswith(":"):
            cur = stripped[:-1]
            out[cur] = {}
        elif indent >= 4 and cur and ":" in stripped:
            k, _, v = stripped.partition(":")
            v = v.strip()
            if v and v != "null":
                out[cur][k.strip()] = v
    return out


def _model_card(model_id: str, registry: dict) -> dict[str, Any]:
    meta = (registry.get("models") or {}).get(model_id) or {}
    return {
        "id": model_id,
        "family": meta.get("family"),
        "params": meta.get("params"),
        "quant": meta.get("quant"),
        "note": meta.get("note"),
    }


# Each vendor family collapses to ONE short name for the human-readable arm title — so the
# title reads as roles/vendors ("Liquid coord · Qwen writer"), not dashed machine ids. Unmapped
# families fall back to the raw family (see _short_family). Substring-matched so the size/variant
# suffix doesn't have to be enumerated ("Liquid LFM2", "Liquid LFM2.5" -> "Liquid").
_FAMILY_SHORT = (
    ("Gemma 4", "Gemma"),
    ("MedGemma", "MedGemma"),
    ("Liquid LFM2", "Liquid"),
    ("Qwen", "Qwen"),
)


def _short_family(family: str | None) -> str:
    """Map a model's `family` to its SHORT title name (Gemma 4 -> Gemma, Liquid LFM2 -> Liquid,
    Qwen2.5/Qwen3/Qwen3.6 -> Qwen, MedGemma -> MedGemma); unmapped -> the raw family."""
    fam = (family or "").strip()
    for prefix, short in _FAMILY_SHORT:
        if fam.startswith(prefix):
            return short
    return fam


def _team_title(roles: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """Human-readable team title from the role->model_card lineup. Shape:
    "{orch} coord · {synth} writer" + " · validated" when a validator role exists. The expert is
    omitted (it's the constant medgemma). Returns (title, short_title) — short drops " · validated"
    for tight grid headers."""
    orch = _short_family((roles.get("orchestrator") or {}).get("family"))
    synth = _short_family((roles.get("synthesizer") or {}).get("family"))
    parts = []
    if orch:
        parts.append(f"{orch} coord")
    if synth:
        parts.append(f"{synth} writer")
    short = " · ".join(parts) if parts else "team"
    title = short + (" · validated" if "validator" in roles else "")
    return title, short


def _single_title(card: dict[str, Any]) -> tuple[str, str]:
    """Human-readable single-arm title: "{family} {params} · {quant} · single"
    (e.g. "Gemma 4 12B · Q8 · single"). The quant token distinguishes same-size/family arms that
    differ only by quantization (Gemma 4 12B at Q8 vs Q4). Returns (title, short_title) — short is
    the family·params·quant essence without the " · single" tag."""
    fam = (card.get("family") or "").strip()
    params = (card.get("params") or "").strip()
    quant = (card.get("quant") or "").strip()
    q = quant.split("_")[0].strip()  # Q8_0 -> Q8, Q4_K_M -> Q4, "Q8_0 (QAT)" -> Q8
    essence = " ".join(p for p in (fam, params) if p) or (card.get("id") or "model")
    if q:
        essence = f"{essence} · {q}"
    return f"{essence} · single", essence


def arm_card(
    backend_id: str,
    *,
    backends_path: Path | str = _BACKENDS,
    registry_path: Path | str = _REGISTRY,
    levels_path: Path | str = _LEVELS,
    llama_ini_path: Path | str = _LLAMA_INI,
) -> dict[str, Any]:
    """Resolve one backend_id to a structured arm card.

    Returns: {backend_id, label, kind ('single'|'team'|'unknown'), path
    ('vanilla chartsearchai'|'med-agent-hub team'), models [model cards], roles
    {role: model_card} (team only), config {knobs, prompts, retrieval}}. The config
    carries the REAL sampler knobs (merged from scripts/llama-router.ini), the per-role
    system prompts (med-agent-hub prompt files / chartsearchai DEFAULT_SYSTEM_PROMPT), and
    the chartsearchai retrieval GPs. Never raises — unknown/missing -> best-effort card.
    """
    backends = _load_json(backends_path)
    registry = _load_json(registry_path)
    ini = _parse_ini(llama_ini_path)
    arm = (backends.get(backend_id) or {}) if isinstance(backends, dict) else {}
    endpoint = arm.get("endpointUrl") or ""
    model_name = arm.get("modelName") or backend_id
    label = arm.get("label") or backend_id

    # Solo single-model legs through the hub (answer:<m> / indepth-only:<m> / single:<m>) — ONE model,
    # no orchestrator/team — render as a SINGLE arm with the writer's family·size·quant, not "team".
    _solo_w = next((model_name.split(":", 1)[1]
                    for p in ("answer:", "indepth-only:", "single:", "single-indepth:")
                    if model_name.startswith(p)), None)
    if _solo_w:
        single_card = _model_card(_solo_w, registry)
        title, short_title = _single_title(single_card)
        return {
            "backend_id": backend_id, "label": label, "title": title, "short_title": short_title,
            "kind": "single", "path": "med-agent-hub single",
            "models": [single_card], "config": _single_config(_solo_w, ini),
        }

    if ":8080" in endpoint or model_name.startswith("med-agent-team"):
        roles_map = _load_levels(levels_path).get(model_name, {})
        level = _load_levels_raw(levels_path).get(model_name, {})
        roles = {r: _model_card(roles_map[r], registry) for r in _ROLES if r in roles_map}
        title, short_title = _team_title(roles)
        return {
            "backend_id": backend_id,
            "label": label,
            "title": title,
            "short_title": short_title,
            "kind": "team",
            "path": "med-agent-hub team",
            "roles": roles,
            "models": list(roles.values()),
            "n_models": len(roles),
            "config": _team_config(roles_map, level, ini),
        }

    single_card = _model_card(model_name, registry)
    title, short_title = _single_title(single_card)
    if ":8077" in endpoint or endpoint:
        return {
            "backend_id": backend_id,
            "label": label,
            "title": title,
            "short_title": short_title,
            "kind": "single",
            "path": "vanilla chartsearchai",
            "models": [single_card],
            "config": _single_config(model_name, ini),
        }

    return {"backend_id": backend_id, "label": label, "title": title, "short_title": short_title,
            "kind": "unknown", "path": None, "models": [single_card],
            "config": _single_config(model_name, ini)}
