#!/usr/bin/env python3
"""Generate a Catalyst data-source catalog from the analytics database.

The catalog file the gateway loads is DERIVED, never hand-maintained:

- columns + types      -> introspected from the view (pg_attribute)
- column descriptions  -> COMMENT ON COLUMN (pg_description), authored in the
                          source's sql/ files alongside the views themselves
- grain                -> COMMENT ON VIEW
- identity + approved views + semantic aliases
                       -> a small per-source catalog-overlay.json

Only the sections the gateway actually consumes are emitted
(Catalog.load reads: approved/name/version/grain/columns/semanticDimensions;
everything else in older hand-written catalogs was inert).

Semantic canonical values are validated against the live data so a canonical
that matches zero rows (e.g. a guessed display string) fails generation
instead of silently producing empty query results.

Usage:
  uv run python scripts/generate-catalyst-source-catalog.py \
      --dsn postgresql://user:pass@host:port/db \
      --overlay catalyst-sources/<source>/catalog-overlay.json \
      --out catalyst-sources/<source>/catalog/<name>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

TYPE_MAP = {
    "text": "string",
    "character varying": "string",
    "character": "string",
    "uuid": "string",
    "numeric": "decimal",
    "double precision": "decimal",
    "real": "decimal",
    "integer": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "boolean": "boolean",
    "date": "date",
    "timestamp with time zone": "timestamp",
    "timestamp without time zone": "timestamp",
}

COLUMNS_SQL = """
SELECT
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS data_type,
    col_description(c.oid, a.attnum) AS description
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = %s
    AND c.relname = %s
    AND a.attnum > 0
    AND NOT a.attisdropped
ORDER BY a.attnum
"""

VIEW_COMMENT_SQL = """
SELECT obj_description(c.oid)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relname = %s
"""


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    overlay = json.loads(args.overlay.read_text())
    unit_columns: dict[str, str] = overlay.get("unitColumns", {})
    semantic_dimensions = overlay.get("semanticDimensions", {})

    views = []
    with psycopg.connect(args.dsn) as connection:
        for approved in overlay["approvedViews"]:
            qualified = approved["name"]
            schema, _, relname = qualified.partition(".")
            with connection.cursor() as cursor:
                cursor.execute(VIEW_COMMENT_SQL, (schema, relname))
                row = cursor.fetchone()
                grain = (row[0] or "").strip() if row else ""
                if not grain:
                    fail(
                        f"{qualified} has no COMMENT ON VIEW; the view comment "
                        "is the catalog grain and must be authored in sql/."
                    )
                cursor.execute(COLUMNS_SQL, (schema, relname))
                column_rows = cursor.fetchall()
                if not column_rows:
                    fail(f"{qualified} does not exist or has no columns.")
                columns = []
                for column_name, data_type, description in column_rows:
                    if not (description or "").strip():
                        fail(
                            f"{qualified}.{column_name} has no COMMENT ON COLUMN; "
                            "descriptions are the model's only schema context and "
                            "must be authored in sql/."
                        )
                    logical_type = TYPE_MAP.get(data_type)
                    if logical_type is None:
                        fail(
                            f"{qualified}.{column_name}: unmapped SQL type "
                            f"{data_type!r}; extend TYPE_MAP."
                        )
                    column = {
                        "name": column_name,
                        "logicalType": logical_type,
                        "nullable": True,
                        "description": description.strip(),
                    }
                    unit_column = unit_columns.get(f"{qualified}.{column_name}")
                    if unit_column:
                        column["unitColumn"] = unit_column
                    columns.append(column)

                view = {
                    "name": qualified,
                    "version": approved["version"],
                    "approved": True,
                    "grain": grain,
                    "columns": columns,
                }

                dimensions = semantic_dimensions.get(qualified, [])
                if dimensions:
                    field_names = {c["name"] for c in columns}
                    for dimension in dimensions:
                        field = dimension["field"]
                        if field not in field_names:
                            fail(
                                f"semantic dimension field {qualified}.{field} "
                                "is not a column of the view."
                            )
                        cursor.execute(
                            f"SELECT DISTINCT {field} FROM {qualified} "  # noqa: S608
                            f"WHERE {field} IS NOT NULL"
                        )
                        observed = {r[0] for r in cursor.fetchall()}
                        for value in dimension["values"]:
                            canonical = value["canonical"]
                            if canonical not in observed:
                                fail(
                                    f"canonical value {canonical!r} for "
                                    f"{qualified}.{field} matches zero rows in "
                                    "the live data - a guessed display string? "
                                    "Fix the overlay (or the data) and rerun."
                                )
                    view["semanticDimensions"] = dimensions
                views.append(view)

    catalog = {
        "contractVersion": "catalyst.analytics.catalog.v1",
        "catalogVersion": overlay["catalogVersion"],
        "deploymentMode": "demo",
        "dataSource": overlay["dataSource"],
        "dialect": overlay["dialect"],
        "schemaVersion": overlay["schemaVersion"],
        "description": (
            "GENERATED FILE - do not edit. Derived from the analytics database "
            "(view/column comments) plus catalog-overlay.json by "
            "scripts/generate-catalyst-source-catalog.py."
        ),
        "views": views,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2) + "\n")
    print(
        f"wrote {args.out} ({len(views)} views, "
        f"{sum(len(v['columns']) for v in views)} columns)"
    )


if __name__ == "__main__":
    main()
