import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "judge_finalize", ROOT / "scripts" / "judge-finalize.py"
)
assert SPEC and SPEC.loader
judge_finalize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge_finalize)


def test_has_temporal_claim_infers_from_returned_rubric_fields():
    assert judge_finalize.has_temporal_claim(
        {"temporal_window": "over-claimed"}
    )
    assert judge_finalize.has_temporal_claim(
        {"has_temporal_claim": False, "temporal_trend": "ok"}
    )


def test_has_temporal_claim_preserves_explicit_workflow_flag():
    assert judge_finalize.has_temporal_claim({"has_temporal_claim": True})
    assert not judge_finalize.has_temporal_claim({"has_temporal_claim": False})


def test_make_actor_finalize_passes_required_provenance():
    makefile = (ROOT / "Makefile").read_text()
    target = makefile.split("validate-judge-finalize:", 1)[1].split(
        "validate-report:", 1
    )[0]

    assert "--actor-type $(JUDGE_ACTOR_TYPE)" in target
    assert "--model \"$(JUDGE_MODEL)\"" in target
    assert "--method \"$(JUDGE_METHOD)\"" in target
    assert "[ -z \"$(JUDGE_CARD)\" ]" in target


def test_make_judge_finalize_skips_report_when_judge_card_is_unpromoted():
    import subprocess

    unpromoted = subprocess.run(
        ["make", "-n", "validate-judge-finalize", "RUN=example", "ROWS=rows.json", "JUDGE_CARD=card.json"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    # Execute the shell snippet emitted by make -n after replacing commands with echo markers
    assert '[ -z "" ] && [ -z "card.json" ]' in unpromoted

    promoted = subprocess.run(
        ["make", "-n", "validate-judge-finalize", "RUN=example", "ROWS=rows.json", "JUDGE_CARD=card.json", "JUDGE_PROMOTE=1"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    assert '--card card.json' in promoted and '--promote' in promoted
