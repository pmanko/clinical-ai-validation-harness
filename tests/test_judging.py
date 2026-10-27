import json
from pathlib import Path

from harness.validate.judging import (
    actor_id,
    canonical_actors,
    judge_card_line,
    judge_summary,
    load_judge_cards,
)


def _pass(run: Path, actor: str, card: dict) -> None:
    d = run / "judges" / actor
    d.mkdir(parents=True)
    (d / "judge.jsonl").write_text('{"scenario_id": "s1", "backend_id": "b1", "accuracy": 8}\n')
    (d / "manifest.json").write_text(json.dumps(card))


def test_actor_id_names_the_pass_by_agent_model_effort_and_index():
    assert actor_id({"agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high"}) == \
        "codex-gpt-6-astra-high-p1"
    assert actor_id({"agent": "claude", "model": "claude-opus-5-5", "reasoning_effort": "high",
                     "pass_index": 3}) == "claude-claude-opus-5-5-high-p3"
    assert actor_id({"model": "Some Model/2"}) == "some-model-2-p1"


def test_judge_card_line_names_what_is_known_and_guesses_nothing():
    full = {"agent": "codex", "agent_version": "0.160.1", "model": "gpt-6-astra",
            "reasoning_effort": "high", "pass_index": 1, "passes": 1,
            "brief_sha256": "8b3b7a180ffb9faf70545bd67a952a62fac729488316207509b357eda02f7ad1"}
    assert judge_card_line(full) == \
        "gpt-6-astra, reasoning high, Codex CLI 0.160.1, pass 1 of 1, brief 8b3b7a1"
    assert judge_card_line({"model": "claude-opus-5-5", "agent": "claude"}) == \
        "claude-opus-5-5, Claude Code CLI"
    assert judge_card_line({"actor_type": "human", "model": "clinician"}) == "human review by clinician"
    assert judge_card_line({}) == "judge not recorded"


def test_judge_summary_puts_the_canonical_pass_first_and_names_the_rest(tmp_path):
    run = tmp_path / "run"
    _pass(run, "codex-gpt-6-astra-high-p1",
          {"model": "gpt-6-astra", "reasoning_effort": "high", "agent": "codex"})
    _pass(run, "claude-claude-opus-5-5-high-p1",
          {"model": "claude-opus-5-5", "reasoning_effort": "high", "agent": "claude"})
    (run / "judges" / "canonical.json").write_text(
        json.dumps({"built_from": ["codex-gpt-6-astra-high-p1"]}))

    summary = judge_summary(run)

    assert summary["recorded"] is True
    assert summary["canonical"] == ["codex-gpt-6-astra-high-p1"]
    assert [c["actor_id"] for c in summary["cards"]] == [
        "codex-gpt-6-astra-high-p1", "claude-claude-opus-5-5-high-p1"]
    assert summary["sentence"] == (
        "Judged by gpt-6-astra, reasoning high, Codex CLI. "
        "Also scored by claude-opus-5-5, reasoning high, Claude Code CLI.")
    assert canonical_actors(run) == ["codex-gpt-6-astra-high-p1"]


def test_a_run_without_cards_says_so_instead_of_inventing_a_judge(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "judge.jsonl").write_text('{"scenario_id": "s1", "backend_id": "b1", "accuracy": 8}\n')

    summary = judge_summary(run)

    assert summary == {"recorded": False, "cards": [], "canonical": [], "aggregation": "",
                       "sentence": "Judge not recorded for this run."}
    assert load_judge_cards(run) == []


def test_a_card_that_is_not_json_is_skipped_not_fatal(tmp_path):
    run = tmp_path / "run"
    _pass(run, "good", {"model": "m"})
    bad = run / "judges" / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text("{not json")

    assert [c["actor_id"] for c in load_judge_cards(run)] == ["good"]


def test_an_aggregated_headline_says_how_many_passes_and_the_rule(tmp_path):
    run = tmp_path / "run"
    for i in (1, 2, 3):
        _pass(run, f"codex-gpt-6-astra-high-p{i}",
              {"model": "gpt-6-astra", "reasoning_effort": "high", "agent": "codex",
               "pass_index": i, "passes": 3})
    (run / "judges" / "canonical.json").write_text(json.dumps({
        "built_from": [f"codex-gpt-6-astra-high-p{i}" for i in (1, 2, 3)],
        "aggregation": "median-majority"}))

    summary = judge_summary(run)

    assert summary["aggregation"] == "median-majority"
    assert summary["sentence"].startswith("Judged in 3 passes by gpt-6-astra, reasoning high, Codex CLI, pass 1 of 3; ")
    assert summary["sentence"].endswith("a harm tie counting as harmful.")
