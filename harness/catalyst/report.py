"""Offline Catalyst notebook validation report (report family: catalyst)."""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from statistics import median
from typing import Any

from harness.common.jsonl import read_jsonl
from harness.common.text import esc
from harness.catalyst.notebook_validation import assertion_class
from harness.catalyst.judge_ranking import aggregate_rankings
from harness.catalyst.judge_consensus import (
    agreement,
    consensus,
    load_adjudication,
)
from harness.catalyst.reconcile import merge_gold_and_judge
from harness.catalyst.run_config import load_frozen
from harness.report_shell.assets import (
    SHARED_CSS,
    SHARED_JS,
    SHARED_JS_DEPS,
    THEME_TOGGLE_BUTTON_HTML,
    theme_toggle_js,
)
from harness.report_shell.document import render_document

_STYLE = (
    SHARED_CSS
    + """
body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--fg); }
header.topbar { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding:18px 24px; border-bottom:1px solid var(--line); background: var(--surface); }
header.topbar h1 { margin:0; font-size:20px; }
.meta { color: var(--mut); font-size: 12px; margin-top: 4px; }
main { padding: 18px 24px 48px; max-width: 1200px; }
section { margin: 22px 0; }
h2 { font-size: 16px; margin: 0 0 10px; }
table.data { width:100%; border-collapse:collapse; font-size:13px; background:var(--surface); }
table.data th, table.data td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
table.data th { background: var(--surface2); }
.pass { color: #0a7; font-weight: 600; }
.fail { color: var(--err); font-weight: 700; }
.adv { color: var(--mut); font-size: 12px; }\n.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0; }
.note { background: var(--note-bg); border:1px solid var(--line); padding:10px 12px; border-radius:8px; font-size:13px; }
pre.diff, pre.sql, pre.rationale { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 12px; background: var(--surface2); border:1px solid var(--line); padding:10px; border-radius:8px; }
a.ev { color: var(--accent); }
.chip-fail { display:inline-block; background:#a01; color:#fff; font-size:11px; padding:1px 6px; border-radius:3px; }
.chip-invalid { display:inline-block; background:#5b2d91; color:#fff; font-size:11px; padding:1px 6px; border-radius:3px; }
.chip-pass { display:inline-block; background:#0a7; color:#fff; font-size:11px; padding:1px 6px; border-radius:3px; }
.abstract { font-size:14.5px; line-height:1.6; max-width:70ch; }
.abstract p { margin: 8px 0; }
.gate-verdict { font-size:15px; font-weight:600; margin:0 0 10px; }
.vchips { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0; }
.vchip { border:1px solid var(--line); border-radius:8px; padding:7px 12px; font-size:13px; background:var(--surface); }
.vchip.lead { border-color:var(--accent); }
.vchip b { font-size:15px; }
.vchip .sub { display:block; color:var(--mut); font-size:11px; }
.pill-adv { display:inline-block; font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--mut); border:1px solid var(--line); border-radius:999px; padding:1px 8px; vertical-align:middle; margin-left:6px; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.flagged { color: var(--err); font-weight:700; }
dl.legend { font-size:12px; color:var(--mut); margin:10px 0 0; }
dl.legend dt { font-weight:600; float:left; clear:left; width:9em; color:var(--fg); }
dl.legend dd { margin:0 0 3px 10em; }
details.jcell { border:1px solid var(--line); border-radius:8px; background:var(--note-bg); padding:6px 10px; margin:6px 0; font-size:13px; }
details.jcell summary { cursor:pointer; }
a.jlink { color: var(--accent); }
"""
)

_SCRIPT = SHARED_JS_DEPS + SHARED_JS + theme_toggle_js("oc-theme-report") + """
document.querySelectorAll('table.data').forEach(makeSortable);
/* A judge anchor may live on a collapsed <details>; open it when targeted. */
function openJudgeTarget(){
  var id = location.hash && location.hash.slice(1);
  var el = id && document.getElementById(id);
  if (el && el.tagName === 'DETAILS') { el.open = true; }
}
window.addEventListener('hashchange', openJudgeTarget);
openJudgeTarget();
"""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rstrip_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def unified_sql_diff(before: str, after: str, *, fromfile: str, tofile: str) -> str:
    """Line-level unified diff; strip trailing whitespace per line, keep boundaries."""
    return "\n".join(
        difflib.unified_diff(
            _rstrip_lines(before),
            _rstrip_lines(after),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def _extract_sql(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.suffix == ".sql":
        return path.read_text(encoding="utf-8")
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(blob.get("sql"), str):
        return blob["sql"]
    body = ((blob.get("response") or {}).get("body")) or {}
    if isinstance(body.get("sql"), str):
        return body["sql"]
    req = ((blob.get("request") or {}).get("body")) or {}
    if isinstance(req.get("sql"), str):
        return req["sql"]
    return None


def _scenario_sql_versions(run_dir: Path, scenario_id: str) -> list[tuple[str, str]]:
    """Return ordered (label, sql) pairs discovered under the scenario evidence tree."""
    root = run_dir / "scenarios" / scenario_id
    if not root.exists():
        return []
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".json", ".sql"}:
            continue
        if "version" not in path.name and "save-base-version" not in path.name and path.suffix != ".sql":
            # Prefer explicit version artifacts and top-level SQL files.
            if path.name not in {"01-base-sql.sql", "02-successor-sql.sql"}:
                continue
        sql = _extract_sql(path)
        if not sql:
            continue
        # Ordinal hint from filename for stable ordering.
        ordinal = 50
        name = path.name
        if "base" in name or name.startswith("01-"):
            ordinal = 1
        elif "version-01" in name or name == "version-01.json":
            ordinal = 2
        elif "version-02" in name or name == "version-02.json" or "successor" in name:
            ordinal = 3
        rel = path.relative_to(run_dir).as_posix()
        candidates.append((ordinal, rel, sql))
    candidates.sort(key=lambda t: (t[0], t[1]))
    # Deduplicate identical consecutive SQL.
    out: list[tuple[str, str]] = []
    for _, rel, sql in candidates:
        if out and out[-1][1] == sql:
            continue
        out.append((rel, sql))
    return out


_JUDGE_AXES = (
    "intent_fidelity",
    "sql_quality",
    "schema_discipline",
    "followup_coherence",
)
_AXIS_HEADS = {
    "intent_fidelity": "intent",
    "sql_quality": "SQL craft",
    "schema_discipline": "schema",
    "followup_coherence": "follow-up",
}
# Which judged queries get called out by name. A fixed composite cutoff was
# arbitrary, and useless on a run whose axes saturate — the composite is then
# nearly a step function of the one axis that dropped. The rubric already
# defines imperfection: any axis below its top anchor means that axis was not
# fully satisfied. So a query is named when the judge marked it down on ANY
# axis, worst composite first, capped so a bad run does not print its whole
# worklist. Purely relative ranking was rejected for the opposite failure: a
# team whose every query scored alike and badly would name nothing.
_MAX_NAMED_PER_TEAM = 3
_AXIS_TOP = 3


def _weakest_rows(
    rows: list[dict[str, Any]], limit: int = _MAX_NAMED_PER_TEAM
) -> list[dict[str, Any]]:
    """The judged queries worth reading: any the judge marked down.

    Ordered by composite so the worst leads, then by scenario and turn so the
    list is stable across runs with identical scores.
    """

    def marked_down(row: dict[str, Any]) -> bool:
        return any(
            isinstance(row.get(axis), (int, float)) and row[axis] < _AXIS_TOP
            for axis in _JUDGE_AXES
        )

    return sorted(
        (row for row in rows if marked_down(row)),
        key=lambda row: (
            row.get("composite") if isinstance(row.get("composite"), (int, float)) else 0,
            str(row.get("scenario_id")),
            int(row.get("turn") or 0),
        ),
    )[:limit]


def _judge_team(row: dict[str, Any]) -> str | None:
    """Which team's query this judge row scored.

    Judge rows are contract-frozen (catalyst-judge-v1 forbids extra fields),
    so the team is not a field — but a comparison run nests every evidence
    file under scenarios/<team>/<scenario>/, and the row links its evidence.
    A single-profile run keeps the flat scenarios/<scenario>/ layout -> None.
    """
    stamped = row.get("team")
    if isinstance(stamped, str) and stamped:
        return stamped
    for path in row.get("evidence_paths") or []:
        parts = str(path).split("/")
        if len(parts) >= 3 and parts[0] == "scenarios":
            return None if parts[2].startswith("repetition-") else parts[1]
    return None


def _judge_anchor(team: str | None, scenario_id: str, turn: int) -> str:
    raw = f"judge-{team or 'run'}-{scenario_id}-t{turn}"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", raw)


def _judges_by_cell(
    rows: list[dict[str, Any]],
) -> dict[tuple[str | None, str], list[dict[str, Any]]]:
    """Judge rows grouped per (team, scenario), each cell's rows in turn order.

    Keying on the team is what keeps a comparison run's three answers to the
    same scenario from overwriting each other.
    """
    cells: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for row in rows:
        cells.setdefault((_judge_team(row), str(row.get("scenario_id"))), []).append(row)
    for cell_rows in cells.values():
        cell_rows.sort(key=lambda r: int(r.get("turn") or 0))
    return cells


def _row_team(row: dict[str, Any]) -> str | None:
    team = row.get("profileId")
    return team if isinstance(team, str) and team else None


def _team_tallies(results: dict[str, Any]) -> list[tuple[str | None, int, int]]:
    """(team, conversations passed, conversations run), best rate first."""
    tallies: dict[str | None, list[int]] = {}
    for row in results.get("results") or []:
        if row.get("status") == "skipped":
            continue
        tally = tallies.setdefault(_row_team(row), [0, 0])
        tally[0] += 1 if row.get("passed") else 0
        tally[1] += 1
    return sorted(
        ((team, passed, total) for team, (passed, total) in tallies.items()),
        key=lambda item: (-(item[1] / item[2] if item[2] else 0.0), str(item[0])),
    )


def _team_labels(results: dict[str, Any], suite: dict[str, Any]) -> dict[str | None, str]:
    """A short human name per team: what distinguishes it, not its full slug."""
    profiles = suite.get("profiles") or {}
    teams: list[str | None] = []
    for row in results.get("results") or []:
        team = _row_team(row)
        if team not in teams:
            teams.append(team)
    labels: dict[str | None, str] = {}
    for team in teams:
        cfg = profiles.get(team) or {}
        writer = cfg.get("writerModelId")
        reviewer = cfg.get("reviewerModelId")
        if not writer:
            labels[team] = team or "this run"
        elif not reviewer:
            labels[team] = "writer-only"
        elif reviewer == writer:
            labels[team] = "self-checked"
        else:
            labels[team] = f"{reviewer}-checked"
    if len(set(labels.values())) < len(labels):
        labels = {team: (team or "this run") for team in teams}
    return labels


def _team_models(suite: dict[str, Any], team: str | None) -> str:
    cfg = (suite.get("profiles") or {}).get(team) or {}
    writer = cfg.get("writerModelId")
    reviewer = cfg.get("reviewerModelId")
    if not writer:
        return ""
    return f"{writer} writer · {reviewer} reviewer" if reviewer else f"{writer}, no reviewer"


def _conformed(assertions: list[dict[str, Any]]) -> bool:
    """No failed conformance assertion — the row is a valid measurement."""
    for assertion in assertions:
        if assertion.get("passed"):
            continue
        kind = assertion.get("class") or assertion_class(str(assertion.get("name") or ""))
        if kind == "conformance":
            return False
    return True


def _gate_outcome(
    results: dict[str, Any],
    labels: dict[str | None, str],
    gates: dict[str, Any],
) -> dict[str, Any] | None:
    """The decision, computed the way comparison.html computes it: overall
    rate and worst per-scenario rate against the frozen gates; a team with an
    invalid measurement is undecidable rather than beaten."""
    overall = gates.get("overall")
    per_scenario = gates.get("per_scenario")
    if overall is None and per_scenario is None:
        return None
    by_team: dict[str | None, dict[str, list[dict[str, Any]]]] = {}
    for row in results.get("results") or []:
        if row.get("status") == "skipped":
            continue
        by_team.setdefault(_row_team(row), {}).setdefault(
            str(row.get("scenarioId")), []
        ).append(row)
    if len(by_team) < 2:
        return None
    qualified: list[str] = []
    undecidable: list[str] = []
    for team, by_scenario in by_team.items():
        rows = [row for runs in by_scenario.values() for row in runs]
        if any(not _conformed(row.get("assertions") or []) for row in rows):
            undecidable.append(labels.get(team, str(team)))
            continue
        rate = sum(1 for row in rows if row.get("passed")) / len(rows) if rows else 0.0
        worst = min(
            (
                sum(1 for r in runs if r.get("passed")) / len(runs)
                for runs in by_scenario.values()
                if runs
            ),
            default=0.0,
        )
        if (overall is None or rate >= float(overall)) and (
            per_scenario is None or worst >= float(per_scenario)
        ):
            qualified.append(labels.get(team, str(team)))
    gate_bits = []
    if overall is not None:
        gate_bits.append(f"≥{float(overall):.0%} overall")
    if per_scenario is not None:
        gate_bits.append(f"≥{float(per_scenario):.0%} per scenario")
    return {
        "gates": gate_bits,
        "qualified": sorted(qualified),
        "undecidable": sorted(undecidable),
    }


def _gate_verdict_line(outcome: dict[str, Any]) -> str:
    prefix = (
        "Against the gates in force at publication"
        f" ({', '.join(outcome['gates'])}): "
    )
    qualified = outcome["qualified"]
    undecidable = outcome["undecidable"]
    if qualified:
        line = prefix + "qualified — " + ", ".join(qualified)
        if undecidable:
            line += (
                " · no decision for "
                + ", ".join(undecidable)
                + " (invalid measurements)"
            )
        return line
    if undecidable:
        return (
            prefix
            + "no decision — invalid measurements for "
            + ", ".join(undecidable)
        )
    return prefix + "no team qualified"


def _row_scenario_key(row: dict[str, Any]) -> str:
    """Where this row's evidence lives under scenarios/.

    A comparison run nests evidence per team; a single-profile run keeps the
    flat layout. The row itself says which world it came from.
    """
    sid = str(row.get("scenarioId"))
    team = row.get("profileId")
    return f"{team}/{sid}" if isinstance(team, str) and team else sid


def _row_label(row: dict[str, Any]) -> str:
    """The scenario id, prefixed by its team when the run compares several."""
    sid = str(row.get("scenarioId"))
    team = row.get("profileId")
    return f"{team} · {sid}" if isinstance(team, str) and team else sid


def _gold_passed(assertions: list[dict[str, Any]]) -> bool:
    gold = [
        a
        for a in assertions
        if "gold_execution_match" in str(a.get("name", ""))
    ]
    if not gold:
        return all(bool(a.get("passed")) for a in assertions)
    return all(bool(a.get("passed")) for a in gold)


def _fail_chip(assertion: dict[str, Any]) -> str:
    """A failed check's chip, labeled by what kind of finding it is.

    A broken contract (an invalid measurement) and a judged miss (a result)
    must not look alike; the split comes stamped from the runner, with the
    name table as the fallback for older rows.
    """
    kind = assertion.get("class") or assertion_class(
        str(assertion.get("name") or "")
    )
    if kind == "conformance":
        return (
            f"<span class='chip-invalid'>contract · "
            f"{esc(assertion.get('name'))}</span>"
        )
    return f"<span class='chip-fail'>judged · {esc(assertion.get('name'))}</span>"


def _assertion_fail_details(
    run_dir: Path,
    scenario_id: str,
    assertion: dict[str, Any],
) -> str:
    evidence = assertion.get("evidence")
    rationale = ""
    rel: str | None = None
    if isinstance(evidence, dict):
        rationale = str(
            evidence.get("mismatch_rationale") or evidence.get("rationale") or ""
        )
        path_val = evidence.get("path")
        if isinstance(path_val, str):
            rel = path_val
    name = str(assertion.get("name") or "")
    if not rel and "gold_execution_match" in name:
        stem = (
            "15-gold-execution-match-base.json"
            if "base_" in name
            else "16-gold-execution-match-successor.json"
        )
        candidate = f"scenarios/{scenario_id}/repetition-01/{stem}"
        if (run_dir / candidate).exists():
            rel = candidate
    chunks: list[str] = []
    if rel:
        abs_path = run_dir / rel
        if abs_path.exists() and abs_path.suffix == ".json":
            blob = _load_json(abs_path)
            file_rationale = blob.get("mismatch_rationale")
            if file_rationale:
                rationale = str(file_rationale)
        chunks.append(f'<a class="ev" href="{esc(rel)}">{esc(rel)}</a>')
    if rationale:
        chunks.insert(0, esc(rationale))
    return "<br>".join(chunks) if chunks else ""


def _render_judge_block(row: dict[str, Any] | None) -> str:
    if row is None:
        return '<span class="adv">Judge not available</span>'
    axes = [
        "intent_fidelity",
        "sql_quality",
        "schema_discipline",
        "followup_coherence",
    ]
    bits = [
        f"<div><b>advisory composite</b>: {esc(row.get('composite'))}</div>",
        "<ul>",
    ]
    for axis in axes:
        if axis not in row:
            continue
        rationale = row.get(f"{axis}_rationale", "")
        bits.append(
            f"<li><code>{esc(axis)}</code>={esc(row.get(axis))} — {esc(rationale)}</li>"
        )
    bits.append("</ul>")
    paths = row.get("evidence_paths") or []
    if paths:
        bits.append("<div class='adv'>evidence: ")
        bits.append(
            ", ".join(
                f'<a class="ev" href="{esc(p)}">{esc(p)}</a>' for p in paths
            )
        )
        bits.append("</div>")
    return "".join(bits)


def _execution_row_count(run_dir: Path, scenario_id: str, stem: str) -> int | None:
    """rowCount from the first repetition's execution artifact, if present."""
    for candidate in (
        run_dir / "scenarios" / scenario_id / "repetition-01" / stem,
        run_dir / "scenarios" / scenario_id / stem,
    ):
        if not candidate.exists():
            continue
        blob = _load_json(candidate)
        body = ((blob.get("response") or {}).get("body")) or blob
        # Live runs nest under result; older fixture exchanges keep
        # rows/rowCount at the body top level.
        result = body.get("result") or body
        if isinstance(result.get("rowCount"), int):
            return result["rowCount"]
        rows = result.get("rows")
        if isinstance(rows, list):
            return len(rows)
    return None


def _judged_failure_map(
    results: dict[str, Any],
) -> tuple[list[str | None], dict[str, list[str | None]]]:
    """Which teams missed which scenarios, counting only valid measurements.

    A conformance-broken row is an invalid measurement, not a miss; it is
    reported separately rather than blended into the failure story.
    """
    teams: list[str | None] = []
    failed: dict[str, list[str | None]] = {}
    for row in results.get("results") or []:
        if row.get("status") == "skipped":
            continue
        team = _row_team(row)
        if team not in teams:
            teams.append(team)
        if row.get("passed"):
            continue
        if not _conformed(row.get("assertions") or []):
            continue
        failed.setdefault(str(row.get("scenarioId")), []).append(team)
    return teams, failed


def _failure_character(
    judges: list[dict[str, Any]], failed_scenarios: set[str] | None = None
) -> str | None:
    """One plain sentence on WHAT went wrong, argued from the judge's axes.

    When construction and schema use stay at ceiling on the very queries
    that failed, the misses are about reading the question, not writing
    SQL — and the abstract can say so from measurement rather than opinion.
    """
    if not judges:
        return None
    # The claim below is about the queries on questions that FAILED, so the
    # evidence must be those queries — not every query the judge marked down
    # anywhere, which would let a passing scenario's style note decide what
    # the failures were.
    scope = (
        [row for row in judges if str(row.get("scenario_id")) in failed_scenarios]
        if failed_scenarios
        else judges
    )
    flagged = _weakest_rows(scope, limit=len(scope))
    if not flagged:
        return (
            "A separate AI judge read every executed query and found nothing"
            " to flag; its per-axis scores are in the judge summary below."
        )

    def med(axis: str) -> float | None:
        values = [
            row[axis] for row in flagged if isinstance(row.get(axis), (int, float))
        ]
        return float(median(values)) if values else None

    intent = med("intent_fidelity")
    craft = med("sql_quality")
    schema = med("schema_discipline")
    if (
        intent is not None
        and craft is not None
        and schema is not None
        and craft >= 2.5
        and schema >= 2.5
        and intent <= 1.5
    ):
        return (
            "A separate AI judge read every executed query. On the failed"
            " questions the SQL itself still scored at ceiling for"
            " construction and schema use — what dropped was fidelity to what"
            " the question actually asked. The errors are misreadings, not"
            " broken queries."
        )
    return (
        "A separate AI judge read every executed query; its per-axis reading"
        " of each failure is in the judge summary below."
    )


def _abstract_section(
    suite: dict[str, Any],
    results: dict[str, Any],
    judges: list[dict[str, Any]],
    config: dict[str, Any],
) -> str:
    """The report in plain terms: assembled from the run's own numbers so it
    cannot drift from them, with the wording templates seeded (optionally)
    from the run config's publish block.

    Deliberately free of pass/fail gates: thresholds are publication policy
    and live in the Result section with the policy that set them. The
    abstract reports how the teams actually did relative to each other and
    what the failures were.
    """
    publish = config.get("publish") or {}
    tallies = _team_tallies(results)
    labels = _team_labels(results, suite)
    n_questions = max((total for _, _, total in tallies), default=0)
    subject = publish.get("plainSubject") or "a clinical database"
    paragraphs: list[str] = []

    lead = publish.get("plainSummary")
    if not lead and tallies:
        if len(tallies) > 1:
            lead = (
                f"We asked {len(tallies)} AI “teams” the same"
                f" {n_questions} questions about {subject}, in plain English,"
                " and let each team write and run the database queries itself"
                " — including asking us to clarify vague questions, and"
                " refusing ones the data can't answer. A team passes a"
                " question only when its final answer matches an independently"
                " written reference answer, row for row."
            )
        else:
            lead = (
                f"We asked an AI team {n_questions} questions about {subject},"
                " in plain English, and let it write and run the database"
                " queries itself. It passes a question only when its final"
                " answer matches an independently written reference answer,"
                " row for row."
            )
    if lead:
        paragraphs.append(f"<p>{esc(lead)}</p>")

    teams, failed = _judged_failure_map(results)
    invalid_teams = sorted(
        {
            labels.get(_row_team(row), str(_row_team(row)))
            for row in results.get("results") or []
            if row.get("status") != "skipped"
            and not _conformed(row.get("assertions") or [])
        }
    )

    # How the teams actually did, relative to each other.
    if len(tallies) > 1:
        scores = " · ".join(
            f"{esc(labels.get(team, str(team)))} {passed} of {total}"
            for team, passed, total in tallies
        )
        spread = tallies[0][1] - tallies[-1][1]
        if spread == 0:
            opener = "<b>The teams tied</b>"
        elif spread == 1:
            opener = (
                "<b>The teams finished within one question of each other</b>"
                " — a practical tie at this sample size"
            )
        else:
            opener = (
                f"<b>{esc(labels.get(tallies[0][0], str(tallies[0][0])))}"
                f" led by {spread} questions</b>"
            )
        sentence = f"{opener}: {scores}."
        if invalid_teams:
            sentence += (
                f" ({esc(', '.join(invalid_teams))} also had invalid"
                " measurements, reported separately in the comparison.)"
            )
        paragraphs.append(f"<p>{sentence}</p>")
    elif tallies:
        _, passed, total = tallies[0]
        paragraphs.append(
            f"<p>It answered <b>{passed} of {total}</b> correctly.</p>"
        )

    # What the failures were — where they landed, and their nature.
    if failed:
        n_teams = len(teams)
        shared = sorted(
            sid for sid, missed_by in failed.items()
            if len(set(missed_by)) == n_teams
        )
        partial = sorted(set(failed) - set(shared))
        if len(tallies) > 1:
            bits: list[str] = []
            if shared:
                bits.append(
                    f"{len(shared)} of the {n_questions} questions"
                    f" ({', '.join(shared)}) were missed by every team"
                )
            if partial:
                bits.append(
                    f"{', '.join(partial)} tripped only"
                    f" {'one team' if all(len(set(failed[sid])) == 1 for sid in partial) else 'some teams'}"
                )
            cluster = (
                "The misses were largely shared, not team-specific: "
                if shared
                else "No miss was shared by every team: "
            ) + "; ".join(bits) + "."
        else:
            cluster = f"It missed {', '.join(sorted(failed))}."
        character = _failure_character(judges, set(failed))
        failure_text = cluster + (f" {character}" if character else "")
        takeaway = publish.get("plainTakeaway")
        if takeaway:
            failure_text += f" {takeaway}"
        paragraphs.append(f"<p>{esc(failure_text)}</p>")
    elif judges:
        character = _failure_character(judges)
        if character:
            paragraphs.append(f"<p>{esc(character)}</p>")

    reps = [1]
    for row in results.get("results") or []:
        if isinstance(row.get("repetition"), int):
            reps.append(int(row["repetition"]))
    once = max(reps) <= 1
    caveat = (
        ("One conversation per question, on a demonstration dataset — "
         if once
         else "A demonstration dataset — ")
        + "read this as directional evidence, not a benchmark; differences of"
        " a question or two are within noise."
    )
    paragraphs.append(f"<p class='adv'>{esc(caveat)}</p>")

    if not paragraphs:
        return ""
    return (
        "<section class='abstract'><h2>In plain terms</h2>"
        + "".join(paragraphs)
        + "</section>"
    )


def _verdict_section(
    suite: dict[str, Any],
    results: dict[str, Any],
    config: dict[str, Any],
) -> str:
    """The decision facts: gate verdict and how each team did, before any detail."""
    passed = results.get("passedCount")
    total = results.get("resultCount")
    skipped = results.get("skippedCount") or 0
    assertion_total = sum(
        len(row.get("assertions") or []) for row in results.get("results") or []
    )
    tallies = _team_tallies(results)
    labels = _team_labels(results, suite)
    outcome = _gate_outcome(results, labels, config.get("gates") or {})
    bits = ["<section>", "<h2>Result</h2>"]
    if outcome:
        cls = "pass" if outcome["qualified"] else "fail"
        bits.append(
            f"<p class='gate-verdict {cls}'>{esc(_gate_verdict_line(outcome))}</p>"
        )
    if len(tallies) > 1:
        chips = []
        for index, (team, team_passed, team_total) in enumerate(tallies):
            models = _team_models(suite, team)
            chips.append(
                f"<div class='vchip{' lead' if index == 0 else ''}'>"
                f"<b>{team_passed}/{team_total}</b> {esc(labels.get(team, str(team)))}"
                + (f"<span class='sub'>{esc(models)}</span>" if models else "")
                + "</div>"
            )
        bits.append(f"<div class='vchips'>{''.join(chips)}</div>")
        bits.append(
            f"<p class='adv'>{esc(passed)}/{esc(total)} conversations passed"
            f" across all teams · {assertion_total} assertions"
            + (f" · {esc(skipped)} manual-only scenario skipped" if skipped else "")
            + " · pass = the final answer matches the independent reference"
            " answer row-for-row.</p>"
        )
    else:
        verdict_cls = "pass" if passed == total else "fail"
        bits.append(
            f"<p class='headline'><span class='{verdict_cls}'>{esc(passed)}/{esc(total)}"
            " conversations passed</span>"
            f" · {assertion_total} assertions"
            + (f" · {esc(skipped)} manual-only scenario skipped" if skipped else "")
            + "</p>"
        )
        bits.append(
            "<p class='adv'>pass = the final answer matches the independent"
            " reference answer row-for-row.</p>"
        )
    bits.append("</section>")
    return "".join(bits)


def _ranking_section(rank_rows: list[dict[str, Any]], labels: dict[str | None, str]) -> str:
    """The comparative standing, when a ranking pass has been run.

    Absent for runs judged pointwise only — which is every run so far, and
    saying nothing is correct there: an empty section would imply the
    comparison was made and came out even.
    """
    if not rank_rows:
        return ""
    result = aggregate_rankings(rank_rows)
    if not result["standing"]:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{esc(labels.get(entry['team'], entry['team']))}</td>"
        f"<td class='num'>{esc(entry['mean_rank'])}</td>"
        f"<td class='num'>{esc(entry['wins'])}</td>"
        f"<td class='num'>{esc(entry['comparisons'])}</td>"
        f"<td class='num adv'>{esc(entry['best'])}–{esc(entry['worst'])}</td>"
        "</tr>"
        for entry in result["standing"]
    )
    verdict = (
        "The ranking separates the teams."
        if result["separates_teams"]
        else "Every team shares the same mean rank: the ranking does not"
        " separate them."
    )
    incomparable = ""
    if result["incomparable"]:
        items = "".join(
            f"<li><code>{esc(item['scenario_id'])}</code> turn"
            f" {esc(item['turn'])} — {esc(item['reason'])}</li>"
            for item in result["incomparable"]
        )
        incomparable = (
            f"<p class='adv'>{len(result['incomparable'])} comparison(s) the"
            f" judge declined to rank:</p><ul class='adv'>{items}</ul>"
        )
    return (
        "<section id='judge-ranking'>"
        "<h2>Comparative standing<span class='pill-adv'>advisory</span></h2>"
        "<p class='adv'>The same question, every team's answer, ranked"
        " best-first by a judge that could not see which team wrote which"
        " (labels are shuffled per comparison). Pointwise scores saturate —"
        " a ranking cannot. Mean rank leads because it survives ties;"
        f" wins are shown because a reader thinks in wins. {esc(verdict)}</p>"
        "<table class='data'><thead><tr>"
        "<th>team</th><th class='num'>mean rank</th><th class='num'>wins</th>"
        "<th class='num'>comparisons</th><th class='num'>best–worst</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"{incomparable}"
        "</section>"
    )


def _judge_trust_block(judges: list[dict[str, Any]], run_dir: Path) -> str:
    """How far these scores can be trusted — stated, not implied.

    Two things a reader cannot see from the numbers: whether more than one
    judge ever looked (three passes of one model measure stability, not
    validity), and whether a human ever checked a call. Both are printed,
    including — especially — when the answer is "no".
    """
    view = consensus(judges)
    bits: list[str] = []
    if view["single_actor"]:
        actor = view["actors"][0] if view["actors"] else "one model"
        bits.append(
            f"<b>One judge actor</b> ({esc(actor)}), three passes finalized by"
            " median. That measures how stably this model scores, not whether"
            " it scores correctly — there is no cross-model agreement evidence"
            " in this run."
        )
    else:
        disagreements = view["disagreements"]
        bits.append(
            f"<b>{len(view['actors'])} judge actors</b>"
            f" ({esc(', '.join(view['actors']))}) scored"
            f" {view['cells_scored_by_all']} of {view['cells']} cells in common."
        )
        if disagreements:
            worst = disagreements[0]
            bits.append(
                f"They disagreed on {len(disagreements)} cells; the widest is"
                f" {esc(worst['cell'])} on <code>{esc(worst['axis'])}</code>"
                f" (spread {worst['spread']})."
            )
        else:
            bits.append("They agreed on every axis of every shared cell.")

    human = agreement(judges, load_adjudication(run_dir))
    if human is None:
        bits.append(
            "<b>No human adjudication.</b> Nobody has confirmed or overruled a"
            " judged call in this run, so the scores carry no human anchor."
        )
    else:
        bits.append(
            f"<b>Human adjudication:</b> the judge's call matched a reviewer on"
            f" {human['agreed']} of {human['reviewed']} cells reviewed"
            f" ({human['rate']:.0%})."
        )
    return "<div class='note'>" + " ".join(bits) + "</div>"


def _judge_summary_section(
    suite: dict[str, Any],
    results: dict[str, Any],
    judges: list[dict[str, Any]],
    judge_manifest: dict[str, Any],
    run_dir: Path,
) -> str:
    """The judge at a glance: one row per team, medians plus the floor and
    the flagged cases — linked into the full rationales below."""
    if not judges:
        return ""
    labels = _team_labels(results, suite)
    by_team: dict[str | None, list[dict[str, Any]]] = {}
    for row in judges:
        by_team.setdefault(_judge_team(row), []).append(row)

    def summary_row(
        name: str, rows: list[dict[str, Any]], *, name_teams: bool = False
    ) -> str:
        composites = [
            row["composite"]
            for row in rows
            if isinstance(row.get("composite"), (int, float))
        ]
        flagged = _weakest_rows(rows)

        def flag_link(row: dict[str, Any]) -> str:
            team = _judge_team(row)
            anchor = _judge_anchor(
                team, str(row.get("scenario_id")), int(row.get("turn") or 0)
            )
            prefix = (
                f"{esc(labels.get(team, str(team)))}: " if name_teams else ""
            )
            return (
                f"<a class='jlink' href='#{anchor}'>{prefix}"
                f"{esc(row.get('scenario_id'))}·turn {esc(row.get('turn'))}"
                f" — {esc(row.get('composite'))}</a>"
            )

        flag_links = ", ".join(flag_link(row) for row in flagged)
        floor = min(composites) if composites else None
        floor_cls = " flagged" if flagged else ""
        cells = [
            f"<td>{esc(name)}</td>",
            f"<td class='num'>{len(rows)}</td>",
        ]
        # Axes first: they are what the judge actually scored. The composite
        # is a derived convenience and sits at the end, where a reader can
        # ignore it.
        for axis in _JUDGE_AXES:
            values = [row[axis] for row in rows if isinstance(row.get(axis), (int, float))]
            if not values:
                cells.append("<td class='num'>—</td>")
                continue
            low, high = min(values), max(values)
            spread = "" if low == high else f"<span class='adv'> {low:g}–{high:g}</span>"
            cells.append(f"<td class='num'>{median(values):g}{spread}</td>")
        cells.append(f"<td>{flag_links or '—'}</td>")
        cells.append(
            f"<td class='num adv'>{median(composites):g}"
            + (f" <span class='{floor_cls.strip() or 'adv'}'>↓{floor:g}</span>" if floor is not None and floor != median(composites) else "")
            + "</td>"
            if composites
            else "<td class='num adv'>—</td>"
        )
        return "<tr>" + "".join(cells) + "</tr>"

    rows_html = [
        summary_row(labels.get(team, str(team) if team else "this run"), team_rows)
        for team, team_rows in sorted(
            by_team.items(), key=lambda item: str(item[0] or "")
        )
    ]
    if len(by_team) > 1:
        rows_html.append(summary_row("all teams", judges, name_teams=True))

    model = judge_manifest.get("model") or (judges[0].get("model") if judges else "")
    provider = judge_manifest.get("provider") or (judges[0].get("provider") if judges else "")
    rubric = str(
        judge_manifest.get("rubric_sha256") or judges[0].get("rubric_sha256") or ""
    )
    protocol = (
        f"Judge: {esc(model)} ({esc(provider)}) · three independent passes"
        " finalized by per-axis medians"
        + (f" · rubric {esc(rubric[:12])}…" if rubric else "")
    )
    axis_heads = "".join(f"<th class='num'>{esc(_AXIS_HEADS[a])}</th>" for a in _JUDGE_AXES)
    return (
        "<section id='judge-summary'>"
        "<h2>Judge summary<span class='pill-adv'>advisory</span></h2>"
        "<p class='adv'>A separate AI judge read every executed query against"
        " its recorded evidence and scored four axes from 0 to 3. The axes are"
        " what it judged, so they lead; each cell shows the median and, where"
        " the scores differ, the range behind it. Advisory means it never gates"
        " acceptance — the row-for-row reference check does. Where that check"
        " failed, the judge explains why; it cannot overrule it.</p>"
        "<table class='data'><thead><tr>"
        "<th>team</th><th class='num'>queries judged</th>"
        f"{axis_heads}<th>weakest queries</th>"
        "<th class='num'>composite</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
        f"<p class='adv'>{protocol}</p>"
        "<dl class='legend'>"
        "<dt>intent</dt><dd>did the SQL answer the question as asked (0–3)</dd>"
        "<dt>SQL craft</dt><dd>clean, minimal, executable construction — joins,"
        " predicates, no dead branches (0–3)</dd>"
        "<dt>schema</dt><dd>only catalogued tables and columns, parameters bound"
        " with correct types (0–3)</dd>"
        "<dt>follow-up</dt><dd>the revision honors the new instruction without"
        " breaking what worked (0–3, follow-up turns only)</dd>"
        "<dt>weakest queries</dt><dd>every query the judge marked down on any"
        " axis, worst first (at most three shown) — the rubric's own anchors"
        " decide, not a composite cutoff. Blank when nothing was marked"
        " down.</dd>"
        "<dt>composite</dt><dd>a weighted convenience score (0–100; opening"
        " queries 47/29/24, follow-ups 40/25/20/15) with the team's floor"
        " after ↓. Read the axes first: when they saturate, the composite is"
        " nearly a step function of whichever axis dropped.</dd>"
        "</dl>"
        f"{_judge_trust_block(judges, run_dir)}"
        "</section>"
    )


def _judge_detail_section(
    suite: dict[str, Any],
    results: dict[str, Any],
    judges: list[dict[str, Any]],
) -> str:
    """Every judge rationale, grouped per team, flagged cases first and open."""
    if not judges:
        return (
            "<section><h2>Judge detail<span class='pill-adv'>advisory</span></h2>"
            "<div class='note'>Judge not available for this run"
            " (development / no-judge path).</div></section>"
        )
    labels = _team_labels(results, suite)
    by_team: dict[str | None, list[dict[str, Any]]] = {}
    for row in judges:
        by_team.setdefault(_judge_team(row), []).append(row)
    chunks: list[str] = []
    for team, team_rows in sorted(by_team.items(), key=lambda item: str(item[0] or "")):
        if len(by_team) > 1 or team is not None:
            chunks.append(
                f"<h3>{esc(labels.get(team, str(team)))}"
                + (f" <span class='adv'>{esc(team)}</span>" if team else "")
                + "</h3>"
            )
        weakest = {
            str(row.get("version_id")) for row in _weakest_rows(team_rows)
        }
        ordered = sorted(
            team_rows,
            key=lambda row: (
                str(row.get("version_id")) not in weakest,
                row.get("composite") if isinstance(row.get("composite"), (int, float)) else 0,
                str(row.get("scenario_id")),
                int(row.get("turn") or 0),
            ),
        )
        for row in ordered:
            composite = row.get("composite")
            flagged = str(row.get("version_id")) in weakest
            anchor = _judge_anchor(
                team, str(row.get("scenario_id")), int(row.get("turn") or 0)
            )
            summary = (
                f"<code>{esc(row.get('scenario_id'))}</code>"
                f" turn {esc(row.get('turn'))}"
                f" · composite {esc(composite)}"
                + (" — <span class='flagged'>flagged</span>" if flagged else "")
            )
            chunks.append(
                f"<details class='jcell' id='{anchor}'{' open' if flagged else ''}>"
                f"<summary>{summary}</summary>"
                f"<div class='adv'>version {esc(row.get('version_id'))}</div>"
                f"{_render_judge_block(row)}"
                "</details>"
            )
    return (
        "<section><h2>Judge detail<span class='pill-adv'>advisory</span></h2>"
        + "".join(chunks)
        + "</section>"
    )


def _methods_section(
    suite: dict[str, Any], results: dict[str, Any], meta_bits: list[str]
) -> str:
    """How the run works, the dataset, and the model lineup — folded, at the end."""
    inner: list[str] = [
        "<p class='adv'>Each conversation runs live: a question"
        " generates SQL (a writer model drafts it; reviewed profiles also invoke"
        " their configured reviewer), the query"
        " is validated and executed against PostgreSQL, then a follow-up"
        " instruction refines the exact current query and the successor is"
        " validated and executed again. Executed results are re-checked against"
        " an independently-authored gold query (byte-level row-set match) and an"
        " independent read-only PostgreSQL cross-check.</p>",
    ]
    dataset = results.get("dataset") or {}
    if dataset:
        facts = []
        for label, key in (
            ("patients", "patients"),
            ("results", "results"),
            ("test types", "testTypes"),
        ):
            if dataset.get(key) is not None:
                facts.append(f"{esc(dataset[key])} {label}")
        window = " – ".join(
            str(dataset[k])[:10] for k in ("firstObservedAt", "lastObservedAt")
            if dataset.get(k)
        )
        if window:
            facts.append(esc(window))
        if facts:
            inner.append(
                f"<p class='adv'>Dataset <code>{esc(dataset.get('datasetId'))}</code>"
                f" ({esc(dataset.get('dataSource'))}): " + " · ".join(facts) + "</p>"
            )
    profiles = suite.get("profiles") or {}
    if profiles:
        rows = "".join(
            f"<tr><td><code>{esc(pid)}</code></td>"
            f"<td>{esc(cfg.get('writerModelId'))}</td>"
            f"<td>{esc(cfg.get('reviewerModelId') or '— (writer only)')}</td></tr>"
            for pid, cfg in sorted(profiles.items())
        )
        inner.append(
            "<table class='data'><thead><tr><th>profile</th><th>writer model</th>"
            f"<th>reviewer model</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    inner.append(f"<p class='adv'>{esc(' · '.join(meta_bits))}</p>")
    return (
        "<section><h2>Methods &amp; provenance</h2>"
        "<details><summary>How this works, the dataset, and the model lineup</summary>"
        + "".join(inner)
        + "</details></section>"
    )


def _scenario_narrative_section(
    run_dir: Path, suite: dict[str, Any], results: dict[str, Any]
) -> str:
    """One card per scenario: what was asked, how it was refined, what ran."""
    # One card per (team, scenario): a comparison run's teams answered the
    # same scenario independently and must not blend into one card.
    by_cell: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    teams: list[str | None] = []
    for row in results.get("results") or []:
        team = row.get("profileId") if isinstance(row.get("profileId"), str) else None
        by_cell.setdefault((team, str(row["scenarioId"])), []).append(row)
        if team not in teams:
            teams.append(team)
    cards: list[str] = []
    for team in teams:
        for scenario in suite.get("scenarios") or []:
            sid = str(scenario.get("id"))
            rows = by_cell.get((team, sid)) or []
            label = f"{team} · {sid}" if team else sid
            completed = [r for r in rows if r.get("status") != "skipped"]
            if rows and not completed:
                cards.append(
                    f"<div class='note'><h3><code>{esc(label)}</code></h3>"
                    "<p class='adv'>Skipped — manual-only scenario (requires an"
                    " operator-controlled external failure).</p></div>"
                )
                continue
            if not rows:
                continue
            cards.append(
                _scenario_card(run_dir, scenario, label, completed)
            )
    return (
        ("<section><h2>What each scenario does</h2>" + "".join(cards) + "</section>")
        if cards
        else ""
    )


def _scenario_card(
    run_dir: Path,
    scenario: dict[str, Any],
    label: str,
    completed: list[dict[str, Any]],
) -> str:
    """One (team, scenario) card: the ask, the refinement, what actually ran."""
    chunks = [f"<div class='note'><h3><code>{esc(label)}</code></h3>"]
    if True:
        chunks.append(
            f"<p><b>Question</b> — {esc(scenario.get('initialQuestion'))}</p>"
        )
        # The conversation as it ran: the writer's opening answer in words
        # when it asked or declined, then each scripted turn and its answer.
        first = completed[0] if completed else {}
        if first.get("baseAnswerText"):
            chunks.append(
                f"<p><b>Writer</b> — {esc(first.get('baseAnswerText'))}</p>"
            )
        recorded_turns = first.get("turns") or []
        if recorded_turns:
            for index, turn in enumerate(recorded_turns, start=2):
                chunks.append(
                    f"<p><b>Turn {index}</b> — "
                    f"“{esc(turn.get('instruction'))}” → "
                    f"{esc(turn.get('observedOutcome') or '?')}"
                    + (
                        f": {esc(turn.get('answerText'))}"
                        if turn.get("answerText")
                        else ""
                    )
                    + "</p>"
                )
        elif scenario.get("followupInstruction"):
            chunks.append(
                f"<p><b>Follow-up</b> — {esc(scenario.get('followupInstruction'))}</p>"
            )
        facts: list[str] = []
        if completed:
            reps = len(completed)
            all_ok = all(
                all(a.get("passed") for a in (r.get("assertions") or []))
                for r in completed
            )
            facts.append(
                f"{reps} run{'s' if reps != 1 else ''} — "
                + ("all passed" if all_ok else "FAILURES present")
            )
        key = (
            _row_scenario_key(completed[0])
            if completed
            else str(scenario.get("id"))
        )
        base_rows = _execution_row_count(run_dir, key, "06-execute-base.json")
        succ_rows = _execution_row_count(run_dir, key, "13-execute-successor.json")
        if base_rows is not None:
            facts.append(f"base query returned {base_rows} rows")
        if succ_rows is not None:
            facts.append(f"refined query returned {succ_rows} rows")
        if facts:
            chunks.append(f"<p class='adv'>{esc(' · '.join(facts))}</p>")
    chunks.append("</div>")
    return "".join(chunks)


def _build_body(run_dir: Path, blob: dict[str, Any]) -> str:
    manifest = blob["manifest"]
    suite = blob["suite"]
    results = blob["results"]
    judges = blob["judges"]
    config = blob.get("config") or {}
    judge_manifest = blob.get("judge_manifest") or {}
    judge_cells = _judges_by_cell(judges)

    suite_id = suite.get("id") or results.get("suiteId") or manifest.get("run_id")
    title = f"Catalyst notebook report · {suite_id}"
    meta_bits = [
        f"run_id={manifest.get('run_id')}",
        f"evidence_status={manifest.get('evidence_status', 'development')}",
        f"dataset={manifest.get('dataset_id')}",
        f"catalog={suite.get('catalogVersion') or manifest.get('schema_mapping_version')}",
        f"provider={suite.get('providerName') or (manifest.get('otel') or {}).get('gen_ai.provider.name')}",
    ]
    profiles = suite.get("profiles") or {}
    if profiles:
        meta_bits.append("profiles=" + ",".join(sorted(profiles)))

    rows_html: list[str] = []
    for row in results.get("results") or []:
        sid = _row_label(row)
        assertions = row.get("assertions") or []
        gold_ok = _gold_passed(assertions)
        # Judge rows join on (team, scenario): a comparison run's teams share
        # every scenario id, so the bare id would collide across teams.
        cell_judges = judge_cells.get(
            (_row_team(row), str(row.get("scenarioId")))
        ) or []
        lowest = min(
            (
                jrow
                for jrow in cell_judges
                if isinstance(jrow.get("composite"), (int, float))
            ),
            key=lambda jrow: jrow["composite"],
            default=None,
        )
        merged = merge_gold_and_judge(gold_passed=gold_ok, judge_row=lowest)
        verdict = merged["reported"]
        v_cls = "pass" if verdict == "PASS" else "fail"
        judge_cell = (
            " · ".join(
                f"<a class='jlink' href='#{_judge_anchor(_judge_team(jrow), str(jrow.get('scenario_id')), int(jrow.get('turn') or 0))}'>"
                f"{esc(jrow.get('composite'))}</a>"
                for jrow in cell_judges
            )
            or "—"
        )
        fail_bits = []
        for a in assertions:
            if a.get("passed"):
                continue
            detail = _assertion_fail_details(run_dir, _row_scenario_key(row), a)
            fail_bits.append(f"<div>{_fail_chip(a)} {detail}</div>")
        assertion_names = ", ".join(esc(a.get("name")) for a in assertions)
        passed_n = sum(1 for a in assertions if a.get("passed"))
        assertions_cell = (
            f"<details><summary>{passed_n}/{len(assertions)} passed</summary>"
            f"<div class='adv'>{assertion_names}</div></details>"
            if assertions
            else "—"
        )
        rows_html.append(
            "<tr>"
            f"<td><code>{esc(sid)}</code><div class='adv'>{esc(row.get('family'))}</div></td>"
            f"<td class='{v_cls}'>{esc(verdict)}</td>"
            f"<td>{'yes' if gold_ok else 'no'}</td>"
            f"<td class='adv'>{judge_cell}</td>"
            f"<td>{assertions_cell}</td>"
            f"<td>{''.join(fail_bits) if fail_bits else '—'}</td>"
            "</tr>"
        )

    timeline: list[str] = []
    for row in results.get("results") or []:
        sid = _row_label(row)
        timeline.append(
            "<tr>"
            f"<td><code>{esc(sid)}</code></td>"
            f"<td>{esc(row.get('sessionId'))}</td>"
            f"<td>{esc(row.get('baseVersionId'))} → {esc(row.get('selectedVersionId'))}</td>"
            f"<td>{esc(row.get('baseExecutionId'))} / {esc(row.get('successorExecutionId'))}</td>"
            f"<td>{esc((row.get('timing') or {}).get('unadjustedGenerationWallMs'))} ms</td>"
            "</tr>"
        )

    diff_sections: list[str] = []
    for row in results.get("results") or []:
        sid = row["scenarioId"]
        versions = _scenario_sql_versions(run_dir, _row_scenario_key(row))
        if len(versions) < 2:
            continue
        chunks = [f"<h3><code>{esc(_row_label(row))}</code> SQL versions</h3>"]
        for i in range(len(versions) - 1):
            a_label, a_sql = versions[i]
            b_label, b_sql = versions[i + 1]
            diff = unified_sql_diff(a_sql, b_sql, fromfile=a_label, tofile=b_label)
            if not diff.strip():
                continue
            chunks.append(
                f"<pre class='diff'>{esc(diff)}</pre>"
            )
        if len(chunks) > 1:
            diff_sections.append("".join(chunks))

    empty_diff = "<div class='note'>No multi-version SQL diffs found.</div>"
    diff_html = "".join(diff_sections) or empty_diff

    body = (
        "<header class='topbar'>"
        "<div>"
        f"<h1>{esc(title)}</h1>"
        f"<div class='meta'>{esc(' · '.join(meta_bits))}</div>"
        "<div class='meta'>Development fixture evidence — not a release claim.</div>"
        "</div>"
        f"{THEME_TOGGLE_BUTTON_HTML}"
        "</header>"
        "<main id='report'>"
        f"{_abstract_section(suite, results, judges, config)}"
        f"{_verdict_section(suite, results, config)}"
        f"{_judge_summary_section(suite, results, judges, judge_manifest, run_dir)}"
        f"{_ranking_section(blob.get('judge_rankings') or [], _team_labels(results, suite))}"
        "<section>"
        "<h2>Scenario matrix</h2>"
        "<table class='data'>"
        "<thead><tr>"
        "<th>scenario</th><th>reported</th><th>gold ok</th>"
        "<th>judge by turn (advisory)</th>"
        "<th>assertions</th><th>gold FAIL detail</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
        "</section>"
        f"{_scenario_narrative_section(run_dir, suite, results)}"
        "<section>"
        "<h2>SQL diffs</h2>"
        f"{diff_html}"
        "</section>"
        "<section>"
        "<h2>Turn / version / execution timeline</h2>"
        "<table class='data'>"
        "<thead><tr><th>scenario</th><th>session</th><th>versions</th>"
        "<th>executions</th><th>gen wall</th></tr></thead>"
        f"<tbody>{''.join(timeline)}</tbody></table>"
        "</section>"
        f"{_judge_detail_section(suite, results, judges)}"
        f"{_methods_section(suite, results, meta_bits)}"
        "</main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
    )
    return body


def build_report(run_dir: Path | str) -> Path:
    """Render self-contained ``report.html`` from a notebook validation run directory."""
    run_dir = Path(run_dir)
    manifest = _load_json(run_dir / "run_manifest.json")
    suite = _load_json(run_dir / "suite.json")
    results = _load_json(run_dir / "results.json")
    judges = read_jsonl(run_dir / "judge.jsonl", strict=True)
    blob = {
        "report_family": "catalyst",
        "manifest": manifest,
        "suite": suite,
        "results": results,
        "judges": judges,
        # The frozen seed (gates, publish copy) and the finalized-judge
        # manifest travel with the run; both may be absent on older runs.
        "config": load_frozen(run_dir),
        # Comparative rankings, when a ranking pass has been run.
        "judge_rankings": read_jsonl(run_dir / "judge_rank.jsonl", strict=False),
        "judge_manifest": _load_json(run_dir / "judge_manifest.json"),
    }
    body = _build_body(run_dir, blob)
    suite_id = suite.get("id") or results.get("suiteId") or manifest.get("run_id") or "catalyst"
    html = render_document(
        title=f"catalyst report · {suite_id}",
        body_html=body,
        embedded_data=blob,
        style=_STYLE,
        script=_SCRIPT,
        theme_storage_key="oc-theme-report",
    )
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
