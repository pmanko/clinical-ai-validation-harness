"""Enumerate OpenConceptLab per-item import errors for a finished CIEL import.

For a given import uuid, walks the openconceptlab module's per-item subresource
(`/openmrs/ws/rest/v1/openconceptlab/import/<uuid>/item?state=ERROR&v=full`) and
emits `artifacts/<run-id>/profile/ciel-import-errors.json` with per-record
evidence: item uuid, item type (CONCEPT/MAPPING/...), the error message, and
any identity hints (source mnemonic + numeric id parsed from the OCL URL,
version URL, hashed URL).

Asserts the error rate is <= 0.1% of total items in the import; the function
returns a payload dict whose `gate_passed` field reports the result. The CLI
exits non-zero when the gate fails so it can wire directly into M2-A.

Satisfies T024c (constitution Principle III — record-level evidence) for the
CIEL load. Uses the HTTP helpers in `harness.ocl.bootstrap` rather than
re-implementing auth + retries.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

from harness.ocl import bootstrap

GATE_THRESHOLD = 0.001  # 0.1%

# OCL URL pattern, e.g.
#   https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/concepts/78200/
#   https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/13127663/
_OCL_URL_RE = re.compile(
    r"/orgs/(?P<org>[^/]+)/sources/(?P<source>[^/]+)/(?P<kind>[^/]+)/(?P<code>[^/]+)/?"
)
# In error messages of the form "...concept with URL https://.../concepts/78200/...".
_REFERRED_CONCEPT_RE = re.compile(
    r"https?://[^\s]+?/sources/(?P<source>[^/]+)/concepts/(?P<code>[^/\s]+)/?"
)


def _parse_ocl_url(url: str | None) -> dict[str, str]:
    """Pull source mnemonic + numeric code out of an OCL URL, if it matches."""
    if not url:
        return {}
    m = _OCL_URL_RE.search(url)
    if not m:
        return {}
    return {
        "org": m.group("org"),
        "source": m.group("source"),
        "kind": m.group("kind"),
        "code": m.group("code"),
    }


def _extract_referred_concept(error_message: str | None) -> dict[str, str] | None:
    """Pull the source/code of the concept referenced in an error message, if any."""
    if not error_message:
        return None
    m = _REFERRED_CONCEPT_RE.search(error_message)
    if not m:
        return None
    return {"source": m.group("source"), "code": m.group("code")}


def _project_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Trim a raw error-item record down to the evidence we want to persist."""
    url = raw.get("url")
    identity = _parse_ocl_url(url)
    referred = _extract_referred_concept(raw.get("errorMessage"))
    record: dict[str, Any] = {
        "uuid": raw.get("uuid"),
        "type": raw.get("type"),
        "state": raw.get("state"),
        "url": url,
        "version_url": raw.get("versionUrl"),
        "hashed_url": raw.get("hashedUrl"),
        "updated_on": raw.get("updatedOn"),
        "error_message": raw.get("errorMessage"),
        "identity": identity or None,
    }
    if referred is not None:
        record["referenced_concept"] = referred
    return record


def _iter_error_items(uuid: str, *, page_size: int = 100) -> Iterable[dict[str, Any]]:
    """Yield every error item by following the paginated subresource cursor.

    Tries the canonical `/item?state=ERROR` shape first; if the server returns
    HTTP 404 we fall back to `/items` (older shape). The paginator follows the
    `rel=next` link returned by the OpenMRS REST module, falling back to
    `startIndex` arithmetic if no link is present.
    """
    base_candidates = (
        f"{bootstrap._IMP_URL}/{uuid}/item",
        f"{bootstrap._IMP_URL}/{uuid}/items",
    )
    base = None
    for candidate in base_candidates:
        params = urllib.parse.urlencode({"state": "ERROR", "v": "full", "limit": page_size})
        code, body, _hdrs = bootstrap._request("GET", f"{candidate}?{params}")
        if code == 200:
            base = candidate
            first = json.loads(body)
            break
    if base is None:
        raise RuntimeError(
            f"No working per-item subresource for import {uuid}; tried {list(base_candidates)}"
        )

    page = first
    start_index = 0
    while True:
        results = page.get("results", []) or []
        for r in results:
            yield r
        next_url = None
        for link in page.get("links", []) or []:
            if link.get("rel") == "next" and link.get("uri"):
                next_url = link["uri"]
                break
        if next_url:
            code, body, _ = bootstrap._request("GET", next_url)
            if code != 200:
                raise RuntimeError(f"GET {next_url} -> HTTP {code}: {body[:200]!r}")
            page = json.loads(body)
            continue
        # Some module versions don't emit a next link; fall back to startIndex.
        if len(results) < page_size:
            return
        start_index += len(results)
        params = urllib.parse.urlencode(
            {"state": "ERROR", "v": "full", "limit": page_size, "startIndex": start_index}
        )
        code, body, _ = bootstrap._request("GET", f"{base}?{params}")
        if code != 200:
            raise RuntimeError(f"GET {base} -> HTTP {code}: {body[:200]!r}")
        page = json.loads(body)


def build_payload(
    *,
    import_uuid: str,
    all_items_count: int,
    error_items_count: int,
    errors: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the on-disk JSON shape + compute the gate result."""
    if generated_at is None:
        generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rate = (error_items_count / all_items_count) if all_items_count else 0.0
    gate_passed = rate <= GATE_THRESHOLD
    return {
        "import_uuid": import_uuid,
        "all_items_count": all_items_count,
        "error_items_count": error_items_count,
        "error_rate": rate,
        "gate_threshold": GATE_THRESHOLD,
        "gate_passed": gate_passed,
        "generated_at": generated_at,
        "errors": errors,
    }


def enumerate_errors(uuid: str) -> dict[str, Any]:
    """Hit the live OpenMRS instance and assemble the audit payload."""
    record = bootstrap.get_import(uuid)
    all_items = int(record.get("allItemsCount", 0) or 0)
    errors_expected = int(record.get("errorItemsCount", 0) or 0)
    collected = [_project_item(r) for r in _iter_error_items(uuid)]
    return build_payload(
        import_uuid=uuid,
        all_items_count=all_items,
        error_items_count=errors_expected or len(collected),
        errors=collected,
    )


def default_run_id() -> str:
    return "dev-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def write_payload(payload: dict[str, Any], *, run_id: str, root: Path = Path("artifacts")) -> Path:
    out_dir = root / run_id / "profile"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "ciel-import-errors.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m harness.profile.ciel_import_errors",
        description="Enumerate per-item CIEL import errors and emit the audit JSON.",
    )
    p.add_argument("--uuid", required=True, help="openconceptlab import uuid")
    p.add_argument(
        "--run-id",
        default=None,
        help="run id for artifacts/<run-id>/profile/. Defaults to dev-<UTC timestamp>.",
    )
    p.add_argument(
        "--root",
        default="artifacts",
        help="root artifacts directory (default: artifacts)",
    )
    args = p.parse_args(argv)
    run_id = args.run_id or default_run_id()
    payload = enumerate_errors(args.uuid)
    out = write_payload(payload, run_id=run_id, root=Path(args.root))
    print(
        f"Wrote {out}\n"
        f"  all_items={payload['all_items_count']}"
        f"  errors={payload['error_items_count']}"
        f"  rate={payload['error_rate']:.6f}"
        f"  threshold={payload['gate_threshold']:.4f}"
        f"  gate_passed={payload['gate_passed']}"
    )
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
