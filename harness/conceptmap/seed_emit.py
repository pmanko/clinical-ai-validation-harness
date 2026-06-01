"""Emit SQLMesh seed CSVs from the accepted ConceptMap.

One-way emit, deterministic given the same inputs:

  - ``concept_translation.csv`` — one row per distinct legacy concept_id that
    successfully resolves to a local target ``concept.concept_id`` via its
    CIEL UUID (``RPAD(N, 36, 'A')`` bridge rule). Columns:
    (source_concept_id, source_uuid, target_concept_id, target_uuid,
    equivalence, policy_bucket, source_record_examples).
  - ``concept_translation_omissions.csv`` — one row per legacy concept_id that
    is NOT clinically referenced in obs AND could not resolve to a target UUID.
    These are omitted from the executable seed; a reviewer must sign off.
    Clinically-referenced concepts that cannot resolve raise ``ValueError``.
  - ``module_table_policy.csv`` — one row per legacy-only table
    (``policy`` ∈ ``drop``/``carry-forward``/``install-module``/``remap``).

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

CT_OMISSIONS_COLUMNS = (
    "source_concept_id",
    "source_uuid",
    "target_uuid",
    "reason",
)

# Legacy concepts the UUID bridge rule cannot resolve but that ARE referenced —
# not through obs (the bridge's coverage set), but through the program model
# (program.concept_id, program_workflow.concept_id, program_workflow_state.concept_id).
# These rebind the legacy AMPATH HIV/TB program + clinical treatment-status states
# to their modern OpenMRS RefApp 3.x / CIEL equivalents. The legacy
# The legacy "treatment GROUP" cohort states are deliberately NOT listed here: they
# have no CIEL equivalent, so stg_concept_carryforward loads them into the dictionary
# as local concepts and the program/workflow/state staging models keep them (LEFT
# JOIN + COALESCE on the legacy id). Nothing is dropped.
MANUAL_CONCEPT_OVERRIDES: dict[int, int] = {
    991482: 1086,   # HIV PROGRAM                      -> Human immunodeficiency virus (HIV) infection
    991648: 35263,  # TUBERCULOSIS PROGRAM            -> TB Program
    992842: 36254,  # MDR-TB PROGRAM                  -> MDR-TB program
    991484: 4180,   # TREATMENT STATUS (workflow)     -> Program status
    991577: 4181,   # ON ANTIRETROVIRALS             -> On Antiretrovirals
    991487: 36285,  # ACTIVE TREATMENT               -> Still on treatment
    991490: 36285,  # FOLLOWING                       -> Still on treatment
    991714: 36291,  # TREATMENT COMPLETE             -> Treatment complete
    991744: 36288,  # PATIENT TRANSFERRED OUT        -> Patient transferred out
    991743: 36298,  # PATIENT DEFAULTED              -> Defaulted
    991483: 36326,  # TREATMENT STOPPED - PATIENT REFUSED -> Treatment never started - patient refused
}


def _ciel_uuid(concept_id: int) -> str:
    """Apply the bridge-rule UUID template: pad to 36 chars with 'A'."""
    s = str(concept_id)
    return s + "A" * (36 - len(s))


def fetch_legacy_concepts(cfg: DBConfig) -> list[tuple[int, str]]:
    """Return [(concept_id, source_uuid), ...] sorted by concept_id."""
    rows = query(cfg, "SELECT concept_id, uuid FROM concept ORDER BY concept_id")
    return [(int(cid), uid) for cid, uid in rows if cid is not None]


def fetch_target_uuid_to_id(cfg: DBConfig) -> dict[str, int]:
    """Return {uuid: concept_id} for every concept in the target DB."""
    rows = query(cfg, "SELECT uuid, concept_id FROM concept WHERE uuid IS NOT NULL")
    return {uid: int(cid) for uid, cid in rows if uid and cid is not None}


def fetch_clinically_referenced_concept_ids(cfg: DBConfig) -> set[int]:
    """Return the set of legacy concept_ids referenced in obs.concept_id or obs.value_coded."""
    rows = query(cfg, (
        "SELECT DISTINCT concept_id FROM obs WHERE concept_id IS NOT NULL "
        "UNION "
        "SELECT DISTINCT value_coded FROM obs WHERE value_coded IS NOT NULL"
    ))
    return {int(r[0]) for r in rows if r[0] is not None}


def emit_concept_translation_rows(
    cm: AcceptedConceptMap,
    legacy_concepts: Sequence[tuple[int, str]],
    target_uuid_to_id: dict[str, int],
    clinically_referenced: set[int] | None = None,
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """One row per distinct legacy concept_id that resolves by CIEL UUID.

    Args:
        cm: Accepted ConceptMap carrying bridge-rule metadata.
        legacy_concepts: (concept_id, source_uuid) from the legacy DB.
        target_uuid_to_id: {uuid: local_concept_id} from the target DB.
        clinically_referenced: Set of legacy concept_ids found in obs. If
            ``None``, every concept is treated as clinically referenced (strict
            mode: any unresolvable concept raises ValueError).

    Returns:
        (rows, omissions) where ``rows`` are valid seed rows and ``omissions``
        are unreferenced concepts that did not resolve.

    Raises:
        ValueError: if a clinically-referenced concept cannot resolve by UUID.
    """
    bridge = cm.bridge_rule
    eq = bridge.equivalence
    pb = bridge.ext.policy_bucket
    rows: list[tuple[str, ...]] = []
    omissions: list[tuple[str, ...]] = []
    target_id_to_uuid = {v: k for k, v in target_uuid_to_id.items()}

    for cid, src_uuid in legacy_concepts:
        override_id = MANUAL_CONCEPT_OVERRIDES.get(cid)
        if override_id is not None:
            ov_uuid = target_id_to_uuid.get(override_id)
            if ov_uuid is None:
                raise ValueError(
                    f"Manual override target concept_id {override_id} for legacy "
                    f"concept {cid} not found in the target database."
                )
            rows.append((
                str(cid),
                src_uuid or "",
                str(override_id),
                ov_uuid,
                eq,
                pb,
                "manual program/state rebind (bridge-rule UUID miss)",
            ))
            continue

        target_uuid = _ciel_uuid(cid)
        local_id = target_uuid_to_id.get(target_uuid)

        if local_id is None:
            is_referenced = (clinically_referenced is None) or (cid in clinically_referenced)
            if is_referenced:
                raise ValueError(
                    f"Clinically referenced concept {cid} (CIEL UUID {target_uuid!r}) "
                    f"has no matching concept.uuid in the target database. "
                    f"Cannot emit a safe seed without a valid local FK. "
                    f"Verify the target DB is fully loaded with CIEL concepts."
                )
            omissions.append((
                str(cid),
                src_uuid or "",
                target_uuid,
                "uuid not found in target concept table; not clinically referenced",
            ))
            continue

        rows.append((
            str(cid),
            src_uuid or "",
            str(local_id),   # UUID-resolved local concept.concept_id (was: source integer)
            target_uuid,
            eq,
            pb,
            "",              # examples kept in ConceptMap element, not per-row
        ))
    return rows, omissions


def write_concept_translation_csv(
    cm: AcceptedConceptMap,
    legacy_concepts: Sequence[tuple[int, str]],
    target_uuid_to_id: dict[str, int],
    clinically_referenced: set[int] | None,
    out: Path,
    omissions_out: Path | None = None,
) -> Path:
    """Write concept_translation.csv, optionally writing omissions alongside."""
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, omissions = emit_concept_translation_rows(
        cm, legacy_concepts, target_uuid_to_id, clinically_referenced
    )
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CT_COLUMNS)
        for row in rows:
            w.writerow(row)
    if omissions_out is not None:
        omissions_out.parent.mkdir(parents=True, exist_ok=True)
        with omissions_out.open("w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(CT_OMISSIONS_COLUMNS)
            for row in omissions:
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
    target_uuid_to_id = fetch_target_uuid_to_id(target_cfg)
    clinically_referenced = fetch_clinically_referenced_concept_ids(legacy_cfg)

    seeds_dir = Path(args.seeds_dir)
    ct_path = write_concept_translation_csv(
        cm,
        legacy_concepts,
        target_uuid_to_id,
        clinically_referenced,
        seeds_dir / "concept_translation.csv",
        omissions_out=seeds_dir / "concept_translation_omissions.csv",
    )
    omissions_path = seeds_dir / "concept_translation_omissions.csv"
    print(f"Wrote {ct_path} ({len(legacy_concepts)} legacy concepts)")
    if omissions_path.exists():
        import csv as _csv
        with omissions_path.open() as f:
            omission_count = sum(1 for _ in _csv.reader(f)) - 1
        print(f"Wrote {omissions_path} ({omission_count} unresolvable unreferenced concepts omitted)")

    legacy_only = discover_legacy_only_tables(legacy_cfg, target_cfg)
    mtp_path = write_module_table_policy_csv(
        legacy_only, seeds_dir / "module_table_policy.csv"
    )
    print(f"Wrote {mtp_path} ({len(legacy_only)} legacy-only tables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
