#!/usr/bin/env python3
"""Provision named research accounts on the local synthetic-data OpenMRS instance."""

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.common.openmrs import OpenMrsClient  # noqa: E402
from harness.evaluation_users import provision_users  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088/openmrs")
    parser.add_argument(
        "--confirm-demo-data",
        action="store_true",
        required=True,
        help="confirm this is the local synthetic/demo evaluation instance",
    )
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("This study provisioner only changes a loopback local instance.")
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        parser.error("Use a local HTTP(S) URL without embedded credentials.")
    password = os.environ.get("CHARTSEARCH_ADMIN_PASSWORD")
    if not password:
        parser.error(
            "Set CHARTSEARCH_ADMIN_PASSWORD in the local environment; do not pass secrets on the command line."
        )
    directory = ROOT / "artifacts/evaluation-setup"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "users.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another study-account operation is active.", file=sys.stderr)
            return 1
        client = OpenMrsClient(
            args.base_url, os.environ.get("CHARTSEARCH_ADMIN_USER", "admin"), password
        )
        config = json.loads(
            (ROOT / "datasets/validation/evaluation-roles.json").read_text()
        )
        result = provision_users(client, config, directory / "credentials.json")
        (directory / "accounts.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
