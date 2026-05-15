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

    ae = sub.add_parser(
        "audit-errors",
        help="Enumerate per-item errors for a finished CIEL import and emit the gate JSON.",
    )
    ae.add_argument("--uuid", required=True, help="openconceptlab import uuid")
    ae.add_argument("--run-id", default=None,
                    help="run id for artifacts/<run-id>/profile/. Defaults to dev-<UTC timestamp>.")
    ae.add_argument("--root", default="artifacts", help="root artifacts directory")
    ae.set_defaults(func=_cmd_audit_errors)

    args = p.parse_args(argv)
    return args.func(args)


def _cmd_audit_errors(args: argparse.Namespace) -> int:
    from harness.profile.ciel_import_errors import (
        default_run_id,
        enumerate_errors,
        write_payload,
    )
    from pathlib import Path

    try:
        run_id = args.run_id or default_run_id()
        payload = enumerate_errors(args.uuid)
        out = write_payload(payload, run_id=run_id, root=Path(args.root))
    except Exception as e:
        print(f"ERROR: audit-errors failed: {e}", file=sys.stderr)
        return 1
    print(
        f"Wrote {out}\n"
        f"  all_items={payload['all_items_count']}"
        f"  errors={payload['error_items_count']}"
        f"  rate={payload['error_rate']:.6f}"
        f"  threshold={payload['gate_threshold']:.4f}"
        f"  gate_passed={payload['gate_passed']}"
    )
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
