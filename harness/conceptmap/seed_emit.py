"""Emit SQLMesh seed CSVs from the accepted ConceptMap.

One-way emit, deterministic given the same inputs:

  - ``concept_translation.csv`` — one row per distinct legacy concept_id
    present in ``legacy_27_raw.concept``. Materializes the bridge rule's
    UUID template (``RPAD(N, 36, 'A')``) as ``(source_concept_id,
    source_uuid, target_concept_id, target_uuid, equivalence,
    policy_bucket, source_record_examples)``.
  - ``module_table_policy.csv`` — one row per legacy-only table
    (``policy`` ∈ ``drop``/``carry-forward``/``install-module``/``remap``).
    Initial pass marks every legacy-only table as ``carry-forward`` for
    iteration; reviewer adjusts at acceptance.

Schema authoritative in
``specs/.../contracts/sqlmesh_project.profile.md`` §Seeds.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from harness.profile.db import DBConfig, query

from .load import AcceptedConceptMap, load_conceptmap


# ---------- concept_translation ----------


CT_COLUMNS = (
    "source_concept_id",
    "source_uuid",
    "target_concept_id",
    "target_uuid",
    "equivalence",
    "policy_bucket",
    "source_record_examples",
)


def _ciel_uuid(concept_id: int) -> str:
    """Apply the bridge-rule UUID template."""
    s = str(concept_id)
    return s + "A" * (36 - len(s))


def fetch_legacy_concepts(cfg: DBConfig) -> list[tuple[int, str]]:
    """Return [(concept_id, source_uuid), ...] sorted by concept_id."""
    rows = query(cfg, "SELECT concept_id, uuid FROM concept ORDER BY concept_id")
    return [(int(cid), uid) for cid, uid in rows if cid is not None]


def emit_concept_translation_rows(
    cm: AcceptedConceptMap, legacy_concepts: Sequence[tuple[int, str]]
) -> list[tuple[str, ...]]:
    """One row per distinct legacy concept_id, encoding the bridge rule."""
    bridge = cm.bridge_rule
    eq = bridge.equivalence
    pb = bridge.ext.policy_bucket
    rows: list[tuple[str, ...]] = []
    for cid, src_uuid in legacy_concepts:
        rows.append((
            str(cid),
            src_uuid or "",
            str(cid),               # target_concept_id: same canonical id by the bridge rule
            _ciel_uuid(cid),
            eq,
            pb,
            "",                     # examples deliberately empty per row (kept in ConceptMap element)
        ))
    return rows


def write_concept_translation_csv(
    cm: AcceptedConceptMap, legacy_concepts: Sequence[tuple[int, str]], out: Path
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CT_COLUMNS)
        for row in emit_concept_translation_rows(cm, legacy_concepts):
            w.writerow(row)
    return out


# ---------- module_table_policy ----------


MTP_COLUMNS = ("table_name", "policy", "rationale", "ticket_ref")


def emit_module_table_policy_rows(
    legacy_only_tables: Iterable[str], default_policy: str = "carry-forward"
) -> list[tuple[str, ...]]:
    """One row per legacy-only table; reviewer adjusts policy at acceptance."""
    rows: list[tuple[str, ...]] = []
    for name in sorted(legacy_only_tables):
        rows.append((
            name,
            default_policy,
            f"legacy-only table not in 2.8 RefApp baseline; default {default_policy}",
            "",
        ))
    return rows


def write_module_table_policy_csv(
    legacy_only_tables: Iterable[str], out: Path,
    default_policy: str = "carry-forward",
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(MTP_COLUMNS)
        for row in emit_module_table_policy_rows(legacy_only_tables, default_policy):
            w.writerow(row)
    return out


def discover_legacy_only_tables(legacy_cfg: DBConfig, target_cfg: DBConfig) -> list[str]:
    """Return tables present in ``legacy_cfg.database`` but absent in ``target_cfg.database``."""
    rows = query(legacy_cfg, (
        f"SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='{legacy_cfg.database}' AND table_type='BASE TABLE'"
    ))
    legacy_set = {r[0] for r in rows if r and r[0]}
    rows = query(target_cfg, (
        f"SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='{target_cfg.database}' AND table_type='BASE TABLE'"
    ))
    target_set = {r[0] for r in rows if r and r[0]}
    return sorted(legacy_set - target_set)


# ---------- CLI ----------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.conceptmap.seed_emit")
    p.add_argument(
        "--conceptmap",
        default="datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json",
    )
    p.add_argument(
        "--seeds-dir",
        default="datasets/transforms/sqlmesh/seeds",
    )
    p.add_argument("--legacy-db", default="legacy_27_raw")
    p.add_argument("--target-db", default="openmrs")
    args = p.parse_args(argv)

    cm = load_conceptmap(args.conceptmap)
    legacy_cfg = DBConfig.from_env(database=args.legacy_db)
    target_cfg = DBConfig.from_env(database=args.target_db)

    legacy_concepts = fetch_legacy_concepts(legacy_cfg)
    ct_path = write_concept_translation_csv(
        cm, legacy_concepts, Path(args.seeds_dir) / "concept_translation.csv"
    )
    print(f"Wrote {ct_path} ({len(legacy_concepts)} rows)")

    legacy_only = discover_legacy_only_tables(legacy_cfg, target_cfg)
    mtp_path = write_module_table_policy_csv(
        legacy_only, Path(args.seeds_dir) / "module_table_policy.csv"
    )
    print(f"Wrote {mtp_path} ({len(legacy_only)} legacy-only tables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
