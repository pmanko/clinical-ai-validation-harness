"""Shared arm-makeup resolver for the report / dashboard / index surfaces.

ONE place that turns a `backend_id` into a structured "arm card": its execution path
(direct router or a med-agent-hub profile) and model makeup (one writer or a team
role lineup), so the three
render surfaces stop string-parsing the label and agree on what each arm is.

Derivation (not stored): direct router calls are single-model; hub profile topology and
roles come from med-agent-hub levels.yaml;
per-model family/params/quant/note come from datasets/validation/model_registry.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

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

# Legacy direct-chartsearchai arms used this default prompt before the hub-relay
# architecture moved prompt/profile ownership into med-agent-hub. Keep the text
# here only so old report metadata can render consistently.
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

# Historical direct arms retain their captured ChartSearchAI retrieval metadata.
_LEGACY_CHARTSEARCHAI_RETRIEVAL = {
    "embedding_topk": 10,
    "querystore_topk": 30,
    "threshold": 0.47,
    "pipeline": "embedding",
}

_HUB_CONTEXT = {
    "owner": "med-agent-hub",
    "pipeline": "complete evidence ledger",
    "selection": "full context when it fits; deterministic exact-token selection when oversized",
    "temporal_checks": "computed from the complete ledger",
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
    return {"knobs": knobs, "prompts": prompts, "retrieval": _HUB_CONTEXT}


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
        "retrieval": _LEGACY_CHARTSEARCHAI_RETRIEVAL,
    }


def _load_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _runtime_config(arm: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    raw = arm.get("llamaRouterModelsMax")
    if raw is None:
        raw = arm.get("routerModelsMax")
    if raw is not None:
        try:
            out["llama_router_models_max"] = int(raw)
        except (TypeError, ValueError):
            out["llama_router_models_max"] = raw
    return out


def _load_profile_specs(p: Path) -> dict[str, dict[str, Any]]:
    """Parse the hub's profile document with the repository's YAML dependency."""
    try:
        document = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    raw = document.get("profiles") or document.get("levels") or {}
    return raw if isinstance(raw, dict) else {}


def _flatten_profile(spec: dict[str, Any]) -> dict[str, Any]:
    """Expose current profile fields through stable report display-role names."""
    if not isinstance(spec.get("models"), dict):
        # Old report fixtures remain readable, but current runtime config uses profiles.
        return dict(spec)
    models = spec.get("models") or {}
    prompts = spec.get("prompts") or {}
    return {
        "label": spec.get("label"),
        "topology": spec.get("topology"),
        "stages": spec.get("stages") or [],
        "orchestrator": models.get("orchestrator"),
        "expert": models.get("expert"),
        "synthesizer": models.get("answer") or models.get("indepth"),
        "validator": models.get("review"),
        "grounding": models.get("grounding"),
        "indepth": models.get("indepth"),
        "orchestrator_prompt": prompts.get("orchestrator"),
        "expert_prompt": prompts.get("expert"),
        "synthesis_prompt": prompts.get("answer"),
        "validation_prompt": prompts.get("review"),
    }


def _load_levels(p: Path) -> dict[str, dict]:
    out = {}
    for profile_id, spec in _load_profile_specs(p).items():
        level = _flatten_profile(spec or {})
        out[profile_id] = {
            role: level[role]
            for role in _ROLES
            if level.get(role)
        }
    return out


def _load_levels_raw(p: Path) -> dict[str, dict[str, Any]]:
    return {
        profile_id: _flatten_profile(spec or {})
        for profile_id, spec in _load_profile_specs(p).items()
    }


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


def _short_params(params: str | None) -> str:
    p = (params or "").strip()
    if not p:
        return ""
    # Keep the distinctive size and drop long parenthetical details in tight titles:
    # "35B (3B active, MoE)" -> "35B".
    return p.split("(", 1)[0].strip()


def _role_model_label(card: dict[str, Any] | None) -> str:
    card = card or {}
    return " ".join(
        x for x in (_short_family(card.get("family")), _short_params(card.get("params"))) if x
    )


def _team_title(roles: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """Human-readable team title from the role->model_card lineup.

    Include model size by role so two Gemma-led teams do not collapse into
    indistinguishable "Gemma coord · Gemma writer" labels.
    """
    orch = _role_model_label(roles.get("orchestrator"))
    expert = _role_model_label(roles.get("expert"))
    synth = _role_model_label(roles.get("synthesizer"))
    validator = _role_model_label(roles.get("validator"))
    parts = []
    if orch:
        parts.append(f"{orch} coord")
    if expert:
        parts.append(f"{expert} expert")
    if synth:
        parts.append(f"{synth} writer")
    if validator:
        parts.append(f"{validator} val")
    short = " · ".join(parts) if parts else "team"
    return short, short


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


def _prompt_lever(synthesis_prompt: Any) -> str:
    """A human-readable lever tag from a non-default solo synthesis prompt.

    This keeps experiment titles distinct without leaking prompt-file stems into
    dashboard headlines. For example, ``synthesis-date-output-contract`` becomes
    ``date contract``; the default ``synthesis-chartsearchai`` stays invisible.
    """
    tag = str(synthesis_prompt or "").strip().split("/")[-1]
    for pre in ("synthesis-", "synthesis_"):
        if tag.startswith(pre):
            tag = tag[len(pre):]
            break
    if tag in ("", "answer", "chartsearchai", "default"):
        return ""
    readable = {
        "date-output-contract": "date contract",
        "cite-or-abstain": "cite/abstain",
    }.get(tag, tag.replace("_", "-").replace("-", " "))
    return readable


def _split_dynamic_prompt_model(model_name: str) -> dict[str, str] | None:
    """Parse hub dynamic prompt ids used for quick prompt iteration.

    Supported forms mirror med-agent-hub's levels_loader:
      answer:<writer>
      answer:<writer>@<prompt>
      answer:<writer>@<prompt>~<temporal_gate>
      answer:<writer>@<prompt>~<temporal_gate>~temp0
      answer:<writer>@<prompt>~<temporal_gate>~temp0.5
      indepth-only:<writer>
      indepth-only:<writer>@<prompt>
    """
    prefix = ""
    for candidate in ("answer:", "indepth-only:"):
        if model_name.startswith(candidate):
            prefix = candidate
            break
    if not prefix:
        return None
    rest = model_name[len(prefix):]
    writer_prompt, *options = rest.split("~")
    writer, at, prompt = writer_prompt.partition("@")
    if not writer:
        return None
    gate = ""
    temp_floor = ""
    for opt in options:
        if opt in {"off", "warn", "enforce"} and not gate:
            gate = opt
        elif opt.startswith("temp") and opt[4:] and not temp_floor:
            temp_floor = opt[4:]
        else:
            return None
    default_prompt = "synthesis-indepth" if prefix == "indepth-only:" else "synthesis-chartsearchai"
    return {
        "mode": prefix[:-1],
        "writer": writer,
        "prompt": prompt if at and prompt else default_prompt,
        "gate": gate,
        "temp_floor": temp_floor,
    }


def _prompt_file_entry(label: str, prompt_stem: str) -> dict[str, str] | None:
    source = f"prompts/{prompt_stem}.txt"
    try:
        text = (_PROMPTS / f"{prompt_stem}.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return {
            "label": label,
            "source": source,
            "text": "",
            "summary": "Prompt file is selected by the med-agent-hub companion PR.",
        }
    summary = " ".join(text.split())
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "…"
    return {"label": label, "source": source, "text": text, "summary": summary}


def _hub_single_config(
    model_id: str,
    prompt_stem: str | None,
    ini: dict[str, dict[str, str]],
    temp_floor: str | None = None,
) -> dict[str, Any]:
    entry = _prompt_file_entry("Synthesis prompt", prompt_stem or "synthesis-chartsearchai")
    knobs = _resolve_knobs(model_id, ini)
    if temp_floor:
        knobs = dict(knobs)
        knobs["synth_temp_floor"] = temp_floor
    return {
        "knobs": {model_id: knobs},
        "prompts": [entry] if entry else [],
        "retrieval": _HUB_CONTEXT,
    }


def arm_model_name(backend_id: str, *, backends_path: Path | str = _BACKENDS) -> str:
    """The hub modelName an arm routes to (backends.json ``modelName``) — which is exactly what the hub
    stamps as the trace ``level_id``. Falls back to the backend_id (legacy arms where the two coincide).
    Lets the report/dashboard correlate a cell to its reasoning trace even when backend_id != modelName
    (e.g. backend ``m-12b-team`` -> level_id ``med-agent-team-12b-qwenval``)."""
    backends = _load_json(backends_path)
    arm = (backends.get(backend_id) or {}) if isinstance(backends, dict) else {}
    return (arm.get("modelName") or backend_id) if isinstance(arm, dict) else backend_id


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
    ('med-agent-hub single'|'med-agent-hub team'), models [model cards], roles
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
    runtime = _runtime_config(arm)

    def _with_runtime(card: dict[str, Any]) -> dict[str, Any]:
        if runtime:
            card = dict(card)
            card["runtime"] = runtime
        return card

    dyn = _split_dynamic_prompt_model(model_name)
    if dyn:
        single_card = _model_card(dyn["writer"], registry)
        title, short_title = _single_title(single_card)
        lever = _prompt_lever(dyn["prompt"])
        suffix = []
        if lever:
            suffix.append(lever)
        if dyn.get("gate"):
            suffix.append(f"gate {dyn['gate']}")
        if dyn.get("temp_floor"):
            suffix.append(f"temp {dyn['temp_floor']}")
        if suffix:
            joined = ", ".join(suffix)
            title, short_title = f"{title} ({joined})", f"{short_title} ({joined})"
        return _with_runtime({
            "backend_id": backend_id, "label": label, "title": title, "short_title": short_title,
            "kind": "single", "path": "med-agent-hub single",
            "models": [single_card],
            "config": _hub_single_config(dyn["writer"], dyn["prompt"], ini, dyn.get("temp_floor")),
        })

    # Solo single-model legs through the hub (answer:<m> / indepth-only:<m> / single:<m>) — ONE model,
    # no orchestrator/team — render as a SINGLE arm with the writer's family·size·quant, not "team".
    _solo_w = next((model_name.split(":", 1)[1]
                    for p in ("answer:", "indepth-only:", "single:", "single-indepth:")
                    if model_name.startswith(p)), None)
    if _solo_w:
        single_card = _model_card(_solo_w, registry)
        title, short_title = _single_title(single_card)
        return _with_runtime({
            "backend_id": backend_id, "label": label, "title": title, "short_title": short_title,
            "kind": "single", "path": "med-agent-hub single",
            "models": [single_card], "config": _single_config(_solo_w, ini),
        })

    configured_roles = _load_levels(levels_path)
    configured_profiles = _load_levels_raw(levels_path)
    if model_name in configured_profiles or ":8080" in endpoint:
        roles_map = configured_roles.get(model_name, {})
        level = configured_profiles.get(model_name, {})
        topology = str(level.get("topology") or "").strip().lower()
        if topology in {"single", "leg"}:
            _w = level.get("synthesizer") or model_name
            _scard = _model_card(_w, registry)
            _t, _st = _single_title(_scard)
            _lever = _prompt_lever(level.get("synthesis_prompt"))
            if _lever:  # a prompt-lever solo (e.g. cite-or-abstain) must not collide with plain solo
                _t, _st = f"{_t} ({_lever})", f"{_st} ({_lever})"
            _stages = list(level.get("stages") or [])
            if "review" in _stages and "ground_verdicts" in _stages:
                _t, _st = f"{_t} · fully checked", f"{_st} · fully checked"
            return _with_runtime({"backend_id": backend_id, "label": label, "title": _t, "short_title": _st,
                                  "kind": "single", "path": "med-agent-hub single",
                                  "models": [_scard], "stages": _stages,
                                  "config": _hub_single_config(_w, level.get("synthesis_prompt"), ini)})
        if not level:
            return _with_runtime({
                "backend_id": backend_id,
                "label": label,
                "title": label,
                "short_title": label,
                "kind": "unknown",
                "path": "med-agent-hub unknown profile",
                "models": [],
                "config": {},
            })
        roles = {r: _model_card(roles_map[r], registry) for r in _ROLES if r in roles_map}
        title, short_title = _team_title(roles)
        if title == "team":
            title = short_title = str(level.get("label") or label or model_name)
        return _with_runtime({
            "backend_id": backend_id,
            "label": label,
            "title": title,
            "short_title": short_title,
            "kind": "team",
            "path": "med-agent-hub team",
            "roles": roles,
            "models": list(roles.values()),
            "n_models": len(roles),
            "stages": list(level.get("stages") or []),
            "config": _team_config(roles_map, level, ini),
        })

    single_card = _model_card(model_name, registry)
    title, short_title = _single_title(single_card)
    if ":8077" in endpoint or endpoint:
        return _with_runtime({
            "backend_id": backend_id,
            "label": label,
            "title": title,
            "short_title": short_title,
            "kind": "single",
            "path": "direct model endpoint",
            "models": [single_card],
            "config": _single_config(model_name, ini),
        })

    return _with_runtime({"backend_id": backend_id, "label": label, "title": title, "short_title": short_title,
                          "kind": "unknown", "path": None, "models": [single_card],
                          "config": _single_config(model_name, ini)})
