"""OCL token retrieval.

Resolution order (first hit wins):

1. `OCL_TOKEN` environment variable (non-empty). Useful for CI / VM / one-off runs.
2. macOS keychain item at service `OCL_KEYCHAIN_SERVICE` (default: `ocl-token`),
   readable via `/usr/bin/security find-generic-password -s <service> -w`.
   Set up once with `scripts/setup-ocl-keychain.sh`; the script ACL-whitelists
   `/usr/bin/security` so subsequent reads do not prompt for keychain password
   or Touch ID.

The token is never written to disk, never logged, and is intentionally not
cached at module level — every call fetches fresh so a token rotation takes
effect immediately on the next call.
"""

from __future__ import annotations

import os
import platform
import subprocess


class OCLTokenError(RuntimeError):
    """Raised when no OCL token can be resolved or it appears invalid."""


def _get_from_env() -> str | None:
    val = os.environ.get("OCL_TOKEN", "").strip()
    return val or None


def _get_from_macos_keychain(service: str) -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    token = r.stdout.strip()
    return token or None


def get_token(*, keychain_service: str | None = None) -> str:
    """Resolve the OCL API token.

    Raises OCLTokenError if no token is found.
    """
    service = keychain_service or os.environ.get("OCL_KEYCHAIN_SERVICE", "ocl-token")

    token = _get_from_env()
    if token:
        return token

    token = _get_from_macos_keychain(service)
    if token:
        return token

    raise OCLTokenError(
        "No OCL token found. Either:\n"
        "  - export OCL_TOKEN=<token> in this shell, or\n"
        "  - run scripts/setup-ocl-keychain.sh to install the token in the macOS keychain."
    )


__all__ = ["get_token", "OCLTokenError"]
