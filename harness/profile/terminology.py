"""Terminology profiling — fills the ``reference_sources[]`` and
``locales[]`` slots of the profile inventory artifact.

Two pieces:

  - ``enumerate_reference_sources(cfg)`` reads ``concept_reference_source``
    rows plus per-source map counts from ``concept_reference_term`` →
    ``concept_reference_map``.
  - ``enumerate_locales(cfg)`` walks ``concept_name`` /
    ``concept_description`` / ``global_property`` (key
    ``locale.allowed.list``) to compute per-locale ``source_count`` and
    flag ``expected_by_refapp`` against the RefApp-default locale set.

Both functions return typed dataclasses and serialize via
``to_dict()`` into the inventory schema shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .db import DBConfig, query


# Locales the modern (O3) RefApp expects by default. Anything outside this
# set is flagged in the inventory so reviewers can confirm the source
# corpus's locale coverage.
DEFAULT_REFAPP_LOCALES: frozenset[str] = frozenset({
    "en", "en_GB", "es", "fr", "ht", "it", "nl", "pt", "pt_BR", "vi",
})


@dataclass(frozen=True)
class ReferenceSource:
    hl7_code: str
    name: str
    description: str | None
    retired: bool
    concept_reference_map_count: int

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "hl7_code": self.hl7_code,
            "name": self.name,
            "retired": self.retired,
            "concept_reference_map_count": self.concept_reference_map_count,
        }
        if self.description:
            d["description"] = self.description
        return d


@dataclass(frozen=True)
class LocaleUsage:
    locale: str
    source_count: int
    expected_by_refapp: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- reference_sources ----------


def enumerate_reference_sources(cfg: DBConfig) -> list[ReferenceSource]:
    """Walk ``concept_reference_source`` + count maps per source.

    Returns sorted by name (alphabetical) for deterministic output.
    Empty list when the schema has zero reference_source rows.
    """
    rows = query(cfg, """
        SELECT s.hl7_code, s.name, s.description, s.retired,
               COUNT(m.concept_map_id) AS map_count
        FROM concept_reference_source s
        LEFT JOIN concept_reference_term t
               ON t.concept_source_id = s.concept_source_id
        LEFT JOIN concept_reference_map m
               ON m.concept_reference_term_id = t.concept_reference_term_id
        GROUP BY s.concept_source_id, s.hl7_code, s.name, s.description, s.retired
        ORDER BY s.name
    """)
    out: list[ReferenceSource] = []
    for hl7_code, name, description, retired, map_count in rows:
        out.append(ReferenceSource(
            hl7_code=hl7_code or "",
            name=name or "",
            description=description or None,
            retired=(str(retired) in {"1", "True", "true"}),
            concept_reference_map_count=int(map_count or 0),
        ))
    return out


# ---------- locales ----------


def _parse_allowed_locale_list(value: str | None) -> set[str]:
    """Parse the global_property ``locale.allowed.list`` value, which is a
    comma-separated string like ``en, es, fr, it, pt``."""
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def enumerate_locales(cfg: DBConfig) -> list[LocaleUsage]:
    """Count per-locale references across concept_name, concept_description,
    and the global_property allowed-list. Sorted alphabetically for
    determinism.
    """
    name_rows = query(cfg, """
        SELECT locale, COUNT(*) FROM concept_name
        WHERE locale IS NOT NULL AND locale != ''
        GROUP BY locale
    """)
    desc_rows = query(cfg, """
        SELECT locale, COUNT(*) FROM concept_description
        WHERE locale IS NOT NULL AND locale != ''
        GROUP BY locale
    """)

    counts: dict[str, int] = {}
    for locale, n in name_rows:
        if locale:
            counts[locale] = counts.get(locale, 0) + int(n or 0)
    for locale, n in desc_rows:
        if locale:
            counts[locale] = counts.get(locale, 0) + int(n or 0)

    # global_property locale.allowed.list adds +1 per locale (presence).
    gp_rows = query(cfg, """
        SELECT property, property_value FROM global_property
        WHERE property = 'locale.allowed.list'
    """)
    declared_locales: set[str] = set()
    for _, value in gp_rows:
        declared_locales |= _parse_allowed_locale_list(value)
    for locale in declared_locales:
        counts[locale] = counts.get(locale, 0) + 1

    return [
        LocaleUsage(
            locale=locale,
            source_count=count,
            expected_by_refapp=(locale in DEFAULT_REFAPP_LOCALES),
        )
        for locale, count in sorted(counts.items())
    ]


# ---------- composition ----------


def emit(cfg: DBConfig) -> dict[str, list[dict[str, Any]]]:
    """Both arrays in one call, ready to splice into the profile inventory."""
    return {
        "reference_sources": [r.to_dict() for r in enumerate_reference_sources(cfg)],
        "locales": [l.to_dict() for l in enumerate_locales(cfg)],
    }


__all__ = [
    "DEFAULT_REFAPP_LOCALES",
    "ReferenceSource", "LocaleUsage",
    "enumerate_reference_sources", "enumerate_locales", "emit",
    "_parse_allowed_locale_list",
]
