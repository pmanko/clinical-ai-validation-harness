#!/usr/bin/env python3
"""Compatibility CLI shim for the packaged live dashboard (`harness.validate.dashboard_server`)."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
_SERVER_PATH = ROOT / "harness" / "validate" / "dashboard_server.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    from harness.validate.dashboard_server import main

    raise SystemExit(main())

exec(compile(_SERVER_PATH.read_text(encoding="utf-8"), str(_SERVER_PATH), "exec"), globals())
