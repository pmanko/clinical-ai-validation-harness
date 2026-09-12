#!/usr/bin/env python3
"""Inspect or prepare a local harness environment; preserve data by default."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.environment_setup import prepare_environment  # noqa: E402
from harness.environment_assets import prepare_assets  # noqa: E402
from harness.evaluation_setup import SetupError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare", "assets"))
    parser.add_argument(
        "--environment", choices=("chartsearchai",), default="chartsearchai"
    )
    parser.add_argument(
        "--data", choices=("preserve", "initialize", "reset"), default="preserve"
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--model", help="assets: pinned router model alias to verify")
    parser.add_argument(
        "--baseline-source",
        help="assets: reviewed local file or HTTPS source with adjacent provenance",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="assets: fetch missing selected files; never overwrite existing files",
    )
    parser.add_argument(
        "--confirm-demo-data",
        action="store_true",
        help="confirm this evaluation instance uses synthetic/demo data; role accounts are required",
    )
    args = parser.parse_args()
    if args.action != "assets" and (args.model or args.baseline_source or args.fetch):
        parser.error("--model, --baseline-source, and --fetch apply only to assets")
    if args.action == "assets" and (args.data != "preserve" or args.confirm_demo_data):
        parser.error(
            "Asset preparation does not initialize/reset a database or provision accounts"
        )
    if sys.platform == "win32":
        parser.error(
            "Use a Linux WSL2 shell; native Windows orchestration is not verified."
        )
    import fcntl

    directory = ROOT / "artifacts/evaluation-setup"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "operation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                "Another environment preparation is active; no services changed.",
                file=sys.stderr,
            )
            return 1
        receipt = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "environment": args.environment,
            "data_action": args.data,
            "readiness": "not_checked",
        }
        try:
            if args.action == "assets":
                result = prepare_assets(
                    ROOT,
                    model=args.model,
                    baseline=args.baseline,
                    baseline_source=args.baseline_source,
                    fetch=args.fetch,
                )
            else:
                result = prepare_environment(
                    ROOT,
                    data_action=args.data,
                    baseline=args.baseline,
                    confirm_demo_data=args.confirm_demo_data,
                    check_only=args.action == "check",
                )
            receipt.update(result)
            code = 0
        except (SetupError, OSError, ValueError) as error:
            receipt.update(status="failed", error=str(error))
            code = 1
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        # Timestamped receipts preserve a failed attempt alongside earlier proof.
        filename = datetime.now(timezone.utc).strftime(
            "environment-%Y%m%dT%H%M%S%fZ.json"
        )
        path = directory / filename
        path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    print(f"Receipt: {path}")
    if code == 0:
        print(
            "Preparation is not application acceptance. Provider, model, login, and UI checks remain."
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
