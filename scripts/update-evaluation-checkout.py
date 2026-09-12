#!/usr/bin/env python3
"""Update the shared main and exact target pins; never reset clinical data."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.evaluation_setup import SetupError, update_checkout  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fetch and report available main changes without changing the checkout",
    )
    args = parser.parse_args()
    directory = ROOT / "artifacts/evaluation-setup"
    directory.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "evaluation_source_update.v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "data_action": "preserve",
        "application_readiness": "not_checked",
    }
    with (directory / "operation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                "Another source update or environment preparation is active; this invocation did nothing.",
                file=sys.stderr,
            )
            return 1
        try:
            receipt.update(update_checkout(ROOT, check_only=args.check))
            code = 0
        except SetupError as error:
            receipt.update(status="failed", error=str(error))
            code = 1
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        path = directory / "source-update.json"
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(receipt, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    print(json.dumps(receipt, indent=2))
    print(f"Source receipt: {path}")
    if code == 0:
        print("Source check only. Application setup and readiness must still run.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
