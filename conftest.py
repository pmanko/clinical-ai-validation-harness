from __future__ import annotations

import sys
from pathlib import Path

_VALIDATE_EVALS = str(Path(__file__).resolve().parent / "evals" / "validate")
if _VALIDATE_EVALS not in sys.path:
    sys.path.insert(0, _VALIDATE_EVALS)
