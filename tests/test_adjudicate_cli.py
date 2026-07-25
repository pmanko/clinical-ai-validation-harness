"""Tests for the adjudication-review CLI path (harness/validate/adjudicate.py
non-interactive driver) and the reference_date threading in runner.py.

The CLI's interactive prompt loop is not exercised here; the NON-INTERACTIVE
(`--from answers.json`) path is, because it is the scripted entry the publish
pipeline and these tests drive. Synthetic judge.jsonl / judge-cells.jsonl are
written to a tmp run dir — no live judge fan-out.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.validate import adjudicate


# --------------------------------------------------------------------------- #
# fixtures: a tiny run dir with judge.jsonl + judge-cells.jsonl + a snapshot
# --------------------------------------------------------------------------- #
def _write_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run-xyz"
    charts = run_dir / "charts"
    charts.mkdir(parents=True)
    (charts / "alice.snapshot.txt").write_text(
        "Patient records (most recent first):\nPatient: 40-year-old Female\n"
        "[1] (2026-01-01) Finding — Weight: 70 kg\n",
        encoding="utf-8",
    )

    judge = [
        {"scenario_id": "s1", "backend_id": "b1", "accuracy": 8, "completeness": 7,
         "relevance": 9, "harm": False, "abstention_outcome": "n-a",
         "citation_groundedness": "supported", "note": "judge note one"},
        {"scenario_id": "s2", "backend_id": "b1", "accuracy": 3, "completeness": 4,
         "relevance": 5, "harm": True, "abstention_outcome": "failed-to-abstain",
         "citation_groundedness": "unsupported", "note": "judge note two"},
    ]
    (run_dir / "judge.jsonl").write_text(
        "\n".join(json.dumps(r) for r in judge) + "\n", encoding="utf-8")

    cells = [
        {"scenario_id": "s1", "backend_id": "b1",
         "snapshot_file": str(charts / "alice.snapshot.txt"),
         "n_turns": 1,
         "turns": [{"n": 1, "question": "What is the weight?",
                    "answer_section": "70 kg.", "references": []}],
         "answer_section": "70 kg."},
        {"scenario_id": "s2", "backend_id": "b1",
         "snapshot_file": str(charts / "alice.snapshot.txt"),
         "n_turns": 1,
         "turns": [{"n": 1, "question": "What is the blood type?",
                    "answer_section": "Type O.", "references": []}],
         "answer_section": "Type O."},
    ]
    (run_dir / "judge-cells.jsonl").write_text(
        "\n".join(json.dumps(r) for r in cells) + "\n", encoding="utf-8")
    return run_dir


def _read_adj(run_dir: Path) -> list[dict]:
    p = run_dir / "adjudication.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# --------------------------------------------------------------------------- #
# non-interactive adjudication writes correct records
# --------------------------------------------------------------------------- #
def test_non_interactive_writes_adjudication_records(tmp_path):
    run_dir = _write_run(tmp_path)
    answers = {
        "s1|b1": {"accuracy": 9, "completeness": 8, "relevance": 9,
                  "harm": False, "note": "human agrees, bumped accuracy"},
        "s2|b1": {"accuracy": 2, "completeness": 3, "relevance": 4,
                  "harm": True, "note": "confabulated, harmful"},
    }

    written = adjudicate.run_adjudication(
        run_dir=run_dir, mode="full", reviewer_id="rev1",
        reviewer_tier="clinical", answers=answers, seed=0,
    )
    assert written == 2

    rows = _read_adj(run_dir)
    assert len(rows) == 2
    by_cell = {(r["scenario_id"], r["backend_id"]): r for r in rows}

    s1 = by_cell[("s1", "b1")]
    assert s1["reviewer_id"] == "rev1"
    assert s1["reviewer_tier"] == "clinical"
    assert s1["axes"]["accuracy"] == 9
    assert s1["axes"]["completeness"] == 8
    assert s1["axes"]["relevance"] == 9
    assert s1["harm"] is False
    assert s1["note"] == "human agrees, bumped accuracy"
    assert s1["judged_at"]  # stamped on write

    s2 = by_cell[("s2", "b1")]
    assert s2["harm"] is True
    assert s2["axes"]["accuracy"] == 2


# --------------------------------------------------------------------------- #
# resumable: a second run skips already-reviewed cells
# --------------------------------------------------------------------------- #
def test_adjudication_is_resumable(tmp_path):
    run_dir = _write_run(tmp_path)

    first = adjudicate.run_adjudication(
        run_dir=run_dir, mode="full", reviewer_id="rev1",
        reviewer_tier="clinical",
        answers={"s1|b1": {"accuracy": 9, "completeness": 8, "relevance": 9,
                           "harm": False, "note": "first pass"}},
        seed=0,
    )
    assert first == 1
    assert len(_read_adj(run_dir)) == 1

    # second pass offers BOTH cells but s1 is already reviewed -> only s2 written
    second = adjudicate.run_adjudication(
        run_dir=run_dir, mode="full", reviewer_id="rev1",
        reviewer_tier="clinical",
        answers={"s1|b1": {"accuracy": 1, "completeness": 1, "relevance": 1,
                           "harm": True, "note": "should be skipped"},
                 "s2|b1": {"accuracy": 2, "completeness": 3, "relevance": 4,
                           "harm": True, "note": "second pass"}},
        seed=0,
    )
    assert second == 1

    rows = _read_adj(run_dir)
    assert len(rows) == 2
    by_cell = {(r["scenario_id"], r["backend_id"]): r for r in rows}
    # s1 keeps its FIRST-pass values (not clobbered by the resume)
    assert by_cell[("s1", "b1")]["axes"]["accuracy"] == 9
    assert by_cell[("s1", "b1")]["note"] == "first pass"
    assert by_cell[("s2", "b1")]["note"] == "second pass"


# --------------------------------------------------------------------------- #
# non-interactive accepts the judge's scores when an answer omits an axis
# --------------------------------------------------------------------------- #
def test_non_interactive_accepts_judge_when_axis_omitted(tmp_path):
    run_dir = _write_run(tmp_path)
    # answer only overrides harm; accuracy/completeness/relevance fall back to judge.
    written = adjudicate.run_adjudication(
        run_dir=run_dir, mode="budget", n=1, reviewer_id="rev1",
        reviewer_tier="owner",
        answers={"s2|b1": {"harm": False, "note": "judge over-flagged harm"}},
        seed=0,
    )
    assert written == 1
    rows = _read_adj(run_dir)
    assert len(rows) == 1
    r = rows[0]
    assert (r["scenario_id"], r["backend_id"]) == ("s2", "b1")  # priority cell first
    # judge scores carried through (3/4/5), harm overridden to False
    assert r["axes"]["accuracy"] == 3
    assert r["axes"]["completeness"] == 4
    assert r["axes"]["relevance"] == 5
    assert r["harm"] is False


# --------------------------------------------------------------------------- #
# reference_date threading on result rows (runner.py)
# --------------------------------------------------------------------------- #
class _StubClient:
    """Records chat kwargs; returns a fixed envelope per turn."""

    def __init__(self):
        self.chat_calls = []

    def new_session(self, patient):
        return "sess-1"

    def chat(self, patient, session, question, *, profile=None,
             reference_date=None):
        self.chat_calls.append({"reference_date": reference_date})
        return _Result()


class _Result:
    status = 200
    envelope = {"answer": "stub answer", "session": "sess-1"}
    latency_ms = 5
    raw_text = "stub answer"


def _read_results(run_dir: Path) -> list[dict]:
    p = run_dir / "results.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_reference_date_recorded_on_result_rows_when_passed(tmp_path):
    from harness.validate.runner import run_comparison

    client = _StubClient()
    res = run_comparison(
        comparison_set_id="demo", client=client,
        output_dir=tmp_path, reference_date="2026-03-15",
        router_policy=lambda _backend: None,
    )
    rows = _read_results(res.run_dir)
    assert rows, "expected at least one result row"
    for r in rows:
        assert r.get("reference_date") == "2026-03-15"
    # plumbed to the client when it accepts the kwarg
    assert client.chat_calls
    assert all(c["reference_date"] == "2026-03-15" for c in client.chat_calls)


def test_reference_date_absent_when_not_passed(tmp_path):
    from harness.validate.runner import run_comparison

    client = _StubClient()
    res = run_comparison(
        comparison_set_id="demo", client=client, output_dir=tmp_path,
        router_policy=lambda _backend: None,
    )
    rows = _read_results(res.run_dir)
    assert rows
    for r in rows:
        assert r.get("reference_date") is None
    assert all(c["reference_date"] is None for c in client.chat_calls)
