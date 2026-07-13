"""Canonical source/evidence layer for chart-answer envelopes.

This module derives a stable ``sources.v1`` object from the response envelope we
already have: resolved top-level references, inline answer citations, and nested
table refs. It is intentionally deterministic and display-oriented. Final hub
grounding states are preserved for transparency, while whole-answer semantic
support remains a separate judge/Scout-rubric concern.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SNAPSHOT_LINE_RE = re.compile(r"^\[(\d+)\]\s*(.+)$", re.MULTILINE)
_DATE_PREFIX_RE = re.compile(r"^\((\d{4}-\d{2}-\d{2})\)\s*(.+)$")
_BRACKET_TOKEN_RE = re.compile(r"\[([^\]\n]{1,40})\]")
_BROKEN_OPEN_RE = re.compile(r"\[[^\]\n]{0,40}(?:>|$)")
_GROUNDING_STATUSES = {"checking", "verified", "unsupported", "unchecked", "mixed"}


def _int_ref(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        n = int(value)
        return n if n > 0 else None
    return None


def _ordered_unique(values: list[Any]) -> list[Any]:
    seen: dict[Any, None] = {}
    for value in values:
        if value not in seen:
            seen[value] = None
    return list(seen)


def _compact(values: list[str], *, limit: int = 8) -> list[str]:
    out = []
    for value in values:
        s = " ".join(str(value).split())
        if s and s not in out:
            out.append(s[:240])
        if len(out) >= limit:
            break
    return out


def _normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return s[:10]
        return s
    return None


def parse_snapshot_records(chart_snapshot: str | None) -> dict[int, dict[str, Any]]:
    """Return chart-snapshot records keyed by displayed ``[N]`` index."""
    records: dict[int, dict[str, Any]] = {}
    if not isinstance(chart_snapshot, str):
        return records
    for m in _SNAPSHOT_LINE_RE.finditer(chart_snapshot):
        idx = int(m.group(1))
        text = " ".join(m.group(2).split())
        date = None
        title = text
        dm = _DATE_PREFIX_RE.match(text)
        if dm:
            date = dm.group(1)
            title = dm.group(2)
        records[idx] = {
            "record_index": idx,
            "source_text": text,
            "date": date,
            "title": title,
        }
    return records


def _chart_mappings(chart_fixture: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for item in ((chart_fixture or {}).get("mappings") or []):
        if not isinstance(item, dict):
            continue
        idx = _int_ref(item.get("index"))
        if idx is not None:
            out[idx] = item
    return out


def _chart_mappings_by_uuid(chart_fixture: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in ((chart_fixture or {}).get("mappings") or []):
        if not isinstance(item, dict):
            continue
        uuid = item.get("resourceUuid") or item.get("uuid")
        if isinstance(uuid, str) and uuid:
            out.setdefault(uuid, item)
    return out


def _reference_objects(response: dict[str, Any]) -> tuple[list[int], dict[int, dict[str, Any]]]:
    refs: list[int] = []
    by_index: dict[int, dict[str, Any]] = {}
    for item in response.get("references") or []:
        if not isinstance(item, dict):
            continue
        idx = _int_ref(item.get("index"))
        if idx is None:
            continue
        refs.append(idx)
        by_index.setdefault(idx, item)
    for item in response.get("citations") or []:
        idx = _int_ref(item)
        if idx is not None:
            refs.append(idx)
            by_index.setdefault(idx, {"index": idx})
    return _ordered_unique(refs), by_index


def _support_status(reference: dict[str, Any]) -> str:
    """Return the final hub grounding state without inventing a verdict."""
    status = reference.get("groundingStatus")
    if isinstance(status, str):
        status = status.strip().lower()
        if status in _GROUNDING_STATUSES:
            return status
    if reference.get("grounded") is True:
        return "verified"
    if reference.get("grounded") is False:
        return "unsupported"
    return "unchecked"


def _answer_usages(answer: Any) -> tuple[list[int], list[dict[str, Any]], list[str]]:
    if not isinstance(answer, str):
        return [], [], []
    refs: list[int] = []
    usages: list[dict[str, Any]] = []
    malformed: list[str] = []
    for m in _BRACKET_TOKEN_RE.finditer(answer):
        raw = "[" + m.group(1) + "]"
        idx = _int_ref(m.group(1))
        if idx is None:
            malformed.append(raw)
            continue
        refs.append(idx)
        start, end = max(0, m.start() - 90), min(len(answer), m.end() + 90)
        excerpt = " ".join(answer[start:end].split())
        usages.append({"ref": idx, "usage": {"kind": "answer_claim", "text": excerpt[:220]}})
    for m in _BROKEN_OPEN_RE.finditer(answer):
        raw = m.group(0).strip()
        if ">" in raw:
            raw = raw[: raw.index(">") + 1]
        if raw and not re.fullmatch(r"\[\d+\]", raw):
            malformed.append(raw[:48])
    return refs, usages, _ordered_unique(malformed)


def _table_usages(blocks: Any) -> tuple[list[int], list[dict[str, Any]], list[dict[str, Any]]]:
    refs: list[int] = []
    usages: list[dict[str, Any]] = []
    rows_without_refs: list[dict[str, Any]] = []
    if not isinstance(blocks, list):
        return refs, usages, rows_without_refs
    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("kind") != "table":
            continue
        title = str(block.get("title") or "Table").strip() or "Table"
        cols = block.get("columns") or []
        labels = {
            c.get("key"): (c.get("label") or c.get("key"))
            for c in cols
            if isinstance(c, dict) and c.get("key")
        }
        keys = [c.get("key") for c in cols if isinstance(c, dict) and c.get("key")]
        for row_index, row in enumerate(block.get("rows") or []):
            cells = (row or {}).get("cells") or {}
            row_refs: list[int] = []
            row_facts: list[str] = []
            facts_by_ref: dict[int, list[str]] = defaultdict(list)
            for key in (keys or list(cells.keys())):
                cell = cells.get(key) or {}
                if not isinstance(cell, dict):
                    continue
                text = str(cell.get("text", "")).strip()
                if not text:
                    continue
                fact = f"{labels.get(key, key)}: {text}"
                row_facts.append(fact)
                cell_refs = [_int_ref(v) for v in (cell.get("refs") or [])]
                cell_refs = [v for v in cell_refs if v is not None]
                refs.extend(cell_refs)
                row_refs.extend(cell_refs)
                for ref in cell_refs:
                    facts_by_ref[ref].append(fact)
            unique_row_refs = _ordered_unique(row_refs)
            if row_facts and not unique_row_refs:
                rows_without_refs.append({
                    "block": title,
                    "block_index": block_index,
                    "row": row_index + 1,
                    "facts": _compact(row_facts, limit=6),
                })
            for ref in unique_row_refs:
                facts = _compact(facts_by_ref.get(ref) or row_facts, limit=6)
                usages.append({
                    "ref": ref,
                    "usage": {
                        "kind": "table_row",
                        "block": title,
                        "row": row_index + 1,
                        "facts": facts,
                    },
                })
    return refs, usages, rows_without_refs


def build_sources(response: dict[str, Any] | None, chart_fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    """Derive canonical ``sources.v1`` from a chart-answer response.

    The returned object is safe for old runs: missing chart fixtures or mappings
    simply produce ``unknown`` resolution metadata instead of raising.
    """
    response = response if isinstance(response, dict) else {}
    snapshot = parse_snapshot_records((chart_fixture or {}).get("chart_snapshot"))
    mappings = _chart_mappings(chart_fixture)
    mappings_by_uuid = _chart_mappings_by_uuid(chart_fixture)
    valid_uuids = set((chart_fixture or {}).get("valid_uuids") or [])

    top_refs, ref_objects = _reference_objects(response)
    answer_refs, answer_usages, malformed = _answer_usages(response.get("answer"))
    nested_refs, table_usages, rows_without_refs = _table_usages(response.get("blocks"))

    usage_by_ref: dict[int, list[dict[str, Any]]] = defaultdict(list)
    facts_by_ref: dict[int, list[str]] = defaultdict(list)
    for item in answer_usages + table_usages:
        ref = item["ref"]
        usage = item["usage"]
        usage_by_ref[ref].append(usage)
        facts_by_ref[ref].extend(usage.get("facts") or [])

    order = _ordered_unique(top_refs + answer_refs + nested_refs)
    sources = []
    for pos, idx in enumerate(order, start=1):
        ref_obj = ref_objects.get(idx) or {}
        mapping_by_index = mappings.get(idx) or {}
        snap = snapshot.get(idx) or {}
        uuid = (
            ref_obj.get("resourceUuid")
            or ref_obj.get("uuid")
            or mapping_by_index.get("resourceUuid")
            or mapping_by_index.get("uuid")
        )
        mapping_by_uuid = mappings_by_uuid.get(uuid) if isinstance(uuid, str) else None
        mapping = mapping_by_uuid or mapping_by_index
        chart_index = _int_ref(mapping.get("index")) or idx
        snap = snapshot.get(chart_index) or snap
        rtype = ref_obj.get("resourceType") or mapping.get("resourceType")
        date = _normalize_date(ref_obj.get("date")) or _normalize_date(mapping.get("date")) or snap.get("date")
        if valid_uuids:
            resolution_status = "resolved" if uuid in valid_uuids else "unresolved"
        elif uuid:
            resolution_status = "unknown"
        else:
            resolution_status = "unknown"
        title = snap.get("title") or (f"{rtype} record" if rtype else f"Record {idx}")
        sources.append({
            "source_id": f"S{pos}",
            "citation_index": idx,
            "record_index": idx,
            "chart_record_index": chart_index,
            "resource_type": rtype,
            "resource_uuid": uuid,
            "date": date,
            "title": title,
            "source_text": snap.get("source_text") or "",
            "facts_used": _compact(facts_by_ref.get(idx, []), limit=8),
            "used_by": usage_by_ref.get(idx, []),
            "resolution_status": resolution_status,
            "support_status": _support_status(ref_obj),
        })

    top_set = set(top_refs)
    nested_set = set(nested_refs)
    usage_set = set(answer_refs) | nested_set
    nested_counts = Counter(nested_refs)
    diagnostics = {
        "top_level_refs": top_refs,
        "answer_inline_refs": _ordered_unique(answer_refs),
        "nested_refs": nested_refs,
        "unique_nested_refs": _ordered_unique(nested_refs),
        "top_only_refs": sorted(top_set - nested_set),
        "nested_only_refs": sorted(nested_set - top_set),
        "unused_top_refs": sorted(top_set - usage_set),
        "duplicated_nested_refs": sorted([k for k, v in nested_counts.items() if v > 1]),
        "unresolved_refs": [s["record_index"] for s in sources if s.get("resolution_status") == "unresolved"],
        "rows_without_refs": rows_without_refs,
        "malformed_tokens": malformed,
    }
    return {"schema_version": "sources.v1", "sources": sources, "diagnostics": diagnostics}


def source_ref_labels(sources_v1: dict[str, Any] | None) -> dict[int, str]:
    labels: dict[int, str] = {}
    for source in ((sources_v1 or {}).get("sources") or []):
        idx = _int_ref(source.get("record_index"))
        sid = source.get("source_id")
        if idx is not None and isinstance(sid, str):
            labels[idx] = sid
    return labels


def audit_sources(response: dict[str, Any] | None, sources_v1: dict[str, Any] | None) -> dict[str, Any]:
    """Return deterministic citation/source diagnostics.

    ``build_sources`` stores these diagnostics in the returned object. This
    helper is the stable public API for callers that only need the audit layer,
    and it can also reconstruct the diagnostics from a response if an older or
    externally supplied sources object lacks them.
    """
    diagnostics = (sources_v1 or {}).get("diagnostics")
    if isinstance(diagnostics, dict):
        return dict(diagnostics)

    response = response if isinstance(response, dict) else {}
    top_refs, _ = _reference_objects(response)
    answer_refs, _, malformed = _answer_usages(response.get("answer"))
    nested_refs, _, rows_without_refs = _table_usages(response.get("blocks"))
    top_set = set(top_refs)
    nested_set = set(nested_refs)
    usage_set = set(answer_refs) | nested_set
    nested_counts = Counter(nested_refs)

    source_indices = []
    for source in ((sources_v1 or {}).get("sources") or []):
        if not isinstance(source, dict):
            continue
        idx = _int_ref(source.get("record_index"))
        if idx is not None:
            source_indices.append(idx)

    return {
        "top_level_refs": top_refs,
        "answer_inline_refs": _ordered_unique(answer_refs),
        "nested_refs": nested_refs,
        "unique_nested_refs": _ordered_unique(nested_refs),
        "top_only_refs": sorted(top_set - nested_set),
        "nested_only_refs": sorted(nested_set - top_set),
        "unused_top_refs": sorted(top_set - usage_set),
        "duplicated_nested_refs": sorted([k for k, v in nested_counts.items() if v > 1]),
        "unresolved_refs": sorted(set(top_refs + nested_refs + answer_refs) - set(source_indices)),
        "rows_without_refs": rows_without_refs,
        "malformed_tokens": malformed,
    }


def render_sources_for_judge(sources_v1: dict[str, Any] | None) -> str:
    sources = (sources_v1 or {}).get("sources") or []
    diagnostics = (sources_v1 or {}).get("diagnostics") or {}
    if not sources and not diagnostics:
        return ""
    lines = ["[Evidence Used]"]
    for s in sources:
        meta = " ".join(
            str(x) for x in [s.get("resource_type"), s.get("date")] if x
        )
        facts = "; ".join(s.get("facts_used") or [])
        if not facts:
            facts = s.get("source_text") or s.get("title") or ""
        citation_index = s.get("citation_index") or s.get("record_index")
        chart_index = s.get("chart_record_index") or s.get("record_index")
        lines.append(
            f"- {s.get('source_id')} = cite [{citation_index}] chart [{chart_index}] {meta}: "
            f"{s.get('title') or ''}. Facts used: {facts or '(not localized)'}; "
            f"chart resolution: {s.get('resolution_status', 'unknown')}; "
            f"hub grounding: {s.get('support_status', 'unchecked')}."
        )
    flags = []
    for key in ("unresolved_refs", "unused_top_refs", "nested_only_refs", "malformed_tokens"):
        val = diagnostics.get(key)
        if val:
            flags.append(f"{key}={val}")
    if flags:
        lines.append("Diagnostics: " + "; ".join(flags))
    return "\n".join(lines)


def load_chart_fixtures(chart_dir: Path) -> dict[str, dict[str, Any]]:
    charts: dict[str, dict[str, Any]] = {}
    if not chart_dir.exists():
        return charts
    for path in chart_dir.glob("*.json"):
        try:
            chart = json_load(path)
        except Exception:
            continue
        uuid = (chart.get("patient") or {}).get("uuid")
        if uuid:
            charts[uuid] = chart
    return charts


def load_scenario_chart(scenario_id: str, scenarios_dir: Path, chart_dir: Path) -> dict[str, Any] | None:
    try:
        scenario = json_load(scenarios_dir / f"{scenario_id}.json")
    except Exception:
        return None
    patient_ref = scenario.get("patient_ref")
    if not patient_ref:
        return None
    return load_chart_fixtures(chart_dir).get(patient_ref)


def json_load(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
