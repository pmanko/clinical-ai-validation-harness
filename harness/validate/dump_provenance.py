"""Verify portable OpenMRS dump identity and consumer-module cleanliness."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stream(path: Path) -> BinaryIO:
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def verify_dump(
    dump_path: Path,
    provenance_path: Path,
    *,
    require_portable: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if not dump_path.is_file():
        return {}, [f"dump missing: {dump_path}"]
    if not provenance_path.is_file():
        return {}, [f"provenance missing: {provenance_path}"]
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"invalid provenance JSON: {exc}"]
    actual_sha = sha256_file(dump_path)
    if provenance.get("output_sha256") != actual_sha:
        issues.append(
            f"dump sha256 mismatch: expected {provenance.get('output_sha256')} actual {actual_sha}"
        )
    if provenance.get("output_bytes") != dump_path.stat().st_size:
        issues.append("dump byte size does not match provenance")
    prefixes = [
        str(prefix) for prefix in provenance.get("excluded_module_prefixes") or []
    ]
    module_state_included = bool(provenance.get("module_state_included"))
    if require_portable and module_state_included:
        issues.append("seed input must be a portable corpus without consumer-module state")
    if not module_state_included:
        missing_prefixes = {"chartsearchai", "querystore"} - set(prefixes)
        if missing_prefixes:
            issues.append(
                "portable corpus provenance must exclude chartsearchai and querystore; "
                f"missing {', '.join(sorted(missing_prefixes))}"
            )
        table_needles = {
            prefix: f"CREATE TABLE `{prefix}_".encode() for prefix in prefixes
        }
        changelog_header = b"INSERT INTO `liquibasechangelog`"
        with _stream(dump_path) as stream:
            for line in stream:
                for prefix, needle in table_needles.items():
                    if needle in line:
                        issues.append(f"consumer-module table survived: {prefix}")
                if changelog_header in line:
                    for prefix in prefixes:
                        if prefix.encode() in line:
                            issues.append(
                                f"consumer-module Liquibase row survived: {prefix}"
                            )
                if issues and any("survived" in issue for issue in issues):
                    break
    return provenance, issues
