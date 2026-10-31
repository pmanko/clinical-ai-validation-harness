"""A panel of judges: each judge's passes become one rating, the judges are compared, and a
judge from an arm's own model family is flagged."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from harness.validate.judging import arm_families, model_family, self_preference

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("judge_aggregate2", ROOT / "scripts" / "judge-aggregate.py")
assert SPEC and SPEC.loader
agg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agg)


def test_model_family_reads_the_name_prefix_and_says_nothing_for_a_profile():
    assert model_family("gemma-4-12b") == "google"
    assert model_family("gpt-6-astra") == "openai"
    assert model_family("claude-opus-5-5") == "anthropic"
    assert model_family("single-12b-checked") is None
    assert model_family(None) is None


def test_self_preference_flags_a_judge_from_an_arms_family(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "run_meta.json").write_text(json.dumps({
        "backends": {"bundled": {"modelName": "gemma-4-12b"}, "hub": {"modelName": "single-12b-checked"}},
        "arm_cards": {"hub": {"models": [{"id": "single-12b-checked"}]}},
    }))

    assert arm_families(run) == {"bundled": "google"}
    flagged = self_preference({"model": "gemma-4-12b-judge"}, run)
    assert flagged["self_preference_risk"] is True and flagged["self_preference_arms"] == ["bundled"]
    clear = self_preference({"model": "gpt-6-astra"}, run)
    assert clear["self_preference_risk"] is False and clear["judge_family"] == "openai"


def _pass(run: Path, actor: str, card: dict, acc: int, harm: bool = False) -> None:
    d = run / "judges" / actor
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({**card, "actor_id": actor}))
    (d / "judge.jsonl").write_text(json.dumps({
        "scenario_id": "s1", "backend_id": "b1", "accuracy": acc, "completeness": acc, "relevance": acc,
        "harm": harm, "abstention_outcome": "n-a", "citation_groundedness": "supported", "note": actor,
        "citation_resolution": {"n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "unresolved": [], "rate": None},
    }) + "\n")


def test_two_judges_passes_become_two_ratings_compared_per_arm_and_by_alpha(tmp_path):
    run = tmp_path / "run"
    codex = {"agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high"}
    claude = {"agent": "claude", "model": "claude-opus-5-5", "reasoning_effort": "high"}
    _pass(run, "codex-gpt-6-astra-high-p1", codex, 9)
    _pass(run, "codex-gpt-6-astra-high-p2", codex, 8)
    _pass(run, "claude-claude-opus-5-5-high-p1", claude, 5, harm=True)
    _pass(run, "claude-claude-opus-5-5-high-p2", claude, 4, harm=True)

    subprocess.run([sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
                    "--actor", "codex-gpt-6-astra-high-p1", "--actor", "codex-gpt-6-astra-high-p2",
                    "--actor", "claude-claude-opus-5-5-high-p1", "--actor", "claude-claude-opus-5-5-high-p2"],
                   check=True, capture_output=True, text=True, cwd=ROOT)

    consensus = json.loads((run / "judges" / "consensus.json").read_text())
    judges = consensus["judges"]
    assert sorted(judges["per_judge"]) == ["claude-claude-opus-5-5-high", "codex-gpt-6-astra-high"]
    assert judges["per_judge"]["codex-gpt-6-astra-high"]["actors"] == [
        "codex-gpt-6-astra-high-p1", "codex-gpt-6-astra-high-p2"]
    codex_scout = judges["per_judge"]["codex-gpt-6-astra-high"]["scout"][0]
    claude_scout = judges["per_judge"]["claude-claude-opus-5-5-high"]["scout"][0]
    assert codex_scout["accuracy_mean"] == 8.5 and codex_scout["harm_count"] == 0
    assert claude_scout["accuracy_mean"] == 4.5 and claude_scout["harm_count"] == 1
    assert "harm" in judges["alpha"] and judges["thresholds"]["good"] == 0.8
    # The headline still comes from every pass of every judge.
    canonical = json.loads((run / "judge.jsonl").read_text().splitlines()[0])
    assert canonical["accuracy"] == 6.5 and canonical["harm"] is True


def test_one_judges_passes_carry_no_judges_block(tmp_path):
    run = tmp_path / "run"
    codex = {"agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high"}
    _pass(run, "codex-gpt-6-astra-high-p1", codex, 9)
    _pass(run, "codex-gpt-6-astra-high-p2", codex, 8)

    subprocess.run([sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
                    "--actor", "codex-gpt-6-astra-high-p1", "--actor", "codex-gpt-6-astra-high-p2"],
                   check=True, capture_output=True, text=True, cwd=ROOT)

    assert "judges" not in json.loads((run / "judges" / "consensus.json").read_text())
