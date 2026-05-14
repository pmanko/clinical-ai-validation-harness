"""CLI entrypoint: python3 -m harness.profile <subcommand>"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _cmd_inventory(args: argparse.Namespace) -> int:
    from harness.profile.db import DBConfig
    from harness.profile.inventory import generate_inventory, write_inventory

    cfg = DBConfig.from_env(database=args.db)
    src = Path(args.src)
    if not src.exists():
        print(f"ERROR: source dump not found: {src}", file=sys.stderr)
        return 1

    run_id = args.run_id or f"dev-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
    out_path = Path("artifacts") / run_id / "profile" / "inventory.json"

    print(f"Profiling DB '{cfg.database}' against source {src} ...")
    inv = generate_inventory(cfg, source_dump_path=src, progress=args.verbose)
    written = write_inventory(inv, out_path)
    print(f"Wrote {written}")
    print(f"  tables: {len(inv['tables'])}")
    populated = [t for t in inv["tables"] if t["row_count"] > 0]
    print(f"  populated: {len(populated)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.profile")
    sub = p.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("inventory", help="Profile a legacy schema (T021).")
    inv.add_argument("--db", default="legacy_27_raw", help="Source DB (default: legacy_27_raw).")
    inv.add_argument("--src", default="data/large-demo-data-2-7-0.sql",
                     help="Path to source dump (default: data/large-demo-data-2-7-0.sql).")
    inv.add_argument("--run-id", default=None,
                     help="Artifact run id (default: dev-<timestamp>).")
    inv.add_argument("--verbose", "-v", action="store_true",
                     help="Print per-table progress.")
    inv.set_defaults(func=_cmd_inventory)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
