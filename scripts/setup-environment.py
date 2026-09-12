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
from harness.evaluation_setup import SetupError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare"))
    parser.add_argument(
        "--environment", choices=("chartsearchai",), default="chartsearchai"
    )
    parser.add_argument(
        "--data", choices=("preserve", "initialize", "reset"), default="preserve"
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--study", choices=("roles",))
    parser.add_argument("--confirm-demo-data", action="store_true")
    args = parser.parse_args()
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
            receipt.update(
                prepare_environment(
                    ROOT,
                    data_action=args.data,
                    baseline=args.baseline,
                    study=args.study == "roles",
                    confirm_demo_data=args.confirm_demo_data,
                    check_only=args.action == "check",
                )
            )
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
