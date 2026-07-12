#!/usr/bin/env python3
"""Verify a dump against its provenance sidecar before publishing or restoring."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.validate.dump_provenance import verify_dump


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument(
        "--require-portable",
        action="store_true",
        help="reject full backups that retain consumer-module state",
    )
    args = parser.parse_args()
    provenance_path = args.provenance or Path(f"{args.dump}.provenance.json")
    provenance, issues = verify_dump(
        args.dump, provenance_path, require_portable=args.require_portable
    )
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print(f"    verified dump sha256 {provenance['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
