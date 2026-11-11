#!/usr/bin/env python3
"""CLI wrapper delegating to packaged `harness.validate.judge_aggregate`."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import harness.validate.judge_aggregate as _impl  # noqa: E402

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})


def run_dir(arg: str) -> pathlib.Path:
    _impl.ROOT = ROOT
    return _impl.run_dir(arg)


def main(argv: list[str] | None = None) -> None:
    _impl.ROOT = ROOT
    return _impl.main(argv)


if __name__ == "__main__":
    main()
