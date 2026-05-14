"""Bootstrap the OpenMRS OpenConceptLab module against a pinned CIEL release.

Connects to a running harness OpenMRS instance (default: via the proxy at
http://localhost:8088/openmrs) and:

  1. Sets the OpenConceptLab subscription to a pinned CIEL version URL so the
     module records "this dictionary version" in the OpenMRS global_property
     table (persists across restarts).
  2. Performs an OFFLINE import: uploads a pinned CIEL ZIP (downloaded once via
     scripts/fetch-ciel-release.sh) via the module's multipart upload endpoint.
     This is fully deterministic — no live OCL fetch happens from inside
     OpenMRS.
  3. Polls the import endpoint until the import finishes and reports counts.

Designed to be idempotent: if the latest import already shows the same
`releaseVersion` stamp and status "import done", it is a no-op.

Auth: uses HTTP basic auth with the admin/Admin123 default (configurable via
OPENMRS_ADMIN_USER / OPENMRS_ADMIN_PASSWORD env vars). OCL token comes from
the keychain via harness.ocl.get_token.

References:
- SubscriptionResource.java getCreatableProperties: {url, token, subscribedToSnapshot, validationType}
- ImportResource.java implements Uploadable: multipart upload (field `file`)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.ocl.credentials import get_token

_BASE = os.environ.get("OPENMRS_BASE_URL", "http://localhost:8088/openmrs")
_USER = os.environ.get("OPENMRS_ADMIN_USER", "admin")
_PASS = os.environ.get("OPENMRS_ADMIN_PASSWORD", "Admin123")

_REST = f"{_BASE}/ws/rest/v1"
_SUB_URL = f"{_REST}/openconceptlab/subscription"
_IMP_URL = f"{_REST}/openconceptlab/import"


def _basic_auth_header() -> str:
    import base64

    raw = f"{_USER}:{_PASS}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _request(method: str, url: str, *, body: bytes | None = None,
             content_type: str | None = None, accept: str = "application/json",
             timeout: int = 60) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", _basic_auth_header())
    req.add_header("Accept", accept)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


def get_subscription() -> dict[str, Any] | None:
    """Return the current subscription dict, or None if no subscription is configured."""
    code, body, _ = _request("GET", _SUB_URL)
    if code != 200:
        raise RuntimeError(f"GET {_SUB_URL} -> HTTP {code}: {body[:200]!r}")
    data = json.loads(body)
    results = data.get("results", [])
    if not results or results[0] is None:
        return None
    return results[0]


def set_subscription(*, url: str, token: str | None = None,
                     subscribed_to_snapshot: bool = False,
                     validation_type: str = "FULL") -> dict[str, Any]:
    """Create or update the subscription. POST creates; PUT updates if it exists.

    The module accepts both; we use POST which the underlying SubscriptionResource
    handles as create-or-replace.
    """
    if token is None:
        token = get_token()
    payload = {
        "url": url,
        "token": token,
        "subscribedToSnapshot": subscribed_to_snapshot,
        "validationType": validation_type,
    }
    body = json.dumps(payload).encode()
    code, resp, _ = _request("POST", _SUB_URL, body=body, content_type="application/json")
    if code not in (200, 201):
        raise RuntimeError(f"POST {_SUB_URL} -> HTTP {code}: {resp[:500]!r}")
    return json.loads(resp)


def upload_import_zip(zip_path: Path) -> str:
    """Upload a pinned OCL export ZIP for offline import. Returns the import UUID."""
    if not zip_path.exists():
        raise FileNotFoundError(f"OCL ZIP not found at {zip_path}")
    boundary = f"------------HarnessBootstrap{int(time.time())}"
    data = zip_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{zip_path.name}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    content_type = f"multipart/form-data; boundary={boundary}"
    code, resp, _ = _request("POST", _IMP_URL, body=body, content_type=content_type, timeout=600)
    if code not in (200, 201):
        raise RuntimeError(f"POST {_IMP_URL} (upload {zip_path.name}) -> HTTP {code}: {resp[:500]!r}")
    parsed = json.loads(resp) if resp else {}
    uuid = parsed.get("uuid")
    if not uuid:
        raise RuntimeError(f"Upload succeeded but no uuid in response: {parsed!r}")
    return uuid


def trigger_subscription_import() -> str:
    """Trigger an ONLINE import using the configured subscription URL+token. Returns import UUID."""
    code, resp, _ = _request("POST", _IMP_URL, body=b"{}", content_type="application/json")
    if code not in (200, 201):
        raise RuntimeError(f"POST {_IMP_URL} (subscription import) -> HTTP {code}: {resp[:500]!r}")
    parsed = json.loads(resp) if resp else {}
    return parsed.get("uuid", "")


def get_import(uuid: str) -> dict[str, Any]:
    """Fetch import status by uuid."""
    code, resp, _ = _request("GET", f"{_IMP_URL}/{uuid}?v=full")
    if code != 200:
        raise RuntimeError(f"GET {_IMP_URL}/{uuid} -> HTTP {code}: {resp[:200]!r}")
    return json.loads(resp)


def list_imports(limit: int = 5) -> list[dict[str, Any]]:
    """Fetch recent imports (most recent first)."""
    code, resp, _ = _request("GET", f"{_IMP_URL}?v=full&limit={limit}")
    if code != 200:
        raise RuntimeError(f"GET {_IMP_URL} -> HTTP {code}: {resp[:200]!r}")
    return json.loads(resp).get("results", [])


@dataclass
class ImportProgress:
    uuid: str
    started_at: str | None
    stopped_at: str | None
    progress_pct: int
    status: str
    all_items: int
    added: int
    updated: int
    up_to_date: int
    retired: int
    unretired: int
    errors: int
    error_message: str | None

    @property
    def is_finished(self) -> bool:
        return self.stopped_at is not None

    @property
    def is_success(self) -> bool:
        return self.is_finished and not self.error_message and self.errors == 0


def parse_progress(d: dict[str, Any]) -> ImportProgress:
    return ImportProgress(
        uuid=d.get("uuid", ""),
        started_at=d.get("localDateStarted"),
        stopped_at=d.get("localDateStopped"),
        progress_pct=int(d.get("importProgress", "0") or 0),
        status=d.get("status", ""),
        all_items=int(d.get("allItemsCount", 0) or 0),
        added=int(d.get("addedItemsCount", 0) or 0),
        updated=int(d.get("updatedItemsCount", 0) or 0),
        up_to_date=int(d.get("upToDateItemsCount", 0) or 0),
        retired=int(d.get("retiredItemsCount", 0) or 0),
        unretired=int(d.get("unretiredItemsCount", 0) or 0),
        errors=int(d.get("errorItemsCount", 0) or 0),
        error_message=d.get("errorMessage"),
    )


def wait_for_import(uuid: str, *, timeout_seconds: int = 5400,
                    poll_interval: int = 10) -> ImportProgress:
    """Poll until the import completes; report progress periodically."""
    deadline = time.time() + timeout_seconds
    last_progress = -1
    while time.time() < deadline:
        prog = parse_progress(get_import(uuid))
        if prog.is_finished:
            return prog
        if prog.progress_pct != last_progress:
            print(
                f"  [progress] {prog.progress_pct}%  items={prog.all_items}"
                f"  added={prog.added}  updated={prog.updated}  errors={prog.errors}"
                f"  status={prog.status!r}"
            )
            last_progress = prog.progress_pct
        time.sleep(poll_interval)
    raise TimeoutError(f"Import {uuid} did not finish within {timeout_seconds}s")


def is_already_bootstrapped(version: str) -> bool:
    """Return True if a recent import is for the expected CIEL release version and succeeded."""
    for imp in list_imports(limit=10):
        if imp.get("releaseVersion") == version and not imp.get("errorMessage"):
            if imp.get("localDateStopped") and int(imp.get("importProgress", "0") or 0) == 100:
                return True
    return False


def bootstrap_ciel(
    version: str = "v2026-04-28",
    *,
    pinned_zip: Path | None = None,
    use_online_subscription: bool = False,
) -> ImportProgress | None:
    """Idempotent bootstrap: pin subscription + (if needed) trigger offline import.

    Returns the ImportProgress of the run, or None if already bootstrapped.
    """
    subscription_url = (
        f"https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/{version}/"
    )

    if is_already_bootstrapped(version):
        print(f"CIEL {version} already imported successfully. No-op.")
        return None

    # Always (re)set the subscription so OpenMRS records the pinned URL.
    cur = get_subscription()
    needs_set = not cur or cur.get("url") != subscription_url
    if needs_set:
        print(f"Setting subscription to {subscription_url} ...")
        set_subscription(url=subscription_url)
        print("  set.")
    else:
        print(f"Subscription already pinned to {subscription_url}.")

    if use_online_subscription:
        print("Triggering online subscription import...")
        uuid = trigger_subscription_import()
    else:
        if pinned_zip is None:
            pinned_zip = (
                Path("datasets/sources/ocl/CIEL")
                / version
                / f"CIEL_{version}.zip"
            )
        print(f"Uploading offline ZIP {pinned_zip} ({pinned_zip.stat().st_size / 1e6:.1f} MB) ...")
        uuid = upload_import_zip(pinned_zip)
        print(f"  import queued: uuid={uuid}")

    print("Waiting for import to complete (this can take 30-90 minutes for full CIEL)...")
    prog = wait_for_import(uuid)
    print(
        f"  finished. status={prog.status!r}  items={prog.all_items}  added={prog.added}"
        f"  updated={prog.updated}  errors={prog.errors}"
    )
    return prog


__all__ = [
    "ImportProgress",
    "bootstrap_ciel",
    "get_subscription",
    "set_subscription",
    "list_imports",
    "get_import",
    "upload_import_zip",
    "trigger_subscription_import",
    "wait_for_import",
    "parse_progress",
    "is_already_bootstrapped",
]
