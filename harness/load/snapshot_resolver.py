"""Resolve user-facing SQLMesh views to their underlying physical snapshot
tables.

SQLMesh's virtual layer stores user-facing schemas (e.g. ``refapp_28_demo``)
as views over versioned snapshot tables in a parallel schema (e.g.
``sqlmesh__refapp_28_demo``). For example:

  refapp_28_demo.clin__obs (VIEW)
      └── refapp_28_demo__clin__obs__3649557428 (TABLE, in sqlmesh__refapp_28_demo)

For the dlt load step, we read directly from the physical snapshot tables.
This module bridges the indirection: given a user-facing view name, return
the underlying snapshot table name.

Why query view definitions rather than infer:
- SQLMesh's snapshot fingerprint changes on every model edit, so the
  snapshot table name is not stable.
- The view definition is the authoritative pointer at run time. Reading it
  is cheap (one SELECT per view).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from harness.profile.db import DBConfig, query


@dataclass(frozen=True)
class ResolvedSnapshot:
    view_name: str               # e.g. "clin__obs"
    physical_table: str          # e.g. "refapp_28_demo__clin__obs__3649557428"
    physical_schema: str         # e.g. "sqlmesh__refapp_28_demo"


# Pattern matches `sqlmesh__refapp_28_demo`.`refapp_28_demo__clin__obs__<digits>`
# inside a CREATE VIEW definition. The backtick quoting is what MariaDB emits;
# unquoted forms are also possible from other emitters, so accept both.
_SNAPSHOT_REF_RE = re.compile(
    r"`?(?P<schema>sqlmesh__[A-Za-z0-9_]+)`?\s*\.\s*`?(?P<table>[A-Za-z0-9_]+)`?"
)


def _parse_view_definition(view_definition: str) -> Optional[tuple[str, str]]:
    """Extract (schema, table) for the first sqlmesh__* reference in a view body.

    Returns None if no SQLMesh snapshot reference is found (e.g. a view that
    references base tables instead of snapshots).
    """
    m = _SNAPSHOT_REF_RE.search(view_definition)
    if not m:
        return None
    return m.group("schema"), m.group("table")


def resolve_snapshots(
    cfg: DBConfig,
    user_schema: str = "refapp_28_demo",
) -> dict[str, ResolvedSnapshot]:
    """Return a mapping of user-facing view name → ResolvedSnapshot.

    Queries ``information_schema.views`` for every view in ``user_schema``,
    parses the view definition to extract the underlying SQLMesh snapshot
    table reference, and returns a dict keyed by view name.

    Views without a SQLMesh-snapshot reference (e.g. union-style audit views
    over the marts) are omitted from the result so the caller can detect
    them.
    """
    rows = query(cfg, f"""
        SELECT table_name, view_definition
        FROM information_schema.views
        WHERE table_schema='{user_schema}'
        ORDER BY table_name
    """)
    out: dict[str, ResolvedSnapshot] = {}
    for row in rows:
        view_name = row[0]
        view_definition = row[1] or ""
        parsed = _parse_view_definition(view_definition)
        if parsed is None:
            continue
        schema, table = parsed
        out[view_name] = ResolvedSnapshot(
            view_name=view_name,
            physical_table=table,
            physical_schema=schema,
        )
    return out


__all__ = ["ResolvedSnapshot", "resolve_snapshots"]
