"""Side-by-side comparison report across multiple Catalyst notebook-validation runs.

Each entry is one model profile's independent run (its own suite, its own run
directory) against the same scenario set. This does not replace the single-run
narrative report in report.py — it summarizes several of them in one page.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.report_shell.document import render_document


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
    if row.get("status") != "completed":
        return False
    assertions = row.get("assertions") or []
    return all(bool(a.get("passed")) for a in assertions)


def build_comparison_report(
    entries: list[dict[str, Any]],
    *,
    title: str = "Catalyst profile comparison",
) -> str:
    """Render one HTML page comparing each entry's notebook-validation run.

    ``entries`` is a list of ``{"run_dir": Path, "profile_id": str,
    "profile_label": str}``.
    """
    rows: list[str] = []
    for entry in entries:
        results = _load_results(entry["run_dir"])
        passed = results.get("passedCount", 0)
        total = results.get("resultCount", 0)
        result_rows = results.get("results") or []
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
        "<table><thead><tr>"
        "<th>Profile</th><th>Profile ID</th>"
        "<th>Scenario repetitions passed</th><th>Assertions</th>"
        "<th>Avg generation time</th>"
        "</tr></thead><tbody>"
        f"{''.join(rows)}"
        "</tbody></table>"
    )

    scenario_ids: list[str] = []
    per_entry_results: list[dict[str, Any]] = []
    for entry in entries:
        results = _load_results(entry["run_dir"])
        by_scenario: dict[str, list[dict[str, Any]]] = {}
        for row in results.get("results") or []:
            by_scenario.setdefault(row["scenarioId"], []).append(row)
            if row["scenarioId"] not in scenario_ids:
                scenario_ids.append(row["scenarioId"])
        per_entry_results.append(by_scenario)

    matrix_rows: list[str] = []
    for scenario_id in scenario_ids:
        cells = [f"<td>{_esc(scenario_id)}</td>"]
        for by_scenario in per_entry_results:
            reps = by_scenario.get(scenario_id, [])
            if not reps:
                cells.append("<td>—</td>")
                continue
            passed_reps = sum(1 for row in reps if _scenario_passed(row))
            verdict = "PASS" if passed_reps == len(reps) else "FAIL"
            cells.append(f"<td>{verdict} ({passed_reps}/{len(reps)})</td>")
        matrix_rows.append(f"<tr>{''.join(cells)}</tr>")

    matrix_header = "<th>Scenario</th>" + "".join(
        f"<th>{_esc(e['profile_label'])}</th>" for e in entries
    )
    matrix_table = (
        "<table><thead><tr>"
        f"{matrix_header}"
        "</tr></thead><tbody>"
        f"{''.join(matrix_rows)}"
        "</tbody></table>"
    )

    body = (
        f"<h1>{_esc(title)}</h1>"
        "<h2>Summary</h2>"
        f"{summary_table}"
        "<h2>Per-scenario breakdown</h2>"
        f"{matrix_table}"
    )

    return render_document(
        title=title,
        body_html=body,
        embedded_data={"entries": [e["profile_id"] for e in entries]},
    )
