"""Side-by-side comparison report across multiple Catalyst notebook-validation runs.

Each entry is one model profile's independent run (its own suite, its own run
directory) against the same scenario set. This does not replace the single-run
narrative report in report.py — it summarizes several of them in one page.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.report_shell.assets import (
    SHARED_CSS,
    SHARED_JS,
    SHARED_JS_DEPS,
    THEME_TOGGLE_BUTTON_HTML,
    theme_toggle_js,
)
from harness.report_shell.document import render_document

from .attribution import blame, conformed, root_name

_STYLE = (
    SHARED_CSS
    + """
body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--fg); }
header.topbar { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding:18px 24px; border-bottom:1px solid var(--line); background: var(--surface); }
header.topbar h1 { margin:0; font-size:20px; }
main { padding: 18px 24px 48px; max-width: 1200px; }
section { margin: 22px 0; }
h2 { font-size: 16px; margin: 0 0 10px; }
table.data { width:100%; border-collapse:collapse; font-size:13px; background:var(--surface); }
table.data th, table.data td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
table.data th { background: var(--surface2); }
.verdict { font-size: 15px; background: var(--note-bg); border:1px solid var(--line); padding:12px 14px; border-radius:8px; }
.verdict b { font-size: 17px; }
.gatelist { color: var(--mut); font-size: 13px; margin: 8px 0 0; padding-left: 18px; }
.note { color: var(--mut); font-size: 12px; margin: 0 0 8px; }
.vpass { color: #0a7; font-weight: 600; }
.vfail { color: var(--err); font-weight: 700; }
.vinvalid { color: var(--purple, #8250df); font-weight: 700; }
.flow { color: var(--mut); font-size: 11px; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0; }
"""
)

_SCRIPT = SHARED_JS_DEPS + SHARED_JS + theme_toggle_js("oc-theme-report") + """
document.querySelectorAll('table.data').forEach(makeSortable);
"""


def _esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _load_results(run_dir: Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "results.json").read_text(encoding="utf-8"))


def _scenario_passed(row: dict[str, Any]) -> bool:
    # The runner's own verdict is authoritative: a scenario can pass with
    # status "failed" (a bounded failure it was told to expect). The status
    # heuristic only serves rows recorded before the verdict existed.
    if "passed" in row:
        return bool(row["passed"])
    if row.get("status") != "completed":
        return False
    assertions = row.get("assertions") or []
    return all(bool(a.get("passed")) for a in assertions)


def entries_from_comparison_run(run_dir: Path | str) -> list[dict[str, Any]]:
    """One entry per team from a single frozen-comparison run.

    The comparison is one run whose rows are stamped by the team that
    produced them, so the page's entries share the run directory and differ
    only in which rows they own.
    """
    results = _load_results(Path(run_dir))
    team_ids: list[str] = []
    for row in results.get("results") or []:
        profile_id = row.get("profileId")
        if isinstance(profile_id, str) and profile_id not in team_ids:
            team_ids.append(profile_id)
    return [
        {"run_dir": Path(run_dir), "profile_id": team, "profile_label": team}
        for team in team_ids
    ]


def _entry_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows this entry is scored on.

    Rows stamped with a profileId belong to that team alone; a legacy
    one-run-per-profile directory has unstamped rows, which all belong to
    its single entry.
    """
    results = _load_results(entry["run_dir"])
    rows = [
        row
        for row in results.get("results") or []
        if row.get("status") not in {"skipped", "infrastructure_failed"}
    ]
    if any(row.get("profileId") for row in rows):
        return [row for row in rows if row.get("profileId") == entry["profile_id"]]
    return rows


def _flow_kind(runs: list[dict[str, Any]]) -> str:
    """What kind of conversation this scenario runs.

    A reviewer weighing teams reads a clarification exchange differently
    from a three-turn refinement, so the row says which it is.
    """
    row = runs[0]
    total = 1 + len(row.get("turns") or [])
    if row.get("expectedBaseOutcome") == "needs_clarification":
        return "clarification"
    if total > 1:
        return f"multi-turn ×{total}"
    return "single-turn"


def _failed_turn(row: dict[str, Any]) -> str:
    """'at turn K of N' for the earliest turn a judged check failed on."""
    total = 1 + len(row.get("turns") or [])
    turn_numbers = []
    for item in row.get("assertions") or []:
        if item.get("passed"):
            continue
        name = str(item.get("name") or "")
        if name.endswith("-base") or name == root_name(name):
            turn_numbers.append(1)
        else:
            suffix = name.rsplit("-t", 1)[-1]
            if suffix.isdigit():
                turn_numbers.append(int(suffix) + 1)
    if not turn_numbers or total <= 1:
        return ""
    return f" (at turn {min(turn_numbers)} of {total})"


def _cell_verdict(runs: list[dict[str, Any]]) -> tuple[str, str]:
    """One conversation's verdict, and the sentence that explains it.

    A cell whose contract broke is INVALID, never FAIL: it measured nothing,
    so reporting it as a team's result would be a lie about the team.
    """
    for row in runs:
        assertions = row.get("assertions") or []
        if not conformed(assertions):
            reason = blame(assertions)
            root = reason.get("root") or {}
            return "INVALID", (
                "invalid measurement — "
                + str(root.get("why") or root.get("human") or root.get("name") or "")
            )
    if all(_scenario_passed(row) for row in runs):
        return "PASS", ""
    for row in runs:
        if not _scenario_passed(row):
            reason = blame(row.get("assertions") or [])
            root = reason.get("root") or {}
            return "FAIL", str(
                root.get("why") or root.get("human") or root.get("name") or ""
            ) + _failed_turn(row)
    return "FAIL", ""


def _qualification(
    entries: list[dict[str, Any]],
    per_entry_results: list[dict[str, Any]],
    invalid_by_entry: dict[str, int],
    gates: dict[str, float],
) -> str:
    """The decision, with the thresholds it was made against.

    Printed together so the page still means something when the programme's
    gates move; a team with an invalid measurement is undecidable rather
    than beaten, and says so.
    """
    overall = gates.get("overall")
    per_scenario = gates.get("per_scenario")
    lines: list[str] = []
    qualified: list[str] = []
    for entry, by_scenario in zip(entries, per_entry_results):
        rows = [row for runs in by_scenario.values() for row in runs]
        scored = len(rows)
        passed = sum(1 for row in rows if _scenario_passed(row))
        rate = (passed / scored) if scored else 0.0
        worst = min(
            (
                sum(1 for r in runs if _scenario_passed(r)) / len(runs)
                for runs in by_scenario.values()
                if runs
            ),
            default=0.0,
        )
        invalid = invalid_by_entry.get(entry["profile_id"], 0)
        if invalid:
            note = (
                f"undecidable — {invalid} invalid measurement"
                + ("s" if invalid > 1 else "")
            )
        elif (overall is None or rate >= overall) and (
            per_scenario is None or worst >= per_scenario
        ):
            qualified.append(entry["profile_label"])
            note = "meets every gate"
        else:
            note = "below the gates"
        lines.append(
            f"<li><code>{_esc(entry['profile_label'])}</code> — "
            f"{passed}/{scored} conversations ({rate:.0%} overall, "
            f"worst scenario {worst:.0%}) — {note}</li>"
        )
    verdict = (
        f"Qualified: {_esc(qualified[0])}" if len(qualified) == 1
        else (f"Qualified: {_esc(', '.join(qualified))}" if qualified
              else "No team qualified")
    )
    applied = []
    if overall is not None:
        applied.append(f"at least {overall:.0%} of conversations overall")
    if per_scenario is not None:
        applied.append(f"at least {per_scenario:.0%} on every scenario")
    gate_text = (
        "Against the gates in force at publication ("
        + " and ".join(applied)
        + "):"
        if applied
        else "No acceptance gates were applied to this run:"
    )
    return (
        "<section><h2>Decision</h2>"
        f"<p class=verdict>{gate_text} <b>{verdict}</b>.</p>"
        f"<ul class=gatelist>{''.join(lines)}</ul></section>"
    )


def build_comparison_report(
    entries: list[dict[str, Any]],
    *,
    title: str = "Catalyst profile comparison",
    gates: dict[str, float] | None = None,
) -> str:
    """Render one HTML page comparing each entry's notebook-validation run.

    ``entries`` is a list of ``{"run_dir": Path, "profile_id": str,
    "profile_label": str}``.
    """
    rows: list[str] = []
    for entry in entries:
        result_rows = _entry_rows(entry)
        passed = sum(1 for row in result_rows if _scenario_passed(row))
        total = len(result_rows)
        assertion_total = sum(len(row.get("assertions") or []) for row in result_rows)
        wall_times = [
            row["timing"]["unadjustedGenerationWallMs"]
            for row in result_rows
            if isinstance(row.get("timing"), dict)
            and "unadjustedGenerationWallMs" in row["timing"]
        ]
        avg_wall_ms = round(sum(wall_times) / len(wall_times)) if wall_times else None
        rows.append(
            "<tr>"
            f"<td>{_esc(entry['profile_label'])}</td>"
            f"<td><code>{_esc(entry['profile_id'])}</code></td>"
            f"<td>{passed}/{total}</td>"
            f"<td>{assertion_total}</td>"
            f"<td>{avg_wall_ms if avg_wall_ms is not None else '—'} ms</td>"
            "</tr>"
        )

    summary_table = (
        "<table class=data><thead><tr>"
        "<th>Profile</th><th>Profile ID</th>"
        "<th>Conversations passed</th><th>Assertions</th>"
        "<th>Avg generation time</th>"
        "</tr></thead><tbody>"
        f"{''.join(rows)}"
        "</tbody></table>"
    )

    scenario_ids: list[str] = []
    per_entry_results: list[dict[str, Any]] = []
    for entry in entries:
        by_scenario: dict[str, list[dict[str, Any]]] = {}
        for row in _entry_rows(entry):
            by_scenario.setdefault(row["scenarioId"], []).append(row)
            if row["scenarioId"] not in scenario_ids:
                scenario_ids.append(row["scenarioId"])
        per_entry_results.append(by_scenario)

    matrix_rows: list[str] = []
    inventory: list[str] = []
    invalid_by_entry: dict[str, int] = {e["profile_id"]: 0 for e in entries}
    for scenario_id in scenario_ids:
        flow = next(
            (
                _flow_kind(by_scenario[scenario_id])
                for by_scenario in per_entry_results
                if by_scenario.get(scenario_id)
            ),
            "",
        )
        cells = [
            f"<td>{_esc(scenario_id)} "
            f"<span class=flow>{_esc(flow)}</span></td>"
        ]
        for entry, by_scenario in zip(entries, per_entry_results):
            runs = by_scenario.get(scenario_id, [])
            if not runs:
                cells.append("<td>—</td>")
                continue
            verdict, note = _cell_verdict(runs)
            if verdict == "INVALID":
                invalid_by_entry[entry["profile_id"]] += 1
            cells.append(
                f'<td class="v{verdict.lower()}">{verdict}</td>'
            )
            if note:
                inventory.append(
                    "<tr>"
                    f"<td>{_esc(scenario_id)}</td>"
                    f"<td>{_esc(entry['profile_label'])}</td>"
                    f'<td class="v{verdict.lower()}">{verdict}</td>'
                    f"<td>{_esc(note)}</td>"
                    "</tr>"
                )
        matrix_rows.append(f"<tr>{''.join(cells)}</tr>")

    inventory_table = (
        "<table class=data><thead><tr><th>Scenario</th><th>Team</th>"
        "<th>Verdict</th><th>What happened</th></tr></thead><tbody>"
        f"{''.join(inventory)}</tbody></table>"
        if inventory
        else "<p>Every conversation passed.</p>"
    )

    matrix_header = "<th>Scenario</th>" + "".join(
        f"<th>{_esc(e['profile_label'])}</th>" for e in entries
    )
    matrix_table = (
        "<table class=data><thead><tr>"
        f"{matrix_header}"
        "</tr></thead><tbody>"
        f"{''.join(matrix_rows)}"
        "</tbody></table>"
    )

    decision = (
        _qualification(entries, per_entry_results, invalid_by_entry, gates)
        if gates is not None
        else ""
    )
    body = (
        "<header class=topbar>"
        f"<h1>{_esc(title)}</h1>{THEME_TOGGLE_BUTTON_HTML}"
        "</header><main>"
        f"{decision}"
        "<section><h2>Summary</h2>"
        f"{summary_table}</section>"
        "<section><h2>Per-scenario breakdown</h2>"
        "<p class=note>PASS and FAIL are the judge's verdict on the answer. "
        "INVALID means the run broke its own contract there and measured "
        "nothing — it is not a score against the team.</p>"
        f"{matrix_table}</section>"
        "<section><h2>What went wrong</h2>"
        f"{inventory_table}</section>"
        "</main>"
    )

    return render_document(
        title=title,
        body_html=body,
        style=_STYLE,
        script=_SCRIPT,
        theme_storage_key="oc-theme-report",
        embedded_data={"entries": [e["profile_id"] for e in entries]},
    )
