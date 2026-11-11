#!/usr/bin/env python3
"""CLI wrapper delegating to packaged `harness.validate.combine_judge_actors`."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.validate.combine_judge_actors import _rows, build, main  # noqa: E402,F401

if __name__ == "__main__":
    raise SystemExit(main())
