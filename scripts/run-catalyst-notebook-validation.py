#!/usr/bin/env python3
"""Compatibility wrapper for ``harness-cli catalyst run``."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from harness.cli import main as harness_main  # noqa: E402


def main() -> int:
    return harness_main(
        ["catalyst", "run", *sys.argv[1:]], project_root=ROOT_DIR
    )


if __name__ == "__main__":
    raise SystemExit(main())
