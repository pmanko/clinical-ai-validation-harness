"""OCL (Open Concept Lab) client + credentials helpers for the harness.

Token storage: macOS keychain item at service `ocl-token` (configurable via
the `OCL_KEYCHAIN_SERVICE` env var). Set up once via `scripts/setup-ocl-keychain.sh`.

For non-macOS environments (CI, VM), fall back to the `OCL_TOKEN` env var.
"""

from harness.ocl.credentials import OCLTokenError, get_token

__all__ = ["get_token", "OCLTokenError"]
