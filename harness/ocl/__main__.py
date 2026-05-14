"""CLI entrypoint for harness.ocl.

Usage:
    python3 -m harness.ocl ciel-baseline --version v2026-04-28
    python3 -m harness.ocl ciel-baseline --version v2026-04-28 --online

Exit codes:
    0  success (or no-op when already bootstrapped)
    1  bootstrap failed
    2  credential / config error
"""

from __future__ import annotations

import argparse
import sys


def _cmd_ciel_baseline(args: argparse.Namespace) -> int:
    # Imported lazily so `--help` doesn't trigger the module-init fail-fast
    # guard or attempt to resolve credentials.
    from harness.ocl.bootstrap import bootstrap_ciel
    from harness.ocl.credentials import OCLTokenError

    try:
        bootstrap_ciel(args.version, use_online_subscription=args.online)
    except OCLTokenError as e:
        print(f"ERROR (credentials): {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: CIEL baseline failed: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.ocl")
    sub = p.add_subparsers(dest="cmd", required=True)

    cb = sub.add_parser(
        "ciel-baseline",
        help="Pin OpenMRS to a CIEL release and run an offline import (idempotent).",
    )
    cb.add_argument("--version", required=True, help="CIEL release tag, e.g. v2026-04-28")
    cb.add_argument(
        "--online",
        action="store_true",
        help="Use the live OCL subscription pull instead of the pinned local ZIP (drops determinism).",
    )
    cb.set_defaults(func=_cmd_ciel_baseline)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
