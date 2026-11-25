"""Blind-session and multi-judge orchestration for validation-harness runs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from typing import Any

from .judging import judge_summary
from .report import build_report
from .resources import (
    read_judge_brief_bytes,
    read_judge_brief_text,
    read_rubric_bytes,
)

HARNESS_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_JUDGE_SETTINGS = {
    "claude": ("claude-sonnet-5-5", "medium"),
    "codex": ("gpt-6.1-sol", "medium"),
    "gemini": ("unrecorded", "unrecorded"),
    "human": ("human", ""),
}

_BASE_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "TERM",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
)

_AGENT_ENV_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "claude": (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CONFIG_DIR",
    ),
    "codex": (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "CODEX_HOME",
    ),
    "gemini": (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
    ),
    "human": (),
}

_ALLOC_LOCK = threading.Lock()


def _minimal_judge_env(agent: str, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Construct a minimal environment for judge subprocesses, stripping ambient credentials."""
    allowed = set(_BASE_ENV_ALLOWLIST) | set(_AGENT_ENV_ALLOWLIST.get(agent, ()))
    clean = {k: v for k, v in os.environ.items() if k in allowed}
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                clean[str(k)] = str(v)
    return clean


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _copy_contained_dir(src_dir: Path, dst_dir: Path, root_dir: Path) -> None:
    """Copy a directory tree into staged judge inputs, rejecting symlinks and paths outside `root_dir`."""
    root_resolved = root_dir.resolve()
    if src_dir.is_symlink():
        raise SystemExit(f"Refusing symlinked directory in judge input: {src_dir}")
    src_resolved = src_dir.resolve()
    if not _is_within(src_resolved, root_resolved):
        raise SystemExit(f"Refusing directory outside run_dir ({root_resolved}): {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=False):
        dp = Path(dirpath)
        if dp.is_symlink() or not _is_within(dp.resolve(), root_resolved):
            raise SystemExit(f"Refusing symlink or escaped directory in judge input: {dp}")
        rel_dir = dp.relative_to(src_dir)
        target_dp = dst_dir / rel_dir
        target_dp.mkdir(parents=True, exist_ok=True)
        for dn in dirnames:
            sub = dp / dn
            if sub.is_symlink() or not _is_within(sub.resolve(), root_resolved):
                raise SystemExit(f"Refusing symlinked subdirectory in judge input: {sub}")
        for fn in filenames:
            fp = dp / fn
            if fp.is_symlink() or not _is_within(fp.resolve(), root_resolved):
                raise SystemExit(f"Refusing symlinked file in judge input: {fp}")
            if fp.is_file():
                shutil.copy2(fp, target_dp / fn)


def _chmod_tree_writable(root: Path) -> None:
    """Restore owner write permissions before cleaning up a read-only staged tree."""
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        try:
            dp.chmod(stat.S_IRWXU)
        except OSError:
            pass
        for fn in filenames:
            fp = dp / fn
            if not fp.is_symlink():
                try:
                    fp.chmod(stat.S_IRUSR | stat.S_IWUSR)
                except OSError:
                    pass
        for dn in dirnames:
            sub = dp / dn
            if not sub.is_symlink():
                try:
                    sub.chmod(stat.S_IRWXU)
                except OSError:
                    pass


def _chmod_tree_readonly(root: Path) -> None:
    """Lock staged judge inputs read-only (`0444` files, `0555` dirs) before running a judge."""
    for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if not fp.is_symlink():
                fp.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        dp.chmod(
            stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        )


@contextmanager
def _run_judge_lock(run_dir: Path):
    """Process- and thread-safe lock around pass reservation and finalization."""
    judges_dir = run_dir / "judges"
    judges_dir.mkdir(parents=True, exist_ok=True)
    lock_path = judges_dir / ".alloc.lock"
    with _ALLOC_LOCK:
        with open(lock_path, "a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield judges_dir
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _pending_human_path(run_dir: Path) -> Path:
    return run_dir / "judges" / ".pending-human.json"


def _has_human_judge(judges: list[dict[str, Any]]) -> bool:
    return any(str(j.get("agent")) == "human" for j in judges)


def _load_pending_human(
    run_dir: Path,
    judges: list[dict[str, Any]],
    *,
    adding: bool | None = None,
) -> dict[str, Any] | None:
    p = _pending_human_path(run_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("judges") != judges:
        return None
    if adding is not None and bool(data.get("adding", False)) != bool(adding):
        return None
    return data


def _save_pending_human(run_dir: Path, payload: dict[str, Any]) -> None:
    p = _pending_human_path(run_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def _clear_pending_human(run_dir: Path) -> None:
    _pending_human_path(run_dir).unlink(missing_ok=True)


def last_json(text: str) -> Any:
    """The last ```json block of a judge's answer, parsed (with trailing-comma repair outside strings)."""
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    if not blocks:
        raise SystemExit("the judge's answer has no ```json block")
    block = blocks[-1]
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        repaired = re.sub(
            r'("(?:\\.|[^"\\])*")|,\s*([}\]])',
            lambda m: m.group(1) if m.group(1) is not None else m.group(2),
            block,
        )
        return json.loads(repaired)


def parse_judges(args: Any) -> list[dict[str, Any]]:
    """Parse `--judge agent:model:effort[:passes]` specifications or fall back to default agent."""
    raw_passes = getattr(args, "judge_passes", 1)
    default = 1 if raw_passes is None else int(raw_passes)
    if default < 1:
        raise SystemExit(f"--judge-passes must be at least 1, got {raw_passes!r}")
    judges: list[dict[str, Any]] = []
    for spec in getattr(args, "judges", None) or []:
        parts = spec.split(":")
        if len(parts) not in (3, 4) or not all(parts) or (len(parts) == 4 and not parts[3].isdigit()):
            raise SystemExit(f"--judge wants agent:model:effort[:passes], got {spec!r}")
        passes = int(parts[3]) if len(parts) == 4 else default
        if passes < 1:
            raise SystemExit(f"--judge {spec!r}: passes must be at least 1")
        judges.append({"agent": parts[0], "model": parts[1], "effort": parts[2], "passes": passes})
    if judges:
        return judges
    agent = getattr(args, "agent", "claude") or "claude"
    default_model, default_effort = DEFAULT_JUDGE_SETTINGS.get(agent, ("gpt-6.1-sol", "medium"))
    return [
        {
            "agent": agent,
            "model": os.environ.get("REVIEW_MODEL") or default_model,
            "effort": os.environ.get("REVIEW_REASONING") or default_effort,
            "passes": default,
        }
    ]


def run_judges(run_dir: Path) -> tuple[list[str], dict[tuple[str, str, str], int], bool]:
    """Return `(built_from, highest_pass_by_judge, blinded)` for an existing run directory."""
    try:
        built = (
            json.loads((run_dir / "judges" / "canonical.json").read_text(encoding="utf-8")).get(
                "built_from"
            )
            or []
        )
    except (OSError, json.JSONDecodeError):
        built = []
    last: dict[tuple[str, str, str], int] = {}
    blinded = False
    for manifest in sorted((run_dir / "judges").glob("*/manifest.json")):
        try:
            card = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = (
            str(card.get("agent") or ""),
            str(card.get("model") or ""),
            str(card.get("reasoning_effort") or ""),
        )
        last[key] = max(last.get(key, 0), int(card.get("pass_index") or 1))
        blinded = blinded or (manifest.parent.name in built and bool(card.get("blinded")))
    return [str(a) for a in built], last, blinded


def _reserve_judge_passes(
    run_dir: Path, judges: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], int, int]]:
    """Atomically reserve contiguous pass numbers for each judge before sessions run."""
    with _run_judge_lock(run_dir) as judges_dir:
        _, last, _ = run_judges(run_dir)
        res_file = judges_dir / ".reserved.json"
        try:
            raw_res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else {}
        except (OSError, json.JSONDecodeError):
            raw_res = {}
        reserved: dict[tuple[str, str, str], int] = {}
        for k_str, val in raw_res.items():
            parts = k_str.split("\0")
            if len(parts) == 3 and isinstance(val, int):
                reserved[(parts[0], parts[1], parts[2])] = val
        allocations: list[tuple[dict[str, Any], int, int]] = []
        for judge in judges:
            key = (str(judge["agent"]), str(judge["model"]), str(judge["effort"]))
            start = max(last.get(key, 0), reserved.get(key, 0))
            end = start + int(judge["passes"])
            reserved[key] = end
            allocations.append((judge, start, end))
        res_file.write_text(
            json.dumps({"\0".join(k): v for k, v in reserved.items()}, indent=1),
            encoding="utf-8",
        )
        return allocations


def _rollback_judge_passes(
    run_dir: Path,
    allocations: list[tuple[dict[str, Any], int, int]],
    done_by_key: dict[tuple[str, str, str], int],
) -> None:
    """Roll back unfinalized pass reservations when a judge pass fails mid-run."""
    with _run_judge_lock(run_dir) as judges_dir:
        res_file = judges_dir / ".reserved.json"
        if not res_file.is_file():
            return
        try:
            raw_res = json.loads(res_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw_res, dict):
            return
        reserved: dict[tuple[str, str, str], int] = {}
        for k_str, val in raw_res.items():
            parts = k_str.split("\0")
            if len(parts) == 3 and isinstance(val, int):
                reserved[(parts[0], parts[1], parts[2])] = val
        _, last, _ = run_judges(run_dir)
        by_key: dict[tuple[str, str, str], tuple[int, int]] = {}
        for judge, start, end in allocations:
            key = (str(judge["agent"]), str(judge["model"]), str(judge["effort"]))
            prev = by_key.get(key)
            by_key[key] = (
                start if prev is None else min(prev[0], start),
                end if prev is None else max(prev[1], end),
            )
        changed = False
        for key, (start, end) in by_key.items():
            if reserved.get(key) == end:
                rollback_to = max(last.get(key, 0), start + done_by_key.get(key, 0))
                if rollback_to != end:
                    if rollback_to <= 0:
                        reserved.pop(key, None)
                    else:
                        reserved[key] = rollback_to
                    changed = True
        if changed:
            res_file.write_text(
                json.dumps({"\0".join(k): v for k, v in reserved.items()}, indent=1),
                encoding="utf-8",
            )


def _expected_session_cells(cells_path: Path) -> list[tuple[str, str]]:
    if not cells_path.is_file():
        return []
    expected: list[tuple[str, str]] = []
    for line in cells_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cell = json.loads(line)
        expected.append((str(cell["scenario_id"]), str(cell["backend_id"])))
    return expected


def _validate_session_rows(rows: Any, expected: list[tuple[str, str]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("verdict JSON must be a non-empty list of cell rows")
    seen: list[tuple[str, str]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {idx} is not an object")
        for req in ("scenario_id", "backend_id", "accuracy"):
            if req not in row:
                raise ValueError(f"row {idx} is missing {req!r}")
        for axis in ("accuracy", "completeness", "relevance"):
            if axis in row:
                val = row[axis]
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    raise ValueError(f"row {idx} {axis!r} must be numeric")
        if "harm" in row and not isinstance(row["harm"], bool):
            raise ValueError(f"row {idx} 'harm' must be boolean")
        seen.append((str(row["scenario_id"]), str(row["backend_id"])))
    if len(set(seen)) != len(seen):
        raise ValueError("duplicate (scenario_id, backend_id) in verdict rows")
    if expected and set(seen) != set(expected):
        missing = sorted(set(expected) - set(seen))
        extra = sorted(set(seen) - set(expected))
        raise ValueError(f"cell coverage mismatch (missing={missing}, unexpected={extra})")
    return rows


def _wrap_long_lines(text: str, limit: int = 1600) -> str:
    """Split single lines exceeding `limit` characters so read-only viewers never truncate them."""
    if not text:
        return text
    if limit < 16:
        limit = 16
    out: list[str] = []
    cont_prefix = "  ↳ "
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        if len(raw_line) <= limit:
            out.append(raw_line)
            continue
        rest = raw_line
        prefix = ""
        while rest:
            avail = limit if not prefix else max(8, limit - len(prefix))
            if len(rest) <= avail:
                out.append(prefix + rest)
                break
            cut = max(rest.rfind(" ", 1, avail + 1), rest.rfind("\t", 1, avail + 1))
            if cut > 0 and rest[:cut].strip():
                out.append(prefix + rest[:cut].rstrip())
                rest = rest[cut + 1 :].lstrip()
            else:
                out.append(prefix + rest[:avail])
                rest = rest[avail:]
            prefix = cont_prefix
    return "\n".join(out)


def _safe_cell_stem(backend_id: str, index: int, used: set[str]) -> str:
    """Build a collision-free filesystem stem preserving blinded arm letters verbatim."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(backend_id)).strip("_") or f"arm_{index}"
    if stem in {".", ".."}:
        stem = f"arm_{index}"
    candidate = stem
    if candidate in used:
        suffix = index
        candidate = f"{stem}_{suffix}"
        while candidate in used:
            suffix += 1
            candidate = f"{stem}_{suffix}"
    used.add(candidate)
    return candidate


def _render_cell_markdown(cell: dict[str, Any]) -> str:
    """Render one judge cell into unescaped multi-line Markdown with short readable lines."""
    scenario_id = cell.get("scenario_id", "")
    backend_id = cell.get("backend_id", "")
    lines = [
        f"# Cell: scenario_id={scenario_id} | backend_id={backend_id}",
        "",
        f"- **scenario_id**: {scenario_id}",
        f"- **backend_id**: {backend_id}",
        f"- **reference_date**: {cell.get('reference_date')}",
        f"- **is_team**: {cell.get('is_team')}",
        f"- **has_in_depth**: {cell.get('has_in_depth')}",
        f"- **score_background**: {cell.get('score_background')}",
        f"- **should_abstain**: {cell.get('should_abstain')}",
        f"- **n_turns**: {cell.get('n_turns')}",
        f"- **snapshot_file**: {cell.get('snapshot_file')}",
        f"- **in_depth_status**: {cell.get('in_depth_status')}",
        f"- **patient**: {json.dumps(cell.get('patient'), ensure_ascii=False)}",
    ]
    if cell.get("what_it_tests"):
        lines.append(f"- **what_it_tests**: {cell.get('what_it_tests')}")
    if cell.get("reference_verification_notes"):
        lines.append(
            f"- **reference_verification_notes**: {cell.get('reference_verification_notes')}"
        )
    if cell.get("temporal_facts_summary") is not None:
        lines.extend(
            [
                "- **temporal_facts_summary**:",
                "```json",
                json.dumps(cell.get("temporal_facts_summary"), indent=2, ensure_ascii=False),
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Citation Resolution (Deterministic Layer 1)",
            "",
            "```json",
            json.dumps(cell.get("citation_resolution"), indent=2, ensure_ascii=False),
            "```",
            "",
            "### Source Diagnostics",
            "",
            "```json",
            json.dumps(cell.get("source_diagnostics"), indent=2, ensure_ascii=False),
            "```",
            "",
            "## Turns / Questions",
        ]
    )
    turns = cell.get("turns") or []
    if not turns:
        lines.append("(none)")
    else:
        for t_idx, turn in enumerate(turns, 1):
            if not isinstance(turn, dict):
                lines.append(f"- {turn}")
                continue
            tn = turn.get("n", t_idx)
            lines.extend(["", f"### Turn {tn} Question", str(turn.get("question") or "")])
            if len(turns) > 1 and t_idx < len(turns) and turn.get("answer_section"):
                lines.extend(
                    ["", f"### Turn {tn} Answer Section", str(turn.get("answer_section") or "")]
                )

    lines.extend(["", "## Final Answer Section", str(cell.get("answer_section") or "")])
    if cell.get("in_depth_section"):
        lines.extend(["", "## Final In-Depth Section", str(cell.get("in_depth_section") or "")])

    lines.extend(["", "## References"])
    refs = cell.get("references") or []
    if not refs:
        lines.append("(none)")
    else:
        for ref in refs:
            lines.append(f"- {json.dumps(ref, ensure_ascii=False)}")

    lines.extend(["", "## Cited Sources"])
    sources = cell.get("sources") or []
    if not sources:
        lines.append("(none)")
    else:
        for s_idx, src in enumerate(sources, 1):
            if not isinstance(src, dict):
                lines.append(f"- {src}")
                continue
            label = src.get("source_id") or src.get("citation_index") or s_idx
            lines.extend(
                [
                    "",
                    f"### Source {s_idx}: {label}",
                    f"- **source_id**: {src.get('source_id')}",
                    f"- **citation_index**: {src.get('citation_index')}",
                    f"- **record_index**: {src.get('record_index')}",
                    f"- **chart_record_index**: {src.get('chart_record_index')}",
                    f"- **resource_type**: {src.get('resource_type')}",
                    f"- **resource_uuid**: {src.get('resource_uuid')}",
                    f"- **date**: {src.get('date')}",
                    f"- **title**: {src.get('title')}",
                    f"- **resolution_status**: {src.get('resolution_status')}",
                    f"- **facts_used**: {json.dumps(src.get('facts_used'), ensure_ascii=False)}",
                    "",
                    "**source_text**:",
                    str(src.get("source_text") or ""),
                ]
            )

    return _wrap_long_lines("\n".join(lines).rstrip() + "\n", limit=1600)


def _copy_maybe_wrapped_chart_file(src: Path, dst: Path, limit: int = 1600) -> None:
    """Copy a chart snapshot file, wrapping lines over `limit` chars in `.txt` files."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".txt":
        raw = src.read_text(encoding="utf-8", errors="replace")
        if any(len(line) > limit for line in raw.replace("\r\n", "\n").split("\n")):
            dst.write_text(_wrap_long_lines(raw, limit=limit), encoding="utf-8")
            return
    shutil.copy2(src, dst)


def _wrap_txt_files_in_dir(root: Path, limit: int = 1600) -> None:
    """Wrap overly long single lines in staged `.txt` chart files in place."""
    if not root.exists():
        return
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if fp.suffix.lower() != ".txt" or not fp.is_file() or fp.is_symlink():
                continue
            raw = fp.read_text(encoding="utf-8", errors="replace")
            if any(len(line) > limit for line in raw.replace("\r\n", "\n").split("\n")):
                fp.write_text(_wrap_long_lines(raw, limit=limit), encoding="utf-8")


def _prepare_blind_session_dir(
    run_dir: Path, out_dir: Path, tag: str, bundle: Path
) -> tuple[Path, Path]:
    """Create a read-only bounded directory with only this session's bundle, cell Markdown files, rubric, and chart snapshots."""
    if bundle.is_symlink():
        raise SystemExit(f"Refusing symlinked bundle input: {bundle}")
    charts_src = run_dir / "charts"
    if charts_src.is_symlink():
        raise SystemExit(f"Refusing symlinked charts directory in run packet: {charts_src}")

    parsed_cells = [
        json.loads(line)
        for line in bundle.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    session_dir = out_dir / f"{tag}-input-{bundle.stem}"
    if session_dir.exists():
        _chmod_tree_writable(session_dir)
        shutil.rmtree(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    staged_bundle = session_dir / bundle.name
    shutil.copy2(bundle, staged_bundle)
    (session_dir / "rubric.md").write_bytes(read_rubric_bytes())

    cells_dir = session_dir / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    used_stems: set[str] = set()
    index_lines = [
        f"# Cell Index ({len(parsed_cells)} expected rows)",
        "",
    ]
    for idx, cell in enumerate(parsed_cells, 1):
        stem = _safe_cell_stem(str(cell.get("backend_id") or f"arm_{idx}"), idx, used_stems)
        cell_file = cells_dir / f"{stem}.md"
        cell_file.write_text(_render_cell_markdown(cell), encoding="utf-8")
        index_lines.append(
            f"- `scenario_id={cell.get('scenario_id')}` | `backend_id={cell.get('backend_id')}` -> `cells/{stem}.md`"
        )
    (cells_dir / "INDEX.md").write_text("\n".join(index_lines).rstrip() + "\n", encoding="utf-8")

    if charts_src.exists():
        if not charts_src.is_dir():
            raise SystemExit(f"Expected charts to be a real directory inside {run_dir}: {charts_src}")
        targeted_sources: list[tuple[Path, Path]] = []
        can_target = bool(parsed_cells) and all(
            isinstance(c.get("snapshot_file"), str) and str(c.get("snapshot_file")).strip()
            for c in parsed_cells
        )
        if can_target:
            charts_resolved = charts_src.resolve()
            rel_snapshots = list(
                dict.fromkeys(str(c["snapshot_file"]).strip() for c in parsed_cells)
            )
            for rel_str in rel_snapshots:
                rel_path = Path(rel_str)
                if rel_path.is_absolute():
                    raise SystemExit(f"Refusing chart snapshot outside charts directory: {rel_str}")
                cur = run_dir
                for part in rel_path.parts:
                    cur = cur / part
                    if cur.is_symlink():
                        raise SystemExit(f"Refusing symlinked chart snapshot in judge input: {cur}")
                cand = run_dir / rel_path
                if not cand.exists() or not cand.is_file():
                    can_target = False
                    break
                cand_resolved = cand.resolve()
                if not _is_within(cand_resolved, charts_resolved):
                    raise SystemExit(f"Refusing chart snapshot outside {charts_src}: {rel_str}")
                targeted_sources.append((cand, cand_resolved.relative_to(charts_resolved)))

        if can_target and targeted_sources:
            staged_charts = session_dir / "charts"
            staged_charts.mkdir(parents=True, exist_ok=True)
            for src_file, rel_inside_charts in targeted_sources:
                _copy_maybe_wrapped_chart_file(src_file, staged_charts / rel_inside_charts)
        else:
            _copy_contained_dir(charts_src, session_dir / "charts", run_dir)
            _wrap_txt_files_in_dir(session_dir / "charts")
    _chmod_tree_readonly(session_dir)
    return session_dir, staged_bundle


def run_judge_role(
    args: Any,
    workdir: Path,
    prompt: str,
    out: Path,
    *,
    agent: str,
    env: dict[str, str] | None = None,
) -> str:
    """Run one fresh read-only sandboxed session of the judge agent and record `<out>.card.json`."""
    prompt_file = out.with_suffix(".prompt.md")
    full_prompt = (
        prompt
        + "\nOperate strictly read-only over the staged session directory: do not execute shell commands, "
        "fetch network URLs, or write files.\n"
        + "\nYour final message is saved as your answer: emit your JSON verdict block directly in your response.\n"
    )
    if agent == "human" and out.exists() and prompt_file.exists():
        previous_prompt = prompt_file.read_text(encoding="utf-8")
        if previous_prompt != full_prompt:
            archive = (
                out.parent
                / "history"
                / hashlib.sha256(previous_prompt.encode() + out.read_bytes()).hexdigest()[:16]
            )
            archive.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, archive / out.name)
            (archive / prompt_file.name).write_text(previous_prompt, encoding="utf-8")
            out.unlink()
    prompt_file.write_text(full_prompt, encoding="utf-8")

    eff_env = _minimal_judge_env(agent, env)
    default_model, default_effort = DEFAULT_JUDGE_SETTINGS.get(agent, ("gpt-6.1-sol", "medium"))
    model = eff_env.get("REVIEW_MODEL") or default_model
    reasoning = eff_env.get("REVIEW_REASONING") or default_effort
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = ""
    rc = 0

    if agent == "claude":
        try:
            version = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, env=eff_env
            ).stdout.splitlines()[0]
        except Exception:
            version = ""
        with prompt_file.open("rb") as stdin_fh, out.open("w", encoding="utf-8") as stdout_fh:
            rc = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--model",
                    model,
                    "--effort",
                    reasoning,
                    "--permission-mode",
                    "plan",
                    "--permission-prompts",
                    "none",
                    "--tools",
                    "Read,Grep,Glob",
                    "--allowedTools",
                    "Read,Grep,Glob",
                    "--disallowedTools",
                    "Bash,Edit,Write,WebFetch,WebSearch",
                ],
                cwd=workdir,
                stdin=stdin_fh,
                stdout=stdout_fh,
                env=eff_env,
            ).returncode
    elif agent == "codex":
        try:
            raw_v = subprocess.run(
                ["codex", "--version"], capture_output=True, text=True, env=eff_env
            ).stdout.splitlines()[0]
            version = re.sub(r"^codex-cli\s+", "", raw_v)
        except Exception:
            version = ""
        log_path = Path(f"{out}.log")
        with prompt_file.open("rb") as stdin_fh, log_path.open("w", encoding="utf-8") as log_fh:
            rc = subprocess.run(
                [
                    "codex",
                    "exec",
                    "--skip-git-repo-check",
                    "-C",
                    str(workdir),
                    "-s",
                    "read-only",
                    "-m",
                    model,
                    "-c",
                    f'model_reasoning_effort="{reasoning}"',
                    "-o",
                    str(out),
                    "-",
                ],
                stdin=stdin_fh,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=eff_env,
            ).returncode
    elif agent == "gemini":
        try:
            version = subprocess.run(
                ["gemini", "--version"], capture_output=True, text=True, env=eff_env
            ).stdout.splitlines()[0]
        except Exception:
            version = ""
        cmd = ["gemini", "--sandbox", "--approval-mode", "plan"]
        if eff_env.get("REVIEW_MODEL"):
            cmd.extend(["-m", model])
        cmd.extend(["-p", "Follow the instructions given on stdin."])
        with prompt_file.open("rb") as stdin_fh, out.open("w", encoding="utf-8") as stdout_fh:
            rc = subprocess.run(cmd, cwd=workdir, stdin=stdin_fh, stdout=stdout_fh, env=eff_env).returncode
    elif agent == "human":
        if not out.is_file() or out.stat().st_size == 0:
            print(f"judge: read {prompt_file}, work in {workdir}, write your answer to {out}, then re-run.")
            sys.exit(3)
        model = eff_env.get("REVIEW_MODEL") or "human"
        reasoning = ""
        version = ""
    else:
        raise SystemExit(f"unknown judge agent {agent!r}")

    finished = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    card_payload = {
        "agent": agent,
        "agent_version": version,
        "model": model,
        "reasoning_effort": reasoning,
        "sampling": "provider default",
        "role": "judge",
        "started_at": started,
        "finished_at": finished,
    }
    Path(f"{out}.card.json").write_text(json.dumps(card_payload) + "\n", encoding="utf-8")
    if rc or not out.exists():
        raise SystemExit(f"judge failed (exit {rc}); see {out}")
    return out.read_text(encoding="utf-8")


def judge_card(answer: Path, pass_index: int, passes: int) -> Path:
    """Attach `brief_sha256`, `brief_path`, `pass_index`, and `passes` to the session card."""
    session = json.loads(answer.with_suffix(".md.card.json").read_text(encoding="utf-8"))
    brief_bytes = read_judge_brief_bytes()
    session.update(
        {
            "brief_sha256": hashlib.sha256(brief_bytes).hexdigest(),
            "brief_path": ".claude/skills/clinical-answer-scoring/judge.md",
            "pass_index": pass_index,
            "passes": passes,
        }
    )
    card = answer.with_suffix(".card.json")
    card.write_text(json.dumps(session, indent=1), encoding="utf-8")
    return card


def _resolved_judge_identity(
    judge: dict[str, Any], env: dict[str, str] | None
) -> tuple[str, str, str]:
    agent_name = str(judge.get("agent") or "")
    eff_env = _minimal_judge_env(agent_name, env)
    default_model, default_effort = DEFAULT_JUDGE_SETTINGS.get(
        agent_name, ("gpt-6.1-sol", "medium")
    )
    model = eff_env.get("REVIEW_MODEL") or default_model
    reasoning = eff_env.get("REVIEW_REASONING") or default_effort
    return agent_name, model, reasoning


def _try_reuse_session(
    out: Path,
    expected: list[tuple[str, str]],
    judge: dict[str, Any],
    env: dict[str, str] | None,
) -> list[dict[str, Any]] | None:
    """Return validated rows from an existing cached session output matching this judge identity."""
    card_path = Path(f"{out}.card.json")
    if not out.is_file() or not card_path.is_file():
        return None
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if not isinstance(card, dict):
            return None
        exp_identity = _resolved_judge_identity(judge, env)
        got_identity = (
            str(card.get("agent") or ""),
            str(card.get("model") or ""),
            str(card.get("reasoning_effort") or ""),
        )
        if got_identity != exp_identity:
            return None
        return _validate_session_rows(last_json(out.read_text(encoding="utf-8")), expected)
    except (OSError, json.JSONDecodeError, ValueError, SystemExit):
        return None


def judge_sessions(
    args: Any,
    run_dir: Path,
    out_dir: Path,
    pass_index: int,
    passes: int,
    judge: dict[str, Any],
    blind: bool,
    tag: str = "judge",
) -> tuple[Path, Path]:
    """Run one pass of one judge across `judge-cells.jsonl` or blinded `judge-bundles/*.jsonl`."""
    base = out_dir / f"{tag}.md"
    brief = read_judge_brief_text()
    env = {
        k: str(v)
        for k, v in (("REVIEW_MODEL", judge.get("model")), ("REVIEW_REASONING", judge.get("effort")))
        if v
    }
    run_resolved = run_dir.resolve()
    if blind:
        bundles_dir = run_dir / "judge-bundles"
        if bundles_dir.is_symlink() or (
            bundles_dir.exists() and not _is_within(bundles_dir.resolve(), run_resolved)
        ):
            raise SystemExit(f"Refusing symlinked or escaped judge-bundles directory: {bundles_dir}")
        bundles = sorted(bundles_dir.glob("*.jsonl"))
        if not bundles:
            raise SystemExit(f"{run_dir}: no judge-bundles; run judge_prep with --blind")
        sessions = []
        for b in bundles:
            if b.is_symlink() or not _is_within(b.resolve(), run_resolved):
                raise SystemExit(f"Refusing symlinked or escaped bundle file: {b}")
            s_dir, s_bundle = _prepare_blind_session_dir(run_dir, out_dir, tag, b)
            rubric_staged = s_dir / "rubric.md"
            expected_arms = list(dict.fromkeys(bid for _, bid in _expected_session_cells(s_bundle)))
            arm_list = ", ".join(expected_arms)
            s_inputs = (
                f"\n## Inputs\n\n- Session directory (bounded read-only input containing only this scenario's "
                f"bundle, rubric, per-cell Markdown files, and chart snapshots; do not read outside {s_dir}): {s_dir}\n"
                f"- Rubric: {rubric_staged}\n"
                f"- Per-cell readable Markdown files (read INDEX.md and each .md file in {s_dir / 'cells'} "
                f"so long JSONL lines are never truncated; you MUST emit a verdict row for EVERY expected "
                f"backend_id [{arm_list}]): {s_dir / 'cells'}\n"
                f"- Cells bundle for this session: {s_bundle} (one scenario; its arms are lettered, so score each "
                "answer on its own against the chart and keep the letter as backend_id)\n"
            )
            sessions.append((out_dir / f"{tag}-{b.stem}.md", brief + s_inputs, s_dir, s_bundle))
    else:
        cells_src = run_dir / "judge-cells.jsonl"
        if cells_src.is_symlink() or (
            cells_src.exists() and not _is_within(cells_src.resolve(), run_resolved)
        ):
            raise SystemExit(f"Refusing symlinked or escaped judge-cells.jsonl: {cells_src}")
        if not cells_src.is_file():
            raise SystemExit(f"{run_dir}: missing judge-cells.jsonl; run judge_prep first")
        s_dir, s_cells = _prepare_blind_session_dir(run_dir, out_dir, tag, cells_src)
        rubric_staged = s_dir / "rubric.md"
        expected_arms = list(dict.fromkeys(bid for _, bid in _expected_session_cells(s_cells)))
        arm_list = ", ".join(expected_arms)
        inputs = (
            f"\n## Inputs\n\n- Session directory (bounded read-only input): {s_dir}\n"
            f"- Rubric: {rubric_staged}\n"
            f"- Per-cell readable Markdown files (read INDEX.md and each .md file in {s_dir / 'cells'} "
            f"so long JSONL lines are never truncated; you MUST emit a verdict row for EVERY expected "
            f"backend_id [{arm_list}]): {s_dir / 'cells'}\n"
            f"- Cells bundle for this session: {s_cells}\n"
        )
        sessions = [(base, brief + inputs, s_dir, s_cells)]

    attempts = max(1, int(os.environ.get("JUDGE_ATTEMPTS", "4")))
    retry_delay = int(os.environ.get("JUDGE_RETRY_DELAY", "60"))
    can_resume_cached = bool(getattr(args, "work_dir", None)) and str(judge.get("agent")) != "human"

    def one(session: tuple[Path, str, Path, Path]) -> list[dict[str, Any]]:
        out, prompt, workdir, cells_path = session
        expected = _expected_session_cells(cells_path)
        if can_resume_cached:
            cached = _try_reuse_session(out, expected, judge, env)
            if cached is not None:
                return cached
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            attempt_prompt = prompt
            if attempt > 1 and last_error:
                cells_dir = workdir / "cells"
                attempt_prompt = (
                    prompt
                    + f"\n\nIMPORTANT RETRY NOTE (attempt {attempt}/{attempts}): Your previous attempt failed validation ({last_error}). "
                    f"Read {cells_dir / 'INDEX.md'} and every arm file in {cells_dir} individually, then emit a single ```json array containing ALL {len(expected)} expected (scenario_id, backend_id) rows.\n"
                )
            try:
                answer = run_judge_role(args, workdir, attempt_prompt, out, agent=str(judge["agent"]), env=env)
                return _validate_session_rows(last_json(answer), expected)
            except SystemExit as e:
                if e.code == 3 or attempt == attempts:
                    raise
                last_error = str(e)
            except (json.JSONDecodeError, ValueError) as e:
                if attempt == attempts:
                    raise SystemExit(f"{out}: the judge's verdict block is invalid ({e})")
                last_error = str(e)
            time.sleep(retry_delay * attempt)
        return []

    if str(judge.get("agent")) == "human":
        rows = []
        waiting_human = False
        for s in sessions:
            try:
                rows.extend(one(s))
            except SystemExit as e:
                if e.code == 3:
                    waiting_human = True
                else:
                    raise
        if waiting_human:
            sys.exit(3)
    else:
        parallel = max(1, int(os.environ.get("JUDGE_PARALLEL", "4")))
        with ThreadPoolExecutor(max_workers=min(parallel, len(sessions))) as pool:
            rows = [r for session_rows in pool.map(one, sessions) for r in session_rows]

    rows_path = base.with_suffix(".rows.json")
    rows_path.write_text(json.dumps(rows), encoding="utf-8")
    cards = [
        json.loads(out.with_suffix(".md.card.json").read_text(encoding="utf-8"))
        for out, _, _, _ in sessions
    ]
    identities = {
        (
            c.get("agent"),
            c.get("agent_version"),
            c.get("model"),
            c.get("reasoning_effort"),
            c.get("sampling"),
        )
        for c in cards
    }
    if len(identities) > 1:
        raise SystemExit(f"{base}: session cards diverged within one pass: {identities}")
    merged = {
        **cards[0],
        "started_at": min(str(c.get("started_at", "")) for c in cards),
        "finished_at": max(str(c.get("finished_at", "")) for c in cards),
        "sessions": len(cards),
        "session_cards": cards,
        "blinded": blind,
    }
    base.with_suffix(".md.card.json").write_text(json.dumps(merged, indent=1), encoding="utf-8")
    return rows_path, judge_card(base, pass_index=pass_index, passes=passes)


def judge_passes(
    args: Any, run_dir: Path, out_dir: Path, keep: list[str] | None = None
) -> list[str]:
    """Judge the run's cells with each judge and finalize/aggregate into `judges/` and `judge.jsonl`."""
    keep = list(keep or [])
    judges = parse_judges(args)
    blind = bool(getattr(args, "blind", False))
    adding = bool(getattr(args, "add", False))
    has_human = _has_human_judge(judges)

    pending: dict[str, Any] | None = None
    finalized_tags: dict[str, str] = {}
    if has_human:
        pending = _load_pending_human(run_dir, judges, adding=adding)
    if pending is not None:
        allocations = [
            (dict(item["judge"]), int(item["start"]), int(item["end"]))
            for item in (pending.get("allocations") or [])
        ]
        finalized_tags = {str(k): str(v) for k, v in (pending.get("finalized_tags") or {}).items()}
        saved_out = Path(str(pending.get("out_dir") or out_dir))
        if saved_out.is_dir():
            out_dir = saved_out
    else:
        allocations = _reserve_judge_passes(run_dir, judges)
        if has_human:
            pending = {
                "adding": adding,
                "blind": blind,
                "keep": keep,
                "judges": judges,
                "allocations": [
                    {"judge": j, "start": start, "end": end} for j, start, end in allocations
                ],
                "out_dir": str(out_dir.resolve()),
                "stamp": str(getattr(args, "_judge_stamp", "") or time.strftime("%Y%m%d-%H%M%S")),
                "finalized_tags": {},
            }
            _save_pending_human(run_dir, pending)

    total_new = sum(int(j["passes"]) for j in judges)
    actors: list[str] = []
    done_by_key: dict[tuple[str, str, str], int] = {}
    try:
        for k, (judge, start, end) in enumerate(allocations, 1):
            key = (str(judge["agent"]), str(judge["model"]), str(judge["effort"]))
            for i in range(start + 1, end + 1):
                tag = (
                    "judge"
                    + (f"-j{k}" if len(judges) > 1 else "")
                    + (f"-p{i}" if total_new > 1 or start else "")
                )
                if tag in finalized_tags:
                    actors.append(finalized_tags[tag])
                    done_by_key[key] = done_by_key.get(key, 0) + 1
                    continue
                rows, card = judge_sessions(args, run_dir, out_dir, i, end, judge, blind, tag)
                with _run_judge_lock(run_dir):
                    cmd = [
                        sys.executable,
                        "-m",
                        "harness.validate.judge_finalize",
                        str(run_dir),
                        str(rows),
                        "--card",
                        str(card),
                    ]
                    if total_new == 1 and not keep:
                        cmd.append("--promote")
                    done = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
                m = re.search(r"judges/([^/\s]+)/judge\.jsonl", done)
                if not m:
                    raise SystemExit(f"finalize named no actor for {tag}:\n{done}")
                actor_name = m.group(1)
                actors.append(actor_name)
                done_by_key[key] = done_by_key.get(key, 0) + 1
                if pending is not None:
                    finalized_tags[tag] = actor_name
                    pending["finalized_tags"] = finalized_tags
                    _save_pending_human(run_dir, pending)
                manifest = run_dir / "judges" / actor_name / "manifest.json"
                if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")).get(
                    "self_preference_risk"
                ):
                    print(
                        f"WARNING: {actor_name} is from the same model family as an arm it judged "
                        f"(self-preference risk); see its manifest"
                    )
        headline = keep + [a for a in actors if a not in keep]
        if len(headline) > 1:
            with _run_judge_lock(run_dir):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "harness.validate.judge_aggregate",
                        str(run_dir),
                        *[a for actor in headline for a in ("--actor", actor)],
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
    except BaseException as exc:
        if not (isinstance(exc, SystemExit) and exc.code == 3):
            _rollback_judge_passes(run_dir, allocations, done_by_key)
        raise
    if has_human:
        _clear_pending_human(run_dir)
    return headline


def arm_means(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Each arm's judged cell count, mean scores, and harm flags."""
    judge_file = run_dir / "judge.jsonl"
    if not judge_file.is_file():
        return {}
    judged = [
        json.loads(line)
        for line in judge_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out: dict[str, dict[str, Any]] = {}
    for arm in sorted({r["backend_id"] for r in judged}):
        rs = [r for r in judged if r["backend_id"] == arm]
        mean = lambda k: round(sum(r[k] for r in rs) / len(rs), 2)
        out[arm] = {
            "cells": len(rs),
            "accuracy": mean("accuracy"),
            "completeness": mean("completeness"),
            "relevance": mean("relevance"),
            "harm": sum(bool(r.get("harm")) for r in rs),
        }
    return out


def arm_table(run_dir: Path) -> list[str]:
    lines = [
        "| Arm | Cells | Accuracy | Completeness | Relevance | Harm |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, m in arm_means(run_dir).items():
        lines.append(
            f"| {arm} | {m['cells']} | {m['accuracy']} | {m['completeness']} | "
            f"{m['relevance']} | {m['harm']} |"
        )
    return lines


def run_judge_command(args: Any) -> int:
    """Execute `harness-cli validate judge` on a completed run directory."""
    adding = bool(getattr(args, "add", False))
    raw_dir = getattr(args, "run_dir", None) or (
        Path(getattr(args, "output_dir", "artifacts/validate")) / str(getattr(args, "run_id", ""))
    )
    run_dir = Path(raw_dir).resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")

    judges = parse_judges(args)
    has_human = _has_human_judge(judges)
    pending = _load_pending_human(run_dir, judges, adding=adding) if has_human else None

    if pending is not None and Path(str(pending.get("out_dir") or "")).is_dir():
        keep = list(pending.get("keep") or [])
        args.blind = bool(pending.get("blind", False))
        stamp = str(pending.get("stamp") or time.strftime("%Y%m%d-%H%M%S"))
        out_dir = Path(str(pending["out_dir"]))
    else:
        keep, _, blinded = run_judges(run_dir) if adding else ([], {}, False)
        if adding and not keep:
            raise SystemExit(f"{run_dir} has no judged headline to add to; omit --add to rejudge")
        args.blind = bool(getattr(args, "blind", False)) or blinded
        stamp = time.strftime("%Y%m%d-%H%M%S")
        explicit_work_dir = getattr(args, "work_dir", None)
        if explicit_work_dir:
            out_dir = Path(explicit_work_dir).resolve()
        else:
            out_dir = (run_dir / "judge-work") / f"{'add-judges' if adding else 'judge'}-{stamp}"
        out_dir.mkdir(parents=True, exist_ok=True)

    args._judge_stamp = stamp

    need_prep = pending is None or not (run_dir / "judge-cells.jsonl").is_file()
    if args.blind and not any((run_dir / "judge-bundles").glob("*.jsonl")):
        need_prep = True
    if need_prep:
        prep_cmd = [sys.executable, "-m", "harness.validate.judge_prep", str(run_dir)]
        if args.blind:
            prep_cmd.append("--blind")
        subprocess.run(prep_cmd, check=True, capture_output=True, text=True)

    actors = judge_passes(args, run_dir, out_dir, keep)
    report_path = build_report(run_dir)
    j_sum = judge_summary(run_dir)
    title = "Added judges to" if adding else "Judged"
    lines = [
        f"# {title} {run_dir.name} ({stamp})",
        "",
        f"Headline passes: {', '.join(actors)}",
        f"Report packet: {report_path}",
        "",
        str(j_sum.get("sentence") or ""),
        "",
        *arm_table(run_dir),
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0
