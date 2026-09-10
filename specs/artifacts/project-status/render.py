#!/usr/bin/env python3
"""Render the repository status inventories without network or third-party tools."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


DIRECTORY = Path(__file__).resolve().parent
REPOSITORY = DIRECTORY.parents[2]
COMMON_ARTIFACT_COLUMNS = (
    ("id", "ID"),
    ("title", "Title"),
    ("role", "Role"),
    ("status", "Status"),
    ("next_update", "Next update"),
    ("url/path", "Source"),
)
VIEWS = {
    "efforts": (
        "Current efforts",
        (
            ("id", "ID"),
            ("title", "Effort"),
            ("status", "Status"),
            ("next_deliverable", "Next deliverable"),
            ("acceptance", "Acceptance"),
            ("sources", "Sources"),
        ),
    ),
    "roadmaps": ("Roadmaps and plans", COMMON_ARTIFACT_COLUMNS),
    "artifacts": ("Target artifacts", COMMON_ARTIFACT_COLUMNS),
    "public-surfaces": (
        "Public surfaces",
        (
            ("title", "Surface"),
            ("url", "Link"),
            ("role", "Role"),
            ("status", "Status"),
            ("next_update", "Next update"),
        ),
    ),
    "reports": (
        "Reports and evidence",
        (
            ("title", "Report"),
            ("family", "Family"),
            ("source_date", "Source date"),
            ("claim_limit", "What it establishes and its limits"),
            ("url", "Link"),
        ),
    ),
    "decisions": (
        "Decisions and owner review",
        (
            ("id", "ID"),
            ("title", "Decision"),
            ("state", "State"),
            ("next_action", "Next action"),
            ("source", "Source"),
        ),
    ),
    "sessions": (
        "Working sessions",
        (
            ("title", "Session"),
            ("system", "System"),
            ("last_work", "Last work"),
            ("state", "State"),
            ("source", "Source"),
        ),
    ),
    "pull-requests": (
        "Pull request inventory",
        (
            ("pr", "PR"),
            ("title", "Title"),
            ("state", "State"),
            ("head", "Head"),
            ("effort", "Effort"),
            ("currentSignal", "Current signal"),
            ("nextAction", "Next action"),
        ),
    ),
}
LINK_FIELDS = {"url", "path", "url/path", "source", "sources"}
URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def escape(value: Any) -> str:
    """Keep a value in one Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


@lru_cache(maxsize=8)
def committed_files(repository: Path) -> frozenset[str]:
    """Cache one committed file inventory; runtime files never create links."""
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-tree", "-r", "-z", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return frozenset(
        name
        for record in result.stdout.split("\0")
        for metadata, separator, name in [record.partition("\t")]
        if separator and metadata.startswith(("100644 blob ", "100755 blob "))
    )


def portable_target(target: str) -> str | None:
    """Resolve and check the same path for string and labeled references."""
    target = target.strip()
    if re.match(r"^https?://", target, re.I) or target.startswith("#"):
        return target
    if URL.match(target):
        return None
    path, separator, fragment = target.partition("#")
    if not separator:
        line_reference = re.fullmatch(r"(.+):(\d+)", path)
        if line_reference:
            path, separator, fragment = (
                line_reference.group(1),
                "#",
                f"L{line_reference.group(2)}",
            )
    status_relative = path.startswith(
        ("./", "../", "exports/", "reports/", "reviews/", "evidence/")
    ) or path in {
        f"{name}.{extension}" for name in VIEWS for extension in ("md", "json")
    }
    # Normalize lexically: following a machine-local symlink would make output
    # depend on the checkout's filesystem rather than its committed contents.
    local = Path(os.path.abspath((DIRECTORY if status_relative else REPOSITORY) / path))
    try:
        relative = local.relative_to(REPOSITORY)
    except ValueError:
        return None
    if relative.as_posix() not in committed_files(REPOSITORY):
        return None
    return os.path.relpath(local, DIRECTORY) + (
        separator + fragment if separator else ""
    )


def link(target: str, label: str = "Source") -> str:
    """Keep unavailable references readable without emitting a broken link."""
    destination = portable_target(target)
    if destination is None:
        reference = f"`{escape(target)}`"
        return (
            reference
            if label in ("Source", target)
            else f"{escape(label)} ({reference})"
        )
    # Angle-bracket destinations preserve spaces and parentheses in file names.
    target = (
        destination.replace("|", "%7C")
        .replace("<", "%3C")
        .replace(">", "%3E")
        .replace("\n", "%0A")
        .replace("\r", "%0D")
    )
    label = escape(label).replace("[", "\\[").replace("]", "\\]")
    return f"[{label}](<{target}>)"


def looks_like_path(value: str) -> bool:
    return (
        value.startswith(("/", "./", "../"))
        or ("/" in value and "\n" not in value and " " not in value)
        or bool(
            re.fullmatch(
                r"[^\s]+\.(?:md|json|jsonl|ya?ml|py|sh|toml|csv|html|sql)(?:#.*|:\d+)?",
                value,
            )
        )
    )


def cell(value: Any, field: str = "") -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        return "<br>".join(cell(item, field) for item in value)
    if isinstance(value, dict):
        target = value.get("url") or value.get("path") or value.get("href")
        if isinstance(target, str):
            label = value.get("label") or value.get("title") or value.get("name") or "Source"
            return link(target, str(label))
        return escape(json.dumps(value, ensure_ascii=False, sort_keys=True))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    if text.startswith("[") and "](" in text:
        return escape(text)
    if URL.match(text.strip()) and "\n" not in text:
        return link(text, "Open" if field == "url" else "Source")
    if field in LINK_FIELDS and looks_like_path(text):
        return link(text, text)
    return escape(text)


def row_value(row: dict[str, Any], field: str, name: str) -> str:
    if name == "pull-requests" and field == "pr":
        number = row.get("number")
        url = row.get("url")
        return link(url, f"#{number}") if isinstance(url, str) else cell(number)
    if name == "pull-requests" and field == "head":
        branch = cell(row.get("head"))
        sha = row.get("headSha")
        return f"{branch}<br>{escape(str(sha)[:12])}" if sha else branch
    if field == "url/path":
        return cell(row.get("url") or row.get("path"), field)
    return cell(row.get(field), field)


def read_inventory(name: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    source = DIRECTORY / f"{name}.json"
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{source.name}: expected a JSON object")
    row_key = "pullRequests" if name == "pull-requests" and "pullRequests" in payload else "rows"
    rows = payload.get(row_key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{source.name}: {row_key} must be an array of objects")
    ids: set[str] = set()
    for index, row in enumerate(rows, 1):
        if "id" in row:
            identifier = row["id"]
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"{source.name}: row {index} has an empty or non-string id")
            if identifier in ids:
                raise ValueError(f"{source.name}: duplicate id {identifier!r}")
            ids.add(identifier)
        if name == "pull-requests" and not isinstance(row.get("repository"), str):
            raise ValueError(f"{source.name}: row {index} requires a repository")
    return payload, rows, row_key


def pr_order(row: dict[str, Any]) -> tuple[int, int]:
    priority = {"open": 0, "merged": 1, "closed": 2}.get(str(row.get("state")), 3)
    number = row.get("number", 0)
    return priority, -number if isinstance(number, int) else 0


def table(name: str, rows: list[dict[str, Any]]) -> str:
    columns = VIEWS[name][1]
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(row_value(row, field, name) for field, _ in columns) + " |"
        for row in rows
    )
    return "\n".join(lines)


def markdown(name: str, payload: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    parts = [f"# {VIEWS[name][0]}"]
    as_of = payload.get("as_of") or payload.get("asOf")
    if as_of:
        parts.append(f"As of {escape(as_of)}. {len(rows)} entries.")
    else:
        parts.append(f"{len(rows)} entries. Snapshot date not recorded.")
    if payload.get("description"):
        parts.append(str(payload["description"]).strip())
    parts.append(f"[Source JSON]({name}.json) · [CSV export](exports/{name}.csv)")
    if name == "pull-requests":
        scope = payload.get("scope", {})
        if isinstance(scope, dict):
            statements = [scope.get("maintainedRepositoryRule"), scope.get("upstreamRule")]
            parts.extend(str(value) for value in statements if value)
        parts.append("Open pull requests appear first within each repository. Check dates and exact revisions remain in the source JSON and CSV; merged status does not establish product acceptance.")
        for repository in sorted({row["repository"] for row in rows}):
            group = sorted((row for row in rows if row["repository"] == repository), key=pr_order)
            parts.extend([f"## {escape(repository)}", table(name, group)])
    elif rows:
        parts.append(table(name, rows))
    else:
        parts.append("No entries recorded.")
    parts.append("Generated from the source JSON by `render.py`. Edit the JSON, then regenerate this view.")
    return "\n\n".join(parts) + "\n"


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def csv_export(payload: dict[str, Any], rows: list[dict[str, Any]], row_key: str) -> str:
    """Retain every row field and envelope field; nested values remain JSON."""
    metadata = {f"snapshot.{key}": value for key, value in payload.items() if key != row_key}
    row_fields = list(dict.fromkeys(key for row in rows for key in row))
    collision = set(row_fields).intersection(metadata)
    if collision:
        raise ValueError(f"CSV metadata fields conflict with row fields: {sorted(collision)}")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=row_fields + list(metadata), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_value(value) for key, value in {**row, **metadata}.items()})
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report missing or stale generated views without writing files")
    args = parser.parse_args()
    outputs: dict[Path, str] = {}
    try:
        # Validate and render every source before changing any generated file.
        for name in VIEWS:
            payload, rows, row_key = read_inventory(name)
            outputs[DIRECTORY / f"{name}.md"] = markdown(name, payload, rows)
            outputs[DIRECTORY / "exports" / f"{name}.csv"] = csv_export(payload, rows, row_key)
    except ValueError as exc:
        print(f"Inventory error: {exc}", file=sys.stderr)
        return 2
    differences = []
    for path, expected in outputs.items():
        try:
            actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            actual = None
        if actual != expected:
            differences.append(path)
    if args.check:
        if differences:
            for path in differences:
                print(f"Out of date: {path.relative_to(REPOSITORY)}", file=sys.stderr)
            return 1
        print(f"All {len(outputs)} generated views match their JSON sources.")
        return 0
    for path in differences:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(outputs[path], encoding="utf-8")
    print(f"Updated {len(differences)} of {len(outputs)} generated views.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
