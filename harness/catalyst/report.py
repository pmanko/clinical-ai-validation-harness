"""Pure structured JSON report packet builder for Catalyst notebook validation (`openclinai.report.v2`).

Produces `report-data.json`, `run-summary.json`, and `dashboard-data.json` with zero HTML/CSS/JS
in Python or JSON. Supports single-profile, multi-team comparison, and reader-led Phase 1 runs.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.common.dashboard_shards import write_sharded_dashboard_packet
from harness.common.jsonl import read_jsonl
from harness.common.stats import avg, box_stats, ordered_unique, robust_axis_max
from harness.catalyst.attribution import blame, conformed
from harness.catalyst.notebook_validation import assertion_class, validate_notebook_evidence
from harness.catalyst.phase1_evidence import case_records, collection_summary
from harness.catalyst.reader_review import prepare_reader_review, validate_reader_reviews
from harness.catalyst.reconcile import merge_gold_and_judge
from harness.catalyst.run_config import load_frozen


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


def _path_matches_repetition(path: Path, root: Path, repetition: int | None) -> bool:
    if repetition is None:
        return True
    rel_parts = path.relative_to(root).parts
    rep_dirs = [p for p in rel_parts if p.startswith("repetition-")]
    if not rep_dirs:
        return True
    allowed = {f"repetition-{int(repetition):02d}", f"repetition-{int(repetition)}"}
    return all(p in allowed for p in rep_dirs)


def _scenario_sql_versions(
    run_dir: Path,
    scenario_key: str,
    *,
    repetition: int | None = None,
) -> list[tuple[str, str]]:
    """Return ordered `(relative_path, sql)` pairs discovered under the scenario evidence tree."""
    root = run_dir / "scenarios" / scenario_key
    if not root.exists():
        return []
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".sql"}:
            continue
        if not _path_matches_repetition(path, root, repetition):
            continue
        if (
            "version" not in path.name
            and "save-base-version" not in path.name
            and path.suffix != ".sql"
            and path.name not in {"01-base-sql.sql", "02-successor-sql.sql"}
        ):
            continue
        sql = _extract_sql(path)
        if not sql:
            continue
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
    out: list[tuple[str, str]] = []
    for _, rel, sql in candidates:
        if out and out[-1][1] == sql:
            continue
        out.append((rel, sql))
    return out


def _extract_result_preview(
    run_dir: Path,
    scenario_key: str,
    *,
    repetition: int | None = None,
) -> dict[str, Any] | None:
    root = run_dir / "scenarios" / scenario_key
    if not root.exists():
        return None
    exec_files = [
        p
        for p in sorted(root.rglob("*execute*.json"))
        if _path_matches_repetition(p, root, repetition)
    ]
    for path in reversed(exec_files):
        blob = _load_json(path)
        body = ((blob.get("response") or {}).get("body")) or blob
        res = (body.get("result") if isinstance(body, dict) and isinstance(body.get("result"), dict) else body)
        if isinstance(res, dict) and ("rows" in res or "rowCount" in res):
            rows = res.get("rows") or []
            row_count = res.get("rowCount") if res.get("rowCount") is not None else len(rows)
            return {
                "columns": res.get("columns") or (list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []),
                "rows": rows[:10],
                "row_count": row_count,
                "returned": row_count,
            }
    return None


def entries_from_comparison_run(run_dir: Path | str) -> list[dict[str, Any]]:
    """One entry per team from a single frozen-comparison run."""
    results = _load_json(Path(run_dir) / "results.json")
    team_ids: list[str] = []
    for row in results.get("results") or []:
        profile_id = row.get("profileId")
        if isinstance(profile_id, str) and profile_id not in team_ids:
            team_ids.append(profile_id)
    return [
        {"run_dir": Path(run_dir), "profile_id": team, "profile_label": team}
        for team in team_ids
    ]


def _team_labels(results: dict[str, Any], suite: dict[str, Any]) -> dict[str, str]:
    profiles = suite.get("profiles") or {}
    teams: list[str] = []
    for row in results.get("results") or []:
        team = row.get("profileId") or suite.get("profileId") or "catalyst-default"
        if str(team) not in teams:
            teams.append(str(team))
    if not teams:
        teams = [str(suite.get("profileId") or "catalyst-default")]
    labels: dict[str, str] = {}
    for team in teams:
        cfg = profiles.get(team) or {}
        writer = cfg.get("writerModelId")
        reviewer = cfg.get("reviewerModelId")
        if not writer:
            labels[team] = team
        elif not reviewer:
            labels[team] = f"{writer} (writer-only)"
        elif reviewer == writer:
            labels[team] = f"{writer} (self-checked)"
        else:
            labels[team] = f"{writer} + {reviewer} checker"
    return labels


def _arm_cards_from_suite(
    backends: list[str],
    suite: dict[str, Any],
    labels: dict[str, str],
) -> dict[str, dict[str, Any]]:
    profiles = suite.get("profiles") or {}
    cards: dict[str, dict[str, Any]] = {}
    for b in backends:
        cfg = profiles.get(b) or {}
        writer = cfg.get("writerModelId")
        reviewer = cfg.get("reviewerModelId")
        is_team = bool(writer and reviewer and reviewer != writer)
        models = []
        roles: dict[str, dict[str, Any]] = {}
        if writer:
            w_entry = {"id": writer, "family": writer, "params": "", "quant": ""}
            models.append(w_entry)
            roles["writer"] = w_entry
        if reviewer:
            r_entry = {"id": reviewer, "family": reviewer, "params": "", "quant": ""}
            if reviewer != writer:
                models.append(r_entry)
            roles["reviewer"] = r_entry
        cards[b] = {
            "title": labels.get(b) or b,
            "short_title": labels.get(b) or b,
            "kind": "team" if is_team else "single",
            "path": "catalyst notebook validation",
            "models": models,
            "roles": roles,
            "config": {"knobs": {}, "prompts": []},
        }
    return cards


def _gate_verdict(
    results: dict[str, Any],
    labels: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    gates = (config or {}).get("gates") or {}
    overall = gates.get("overall")
    per_scenario = gates.get("per_scenario")
    rows = [
        r
        for r in (results.get("results") or [])
        if r.get("status") not in {"skipped", "infrastructure_failed"}
    ]
    total = len(rows)
    passed = sum(1 for r in rows if r.get("passed"))
    invalid = sum(
        1 for r in rows if not conformed(r.get("assertions") or [])
    )
    blockers: list[str] = []
    for r in rows:
        if not r.get("passed") or not conformed(r.get("assertions") or []):
            b_info = blame(r.get("assertions") or [])
            root = b_info.get("root") or {}
            why = root.get("why") or root.get("human") or root.get("name") or "failed check"
            sid = r.get("scenarioId") or "?"
            pid = r.get("profileId")
            prefix = f"{pid} / {sid}" if pid else str(sid)
            blockers.append(f"{prefix}: {why}")

    if overall is None and per_scenario is None:
        qualified = (total > 0 and passed == total and invalid == 0)
        verdict = (
            f"Passed {passed}/{total} conversations"
            if qualified
            else (
                f"Undecidable ({invalid} invalid measurement{'s' if invalid != 1 else ''})"
                if invalid
                else f"{passed}/{total} conversations passed"
            )
        )
        return {
            "qualified": qualified,
            "verdict": verdict,
            "passed": passed,
            "total": total,
            "invalid": invalid,
            "blockers": blockers[:12],
        }

    by_team: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        t = str(r.get("profileId") or "default")
        by_team.setdefault(t, {}).setdefault(str(r.get("scenarioId")), []).append(r)

    qual_teams: list[str] = []
    undec_teams: list[str] = []
    for t, by_scen in by_team.items():
        t_rows = [r for rs in by_scen.values() for r in rs]
        if any(not conformed(r.get("assertions") or []) for r in t_rows):
            undec_teams.append(labels.get(t, t))
            continue
        rate = sum(1 for r in t_rows if r.get("passed")) / len(t_rows) if t_rows else 0.0
        worst = min(
            (sum(1 for r in rs if r.get("passed")) / len(rs) for rs in by_scen.values() if rs),
            default=0.0,
        )
        if (overall is None or rate >= float(overall)) and (
            per_scenario is None or worst >= float(per_scenario)
        ):
            qual_teams.append(labels.get(t, t))

    verdict_str = (
        f"Qualified: {', '.join(qual_teams)}"
        if qual_teams
        else (
            f"Undecidable: {', '.join(undec_teams)}"
            if undec_teams
            else "No team qualified"
        )
    )
    return {
        "qualified": bool(qual_teams),
        "verdict": verdict_str,
        "qualified_teams": qual_teams,
        "undecidable_teams": undec_teams,
        "gates": gates,
        "passed": passed,
        "total": total,
        "invalid": invalid,
        "blockers": blockers[:12],
    }


def _assertion_counts(results: dict[str, Any]) -> dict[str, dict[str, int]]:
    ev_pass = ev_fail = cf_pass = cf_fail = 0
    for r in results.get("results") or []:
        for a in r.get("assertions") or []:
            kind = a.get("class") or assertion_class(str(a.get("name") or ""))
            ok = bool(a.get("passed"))
            if kind == "conformance":
                if ok:
                    cf_pass += 1
                else:
                    cf_fail += 1
            else:
                if ok:
                    ev_pass += 1
                else:
                    ev_fail += 1
    return {
        "evaluation": {"passed": ev_pass, "failed": ev_fail},
        "conformance": {"passed": cf_pass, "failed": cf_fail},
    }


def build_catalyst_report_packet(run_dir: Path | str) -> dict[str, Any]:
    """Assemble the `openclinai.report.v2` JSON packet for a Catalyst run directory."""
    run_dir = Path(run_dir)
    suite = _load_json(run_dir / "suite.json")
    manifest = _load_json(run_dir / "run_manifest.json")
    results = _load_json(run_dir / "results.json")
    judges = read_jsonl(run_dir / "judge.jsonl", strict=False)
    config = load_frozen(run_dir)
    judge_manifest = _load_json(run_dir / "judge_manifest.json")

    is_reader_led = suite.get("reportMode") == "reader-led"
    reader_led_block: dict[str, Any] | None = None
    if is_reader_led:
        prepare_reader_review(run_dir)
        validate_reader_reviews(run_dir)
        evidence_index = validate_notebook_evidence(run_dir)
        records = case_records(
            run_dir,
            suite=suite,
            results=results,
            evidence_index=evidence_index,
        )
        coll = collection_summary(suite, results)
        reviews_map: dict[str, Any] = {}
        review_dir = run_dir / "reader-reviews"
        if review_dir.is_dir():
            for path in sorted(review_dir.glob("*.md")):
                rmeta = _load_json(path.with_suffix(".json"))
                reviews_map[path.stem] = {
                    "reviewer": rmeta.get("reviewer"),
                    "model": rmeta.get("model"),
                    "reviewed_at": rmeta.get("reviewedAt"),
                    "text": path.read_text(encoding="utf-8"),
                }
        reader_led_block = {
            "collection_summary": {
                **coll,
                "case_count": len(records),
            },
            "case_records": [
                {
                    "case_id": f"{r.get('profileId')}:{r.get('scenarioId')}",
                    "scenario_id": r.get("scenarioId"),
                    "profile_id": r.get("profileId"),
                    "family": r.get("family"),
                    "measurement_valid": r.get("measurementValid"),
                    "question": ((r.get("turns") or [{}])[0]).get("instruction") or "",
                    "observed_outcome": ((r.get("turns") or [{}])[-1]).get("observedOutcome") or "",
                    "turns": r.get("turns") or [],
                }
                for r in records
            ],
            "reader_reviews": reviews_map,
        }

    labels = _team_labels(results, suite)
    backends = list(labels.keys())
    arm_cards = _arm_cards_from_suite(backends, suite, labels)

    suite_scenarios = {
        str(s.get("id")): s
        for s in (suite.get("scenarios") or [])
        if isinstance(s, dict) and s.get("id")
    }
    raw_rows = [
        r
        for r in (results.get("results") or [])
        if isinstance(r, dict) and r.get("scenarioId")
    ]
    scenario_ids = ordered_unique(
        [str(r.get("scenarioId")) for r in raw_rows]
        + list(suite_scenarios.keys())
    )

    judge_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for j in judges:
        if not isinstance(j, dict):
            continue
        j_team = j.get("team")
        if not j_team:
            for p in j.get("evidence_paths") or []:
                parts = str(p).split("/")
                if len(parts) >= 3 and parts[0] == "scenarios" and not parts[2].startswith("repetition-"):
                    j_team = parts[1]
                    break
        b_id = str(j_team or backends[0])
        s_id = str(j.get("scenario_id") or "")
        judge_by_cell.setdefault((s_id, b_id), []).append(j)

    scenarios_out: list[dict[str, Any]] = []
    judge_rows_out: list[dict[str, Any]] = []
    lat_by_b: dict[str, list[float]] = {b: [] for b in backends}
    chars_by_b: dict[str, list[float]] = {b: [] for b in backends}

    for sid in scenario_ids:
        s_def = suite_scenarios.get(sid) or {}
        question = str(s_def.get("initialQuestion") or s_def.get("comment") or sid)
        s_rows = [r for r in raw_rows if str(r.get("scenarioId")) == sid]
        rows_by_b: dict[str, list[dict[str, Any]]] = {}
        for b in backends:
            b_rows = [
                r
                for r in s_rows
                if str(r.get("profileId") or suite.get("profileId") or "catalyst-default") == b
            ]
            if not b_rows and len(backends) == 1 and s_rows:
                b_rows = list(s_rows)
            if b_rows:
                indexed = list(enumerate(b_rows))
                indexed.sort(
                    key=lambda pair: (
                        int(pair[1]["repetition"])
                        if isinstance(pair[1].get("repetition"), int)
                        else pair[0],
                        pair[0],
                    )
                )
                rows_by_b[b] = [pair[1] for pair in indexed]

        max_reps = max((len(rs) for rs in rows_by_b.values()), default=0)
        scen_turns_out: list[dict[str, Any]] = []
        for rep_idx in range(max_reps):
            turn_no = rep_idx + 1
            turn_cells: dict[str, dict[str, Any]] = {}
            rep_labels: list[int] = []
            for b, b_rows in rows_by_b.items():
                if rep_idx >= len(b_rows):
                    continue
                row = b_rows[rep_idx]
                raw_rep = row.get("repetition")
                rep_num = (
                    int(raw_rep)
                    if isinstance(raw_rep, int)
                    else (turn_no if len(b_rows) > 1 else None)
                )
                if rep_num is not None:
                    rep_labels.append(rep_num)
                scen_key = (
                    f"{b}/{sid}"
                    if (row.get("profileId") and (run_dir / "scenarios" / b / sid).exists())
                    else sid
                )
                versions = _scenario_sql_versions(run_dir, scen_key, repetition=rep_num)
                sql_diff = ""
                if len(versions) >= 2:
                    diffs = []
                    for idx in range(len(versions) - 1):
                        d_txt = unified_sql_diff(
                            versions[idx][1],
                            versions[idx + 1][1],
                            fromfile=versions[idx][0],
                            tofile=versions[idx + 1][0],
                        )
                        if d_txt.strip():
                            diffs.append(d_txt)
                    sql_diff = "\n\n".join(diffs)

                conv_turns: list[dict[str, Any]] = []
                base_q = row.get("question") or question
                conv_turns.append({"role": "user", "text": base_q})
                conv_turns.append(
                    {
                        "role": "writer",
                        "outcome": row.get("baseOutcome"),
                        "text": row.get("baseAnswerText") or "",
                        "sql": row.get("baseSql") or (versions[0][1] if versions else ""),
                    }
                )
                turns_list = row.get("turns") or []
                if not turns_list and s_def.get("followupInstruction"):
                    conv_turns.append(
                        {"role": "user (turn 2)", "text": str(s_def.get("followupInstruction"))}
                    )
                for idx, t_item in enumerate(turns_list, start=2):
                    if not isinstance(t_item, dict):
                        continue
                    conv_turns.append(
                        {"role": f"user (turn {idx})", "text": t_item.get("instruction") or ""}
                    )
                    conv_turns.append(
                        {
                            "role": f"writer (turn {idx})",
                            "outcome": t_item.get("observedOutcome"),
                            "text": t_item.get("answerText") or "",
                            "sql": t_item.get("sql") or "",
                        }
                    )

                assertions = row.get("assertions") or []
                all_assertions = [
                    {
                        "name": a.get("name"),
                        "passed": bool(a.get("passed")),
                        "class": a.get("class") or assertion_class(str(a.get("name") or "")),
                        "evidence": a.get("evidence"),
                    }
                    for a in assertions
                    if isinstance(a, dict)
                ]
                failed_assertions = [a for a in all_assertions if not a["passed"]]
                final_sql = (
                    row.get("selectedSql")
                    or (versions[-1][1] if versions else "")
                    or row.get("baseSql")
                    or ""
                )
                wall_ms = int(
                    ((row.get("timing") or {}).get("unadjustedGenerationWallMs")) or 0
                )
                if wall_ms > 0:
                    lat_by_b.setdefault(b, []).append(float(wall_ms))
                chars_by_b.setdefault(b, []).append(float(len(final_sql)))

                passed = bool(row.get("passed"))
                is_conformant = conformed(assertions)
                c_jrows_all = judge_by_cell.get((sid, b)) or []
                if rep_num is not None and c_jrows_all:
                    rep_tokens = {f"repetition-{rep_num:02d}", f"repetition-{rep_num}"}
                    matched_jrows = [
                        j
                        for j in c_jrows_all
                        if j.get("repetition") == rep_num
                        or any(
                            any(tok in str(p).split("/") for tok in rep_tokens)
                            for p in (j.get("evidence_paths") or [])
                        )
                    ]
                    c_jrows = matched_jrows if matched_jrows else c_jrows_all
                else:
                    c_jrows = c_jrows_all

                merged = merge_gold_and_judge(
                    gold_passed=passed,
                    judge_row=c_jrows[-1] if c_jrows else None,
                )
                reported_str = (
                    f"{merged['reported']} (advisory judge {merged['judge_composite']}/100)"
                    if merged.get("judge_composite") is not None
                    else merged["reported"]
                )
                res_preview = row.get("resultPreview") or _extract_result_preview(
                    run_dir, scen_key, repetition=rep_num
                )
                turn_cells[b] = {
                    "error": None if is_conformant else "conformance check failed",
                    "http_status": 200 if is_conformant else 500,
                    "answer_text": final_sql,
                    "answer_view": {
                        "status": "checked" if passed else ("failed" if not is_conformant else "needs_review"),
                        "label": reported_str,
                        "tone": "success" if passed else "danger",
                        "note": "" if passed else (failed_assertions[0]["name"] if failed_assertions else ""),
                        "findings": [],
                    },
                    "indepth_view": {"status": "not_in_profile"},
                    "answer_validation_status": "checked" if passed else "needs_review",
                    "blocks": [],
                    "sources": {},
                    "temporal_gate": {"status": "pass" if passed else "fail"},
                    "stage_timings": [],
                    "degraded": not is_conformant,
                    "metrics": {
                        "latency_ms": wall_ms,
                        "http_status": 200 if is_conformant else 500,
                        "citation_count": len(versions),
                        "first_turn": turn_no == 1,
                        "json_valid": is_conformant,
                    },
                    "catalyst_turn": {
                        "repetition": rep_num,
                        "passed": passed,
                        "conformed": is_conformant,
                        "reported": reported_str,
                        "final_answer": final_sql,
                        "conversation_turns": conv_turns,
                        "sql_versions": [{"path": p, "sql": s} for p, s in versions],
                        "sql_diff": sql_diff,
                        "result_preview": res_preview,
                        "assertions": all_assertions,
                        "failed_assertions": failed_assertions,
                        "judge_detail": c_jrows,
                    },
                }

            if turn_cells:
                rep_lbl = rep_labels[0] if rep_labels else turn_no
                turn_entry: dict[str, Any] = {
                    "turn": turn_no,
                    "question": (
                        f"{question} (repetition {rep_lbl})" if max_reps > 1 else question
                    ),
                    "cells": turn_cells,
                }
                if max_reps > 1 or rep_labels:
                    turn_entry["repetition"] = rep_lbl
                scen_turns_out.append(turn_entry)

        for b, b_rows in rows_by_b.items():
            c_jrows_all = judge_by_cell.get((sid, b)) or []
            if not c_jrows_all:
                continue
            scen_passed = all(bool(r.get("passed")) for r in b_rows)
            raw_comp = round(
                sum(float(j.get("composite") or 0.0) for j in c_jrows_all) / len(c_jrows_all),
                1,
            )
            adj_comp = raw_comp if scen_passed else min(raw_comp, 40.0)
            acc_10 = round(raw_comp / 10.0, 1)
            last_j = c_jrows_all[-1]
            note_parts = [
                str(last_j.get(k))
                for k in (
                    "rationale",
                    "intent_fidelity_rationale",
                    "sql_quality_rationale",
                    "schema_discipline_rationale",
                )
                if last_j.get(k)
            ]
            judge_rows_out.append(
                {
                    "scenario_id": sid,
                    "backend_id": b,
                    "composite": raw_comp,
                    "raw_benchmark_score": raw_comp,
                    "benchmark_score": adj_comp,
                    "safety_adjusted_benchmark_score": adj_comp,
                    "accuracy": acc_10,
                    "completeness": acc_10,
                    "relevance": acc_10,
                    "abstention_outcome": "n-a",
                    "citation_groundedness": "supported" if scen_passed else "partly",
                    "harm": False,
                    "critical_omission": not scen_passed,
                    "severe_harm": False,
                    "note": " · ".join(note_parts),
                }
            )

        if scen_turns_out:
            scenarios_out.append(
                {
                    "scenario_id": sid,
                    "turns": scen_turns_out,
                }
            )

    summary_rows: list[dict[str, Any]] = []
    judge_summary_rows: list[dict[str, Any]] = []
    for b in backends:
        b_rows = [
            r
            for r in raw_rows
            if str(r.get("profileId") or suite.get("profileId") or "catalyst-default") == b
        ]
        if not b_rows and len(backends) == 1:
            b_rows = raw_rows
        lats = [int(x) for x in lat_by_b.get(b, [])]
        passed_n = sum(1 for r in b_rows if r.get("passed"))
        invalid_n = sum(1 for r in b_rows if not conformed(r.get("assertions") or []))
        total_n = len(b_rows)
        summary_rows.append(
            {
                "backend_id": b,
                "label": labels.get(b, b),
                "turns": total_n,
                "valid_turns": total_n - invalid_n,
                "avg_latency_ms": avg(lats),
                "max_latency_ms": max(lats) if lats else 0,
                "total_chart_refs": total_n,
                "resolved_chart_refs": passed_n,
                "unresolved_chart_refs": total_n - passed_n,
                "degraded": invalid_n,
                "errors": invalid_n,
                "temporal_gate_pass": passed_n,
                "temporal_gate_warn": 0,
                "temporal_gate_fail": total_n - passed_n,
                "temporal_gate_applied": 0,
                "answer_check_edited": 0,
                "answer_check_flagged": total_n - passed_n,
                "stage_latency_ms": {},
                "catalyst": {
                    "passed": passed_n,
                    "total": total_n,
                    "invalid": invalid_n,
                },
            }
        )
        b_jrows = [jr for jr in judge_rows_out if jr["backend_id"] == b]
        if b_jrows:
            raw_scores = [float(jr["raw_benchmark_score"]) for jr in b_jrows]
            adj_scores = [float(jr["safety_adjusted_benchmark_score"]) for jr in b_jrows]
            raw_mean = round(sum(raw_scores) / len(raw_scores), 1)
            adj_mean = round(sum(adj_scores) / len(adj_scores), 1)
            mean_10 = round(raw_mean / 10.0, 2)
            judge_summary_rows.append(
                {
                    "backend": b,
                    "n": len(b_jrows),
                    "composite_mean": raw_mean,
                    "raw_benchmark_score": raw_mean,
                    "benchmark_score": adj_mean,
                    "safety_adjusted_benchmark_score": adj_mean,
                    "accuracy_mean": mean_10,
                    "completeness_mean": mean_10,
                    "relevance_mean": mean_10,
                    "harm_count": 0,
                    "critical_omission_count": sum(1 for jr in b_jrows if jr.get("critical_omission")),
                    "severe_harm_count": 0,
                    "abstention": {"correct": 0, "failed-to-abstain": 0},
                    "groundedness": {
                        "supported": sum(1 for jr in b_jrows if jr.get("citation_groundedness") == "supported"),
                        "partly": sum(1 for jr in b_jrows if jr.get("citation_groundedness") == "partly"),
                        "unsupported": sum(1 for jr in b_jrows if jr.get("citation_groundedness") == "unsupported"),
                    },
                    "temporal": {"date_wrong": 0, "window_over": 0, "trend_fab": 0},
                }
            )

    lat_series = [
        {"backend": b, **(box_stats(lat_by_b[b]) or {})}
        for b in backends
        if lat_by_b.get(b) and box_stats(lat_by_b[b])
    ]
    all_lats = [x for b in backends for x in lat_by_b.get(b, [])]
    char_series = [
        {"backend": b, **(box_stats(chars_by_b[b]) or {})}
        for b in backends
        if chars_by_b.get(b) and box_stats(chars_by_b[b])
    ]
    all_chars = [x for b in backends for x in chars_by_b.get(b, [])]

    run_id = str(
        results.get("runId")
        or manifest.get("run_id")
        or run_dir.name
    )
    gv = _gate_verdict(results, labels, config)
    ac = _assertion_counts(results)

    catalyst_meta: dict[str, Any] = {
        "kind": "reader-led" if is_reader_led else ("comparison" if len(backends) > 1 else "single"),
        "suite_id": suite.get("id") or results.get("suiteId") or "",
        "catalog_version": results.get("catalogVersion") or "",
        "dataset": results.get("dataset"),
        "gate_verdict": gv,
        "assertion_counts": ac,
        "gate": {
            "verdict": "QUALIFIED" if gv.get("qualified") else ("UNDECIDABLE" if gv.get("invalid") else "NOT_QUALIFIED"),
            "headline": gv.get("verdict") or "",
            "qualified": gv.get("qualified_teams") or ([backends[0]] if gv.get("qualified") and backends else []),
            "undecidable": gv.get("undecidable_teams") or [],
        },
        "totals": {
            "passed": gv.get("passed", 0),
            "total": gv.get("total", 0),
            "invalid": gv.get("invalid", 0),
            "conformance_passed": ac["conformance"]["passed"],
            "conformance_total": ac["conformance"]["passed"] + ac["conformance"]["failed"],
            "evaluation_passed": ac["evaluation"]["passed"],
            "evaluation_total": ac["evaluation"]["passed"] + ac["evaluation"]["failed"],
        },
    }
    if reader_led_block:
        catalyst_meta["reader_led"] = reader_led_block

    has_judge = bool(judge_rows_out)
    judge_actor_name = str(judge_manifest.get("model") or "catalyst-gold-and-judge")
    run_blob: dict[str, Any] = {
        "run_id": run_id,
        "family": "catalyst",
        "meta": {
            "run_id": run_id,
            "component": manifest.get("component") or "catalyst-notebook-validation",
            "git_sha": str(manifest.get("git_sha") or "")[:10],
            "dataset_id": manifest.get("dataset_id") or suite.get("id") or "catalyst-notebook",
            "provider": ((manifest.get("otel") or {}).get("gen_ai.provider.name")) or "catalyst",
            "generated_at": manifest.get("generated_at") or results.get("completedAt") or "",
            "reference_date": None,
        },
        "backends": backends,
        "labels": labels,
        "scenarios": scenarios_out,
        "summary": summary_rows,
        "metrics": {
            "latency_ms": {
                "label": "latency (ms)",
                "series": lat_series,
                "axis_max": round(robust_axis_max(lat_series, all_lats), 2),
            },
            "citation_count": {"label": "SQL versions", "series": [], "axis_max": 0},
            "answer_chars": {
                "label": "SQL length (chars)",
                "series": char_series,
                "axis_max": round(robust_axis_max(char_series, all_chars), 2),
            },
        },
        "judge": judge_summary_rows,
        "judge_rows": judge_rows_out,
        "judge_actors": [judge_actor_name] if has_judge else [],
        "judge_actor_cells": {},
        "judging": {
            "recorded": has_judge,
            "aggregation": "single" if has_judge else "none",
            "canonical": [judge_actor_name] if has_judge else [],
            "sentence": (
                f"Deterministic SQL gold-check + advisory judge ({judge_actor_name})."
                if has_judge
                else "Deterministic SQL gold-check & conformance suite."
            ),
            "cards": [],
        },
        "judge_passes": {},
        "judge_combined": [],
        "calibrated": [],
        "adjudication_rows": [],
        "check_precision": None,
        "patients": [],
        "context": None,
        "arm_cards": arm_cards,
        "catalyst": catalyst_meta,
    }
    return {
        "schema": "openclinai.report.v2",
        "schema_version": 2,
        "family": "catalyst",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [run_blob],
    }


def build_comparison_report(
    entries: list[dict[str, Any]],
    *,
    title: str = "Catalyst profile comparison",
    gates: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assemble a multi-entry Catalyst profile comparison `openclinai.report.v2` packet."""
    if not entries:
        return {
            "schema": "openclinai.report.v2",
            "schema_version": 2,
            "family": "catalyst",
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runs": [],
        }
    first_dir = Path(entries[0]["run_dir"])
    packet = build_catalyst_report_packet(first_dir)
    packet["title"] = title
    run_blob = packet["runs"][0]
    comparison_entries = []
    for entry in entries:
        r_dir = Path(entry["run_dir"])
        res = _load_json(r_dir / "results.json")
        pid = entry["profile_id"]
        rows = [
            r
            for r in (res.get("results") or [])
            if r.get("status") not in {"skipped", "infrastructure_failed"}
            and (not r.get("profileId") or r.get("profileId") == pid)
        ]
        passed = sum(1 for r in rows if r.get("passed"))
        conf = sum(1 for r in rows if conformed(r.get("assertions") or []))
        wall = [
            int(r["timing"]["unadjustedGenerationWallMs"])
            for r in rows
            if isinstance(r.get("timing"), dict) and "unadjustedGenerationWallMs" in r["timing"]
        ]
        comparison_entries.append(
            {
                "entry_id": entry.get("profile_label") or pid,
                "profile_id": pid,
                "model_id": pid,
                "passed_count": f"{passed}/{len(rows)}",
                "conformed_count": f"{conf}/{len(rows)}",
                "avg_latency_ms": avg(wall) if wall else None,
            }
        )
    run_blob.setdefault("catalyst", {})["comparison_entries"] = comparison_entries
    if gates is not None:
        results = _load_json(first_dir / "results.json")
        suite = _load_json(first_dir / "suite.json")
        labels = {e["profile_id"]: e.get("profile_label") or e["profile_id"] for e in entries}
        gv = _gate_verdict(results, labels, {"gates": gates})
        run_blob["catalyst"]["gate_verdict"] = gv
    return packet


def _write_catalyst_run_summary(run_dir: Path, packet: dict[str, Any]) -> Path:
    runs = packet.get("runs") or []
    run = runs[0] if runs else {}
    meta = run.get("meta") or {}
    backends = list(run.get("backends") or [])
    scenarios = list(run.get("scenarios") or [])
    summary_rows = list(run.get("summary") or [])
    total_turns = sum(int(s.get("turns") or 0) for s in summary_rows)
    scout = [
        {
            "backend": j.get("backend"),
            "benchmark_score": j.get("benchmark_score"),
            "safety_adjusted_benchmark_score": j.get("safety_adjusted_benchmark_score"),
            "accuracy": j.get("accuracy_mean"),
            "completeness": j.get("completeness_mean"),
            "relevance": j.get("relevance_mean"),
            "harm_count": j.get("harm_count", 0),
        }
        for j in (run.get("judge") or [])
    ]
    summary = {
        "schema": "openclinai.summary.v2",
        "schema_version": 2,
        "family": "catalyst",
        "run_id": run.get("run_id") or meta.get("run_id") or run_dir.name,
        "git_sha": str(meta.get("git_sha") or "")[:10],
        "dataset_id": meta.get("dataset_id") or "catalyst-notebook",
        "provider": meta.get("provider") or "catalyst",
        "generated_at": str(meta.get("generated_at") or "")[:19],
        "date": str(meta.get("generated_at") or "")[:10],
        "reference_date": None,
        "arms": backends,
        "arm_labels": run.get("labels") or {},
        "arm_cards": run.get("arm_cards") or {},
        "scenarios": len(scenarios),
        "patients": 0,
        "cells": total_turns,
        "judges": list(run.get("judge_actors") or []),
        "judging": run.get("judging") or {"recorded": False},
        "scout": scout,
        "calibrated": None,
        "hardware": None,
        "catalyst": (run.get("catalyst") or {}).get("gate_verdict"),
    }
    out = run_dir / "run-summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _write_catalyst_dashboard_data(run_dir: Path, packet: dict[str, Any]) -> Path:
    runs = packet.get("runs") or []
    run = runs[0] if runs else {}
    backends = list(run.get("backends") or [])
    scenarios = list(run.get("scenarios") or [])
    jrow_by_cell = {
        (jr.get("scenario_id"), jr.get("backend_id")): jr
        for jr in (run.get("judge_rows") or [])
        if isinstance(jr, dict)
    }
    grid: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    for scen in scenarios:
        sid = scen.get("scenario_id")
        scen_turns = scen.get("turns") or []
        for b in backends:
            b_entries = [
                (t_obj, (t_obj.get("cells") or {}).get(b))
                for t_obj in scen_turns
                if isinstance(t_obj, dict) and (t_obj.get("cells") or {}).get(b)
            ]
            if not b_entries:
                grid.append({"scenario": sid, "backend": b, "state": "pending"})
                continue
            all_conformed = all(
                bool((c.get("catalyst_turn") or {}).get("conformed", True))
                for _, c in b_entries
            )
            all_passed = all(
                bool((c.get("catalyst_turn") or {}).get("passed"))
                for _, c in b_entries
            )
            total_lat = sum(
                int(((c.get("metrics") or {}).get("latency_ms")) or 0)
                for _, c in b_entries
            )
            state = "done" if all_conformed else "err"
            grid.append(
                {
                    "scenario": sid,
                    "backend": b,
                    "state": state,
                    "turns_done": len(b_entries),
                    "turns_total": len(b_entries),
                    "passed": all_passed,
                    "latency_ms": total_lat,
                }
            )
            detail_turns = []
            for idx, (t_obj, c) in enumerate(b_entries, start=1):
                ct = c.get("catalyst_turn") or {}
                detail_turns.append(
                    {
                        "turn": int(t_obj.get("turn") or idx),
                        "repetition": ct.get("repetition"),
                        "question": t_obj.get("question"),
                        "status": c.get("http_status", 200),
                        "passed": ct.get("passed"),
                        "latency_ms": (c.get("metrics") or {}).get("latency_ms"),
                        "chars": len(c.get("answer_text") or ""),
                        "citations": len(ct.get("sql_versions") or []),
                        "answer": c.get("answer_text") or "",
                        "failed_assertions": ct.get("failed_assertions") or [],
                        "blame": blame(ct.get("assertions") or []),
                        "answer_view": c.get("answer_view"),
                        "indepth_view": c.get("indepth_view"),
                        "blocks": [],
                        "sources_ref": None,
                        "refs_ref": None,
                        "error": c.get("error"),
                        "trace": None,
                    }
                )
            details[f"{sid}|{b}"] = {
                "scenario": sid,
                "backend": b,
                "turns": detail_turns,
                "judge": jrow_by_cell.get((sid, b)) or {},
            }
    cat_meta = run.get("catalyst") or {}
    totals = cat_meta.get("totals") or {}
    jrows = run.get("judge_rows") or []
    judged_scored = len(jrows)
    judged_passed = sum(
        1 for jr in jrows if not jr.get("critical_omission") and not jr.get("harm")
    )
    dash = {
        "schema": "openclinai.dashboard.v2",
        "schema_version": 2,
        "family": "catalyst",
        "status": {
            "run": run.get("run_id") or run_dir.name,
            "family": "catalyst",
            "set": (run.get("meta") or {}).get("dataset_id") or "catalyst",
            "done": len(details),
            "total": len(grid),
            "ok": totals.get("passed", 0),
            "err": totals.get("invalid", 0),
            "conformant": totals.get("total", 0) - totals.get("invalid", 0),
            "unexpected": totals.get("invalid", 0),
            "judged_passed": judged_passed,
            "judged_scored": judged_scored,
            "finished": True,
            "scenarios": [s.get("scenario_id") for s in scenarios],
            "backends": backends,
            "arms": {b: {"label": (run.get("labels") or {}).get(b, b)} for b in backends},
            "arm_cards": run.get("arm_cards") or {},
            "profile_titles": {},
            "grid": grid,
            "status_legend": [],
            "judge": run.get("judge") or [],
            "judge_actors": run.get("judge_actors") or [],
            "judge_combined": [],
            "judging": run.get("judging") or {"recorded": False},
            "check_precision": None,
            "feed": [],
            "models": [],
        },
        "record_pool": [],
        "sources_pool": [],
        "refs_pool": [],
        "details": details,
    }
    return write_sharded_dashboard_packet(run_dir, dash)


def build_report(
    run_dir: Path | str,
    *,
    write_summary: bool = True,
    write_dashboard: bool = True,
) -> Path:
    """Write `report-data.json`, `run-summary.json`, and `dashboard-data.json` into `run_dir`."""
    run_dir = Path(run_dir)
    packet = build_catalyst_report_packet(run_dir)
    out = run_dir / "report-data.json"
    out.write_text(json.dumps(packet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if write_summary:
        _write_catalyst_run_summary(run_dir, packet)
    if write_dashboard:
        _write_catalyst_dashboard_data(run_dir, packet)
    return out
